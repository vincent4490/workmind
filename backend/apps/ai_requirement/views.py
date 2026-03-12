# -*- coding: utf-8 -*-
"""
AI 需求智能体 API 视图

提供：
- run-stream: SSE 流式生成（异步）
- run:        非流式同步调用
- feedback:   用户反馈
- tasks:      CRUD ViewSet
"""
import asyncio
import json
import logging
import time

from django.conf import settings
from django.http import HttpResponse, StreamingHttpResponse
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.decorators import action

from .models import (
    AiRequirementTask, AiRequirementFeedback,
    PromptVersion, EvalDataset, EvalRun, WorkflowRun,
    LlmCallLog,
)
from .serializers import (
    AiRequirementTaskSerializer,
    RunStreamRequestSerializer,
    FeedbackSerializer,
    PromptVersionSerializer,
    PromptVersionActivateSerializer,
    EvalDatasetSerializer,
    EvalRunSerializer,
    WorkflowRunSerializer,
    WorkflowStartSerializer,
    WorkflowApproveSerializer,
)
from .services.agent_router import RequirementAgentRouter
from .services.security import SecurityError

logger = logging.getLogger(__name__)

def _extract_result_md(output_format: str, result_json, raw_content: str) -> str | None:
    """
    根据 output_format 生成/提取人类可读 Markdown。

    当前策略（Phase 1）：
    - 若解析到了 JSON，优先取 JSON 内的 markdown_full（如 prd_draft）
    - 若没有 JSON，则 raw_content 视为 Markdown 文本
    """
    if output_format == 'json':
        return None

    if isinstance(result_json, dict):
        md = result_json.get('markdown_full')
        if isinstance(md, str) and md.strip():
            return md.strip()
        return None

    if isinstance(raw_content, str) and raw_content.strip():
        return raw_content.strip()
    return None


def _add_cors_headers(response):
    """SSE 直连时浏览器需要 CORS 头"""
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response


# ============ Kimi 连通性检测 ============

async def kimi_ping_view(request):
    """
    GET /api/ai_requirement/kimi-ping/
    检测当前配置的 Kimi（Moonshot）API 是否可用，便于排查「需求智能体不出结果」等问题。
    返回 JSON: { "ok": true, "message": "..." } 或 { "ok": false, "error": "..." }
    """
    from django.http import JsonResponse
    if request.method == 'OPTIONS':
        return _add_cors_headers(HttpResponse(status=200))
    if request.method != 'GET':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405))

    api_key = getattr(settings, 'KIMI_API_KEY', '')
    base_url = getattr(settings, 'KIMI_BASE_URL', 'https://api.moonshot.cn/v1')
    model = getattr(settings, 'KIMI_MODEL', 'kimi-k2.5')

    if not api_key:
        return _add_cors_headers(JsonResponse({
            'ok': False,
            'error': '未配置 KIMI_API_KEY（请在 settings.py 或环境变量中设置）',
        }))

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        # 最小化请求：一句话对话，验证接口通不通
        resp = await client.chat.completions.create(
            model=model,
            messages=[{'role': 'user', 'content': '回复一个字：好'}],
            max_tokens=10,
        )
        content = (resp.choices[0].message.content or '').strip() if resp.choices else ''
        return _add_cors_headers(JsonResponse({
            'ok': True,
            'message': f'Kimi 连通正常（model={model}，回复: {content[:50] or "(空)"}）',
        }))
    except Exception as e:
        err = str(e)
        logger.warning("[AI需求] Kimi 连通检测失败: %s", err)
        return _add_cors_headers(JsonResponse({
            'ok': False,
            'error': err[:500],
        }, status=200))  # 200 方便前端统一解析


# ============ SSE 流式接口 ============

