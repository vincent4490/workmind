# -*- coding: utf-8 -*-
"""
评估流水线执行器

对 EvalRun 关联的数据集逐条调用 run_validated，计算准确率/幻觉率/Schema 合规率等，
写回 EvalRun 与 PromptVersion 的指标字段。
"""
import asyncio
import logging
import threading
import time
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)

# task_type -> role（与 PROMPT_REGISTRY 一致）
TASK_TYPE_TO_ROLE = {
    'competitive_analysis': 'product',
    'prd_draft': 'product',
    'prd_refine': 'product',
    'requirement_analysis': 'dev',
    'tech_design': 'dev',
    'test_requirement_analysis': 'test',
}


def _coverage_score(output_text: str, expected_key_facts: list) -> float:
    """
    计算期望关键事实在输出中的覆盖率（0~1）。
    若 expected_key_facts 为空，返回 1.0。
    """
    if not expected_key_facts:
        return 1.0
    if not output_text:
        return 0.0
    text_lower = output_text.lower()
    hit = 0
    for fact in expected_key_facts:
        if not fact or not isinstance(fact, str):
            continue
        if fact.strip().lower() in text_lower:
            hit += 1
    return hit / len(expected_key_facts) if expected_key_facts else 1.0


def _hallucination_simple(output_text: str, expected_key_facts: list) -> float:
    """
    简化幻觉率：基于“输出中是否包含明显无关片段”的启发式。
    若未配置 expected_key_facts 或无法计算，返回 0。
    """
    if not expected_key_facts or not output_text:
        return 0.0
    # 简单实现：与覆盖率互补的粗略估计（1 - coverage 作为幻觉倾向）
    coverage = _coverage_score(output_text, expected_key_facts)
    return max(0.0, 1.0 - coverage - 0.1)  # 留一点余量，避免误判


def _stability_score(detail_results: list) -> float:
    """
    P1-2 CLASSIC 稳定性：1 - min(1, std(样本准确率))。
    样本数 < 2 时返回 1.0。
    """
    if not detail_results or len(detail_results) < 2:
        return 1.0
    accs = []
    for d in detail_results:
        a = d.get('accuracy')
        if a is not None:
            accs.append(float(a))
    if len(accs) < 2:
        return 1.0
    mean = sum(accs) / len(accs)
    var = sum((x - mean) ** 2 for x in accs) / len(accs)
    std = var ** 0.5
    return round(1.0 - min(1.0, std), 4)


def _get_baseline_for_task_type(task_type: str):
    """返回该 task_type 下最近一次标记为基线的 EvalRun，若无则 None。"""
    from apps.ai_requirement.models import EvalRun
    return (
        EvalRun.objects.filter(
            prompt_version__task_type=task_type,
            is_baseline=True,
            status='completed',
        )
        .order_by('-created_at')
        .first()
    )


# 回归判定阈值：相对基线的允许波动
_REGRESSION_ACCURACY_DROP = 0.05   # 准确率下降超过 5% 视为回归
_REGRESSION_HALLUCINATION_UP = 0.05  # 幻觉率上升超过 5% 视为回归
_REGRESSION_SCHEMA_DROP = 0.05    # Schema 合规率下降超过 5% 视为回归


def _check_regression(current_run, baseline_run) -> bool:
    """当前运行与基线对比，任一项明显变差则判定为回归。"""
    if not baseline_run or baseline_run.avg_accuracy is None:
        return False
    acc_cur = current_run.avg_accuracy or 0
    acc_base = baseline_run.avg_accuracy or 0
    if acc_base - acc_cur > _REGRESSION_ACCURACY_DROP:
        return True
    hall_cur = current_run.avg_hallucination or 0
    hall_base = baseline_run.avg_hallucination or 0
    if hall_cur - hall_base > _REGRESSION_HALLUCINATION_UP:
        return True
    schema_cur = current_run.avg_schema_compliance or 0
    schema_base = baseline_run.avg_schema_compliance or 0
    if schema_base - schema_cur > _REGRESSION_SCHEMA_DROP:
        return True
    return False


