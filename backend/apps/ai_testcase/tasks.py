# -*- coding: utf-8 -*-
import asyncio
import logging
import os

from celery import shared_task
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import transaction, close_old_connections
from django.db.utils import InterfaceError, OperationalError
from django.utils import timezone
from datetime import timedelta

from apps.ai_testcase.models import AiTestcaseEvent, AiTestcaseGeneration
from apps.ai_testcase.services.file_processor import FileProcessor
from apps.ai_testcase.services.prompts import get_testcase_prompt, get_testcase_prompt_multimodal
from apps.ai_testcase.services.model_router import TestcaseModelRouter
from apps.ai_testcase.services.schemas import validate_testcase_result
from apps.ai_testcase.services.xmind_builder import XMindBuilder
from apps.ai_testcase.services.dedupe import dedupe_result_json
from apps.ai_testcase.workflows.executor import TestcaseAgentExecutor
from apps.ai_testcase.utils import normalize_case_strategy_mode

logger = logging.getLogger(__name__)

XMIND_OUTPUT_DIR = os.path.join(settings.BASE_DIR, 'apps', 'ai_testcase', 'output')

def _db_retry(op, *, retries: int = 1, op_name: str = "db_op"):
    """
    Celery 长任务中，数据库连接可能在等待 LLM 期间被服务端断开，导致 InterfaceError(0,'')。
    这里做一次轻量重试：先 close_old_connections() 再重试一次。
    """
    last_err: Exception | None = None
    for i in range(retries + 1):
        try:
            close_old_connections()
            return op()
        except (InterfaceError, OperationalError) as e:
            last_err = e
            logger.warning(f"[ai_testcase] {op_name}.retry | i={i} err={e!r}")
            try:
                close_old_connections()
            except Exception:
                pass
            continue
    if last_err:
        raise last_err
    return op()

def _publish_live_chunk(record_id: int, content: str):
    """
    A 方案：chunk 不落库，只通过 Redis PubSub 实时推送给 events-stream。
    断线重连时允许丢失少量 chunk（最终结果仍由 DB done 事件保证）。
    """
    try:
        from redis import Redis
        r = Redis(
            host=getattr(settings, 'REDIS_HOST', '127.0.0.1'),
            port=int(getattr(settings, 'REDIS_PORT', 6379)),
            db=int(getattr(settings, 'REDIS_DB', 0)),
            password=getattr(settings, 'REDIS_PASSWORD', None) or None,
            decode_responses=True,
        )
        r.publish(f"ai_testcase:chunks:{record_id}", content)
    except Exception:
        # 仅影响实时体验，不影响最终结果
        return


def _write_event(generation: AiTestcaseGeneration, event_type: str, payload: dict):
    def _op():
        return AiTestcaseEvent.objects.create(
            generation=generation,
            event_type=event_type,
            payload=payload or {},
        )
    _db_retry(_op, op_name="write_event")


def _set_progress(generation: AiTestcaseGeneration, stage: str | None, progress: int | None):
    update_fields = []
    if stage is not None:
        generation.current_stage = stage
        update_fields.append('current_stage')
    if progress is not None:
        generation.progress = int(progress)
        update_fields.append('progress')
    if update_fields:
        _db_retry(lambda: generation.save(update_fields=update_fields), op_name="set_progress.save")

async def _write_event_async(generation: AiTestcaseGeneration, event_type: str, payload: dict):
    def _op():
        return AiTestcaseEvent.objects.create(
            generation=generation,
            event_type=event_type,
            payload=payload or {},
        )
    await sync_to_async(_db_retry)(_op, op_name="write_event_async")


async def _set_progress_async(generation: AiTestcaseGeneration, stage: str | None, progress: int | None):
    update_fields = []
    if stage is not None:
        generation.current_stage = stage
        update_fields.append('current_stage')
    if progress is not None:
        generation.progress = int(progress)
        update_fields.append('progress')
    if update_fields:
        await sync_to_async(_db_retry)(lambda: generation.save(update_fields=update_fields), op_name="set_progress_async.save")