async def run_stream_view(request):
    """
    SSE 流式生成需求分析结果

    POST /api/ai_requirement/run-stream/

    支持两种提交方式：
    1. JSON:      {"role": "product", "task_type": "prd_draft", ...}
    2. FormData:  role + task_type + requirement_input + files

    Response: text/event-stream
    """
    if request.method == 'OPTIONS':
        return _add_cors_headers(HttpResponse(status=200))

    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405))

    # ---------- 解析请求 ----------
    extracted_texts = []
    images = []

    content_type = request.content_type or ''

    if 'multipart' in content_type:
        from asgiref.sync import sync_to_async
        _post = await sync_to_async(lambda: request.POST)()
        _files = await sync_to_async(lambda: request.FILES)()

        role = _post.get('role', '').strip()
        task_type = _post.get('task_type', '').strip()
        requirement_input = _post.get('requirement_input', '').strip()
        use_thinking = _post.get('use_thinking', 'false').lower() in ('true', '1', 'yes')
        output_format = _post.get('output_format', 'both')
        security_level = _post.get('security_level', 'internal')
        cost_confirmed = _post.get('cost_confirmed', 'false').lower() in ('true', '1', 'yes')

        uploaded_files = _files.getlist('files')
        if uploaded_files:
            try:
                from apps.ai_testcase.services.file_processor import FileProcessor, FileProcessError
                from apps.ai_requirement.services.video_processor import VideoProcessor, SUPPORTED_VIDEO_EXTS
                from pathlib import Path as _Path

                doc_files = []
                video_files = []
                for f in uploaded_files:
                    ext = _Path(f.name).suffix.lower() if hasattr(f, 'name') else ''
                    if ext in SUPPORTED_VIDEO_EXTS:
                        video_files.append(f)
                    else:
                        doc_files.append(f)

                if doc_files:
                    processor = FileProcessor()
                    file_result = await sync_to_async(processor.process_files)(doc_files)
                    extracted_texts = file_result['texts']
                    images = file_result['images']

                if video_files:
                    vp = VideoProcessor()
                    for vf in video_files:
                        vr = await sync_to_async(vp.process_video)(vf)
                        for kf in vr.get('keyframes', []):
                            images.append({
                                'source': f"{vf.name}@{kf['timestamp_s']}s",
                                'data': kf['data'],
                                'mime': kf['mime'],
                            })
                        if vr.get('transcript'):
                            extracted_texts.append({
                                'source': f'{vf.name} (ASR)',
                                'content': vr['transcript'],
                            })
                        meta = vr.get('metadata', {})
                        if meta:
                            extracted_texts.append({
                                'source': f'{vf.name} (元信息)',
                                'content': f"时长: {meta.get('duration_s', 0)}s, "
                                           f"分辨率: {meta.get('width', 0)}x{meta.get('height', 0)}, "
                                           f"FPS: {meta.get('fps', 0)}",
                            })
            except Exception as e:
                logger.exception(f"[AI需求] 文件处理异常: {e}")
                return _add_cors_headers(HttpResponse(f'文件处理失败: {str(e)}', status=400))
    else:
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return _add_cors_headers(HttpResponse('Invalid JSON', status=400))

        role = body.get('role', '').strip()
        task_type = body.get('task_type', '').strip()
        requirement_input = body.get('requirement_input', '').strip()
        use_thinking = body.get('use_thinking', False)
        output_format = body.get('output_format', 'both')
        security_level = body.get('security_level', 'internal')
        cost_confirmed = body.get('cost_confirmed', False)

    # 校验
    if not role or not task_type:
        return _add_cors_headers(HttpResponse('role 和 task_type 必填', status=400))
    if not requirement_input and not extracted_texts and not images:
        return _add_cors_headers(HttpResponse('请输入需求描述或上传文件', status=400))

    requirement_summary = requirement_input or ''
    if not requirement_summary and extracted_texts:
        requirement_summary = f"[附件] {', '.join(t['source'] for t in extracted_texts[:3])}"

    async def event_stream():
        from asgiref.sync import sync_to_async
        from django.conf import settings as _settings
        from apps.ai_requirement.services.cost_quota import check_user_quota, check_and_fire_cost_alert

        record = None
        try:
            estimated_usd = 0.0
            try:
                _router = RequirementAgentRouter()
                estimated_usd = _router.estimate_cost_usd(
                    role, task_type, requirement_input, extracted_texts, images,
                    use_thinking, security_level,
                )
            except Exception as e:
                logger.warning("[AI需求] 成本预估跳过: %s (role=%s, task_type=%s)", e, role, task_type)

            # 用户配额：当日成本/请求数超限则拒绝
            ok, msg = await sync_to_async(check_user_quota)(request.user, estimated_usd)
            if not ok:
                yield f"data: {json.dumps({'type': 'quota_exceeded', 'error': msg}, ensure_ascii=False)}\n\n"
                return

            # 成本预估确认：超过阈值且未确认时，仅返回 cost_estimate_required 事件
            threshold_usd = getattr(_settings, 'AI_REQUIREMENT_COST_CONFIRM_THRESHOLD_USD', 0) or 0
            if threshold_usd > 0 and not cost_confirmed and estimated_usd > threshold_usd:
                yield f"data: {json.dumps({'type': 'cost_estimate_required', 'estimated_usd': round(estimated_usd, 4), 'threshold_usd': threshold_usd, 'message': f'预估成本 ${estimated_usd:.2f} 超过阈值 ${threshold_usd:.2f}，请确认是否继续'}, ensure_ascii=False)}\n\n"
                return

            # 创建记录（写入 created_by 供配额统计）
            user_id = getattr(request.user, 'id', None) if getattr(request.user, 'is_authenticated', False) else None
            record = await sync_to_async(AiRequirementTask.objects.create)(
                role=role,
                task_type=task_type,
                requirement_input=requirement_summary,
                status='generating',
                use_thinking=use_thinking,
                output_format=output_format,
                security_level=security_level,
                created_by_id=user_id,
            )

            yield f"data: {json.dumps({'type': 'start', 'record_id': record.id}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("[AI需求] 流式启动异常 role=%s task_type=%s: %s", role, task_type, e)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)[:500]}, ensure_ascii=False)}\n\n"
            return

        try:
            start_time = time.perf_counter()
            router = RequirementAgentRouter()
            full_content = ""
            usage = {}
            model_used = ""
            prompt_ver = ""

            use_dual = (task_type == 'tech_design' and use_thinking)
            gen = (
                router.run_dual_model_verified(role, task_type, requirement_input, extracted_texts, images, security_level)
                if use_dual
                else router.run_stream(role, task_type, requirement_input, extracted_texts, images, use_thinking, security_level)
            )

            async for event in gen:
                evt_type = event["type"]

                if evt_type in ('phase1_start', 'phase2_start'):
                    yield f"data: {json.dumps({'type': 'phase', 'message': event.get('message', '')}, ensure_ascii=False)}\n\n"

                elif evt_type in ('chunk', 'phase1_chunk', 'phase2_chunk'):
                    full_content += event["content"]
                    yield f"data: {json.dumps({'type': 'chunk', 'content': event['content']}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0)  # 让出事件循环，便于 Daphne/ASGI 立即发送该 chunk

                elif evt_type == 'phase2_fallback':
                    yield f"data: {json.dumps({'type': 'phase', 'message': event.get('message', '')}, ensure_ascii=False)}\n\n"

                elif evt_type == "done":
                    full_content = event["content"]
                    usage = event.get("usage", {})
                    model_used = event.get("model", "")
                    prompt_ver = event.get("prompt_version", "")

                elif event["type"] == "error":
                    latency_ms = int((time.perf_counter() - start_time) * 1000)
                    err_msg = (event.get("error") or "unknown")[:128]

                    def _log_error_span():
                        LlmCallLog.objects.create(
                            task_id=record.id,
                            span_type='llm',
                            model=model_used or '',
                            prompt_tokens=0,
                            completion_tokens=0,
                            latency_ms=latency_ms,
                            error_type=err_msg,
                        )
                        logger.info(
                            "llm_call_span",
                            extra={
                                "task_id": record.id,
                                "span_type": "llm",
                                "model": model_used or "",
                                "prompt_tokens": 0,
                                "completion_tokens": 0,
                                "latency_ms": latency_ms,
                                "error_type": err_msg,
                            },
                        )

                    await sync_to_async(_log_error_span)()
                    await sync_to_async(_update_record_error)(record, event["error"])
                    yield f"data: {json.dumps({'type': 'error', 'error': event['error']}, ensure_ascii=False)}\n\n"
                    return

            # 尝试解析 JSON
            result_json = router.parse_json(full_content)
            confidence = None
            if result_json:
                confidence = (
                    result_json.get('prd_meta', {}).get('confidence_score')
                    or result_json.get('confidence_score')
                )
            result_md = _extract_result_md(output_format, result_json, full_content)

            cost = router.calculate_cost(
                model_used,
                usage.get('prompt_tokens', 0),
                usage.get('completion_tokens', 0),
            )

            # 更新记录
            def save_result():
                record.status = 'success'
                record.raw_content = full_content
                record.result_json = result_json
                record.result_md = result_md
                record.model_used = model_used
                record.prompt_version = prompt_ver
                record.prompt_tokens = usage.get('prompt_tokens', 0)
                record.completion_tokens = usage.get('completion_tokens', 0)
                record.total_tokens = usage.get('total_tokens', 0)
                record.cost_usd = cost
                record.confidence_score = confidence
                record.schema_validated = result_json is not None
                record.save()

            await sync_to_async(save_result)()

            latency_ms = int((time.perf_counter() - start_time) * 1000)
            pt = usage.get('prompt_tokens', 0)
            ct = usage.get('completion_tokens', 0)

            def _log_success_span():
                LlmCallLog.objects.create(
                    task_id=record.id,
                    span_type='llm',
                    model=model_used or '',
                    prompt_tokens=pt,
                    completion_tokens=ct,
                    latency_ms=latency_ms,
                    error_type=None,
                )
                logger.info(
                    "llm_call_span",
                    extra={
                        "task_id": record.id,
                        "span_type": "llm",
                        "model": model_used or "",
                        "prompt_tokens": pt,
                        "completion_tokens": ct,
                        "latency_ms": latency_ms,
                        "error_type": None,
                    },
                )

            await sync_to_async(_log_success_span)()

            # P2-4 RAG：成功任务索引到向量库（同步调用，RAG 未开启则 no-op）
            try:
                from apps.ai_requirement.services.rag import index_task
                await sync_to_async(index_task)(record.id)
            except Exception:
                pass
            try:
                await sync_to_async(check_and_fire_cost_alert)()
            except Exception:
                pass

            # P1-1：供前端「澄清并继续」使用
            requires_clarification = False
            clarification_questions = []
            if result_json and isinstance(result_json, dict):
                prd_meta = result_json.get('prd_meta') or {}
                requires_clarification = prd_meta.get('requires_clarification', False) or result_json.get('requires_clarification', False)
                clarification_questions = prd_meta.get('clarification_questions') or result_json.get('clarification_questions') or []
                if not isinstance(clarification_questions, list):
                    clarification_questions = []

            done_data = {
                'type': 'done',
                'record_id': record.id,
                'status': 'success',
                'result_json': result_json,
                'result_md': result_md,
                'confidence_score': confidence,
                'requires_clarification': requires_clarification,
                'clarification_questions': clarification_questions,
                'usage': {
                    'model': model_used,
                    'prompt_tokens': usage.get('prompt_tokens', 0),
                    'completion_tokens': usage.get('completion_tokens', 0),
                    'total_tokens': usage.get('total_tokens', 0),
                    'cost_usd': str(cost),
                },
            }
            yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"

        except SecurityError as e:
            await sync_to_async(_log_span_on_exception)(record.id, start_time, 'llm', '', str(e))
            await sync_to_async(_update_record_error)(record, str(e))
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'error_code': 'SECURITY'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception(f"[AI需求] 流式生成异常: {e}")
            await sync_to_async(_log_span_on_exception)(record.id, start_time, 'llm', '', str(e))
            await sync_to_async(_update_record_error)(record, str(e))
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    # 防止 GZipMiddleware 压缩 SSE 流（压缩会导致缓冲，前端看不到流式）
    response['Content-Encoding'] = 'identity'
    return _add_cors_headers(response)