async def run_eval_run_async(run_id: int) -> None:
    """
    在异步上下文中执行一次 EvalRun：遍历样本、多次 trial、聚合并写回。
    """
    from apps.ai_requirement.models import EvalRun, EvalDataset, PromptVersion
    from apps.ai_requirement.services.agent_router import RequirementAgentRouter

    try:
        run = await asyncio.to_thread(EvalRun.objects.select_related('prompt_version').get, id=run_id)
    except EvalRun.DoesNotExist:
        logger.warning("[Eval] EvalRun id=%s 不存在", run_id)
        return

    pv = run.prompt_version
    task_type = pv.task_type
    role = TASK_TYPE_TO_ROLE.get(task_type, 'product')
    trials = run.trials_per_sample or 1

    await asyncio.to_thread(_update_run_status, run, 'running', started_at=timezone.now())
    samples = list(await asyncio.to_thread(_get_samples, task_type))
    if not samples:
        await asyncio.to_thread(_update_run_status, run, 'failed', completed_at=timezone.now())
        return

    router = RequirementAgentRouter()
    detail_results = []
    total_tokens = 0
    total_latency_ms = 0
    total_cost = Decimal('0')
    schema_ok_count = 0
    accuracy_sum = 0.0
    hallucination_sum = 0.0
    n_samples = len(samples)

    for idx, sample in enumerate(samples):
        sample_id = getattr(sample, 'id', idx)
        input_text = sample.input_text
        expected_facts = list(sample.expected_key_facts) if sample.expected_key_facts else []

        trial_outputs = []
        sample_tokens = 0
        sample_latency_ms = 0
        sample_cost = Decimal('0')
        all_validated = True

        for _ in range(trials):
            t0 = time.perf_counter()
            try:
                result = await router.run_validated(
                    role=role,
                    task_type=task_type,
                    requirement_input=input_text,
                    max_retries=1,
                    system_prompt_override=pv.system_prompt,
                    prompt_version_override=pv.version,
                )
            except Exception as e:
                logger.exception("[Eval] sample %s trial 失败: %s", sample_id, e)
                all_validated = False
                result = {'validated': False, 'data': None, 'raw': '', 'usage': {}}
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            sample_latency_ms += elapsed_ms
            trial_outputs.append(result)
            if result.get('validated'):
                u = result.get('usage') or {}
                sample_tokens += u.get('total_tokens', 0) or 0
                # 成本需与 router 一致：这里用简单估算或从 router 取
                model = result.get('model', '')
                pt = u.get('prompt_tokens', 0) or 0
                ct = u.get('completion_tokens', 0) or 0
                sample_cost += router.calculate_cost(model, pt, ct)
            else:
                all_validated = False

        # 汇总该条样本的文本用于覆盖率
        raw_texts = [str(t.get('raw') or t.get('data') or '') for t in trial_outputs]
        combined = ' '.join(raw_texts)
        acc = _coverage_score(combined, expected_facts)
        hall = _hallucination_simple(combined, expected_facts) if expected_facts else 0.0

        accuracy_sum += acc
        hallucination_sum += hall
        total_tokens += sample_tokens
        total_latency_ms += sample_latency_ms
        total_cost += sample_cost
        if all_validated:
            schema_ok_count += 1

        detail_results.append({
            'sample_id': sample_id,
            'title': getattr(sample, 'title', ''),
            'accuracy': round(acc, 4),
            'hallucination': round(hall, 4),
            'schema_ok': all_validated,
            'trials': trials,
            'tokens': sample_tokens,
            'latency_ms': sample_latency_ms,
            'cost_usd': str(sample_cost),
        })
        run.completed_samples = idx + 1
        run.detail_results = detail_results
        await asyncio.to_thread(run.save, update_fields=['completed_samples', 'detail_results'])

    # 聚合
    run.avg_accuracy = round(accuracy_sum / n_samples, 4) if n_samples else None
    run.avg_hallucination = round(hallucination_sum / n_samples, 4) if n_samples else None
    run.avg_schema_compliance = round(schema_ok_count / n_samples, 4) if n_samples else None
    run.avg_stability = _stability_score(detail_results)
    run.avg_tokens = total_tokens // max(n_samples * trials, 1)
    run.avg_latency_ms = total_latency_ms // max(n_samples * trials, 1)
    run.total_cost_usd = total_cost
    run.status = 'completed'
    run.completed_at = timezone.now()

    # P1-2：与同 task_type 基线对比，设置 regression_detected
    baseline = await asyncio.to_thread(
        _get_baseline_for_task_type,
        task_type,
    )
    if baseline:
        run.baseline_run_id = baseline.id
        run.regression_detected = _check_regression(run, baseline)
    else:
        run.baseline_run_id = None
        run.regression_detected = False

    await asyncio.to_thread(run.save, update_fields=[
        'avg_accuracy', 'avg_hallucination', 'avg_schema_compliance',
        'avg_stability', 'avg_tokens', 'avg_latency_ms', 'total_cost_usd',
        'status', 'completed_at', 'detail_results',
        'baseline_run_id', 'regression_detected',
    ])

    # 回写 PromptVersion 性能指标（可选，便于看板展示）
    pv.accuracy_score = run.avg_accuracy
    pv.schema_compliance_rate = run.avg_schema_compliance
    pv.hallucination_rate = run.avg_hallucination
    pv.avg_output_tokens = run.avg_tokens
    pv.avg_latency_ms = run.avg_latency_ms
    await asyncio.to_thread(pv.save, update_fields=[
        'accuracy_score', 'schema_compliance_rate', 'hallucination_rate',
        'avg_output_tokens', 'avg_latency_ms',
    ])
    logger.info("[Eval] EvalRun id=%s 完成 avg_accuracy=%.2f schema_ok=%.2f", run_id, run.avg_accuracy or 0, run.avg_schema_compliance or 0)


def _get_samples(task_type: str):
    from apps.ai_requirement.models import EvalDataset
    return list(EvalDataset.objects.filter(task_type=task_type, is_active=True).order_by('id'))


def _update_run_status(run, status: str, started_at=None, completed_at=None):
    run.status = status
    if started_at is not None:
        run.started_at = started_at
    if completed_at is not None:
        run.completed_at = completed_at
    fields = ['status']
    if started_at is not None:
        fields.append('started_at')
    if completed_at is not None:
        fields.append('completed_at')
    run.save(update_fields=fields)


def start_eval_run_in_background(run_id: int) -> None:
    """在后台线程中执行评估（避免阻塞 start 接口）。"""
    def _thread():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_eval_run_async(run_id))
        except Exception as e:
            logger.exception("[Eval] 后台评估异常 run_id=%s: %s", run_id, e)
            from apps.ai_requirement.models import EvalRun
            try:
                run = EvalRun.objects.get(id=run_id)
                run.status = 'failed'
                run.completed_at = timezone.now()
                run.save(update_fields=['status', 'completed_at'])
            except Exception:
                pass
        finally:
            try:
                loop.close()
            except Exception:
                pass

    t = threading.Thread(target=_thread, daemon=True)
    t.start()
    logger.info("[Eval] 已启动后台评估 run_id=%s", run_id)