def _ensure_output_dir():
    if not os.path.exists(XMIND_OUTPUT_DIR):
        os.makedirs(XMIND_OUTPUT_DIR, exist_ok=True)

@shared_task(queue='work_queue')
def run_ai_testcase_direct(record_id: int):
    """
    P2：direct 生成改为 Celery 执行 + 事件持久化。
    """
    record = _db_retry(lambda: AiTestcaseGeneration.objects.get(id=record_id), op_name="direct.get_record")
    if record.status == 'cancelled':
        _write_event(record, 'cancelled', {'record_id': record.id})
        return

    _ensure_output_dir()

    try:
        def _mark_generating():
            with transaction.atomic():
                record.status = 'generating'
                record.generation_mode = 'direct'
                record.error_message = None
                record.save(update_fields=['status', 'generation_mode', 'error_message'])
        _db_retry(_mark_generating, op_name="direct.mark_generating")

        _set_progress(record, 'start', 1)
        _write_event(record, 'start', {
            'record_id': record.id,
            'prompt_version': getattr(settings, 'AI_TESTCASE_PROMPT_VERSION', 'v1'),
            'mode': 'direct',
            'generation_mode': 'direct',
            'case_strategy_mode': normalize_case_strategy_mode(getattr(record, 'case_strategy_mode', None)),
        })

        extracted_texts = []
        images = []
        if record.source_files:
            _set_progress(record, 'file_processing', 5)
            fp = FileProcessor()
            processed = fp.process_local_files(record.source_files)
            extracted_texts = processed.get('texts', [])
            images = processed.get('images', [])
            warnings = processed.get('warnings', [])
            if warnings:
                _write_event(record, 'progress', {'stage': 'file_processing', 'percent': 8, 'message': '附件解析完成（部分文件可能有警告）', 'warnings': warnings})
            else:
                _write_event(record, 'progress', {'stage': 'file_processing', 'percent': 8, 'message': '附件解析完成'})

        _set_progress(record, 'llm_generate', 10)
        _write_event(record, 'progress', {'stage': 'llm_generate', 'percent': 10, 'message': '开始生成用例'})

        router = TestcaseModelRouter()
        model = router.select_model('generate')
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        raw_content = ""

        # 统一走流式：用于实时 chunk 推送（A 方案：chunk 不落库）
        if extracted_texts or images:
            async def _run():
                full = ""
                u = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                client = router.get_client(model, async_=True)
                messages = get_testcase_prompt_multimodal(
                    record.requirement or "",
                    extracted_texts,
                    images,
                    normalize_case_strategy_mode(getattr(record, 'case_strategy_mode', None)),
                )

                extra_body = (
                    {"thinking": {"type": "enabled", "budget_tokens": 10000}}
                    if bool(record.use_thinking)
                    else {"thinking": {"type": "disabled"}}
                )
                stream = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    extra_body=extra_body,
                    stream=True,
                    stream_options={"include_usage": True},
                )

                async for chunk in stream:
                    # 取消检查（降低 DB 压力：每次循环只读内存状态，周期性刷新 DB）
                    if full and (len(full) % 2048 == 0):
                        await sync_to_async(_db_retry)(lambda: record.refresh_from_db(fields=['status']), op_name="direct.refresh_status")
                        if record.status == 'cancelled':
                            return {"cancelled": True}
                    if chunk.usage:
                        u = {
                            "prompt_tokens": chunk.usage.prompt_tokens or 0,
                            "completion_tokens": chunk.usage.completion_tokens or 0,
                            "total_tokens": chunk.usage.total_tokens or 0,
                        }
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if delta and delta.content:
                            full += delta.content
                            _publish_live_chunk(record.id, delta.content)
                return {"cancelled": False, "content": full, "usage": u}

            out = asyncio.run(_run())
            if out.get('cancelled'):
                record.refresh_from_db(fields=['status'])
                _write_event(record, 'cancelled', {'record_id': record.id})
                return
            raw_content = out.get('content', '') or ''
            usage = out.get('usage', usage) or usage
        else:
            async def _run_text():
                full = ""
                u = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                client = router.get_client(model, async_=True)
                messages = get_testcase_prompt(
                    record.requirement or "",
                    normalize_case_strategy_mode(getattr(record, 'case_strategy_mode', None)),
                )
                extra_body = (
                    {"thinking": {"type": "enabled", "budget_tokens": 10000}}
                    if bool(record.use_thinking)
                    else {"thinking": {"type": "disabled"}}
                )
                stream = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    extra_body=extra_body,
                    stream=True,
                    stream_options={"include_usage": True},
                )
                async for chunk in stream:
                    if full and (len(full) % 2048 == 0):
                        await sync_to_async(_db_retry)(lambda: record.refresh_from_db(fields=['status']), op_name="direct.refresh_status")
                        if record.status == 'cancelled':
                            return {"cancelled": True}
                    if chunk.usage:
                        u = {
                            "prompt_tokens": chunk.usage.prompt_tokens or 0,
                            "completion_tokens": chunk.usage.completion_tokens or 0,
                            "total_tokens": chunk.usage.total_tokens or 0,
                        }
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if delta and delta.content:
                            full += delta.content
                            _publish_live_chunk(record.id, delta.content)
                return {"cancelled": False, "content": full, "usage": u}

            out = asyncio.run(_run_text())
            if out.get('cancelled'):
                record.refresh_from_db(fields=['status'])
                _write_event(record, 'cancelled', {'record_id': record.id})
                return
            raw_content = out.get('content', '') or ''
            usage = out.get('usage', usage) or usage

        _db_retry(lambda: record.refresh_from_db(fields=['status']), op_name="direct.refresh_status.final")
        if record.status == 'cancelled':
            _write_event(record, 'cancelled', {'record_id': record.id})
            return

        _set_progress(record, 'parse_validate', 70)
        _write_event(record, 'progress', {'stage': 'parse_validate', 'percent': 70, 'message': '解析与校验结构化输出'})

        data = router.parse_json(raw_content)
        if data is None:
            raise ValueError('parse_error: AI 返回无法解析为 JSON')
        validate_testcase_result(data)
        # Phase 1：确定性去重（不破坏 XMind 核心字段）
        data, dedupe_report = dedupe_result_json(
            data,
            mode=normalize_case_strategy_mode(getattr(record, 'case_strategy_mode', None)),
        )

        _set_progress(record, 'save_result', 85)
        _write_event(record, 'progress', {'stage': 'save_result', 'percent': 85, 'message': '写入结果与生成 XMind'})

        record.result_json = data
        record.raw_content = raw_content
        record.prompt_tokens = int(usage.get('prompt_tokens', 0) or 0)
        record.completion_tokens = int(usage.get('completion_tokens', 0) or 0)
        record.total_tokens = int(usage.get('total_tokens', 0) or 0)
        record.count_stats()

        title = (data.get('title') or f'testcase_{record.id}').strip()
        xmind_filename = f"{title}.xmind"
        xmind_path = os.path.join(XMIND_OUTPUT_DIR, xmind_filename)
        try:
            XMindBuilder.build_and_save(data, xmind_path)
            record.xmind_file = xmind_path
        except Exception as e:
            logger.warning(f"[ai_testcase] xmind.build_failed | record_id={record.id} err={e}")

        record.status = 'success'
        record.current_stage = 'done'
        record.progress = 100
        _db_retry(lambda: record.save(), op_name="direct.save.success")

        _write_event(record, 'done', {
            'record_id': record.id,
            'title': title,
            'data': record.result_json,
            'module_count': record.module_count,
            'case_count': record.case_count,
            'usage': usage,
            'dedupe_report': dedupe_report,
            'prompt_version': getattr(settings, 'AI_TESTCASE_PROMPT_VERSION', 'v1'),
        })

    except Exception as e:
        _db_retry(lambda: record.refresh_from_db(), op_name="direct.refresh_on_error")
        if record.status == 'cancelled':
            _write_event(record, 'cancelled', {'record_id': record.id})
            return
        record.status = 'failed'
        record.error_message = f"server_error[{type(e).__name__}]: {e!r}"
        record.current_stage = 'error'
        _db_retry(lambda: record.save(update_fields=['status', 'error_message', 'current_stage']), op_name="direct.save.failed")
        _write_event(record, 'error', {'error_type': 'server', 'error': f'{type(e).__name__}: {e!r}', 'record_id': record.id})