# ============ P1-1：澄清并继续（自动澄清处置）============

async def clarify_and_continue_view(request):
    """
    POST /api/ai_requirement/clarify-and-continue/
    Body: {"task_id": int, "clarification_answers": ["答1", "答2", ...]}

    根据原任务的 clarification_questions 与用户答案合并为新需求描述，创建新任务并流式生成。
    """
    if request.method == 'OPTIONS':
        return _add_cors_headers(HttpResponse(status=200))
    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405))
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _add_cors_headers(HttpResponse('Invalid JSON', status=400))

    task_id = body.get('task_id')
    answers = body.get('clarification_answers')
    if task_id is None:
        return _add_cors_headers(HttpResponse(json.dumps({'error': 'task_id 必填'}, ensure_ascii=False), content_type='application/json', status=400))
    if not isinstance(answers, list):
        answers = []

    from asgiref.sync import sync_to_async

    try:
        task = await sync_to_async(AiRequirementTask.objects.get)(id=task_id)
    except AiRequirementTask.DoesNotExist:
        return _add_cors_headers(HttpResponse(json.dumps({'error': '任务不存在'}, ensure_ascii=False), content_type='application/json', status=404))

    result_json = task.result_json or {}
    prd_meta = result_json.get('prd_meta') or {}
    questions = prd_meta.get('clarification_questions') or result_json.get('clarification_questions') or []
    if not isinstance(questions, list):
        questions = []
    if not questions:
        return _add_cors_headers(HttpResponse(
            json.dumps({'error': '该任务无澄清问题列表，无法使用澄清并继续'}, ensure_ascii=False),
            content_type='application/json', status=400
        ))

    parts = [task.requirement_input.strip(), "\n\n--- 用户澄清 ---"]
    for i, q in enumerate(questions):
        a = answers[i] if i < len(answers) else "(未回答)"
        if isinstance(a, str):
            parts.append(f"Q: {q}\nA: {a}")
    augmented_input = "\n".join(parts)

    async def event_stream():
        from asgiref.sync import sync_to_async
        record = await sync_to_async(AiRequirementTask.objects.create)(
            role=task.role,
            task_type=task.task_type,
            requirement_input=augmented_input[:50000],
            status='generating',
            use_thinking=task.use_thinking,
            output_format=task.output_format or 'both',
            security_level=task.security_level or 'internal',
            session_id=task.session_id,
            parent_task_id=task_id,
        )
        yield f"data: {json.dumps({'type': 'start', 'record_id': record.id}, ensure_ascii=False)}\n\n"
        start_time = time.perf_counter()
        router = RequirementAgentRouter()
        full_content = ""
        usage = {}
        model_used = ""
        prompt_ver = ""
        try:
            gen = router.run_stream(
                task.role,
                task.task_type,
                augmented_input,
                extracted_texts=None,
                images=None,
                use_thinking=task.use_thinking,
                security_level=task.security_level or 'internal',
            )
            async for event in gen:
                if event.get("type") in ('phase1_start', 'phase2_start'):
                    yield f"data: {json.dumps({'type': 'phase', 'message': event.get('message', '')}, ensure_ascii=False)}\n\n"
                elif event.get("type") in ('chunk', 'phase1_chunk', 'phase2_chunk'):
                    full_content += event.get("content", "")
                    yield f"data: {json.dumps({'type': 'chunk', 'content': event.get('content', '')}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0)
                elif event.get("type") == 'phase2_fallback':
                    yield f"data: {json.dumps({'type': 'phase', 'message': event.get('message', '')}, ensure_ascii=False)}\n\n"
                elif event.get("type") == "done":
                    full_content = event.get("content", "")
                    usage = event.get("usage", {})
                    model_used = event.get("model", "")
                    prompt_ver = event.get("prompt_version", "")
                elif event.get("type") == "error":
                    err_msg = (event.get("error") or "unknown")[:128]
                    def _log_err():
                        LlmCallLog.objects.create(
                            task_id=record.id, span_type='llm', model=model_used or '',
                            prompt_tokens=0, completion_tokens=0,
                            latency_ms=int((time.perf_counter() - start_time) * 1000),
                            error_type=err_msg,
                        )
                    await sync_to_async(_log_err)()
                    await sync_to_async(_update_record_error)(record, event.get("error", ""))
                    yield f"data: {json.dumps({'type': 'error', 'error': event.get('error', '')}, ensure_ascii=False)}\n\n"
                    return

            result_json_out = router.parse_json(full_content)
            confidence = None
            if result_json_out:
                confidence = (
                    result_json_out.get('prd_meta', {}).get('confidence_score')
                    or result_json_out.get('confidence_score')
                )
            result_md = _extract_result_md(task.output_format or 'both', result_json_out, full_content)
            cost = router.calculate_cost(model_used, usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0))

            def save_result():
                record.status = 'success'
                record.raw_content = full_content
                record.result_json = result_json_out
                record.result_md = result_md
                record.model_used = model_used
                record.prompt_version = prompt_ver
                record.prompt_tokens = usage.get('prompt_tokens', 0)
                record.completion_tokens = usage.get('completion_tokens', 0)
                record.total_tokens = usage.get('total_tokens', 0)
                record.cost_usd = cost
                record.confidence_score = confidence
                record.schema_validated = result_json_out is not None
                record.save()

            await sync_to_async(save_result)()
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            def _log_ok():
                LlmCallLog.objects.create(
                    task_id=record.id, span_type='llm', model=model_used or '',
                    prompt_tokens=usage.get('prompt_tokens', 0),
                    completion_tokens=usage.get('completion_tokens', 0),
                    latency_ms=latency_ms, error_type=None,
                )
            await sync_to_async(_log_ok)()
            try:
                from apps.ai_requirement.services.rag import index_task
                await sync_to_async(index_task)(record.id)
            except Exception:
                pass
            req_clar = False
            cl_questions = []
            if result_json_out and isinstance(result_json_out, dict):
                pm = result_json_out.get('prd_meta') or {}
                req_clar = pm.get('requires_clarification', False) or result_json_out.get('requires_clarification', False)
                cl_questions = pm.get('clarification_questions') or result_json_out.get('clarification_questions') or []
                if not isinstance(cl_questions, list):
                    cl_questions = []
            done_data = {
                'type': 'done', 'record_id': record.id, 'status': 'success',
                'result_json': result_json_out, 'result_md': result_md,
                'confidence_score': confidence,
                'requires_clarification': req_clar, 'clarification_questions': cl_questions,
                'usage': {
                    'model': model_used, 'prompt_tokens': usage.get('prompt_tokens', 0),
                    'completion_tokens': usage.get('completion_tokens', 0),
                    'total_tokens': usage.get('total_tokens', 0), 'cost_usd': str(cost),
                },
            }
            yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"
        except SecurityError as e:
            await sync_to_async(_log_span_on_exception)(record.id, start_time, 'llm', '', str(e))
            await sync_to_async(_update_record_error)(record, str(e))
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'error_code': 'SECURITY'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("[AI需求] 澄清并继续流式异常: %s", e)
            await sync_to_async(_log_span_on_exception)(record.id, start_time, 'llm', '', str(e))
            await sync_to_async(_update_record_error)(record, str(e))
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Content-Encoding'] = 'identity'
    return _add_cors_headers(response)


def _update_record_error(record: AiRequirementTask, error_msg: str):
    record.status = 'failed'
    record.error_message = error_msg[:2000]
    record.save(update_fields=['status', 'error_message', 'updated_at'])


def _log_span_on_exception(task_id: int, start_time: float, span_type: str, model: str, error_msg: str):
    """可观测性：异常时写入 LlmCallLog 并打结构化日志"""
    try:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        err = (error_msg or 'unknown')[:128]
        LlmCallLog.objects.create(
            task_id=task_id,
            span_type=span_type,
            model=model or '',
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=latency_ms,
            error_type=err,
        )
        logger.info(
            "llm_call_span",
            extra={
                "task_id": task_id,
                "span_type": span_type,
                "model": model or "",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "latency_ms": latency_ms,
                "error_type": err,
            },
        )
    except Exception:
        pass


# ============ 非流式接口 ============

async def run_sync_view(request):
    """
    非流式同步生成（调试/集成用）

    POST /api/ai_requirement/run/
    """
    if request.method == 'OPTIONS':
        return _add_cors_headers(HttpResponse(status=200))

    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405))

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _add_cors_headers(HttpResponse('Invalid JSON', status=400))

    role = body.get('role', '').strip()
    task_type = body.get('task_type', '').strip()
    requirement_input = body.get('requirement_input', '').strip()
    use_thinking = body.get('use_thinking', False)
    output_format = body.get('output_format', 'both')

    if not role or not task_type or not requirement_input:
        return _add_cors_headers(
            HttpResponse('role, task_type, requirement_input 必填', status=400)
        )

    try:
        router = RequirementAgentRouter()
        full_content = ""
        usage = {}
        model_used = ""

        async for event in router.run_stream(
            role=role,
            task_type=task_type,
            requirement_input=requirement_input,
            use_thinking=use_thinking,
        ):
            if event["type"] == "chunk":
                full_content += event["content"]
            elif event["type"] == "done":
                full_content = event["content"]
                usage = event.get("usage", {})
                model_used = event.get("model", "")
            elif event["type"] == "error":
                resp = HttpResponse(
                    json.dumps({'error': event["error"]}, ensure_ascii=False),
                    content_type='application/json', status=500
                )
                return _add_cors_headers(resp)

        result_json = router.parse_json(full_content)
        result_md = _extract_result_md(output_format, result_json, full_content)
        resp_data = {
            'status': 'success',
            'result_json': result_json,
            'result_md': result_md,
            'output_format': output_format,
            'usage': usage,
            'model': model_used,
        }
        resp = HttpResponse(
            json.dumps(resp_data, ensure_ascii=False),
            content_type='application/json'
        )
        return _add_cors_headers(resp)

    except SecurityError as e:
        resp = HttpResponse(
            json.dumps({'error': str(e), 'error_code': 'SECURITY'}, ensure_ascii=False),
            content_type='application/json', status=403
        )
        return _add_cors_headers(resp)
    except Exception as e:
        logger.exception(f"[AI需求] 同步生成异常: {e}")
        resp = HttpResponse(
            json.dumps({'error': str(e)}, ensure_ascii=False),
            content_type='application/json', status=500
        )
        return _add_cors_headers(resp)


# ============ 反馈接口 ============

async def feedback_view(request):
    """
    用户反馈

    POST /api/ai_requirement/feedback/
    """
    if request.method == 'OPTIONS':
        return _add_cors_headers(HttpResponse(status=200))

    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405))

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _add_cors_headers(HttpResponse('Invalid JSON', status=400))

    task_id = body.get('task_id')
    rating = body.get('rating', '')
    issue_type = body.get('issue_type')
    comment = body.get('comment', '')

    if not task_id or rating not in ('positive', 'negative'):
        return _add_cors_headers(HttpResponse('task_id 和 rating 必填', status=400))

    from asgiref.sync import sync_to_async

    try:
        task = await sync_to_async(AiRequirementTask.objects.get)(id=task_id)
    except AiRequirementTask.DoesNotExist:
        return _add_cors_headers(HttpResponse('任务不存在', status=404))

    await sync_to_async(AiRequirementFeedback.objects.create)(
        task=task,
        rating=rating,
        issue_type=issue_type,
        comment=comment[:2000] if comment else '',
        prompt_version=task.prompt_version or '',
    )

    resp = HttpResponse(
        json.dumps({'status': 'ok'}, ensure_ascii=False),
        content_type='application/json'
    )
    return _add_cors_headers(resp)


# ============ 多轮对话接口 ============