@shared_task(queue='work_queue')
def run_ai_testcase_agent(record_id: int):
    """
    P2：agent 生成改为 Celery 执行 + 事件持久化。
    """
    record = _db_retry(lambda: AiTestcaseGeneration.objects.get(id=record_id), op_name="agent.get_record")
    if record.status == 'cancelled':
        _write_event(record, 'cancelled', {'record_id': record.id})
        return

    _ensure_output_dir()

    try:
        def _mark_generating():
            with transaction.atomic():
                record.status = 'generating'
                record.generation_mode = 'agent'
                record.error_message = None
                record.save(update_fields=['status', 'generation_mode', 'error_message'])
        _db_retry(_mark_generating, op_name="agent.mark_generating")

        extracted_texts = []
        images = []
        if record.source_files:
            _set_progress(record, 'file_processing', 5)
            fp = FileProcessor()
            processed = fp.process_local_files(record.source_files)
            extracted_texts = processed.get('texts', [])
            images = processed.get('images', [])
            warnings = processed.get('warnings', [])
            if warnings:
                _write_event(record, 'progress', {'stage': 'file_processing', 'percent': 8, 'message': '附件解析完成（部分文件可能有警告）', 'warnings': warnings})

        _set_progress(record, 'agent_start', 10)
        _write_event(record, 'start', {
            'record_id': record.id,
            'prompt_version': getattr(settings, 'AI_TESTCASE_PROMPT_VERSION', 'v1'),
            'mode': 'agent',
            'generation_mode': 'agent',
            'case_strategy_mode': normalize_case_strategy_mode(getattr(record, 'case_strategy_mode', None)),
        })

        async def _run_and_persist():
            async for ev in TestcaseAgentExecutor.run(
                record=record,
                requirement=record.requirement or "",
                extracted_texts=extracted_texts,
                images=images,
                use_thinking=bool(record.use_thinking),
                mode=normalize_case_strategy_mode(getattr(record, 'case_strategy_mode', None)),
            ):
                await sync_to_async(_db_retry)(lambda: record.refresh_from_db(fields=['status']), op_name="agent.refresh_status")
                if record.status == 'cancelled':
                    await _write_event_async(record, 'cancelled', {'record_id': record.id})
                    return

                ev_type = ev.get('type') or 'event'
                payload = dict(ev)

                # 统一映射到 P2 事件类型集合（边跑边落库，供 SSE 实时消费）
                if ev_type == 'agent_node_started':
                    node = payload.get('node') or 'agent_step'
                    next_p = max(int(getattr(record, 'progress', 0) or 0), 10)
                    if node.startswith('generate_module:'):
                        mod = node.split(':', 1)[1] if ':' in node else ''
                        msg = f'分模块生成：{mod}（调用模型）' if mod else '分模块生成（调用模型）'
                    elif node == 'analyze_requirement':
                        msg = '需求分析（调用模型）'
                    elif node == 'plan_test_strategy':
                        msg = '策略规划（调用模型）'
                    elif node == 'merge_and_review':
                        msg = '合并与评审（调用模型）'
                    elif node == 'refine_cases':
                        msg = '修订用例（调用模型）'
                    elif node == 'reset_generation':
                        msg = '评审仍未达标，升级策略后重新分模块生成'
                    elif node == 'finalize':
                        msg = '收尾处理'
                    else:
                        msg = '执行中'
                    await _set_progress_async(record, node, next_p)
                    await _write_event_async(record, 'progress', {
                        'stage': node,
                        'percent': next_p,
                        'message': msg,
                        'phase': 'running',
                    })
                elif ev_type in ('agent_start',):
                    await _set_progress_async(record, 'agent_start', 12)
                    await _write_event_async(record, 'start', payload)
                elif ev_type in ('agent_node_done', 'agent_refining'):
                    stage = payload.get('node') or payload.get('current_node') or 'agent_step'
                    if ev_type == 'agent_refining':
                        stage = 'refine_cases'
                    next_p = min(int(getattr(record, 'progress', 0) or 0) + 5, 95)
                    await _set_progress_async(record, stage, next_p)
                    await _write_event_async(record, 'progress', {
                        'stage': stage,
                        'percent': int(getattr(record, 'progress', next_p) or next_p),
                        'message': '智能体阶段推进',
                        'data': payload.get('data', {}) or {'changes_count': payload.get('changes_count')},
                        'iteration_count': payload.get('iteration_count'),
                    })
                elif ev_type in ('agent_review',):
                    await _write_event_async(record, 'review', {
                        'score': payload.get('score'),
                        'feedback': payload.get('feedback') or '',
                        'issues': payload.get('issues') or [],
                        'issues_count': payload.get('issues_count'),
                        'iteration': payload.get('iteration'),
                        'model': payload.get('model'),
                        'usage': payload.get('usage', {}),
                        'cost_usd': payload.get('cost_usd'),
                        'max': payload.get('max'),
                    })
                elif ev_type in ('agent_done',):
                    await _set_progress_async(record, 'done', 100)
                    data = payload.get('data') or {}
                    title = ''
                    if isinstance(data, dict):
                        title = (data.get('title') or '').strip()
                    if not title:
                        title = f'testcase_{record.id}'
                    await _write_event_async(record, 'done', {
                        'record_id': record.id,
                        'title': title,
                        'data': payload.get('data'),
                        'module_count': payload.get('module_count'),
                        'case_count': payload.get('case_count'),
                        'usage': payload.get('usage', {}),
                        'prompt_version': payload.get('prompt_version', getattr(settings, 'AI_TESTCASE_PROMPT_VERSION', 'v1')),
                    })
                    return
                elif ev_type in ('cancelled',):
                    await _set_progress_async(record, 'cancelled', 100)
                    await _write_event_async(record, 'cancelled', {'record_id': record.id})
                    return
                elif ev_type in ('error',):
                    await _set_progress_async(record, 'error', 100)
                    await _write_event_async(record, 'error', {
                        'error_type': payload.get('error_type') or 'server',
                        'error': payload.get('error') or 'unknown error',
                        'record_id': record.id,
                    })
                    return
                else:
                    await _write_event_async(record, 'progress', {
                        'stage': 'agent',
                        'percent': int(getattr(record, 'progress', 0) or 0),
                        'message': '事件',
                        'data': payload,
                    })

        asyncio.run(_run_and_persist())

    except Exception as e:
        _db_retry(lambda: record.refresh_from_db(), op_name="agent.refresh_on_error")
        if record.status == 'cancelled':
            _write_event(record, 'cancelled', {'record_id': record.id})
            return
        record.status = 'failed'
        record.error_message = f"agent_server_error[{type(e).__name__}]: {e!r}"
        record.current_stage = 'error'
        _db_retry(lambda: record.save(update_fields=['status', 'error_message', 'current_stage']), op_name="agent.save.failed")
        _write_event(record, 'error', {'error_type': 'server', 'error': f'{type(e).__name__}: {e!r}', 'record_id': record.id})


@shared_task(queue='beat_tasks')
def cleanup_ai_testcase_events():
    """
    P2：事件表清理（终态任务的历史事件按保留天数删除）。
    """
    days = int(getattr(settings, 'AI_TESTCASE_EVENT_RETENTION_DAYS', 7) or 7)
    cutoff = timezone.now() - timedelta(days=days)
    terminal = ['success', 'failed', 'cancelled']
    qs = AiTestcaseEvent.objects.filter(
        generation__status__in=terminal,
        created_at__lt=cutoff,
    )
    deleted, _ = qs.delete()
    logger.info(f"[ai_testcase] cleanup.events | days={days} deleted={deleted}")
    return {'deleted': deleted, 'days': days}