async def chat_stream_view(request):
    """
    多轮对话 SSE 流式接口（置信度<0.7 时主动澄清）

    POST /api/ai_requirement/chat/
    {
        "session_id": "xxx",           // 首次可空，后端生成
        "role": "product",
        "task_type": "prd_draft",
        "message": "用户本轮输入",
        "use_thinking": false
    }

    多轮对话原理：从同 session_id 的历史记录中恢复上下文，
    拼接为 assistant/user 交替的 messages 列表。
    """
    if request.method == 'OPTIONS':
        return _add_cors_headers(HttpResponse(status=200))
    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405))

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _add_cors_headers(HttpResponse('Invalid JSON', status=400))

    role = body.get('role', '').strip()
    task_type = body.get('task_type', '').strip()
    message = body.get('message', '').strip()
    session_id = body.get('session_id', '').strip()
    use_thinking = body.get('use_thinking', False)

    if not role or not task_type or not message:
        return _add_cors_headers(HttpResponse('role, task_type, message 必填', status=400))

    import uuid
    if not session_id:
        session_id = str(uuid.uuid4())[:8]

    async def event_stream():
        from asgiref.sync import sync_to_async
        from apps.ai_requirement.services.cost_quota import check_user_quota, check_and_fire_cost_alert

        estimated_usd = 0.0
        try:
            _router = RequirementAgentRouter()
            estimated_usd = _router.estimate_cost_usd(role, task_type, message, None, None, use_thinking)
        except Exception:
            pass
        ok, msg = await sync_to_async(check_user_quota)(request.user, estimated_usd)
        if not ok:
            yield f"data: {json.dumps({'type': 'quota_exceeded', 'error': msg}, ensure_ascii=False)}\n\n"
            return

        # 从历史恢复上下文
        def get_history():
            return list(
                AiRequirementTask.objects.filter(
                    session_id=session_id, status='success'
                ).order_by('created_at').values_list('requirement_input', 'raw_content')
            )

        history = await sync_to_async(get_history)()

        user_id = getattr(request.user, 'id', None) if getattr(request.user, 'is_authenticated', False) else None
        record = await sync_to_async(AiRequirementTask.objects.create)(
            role=role,
            task_type=task_type,
            requirement_input=message,
            session_id=session_id,
            status='generating',
            use_thinking=use_thinking,
            created_by_id=user_id,
        )

        yield f"data: {json.dumps({'type': 'start', 'record_id': record.id, 'session_id': session_id}, ensure_ascii=False)}\n\n"

        try:
            router = RequirementAgentRouter()
            system_prompt, prompt_ver = router.get_prompt(role, task_type)
            model = router.select_model(role, task_type, use_thinking)
            client = router._get_client(model)

            messages = [{"role": "system", "content": system_prompt}]
            for user_msg, assistant_msg in history:
                messages.append({"role": "user", "content": user_msg or ""})
                messages.append({"role": "assistant", "content": assistant_msg or ""})
            messages.append({"role": "user", "content": message})

            extra_body = (
                {"thinking": {"type": "enabled", "budget_tokens": 10000}}
                if use_thinking
                else {"thinking": {"type": "disabled"}}
            )

            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                extra_body=extra_body,
                stream=True,
                stream_options={"include_usage": True},
                temperature=0.6,  # Kimi k2.5 仅支持 0.6
            )

            full_content = ""
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

            async for chunk in stream:
                if chunk.usage:
                    usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens or 0,
                        "completion_tokens": chunk.usage.completion_tokens or 0,
                        "total_tokens": chunk.usage.total_tokens or 0,
                    }
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        full_content += delta.content
                        yield f"data: {json.dumps({'type': 'chunk', 'content': delta.content}, ensure_ascii=False)}\n\n"

            result_json = router.parse_json(full_content)
            confidence = None
            if result_json:
                confidence = (
                    result_json.get('prd_meta', {}).get('confidence_score')
                    or result_json.get('confidence_score')
                )

            requires_clarification = False
            if result_json:
                requires_clarification = result_json.get('prd_meta', {}).get('requires_clarification', False)

            cost = router.calculate_cost(model, usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0))

            def save_result():
                record.status = 'success'
                record.raw_content = full_content
                record.result_json = result_json
                record.model_used = model
                record.prompt_version = prompt_ver
                record.prompt_tokens = usage.get('prompt_tokens', 0)
                record.completion_tokens = usage.get('completion_tokens', 0)
                record.total_tokens = usage.get('total_tokens', 0)
                record.cost_usd = cost
                record.confidence_score = confidence
                record.schema_validated = result_json is not None
                record.save()
            await sync_to_async(save_result)()

            try:
                from apps.ai_requirement.services.rag import index_task
                await sync_to_async(index_task)(record.id)
            except Exception:
                pass
            try:
                await sync_to_async(check_and_fire_cost_alert)()
            except Exception:
                pass

            done_data = {
                'type': 'done',
                'record_id': record.id,
                'session_id': session_id,
                'status': 'success',
                'result_json': result_json,
                'confidence_score': confidence,
                'requires_clarification': requires_clarification,
                'usage': {
                    'model': model,
                    'prompt_tokens': usage.get('prompt_tokens', 0),
                    'completion_tokens': usage.get('completion_tokens', 0),
                    'total_tokens': usage.get('total_tokens', 0),
                    'cost_usd': str(cost),
                },
            }
            yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"

        except SecurityError as e:
            await sync_to_async(_update_record_error)(record, str(e))
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'error_code': 'SECURITY'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception(f"[AI需求] 多轮对话异常: {e}")
            await sync_to_async(_update_record_error)(record, str(e))
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Content-Encoding'] = 'identity'
    return _add_cors_headers(response)


# ============ 功能点 → 用例智能体桥接 ============

async def bridge_to_testcase_view(request):
    """
    将 feature_breakdown 结果桥接到 ai_testcase 的 generate-from-structure 接口

    POST /api/ai_requirement/bridge-to-testcase/
    {"task_id": 123}

    将 feature_breakdown 的 JSON 结构转换为 ai_testcase 可消费的格式，
    直接调用 ai_testcase 的 SSE 流式生成。
    """
    if request.method == 'OPTIONS':
        return _add_cors_headers(HttpResponse(status=200))
    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405))

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _add_cors_headers(HttpResponse('Invalid JSON', status=400))

    task_id = body.get('task_id')
    if not task_id:
        return _add_cors_headers(HttpResponse('task_id 必填', status=400))

    from asgiref.sync import sync_to_async

    try:
        task = await sync_to_async(AiRequirementTask.objects.get)(id=task_id)
    except AiRequirementTask.DoesNotExist:
        return _add_cors_headers(HttpResponse('任务不存在', status=404))

    if task.task_type != 'feature_breakdown':
        return _add_cors_headers(HttpResponse('仅支持 feature_breakdown 任务类型', status=400))
    if not task.result_json:
        return _add_cors_headers(HttpResponse('该任务无结构化结果', status=400))

    fb_data = task.result_json
    modules = fb_data.get('modules', [])
    if not modules:
        return _add_cors_headers(HttpResponse('功能点数据为空', status=400))

    # 方式 A：结构直传 —— 将 feature_breakdown 的 JSON 直接映射为 ai_testcase 需要的格式
    requirement_text_parts = [f"# {fb_data.get('title', '功能点梳理')}\n"]
    for mod in modules:
        requirement_text_parts.append(f"\n## 模块：{mod['name']}")
        for func in mod.get('functions', []):
            requirement_text_parts.append(f"\n### {func['name']}（{func.get('priority', 'P1')}）")
            if func.get('description'):
                requirement_text_parts.append(f"描述：{func['description']}")
            if func.get('acceptance_points'):
                for ap in func['acceptance_points']:
                    requirement_text_parts.append(f"  - {ap}")
            if func.get('test_hint'):
                requirement_text_parts.append(f"测试建议：{func['test_hint']}")

    requirement_text = "\n".join(requirement_text_parts)

    # 方式 A 结构直传：供前端调用 ai_testcase generate-from-structure 使用（不包含 cases）
    structure = json.loads(json.dumps(fb_data))  # 深拷贝
    for mod in structure.get('modules', []):
        for func in mod.get('functions', []):
            func.pop('cases', None)  # 去掉已有 cases，由用例接口生成

    # 记录血缘追踪
    def update_downstream():
        downstream = task.downstream_testcases or []
        task.downstream_testcases = downstream
        task.save(update_fields=['downstream_testcases', 'updated_at'])
    await sync_to_async(update_downstream)()

    resp_data = {
        'status': 'ok',
        'requirement_text': requirement_text,
        'structure': structure,
        'source_task_id': task.id,
        'module_count': len(modules),
        'function_count': sum(len(m.get('functions', [])) for m in modules),
    }
    resp = HttpResponse(
        json.dumps(resp_data, ensure_ascii=False),
        content_type='application/json'
    )
    return _add_cors_headers(resp)


# ============ Jira / Confluence 同步（P2-3）============

def sync_to_jira_view(request):
    """
    POST /api/ai_requirement/sync-to-jira/
    Body: {"task_id": int, "project_key": str?, "issue_type": str?}
    根据 feature_breakdown 任务在 Jira 中创建工单；未配置时返回 501。
    """
    if request.method == 'OPTIONS':
        return _add_cors_headers(HttpResponse(status=200))
    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405))
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _add_cors_headers(HttpResponse('Invalid JSON', status=400))
    task_id = body.get('task_id')
    if task_id is None:
        return _add_cors_headers(HttpResponse(json.dumps({"success": False, "error": "task_id 必填"}, ensure_ascii=False), content_type='application/json', status=400))
    from apps.ai_requirement.services.external_tools import create_jira_tickets_from_task
    out = create_jira_tickets_from_task(
        task_id=int(task_id),
        project_key=body.get('project_key'),
        issue_type=body.get('issue_type') or 'Task',
    )
    status_code = 200 if out.get('success') else (501 if out.get('error', '').find('未配置') != -1 else 400)
    return _add_cors_headers(HttpResponse(json.dumps(out, ensure_ascii=False), content_type='application/json', status=status_code))


def sync_to_confluence_view(request):
    """
    POST /api/ai_requirement/sync-to-confluence/
    Body: {"task_id": int, "space_key": str?, "title": str?}
    将任务的 PRD 内容写入 Confluence 页面；未配置时返回 501。
    """
    if request.method == 'OPTIONS':
        return _add_cors_headers(HttpResponse(status=200))
    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405))
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _add_cors_headers(HttpResponse('Invalid JSON', status=400))
    task_id = body.get('task_id')
    if task_id is None:
        return _add_cors_headers(HttpResponse(json.dumps({"success": False, "error": "task_id 必填"}, ensure_ascii=False), content_type='application/json', status=400))
    from apps.ai_requirement.services.external_tools import write_prd_to_confluence
    out = write_prd_to_confluence(
        task_id=int(task_id),
        space_key=body.get('space_key'),
        title=body.get('title'),
    )
    status_code = 200 if out.get('success') else (501 if (out.get('error') or '').find('未配置') != -1 else 400)
    return _add_cors_headers(HttpResponse(json.dumps(out, ensure_ascii=False), content_type='application/json', status=status_code))


# ============ ViewSet ============

def _task_export_response(request, task, fmt):
    """共用导出逻辑：根据 format 生成 PDF/Word 并返回 HttpResponse。注意：本函数被普通 Django 视图调用，只能返回 HttpResponse，不能返回 DRF Response。"""
    from urllib.parse import quote
    from apps.ai_requirement.services.export_doc import export_pdf, export_docx

    def _json_error(msg, status):
        return _add_cors_headers(HttpResponse(
            json.dumps({'error': msg}, ensure_ascii=False),
            content_type='application/json',
            status=status,
        ))

    if fmt not in ('pdf', 'docx'):
        return _json_error('format 须为 pdf 或 docx', 400)
    if not (task.result_md or task.raw_content):
        return _json_error('该任务无文本内容可导出', 400)
    try:
        if fmt == 'pdf':
            data, filename = export_pdf(task)
            content_type = 'application/pdf'
        else:
            data, filename = export_docx(task)
            content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        response = HttpResponse(data, content_type=content_type)
        response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
        response['Access-Control-Expose-Headers'] = 'Content-Disposition'
        return _add_cors_headers(response)
    except ValueError as e:
        return _json_error(str(e), 400)
    except Exception as e:
        logger.exception("[AI需求] 导出失败: %s", e)
        return _json_error(f'导出失败: {str(e)}', 500)


def task_export_view(request, pk):
    """
    GET /api/ai_requirement/tasks/<id>/export/?format=pdf|docx
    独立 URL，确保导出接口稳定可用（不依赖 router 的 action）。
    """
    if request.method == 'OPTIONS':
        return _add_cors_headers(HttpResponse(status=200))
    if request.method != 'GET':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405))
    try:
        task = AiRequirementTask.objects.get(pk=pk)
    except AiRequirementTask.DoesNotExist:
        return _add_cors_headers(HttpResponse(
            json.dumps({'error': '任务不存在'}, ensure_ascii=False),
            content_type='application/json',
            status=404,
        ))
    fmt = (request.GET.get('format') or 'pdf').lower()
    return _task_export_response(request, task, fmt)


class AiRequirementTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """任务记录查询 ViewSet（只读）"""
    serializer_class = AiRequirementTaskSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = AiRequirementTask.objects.all()
        role = self.request.query_params.get('role')
        task_type = self.request.query_params.get('task_type')
        status_filter = self.request.query_params.get('status')
        if role:
            qs = qs.filter(role=role)
        if task_type:
            qs = qs.filter(task_type=task_type)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    @action(detail=True, methods=['get'], url_path='export')
    def export(self, request, pk=None):
        """GET /api/ai_requirement/tasks/<id>/export/?format=pdf|docx（router 注册）"""
        task = self.get_object()
        fmt = (request.query_params.get('format') or 'pdf').lower()
        return _task_export_response(request, task, fmt)


# ============ 成本监控统计 API ============

from django.db.models import Sum, Count, Avg, F, Q
from django.db.models.functions import TruncDate
from rest_framework.decorators import api_view, permission_classes as perm_deco


@api_view(['GET'])
@perm_deco([AllowAny])
def stats_overview(request):
    """
    GET /api/ai_requirement/stats/overview/

    返回总体统计：总任务数、总 Token、总成本、平均置信度、成功率、
    按角色/任务分布、最近 7 天日均趋势。
    """
    qs = AiRequirementTask.objects.all()
    total = qs.count()
    success = qs.filter(status='success').count()
    failed = qs.filter(status='failed').count()

    agg = qs.aggregate(
        total_prompt_tokens=Sum('prompt_tokens'),
        total_completion_tokens=Sum('completion_tokens'),
        total_tokens_sum=Sum('total_tokens'),
        total_cost=Sum('cost_usd'),
        avg_confidence=Avg('confidence_score'),
        avg_tokens_per_task=Avg('total_tokens'),
    )

    # 按角色分布
    by_role = list(
        qs.values('role').annotate(
            count=Count('id'),
            tokens=Sum('total_tokens'),
            cost=Sum('cost_usd'),
        ).order_by('role')
    )

    # 按任务类型分布
    by_task = list(
        qs.values('task_type').annotate(
            count=Count('id'),
            tokens=Sum('total_tokens'),
            cost=Sum('cost_usd'),
            avg_conf=Avg('confidence_score'),
        ).order_by('-count')
    )

    # 最近 14 天日均趋势
    from django.utils import timezone
    import datetime
    cutoff = timezone.now() - datetime.timedelta(days=14)
    daily = list(
        qs.filter(created_at__gte=cutoff)
        .annotate(date=TruncDate('created_at'))
        .values('date')
        .annotate(
            count=Count('id'),
            tokens=Sum('total_tokens'),
            cost=Sum('cost_usd'),
        )
        .order_by('date')
    )
    for d in daily:
        d['date'] = d['date'].isoformat() if d['date'] else None
        d['cost'] = str(d['cost'] or 0)

    # 链路级可观测性：最近 N 条 LLM 调用记录（耗时、错误类型）
    recent_traces = list(
        LlmCallLog.objects.all()
        .values('id', 'task_id', 'span_type', 'model', 'prompt_tokens', 'completion_tokens', 'latency_ms', 'error_type', 'created_at')
        .order_by('-created_at')[:50]
    )
    for t in recent_traces:
        t['created_at'] = t['created_at'].isoformat() if t.get('created_at') else None

    # 反馈统计
    fb_total = AiRequirementFeedback.objects.count()
    fb_positive = AiRequirementFeedback.objects.filter(rating='positive').count()
    fb_by_issue = list(
        AiRequirementFeedback.objects.filter(rating='negative')
        .values('issue_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    for item in by_role:
        item['cost'] = str(item['cost'] or 0)
    for item in by_task:
        item['cost'] = str(item['cost'] or 0)

    # 当日成本与成本告警（供前端展示）
    from apps.ai_requirement.services.cost_quota import get_today_cost_total
    today_cost = get_today_cost_total()
    cost_alert_threshold = float(getattr(settings, 'AI_REQUIREMENT_COST_ALERT_DAILY_USD', 0) or 0)
    cost_alert = cost_alert_threshold > 0 and float(today_cost) >= cost_alert_threshold

    data = {
        'total_tasks': total,
        'success': success,
        'failed': failed,
        'success_rate': round(success / total * 100, 1) if total else 0,
        'total_prompt_tokens': agg['total_prompt_tokens'] or 0,
        'total_completion_tokens': agg['total_completion_tokens'] or 0,
        'total_tokens': agg['total_tokens_sum'] or 0,
        'total_cost_usd': str(agg['total_cost'] or 0),
        'today_cost_usd': str(today_cost),
        'cost_alert': cost_alert,
        'cost_alert_threshold_usd': cost_alert_threshold,
        'avg_confidence': round(agg['avg_confidence'] or 0, 3),
        'avg_tokens_per_task': int(agg['avg_tokens_per_task'] or 0),
        'by_role': by_role,
        'by_task_type': by_task,
        'daily_trend': daily,
        'recent_traces': recent_traces,
        'feedback': {
            'total': fb_total,
            'positive': fb_positive,
            'negative': fb_total - fb_positive,
            'satisfaction_rate': round(fb_positive / fb_total * 100, 1) if fb_total else 0,
            'issues': fb_by_issue,
        },
    }
    return Response(data)


# ============ Prompt 版本管理 ViewSet ============


class PromptVersionViewSet(viewsets.ModelViewSet):
    """Prompt 版本管理 CRUD + 激活/A-B 切换"""
    serializer_class = PromptVersionSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = PromptVersion.objects.all()
        task_type = self.request.query_params.get('task_type')
        if task_type:
            qs = qs.filter(task_type=task_type)
        # 附带使用次数
        qs = qs.annotate(
            usage_count=Count(
                'task_type',
                filter=Q(
                    task_type=F('task_type'),
                )
            )
        )
        return qs

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """
        POST /api/ai_requirement/prompts/{id}/activate/
        {"action": "activate" | "deactivate" | "set_ab", "ab_traffic_ratio": 0.1}
        """
        pv = self.get_object()
        ser = PromptVersionActivateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        act = ser.validated_data['action']

        if act == 'activate':
            PromptVersion.objects.filter(
                task_type=pv.task_type, is_active=True
            ).update(is_active=False)
            pv.is_active = True
            pv.save(update_fields=['is_active'])
            return Response({'status': 'ok', 'message': f'{pv} 已激活'})

        elif act == 'deactivate':
            pv.is_active = False
            pv.is_ab_candidate = False
            pv.ab_traffic_ratio = 0
            pv.save(update_fields=['is_active', 'is_ab_candidate', 'ab_traffic_ratio'])
            return Response({'status': 'ok', 'message': f'{pv} 已停用'})

        elif act == 'set_ab':
            ratio = ser.validated_data.get('ab_traffic_ratio', 0.1)
            PromptVersion.objects.filter(
                task_type=pv.task_type, is_ab_candidate=True
            ).update(is_ab_candidate=False, ab_traffic_ratio=0)
            pv.is_ab_candidate = True
            pv.ab_traffic_ratio = ratio
            pv.save(update_fields=['is_ab_candidate', 'ab_traffic_ratio'])
            return Response({'status': 'ok', 'message': f'{pv} 设为A/B候选 ({ratio*100:.0f}%流量)'})


# ============ 评估管理 ViewSet ============

class EvalDatasetViewSet(viewsets.ModelViewSet):
    """评估数据集 CRUD"""
    serializer_class = EvalDatasetSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = EvalDataset.objects.all()
        task_type = self.request.query_params.get('task_type')
        if task_type:
            qs = qs.filter(task_type=task_type)
        return qs


class EvalRunViewSet(viewsets.ReadOnlyModelViewSet):
    """评估运行记录（只读，由后台任务创建）"""
    serializer_class = EvalRunSerializer
    permission_classes = [AllowAny]
    queryset = EvalRun.objects.all()

    @action(detail=False, methods=['post'])
    def start(self, request):
        """
        POST /api/ai_requirement/eval-runs/start/
        {"prompt_version_id": 1, "trials": 3}

        创建评估运行任务（同步执行简化版：遍历数据集，调用 run_validated）
        """
        pv_id = request.data.get('prompt_version_id')
        trials = request.data.get('trials', 3)

        try:
            pv = PromptVersion.objects.get(id=pv_id)
        except PromptVersion.DoesNotExist:
            return Response({'error': 'Prompt版本不存在'}, status=404)

        samples = EvalDataset.objects.filter(
            task_type=pv.task_type, is_active=True
        )
        if not samples.exists():
            return Response({'error': f'{pv.task_type} 无可用评估样本'}, status=400)

        run = EvalRun.objects.create(
            prompt_version=pv,
            status='pending',
            total_samples=samples.count(),
            trials_per_sample=trials,
        )

        from apps.ai_requirement.services.eval_runner import start_eval_run_in_background
        start_eval_run_in_background(run.id)

        return Response({
            'status': 'ok',
            'eval_run_id': run.id,
            'total_samples': run.total_samples,
            'message': '评估已启动，请通过 GET /api/ai_requirement/eval-runs/{id}/ 查看进度与结果',
        })

    @action(detail=True, methods=['post'])
    def set_baseline(self, request, pk=None):
        """
        POST /api/ai_requirement/eval-runs/{id}/set_baseline/
        将该次评估标记为基线（同 task_type 下其他运行的 is_baseline 置为 False）。
        仅对 status=completed 的运行有效。
        """
        run = self.get_object()
        if run.status != 'completed':
            return Response(
                {'error': '仅可对已完成的评估运行设为基线'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        task_type = run.prompt_version.task_type
        EvalRun.objects.filter(
            prompt_version__task_type=task_type,
        ).update(is_baseline=False)
        run.is_baseline = True
        run.save(update_fields=['is_baseline'])
        return Response({
            'status': 'ok',
            'eval_run_id': run.id,
            'task_type': task_type,
            'message': f'已将该次评估设为 {task_type} 的基线',
        })


# ============ 工作流：PRD 深度模式 ============

async def workflow_start_view(request):
    """
    启动 PRD 深度撰写工作流（SSE 实时推送节点进度）

    POST /api/ai_requirement/workflow/start/
    {"requirement_input": "...", "use_thinking": false}

    Response: text/event-stream
    """
    if request.method == 'OPTIONS':
        return _add_cors_headers(HttpResponse(status=200))
    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405))

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _add_cors_headers(HttpResponse('Invalid JSON', status=400))

    requirement_input = body.get('requirement_input', '').strip()
    use_thinking = body.get('use_thinking', False)

    if not requirement_input:
        return _add_cors_headers(HttpResponse('requirement_input 必填', status=400))

    async def event_stream():
        from .workflows.executor import WorkflowExecutor

        run = await WorkflowExecutor.start_workflow(requirement_input, use_thinking)

        async for event in WorkflowExecutor.execute_workflow(run):
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Content-Encoding'] = 'identity'
    return _add_cors_headers(response)


async def workflow_approve_view(request, workflow_id):
    """
    人工审批工作流（SSE 实时推送后续节点进度）

    POST /api/ai_requirement/workflow/<id>/approve/
    {"approved": true, "comment": "同意"}

    Response: text/event-stream
    """
    if request.method == 'OPTIONS':
        return _add_cors_headers(HttpResponse(status=200))
    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405))

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _add_cors_headers(HttpResponse('Invalid JSON', status=400))

    approved = body.get('approved')
    comment = body.get('comment', '')

    if approved is None:
        return _add_cors_headers(HttpResponse('approved 必填', status=400))

    from asgiref.sync import sync_to_async

    try:
        run = await sync_to_async(WorkflowRun.objects.get)(id=workflow_id)
    except WorkflowRun.DoesNotExist:
        return _add_cors_headers(HttpResponse('工作流不存在', status=404))

    if run.status != 'waiting_approval':
        resp = HttpResponse(
            json.dumps({'error': f'当前状态 {run.status}，无法审批'}, ensure_ascii=False),
            content_type='application/json', status=400,
        )
        return _add_cors_headers(resp)

    async def event_stream():
        from .workflows.executor import WorkflowExecutor
        async for event in WorkflowExecutor.resume_after_approval(run, approved, comment):
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Content-Encoding'] = 'identity'
    return _add_cors_headers(response)


class WorkflowRunViewSet(viewsets.ReadOnlyModelViewSet):
    """工作流记录查询"""
    serializer_class = WorkflowRunSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = WorkflowRun.objects.all()
        status_filter = self.request.query_params.get('status')
        wf_type = self.request.query_params.get('workflow_type')
        if status_filter:
            qs = qs.filter(status=status_filter)
        if wf_type:
            qs = qs.filter(workflow_type=wf_type)
        return qs


# ============ 多智能体协作工作流 ============

async def multi_agent_start_view(request):
    """
    启动多智能体协作工作流（SSE）

    POST /api/ai_requirement/multi-agent/start/
    {"requirement_input": "...", "use_thinking": false}
    """
    if request.method == 'OPTIONS':
        return _add_cors_headers(HttpResponse(status=200))
    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405))

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _add_cors_headers(HttpResponse('Invalid JSON', status=400))

    requirement_input = body.get('requirement_input', '').strip()
    use_thinking = body.get('use_thinking', False)

    if not requirement_input:
        return _add_cors_headers(HttpResponse('requirement_input 必填', status=400))

    async def event_stream():
        from .workflows.multi_agent_executor import MultiAgentExecutor

        run = await MultiAgentExecutor.start_workflow(requirement_input, use_thinking)

        async for event in MultiAgentExecutor.execute_workflow(run):
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Content-Encoding'] = 'identity'
    return _add_cors_headers(response)


async def multi_agent_approve_view(request, workflow_id):
    """
    人工审核多智能体工作流（SSE）

    POST /api/ai_requirement/multi-agent/<id>/approve/
    {"approved": true, "comment": "..."}
    """
    if request.method == 'OPTIONS':
        return _add_cors_headers(HttpResponse(status=200))
    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405))

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _add_cors_headers(HttpResponse('Invalid JSON', status=400))

    approved = body.get('approved')
    comment = body.get('comment', '')

    if approved is None:
        return _add_cors_headers(HttpResponse('approved 必填', status=400))

    from asgiref.sync import sync_to_async

    try:
        run = await sync_to_async(WorkflowRun.objects.get)(id=workflow_id)
    except WorkflowRun.DoesNotExist:
        return _add_cors_headers(HttpResponse('工作流不存在', status=404))

    if run.status != 'waiting_approval':
        resp = HttpResponse(
            json.dumps({'error': f'当前状态 {run.status}，无法审批'}, ensure_ascii=False),
            content_type='application/json', status=400,
        )
        return _add_cors_headers(resp)

    async def event_stream():
        from .workflows.multi_agent_executor import MultiAgentExecutor
        async for event in MultiAgentExecutor.resume_after_approval(run, approved, comment):
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Content-Encoding'] = 'identity'
    return _add_cors_headers(response)
