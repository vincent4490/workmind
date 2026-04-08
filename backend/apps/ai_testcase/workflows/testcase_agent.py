# -*- coding: utf-8 -*-
"""
测试用例 Agent 工作流 —— 基于 LangGraph StateGraph

流程：需求分析 → 策略规划 → 分模块生成(循环) → 合并评审
    → [达标→完成 / 未达标→修订→再评审] → 完成

迭代上限保护：最多 MAX_REVISIONS 轮自动修订。
"""
import asyncio
import logging
import time
from django.conf import settings
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

from .agent_events import emit_node_start

logger = logging.getLogger(__name__)

MAX_REVISIONS = getattr(settings, 'TESTCASE_AGENT_MAX_REVISIONS', 3)
REVIEW_THRESHOLD = getattr(settings, 'TESTCASE_AGENT_REVIEW_THRESHOLD', 0.8)
MODULE_TIMEOUT = getattr(settings, 'TESTCASE_AGENT_MODULE_TIMEOUT', 120)
REVIEW_TIMEOUT = getattr(settings, 'TESTCASE_AGENT_REVIEW_TIMEOUT', 180)


class TestcaseAgentState(TypedDict, total=False):
    # 输入
    requirement: str
    extracted_texts: list
    images: list
    mode: str
    effective_mode: str  # 自适应后实际用于后续节点的模式（focused/comprehensive）
    mode_switch_reason: str
    use_thinking: bool
    quality_tier: str  # cheap/strong
    force_strong_generate: bool

    # 分析结果
    requirement_analysis: dict
    test_strategy: dict

    # 生成中间态
    modules_generated: list
    current_module_index: int
    module_total: int  # 需求分析中的模块总数，供 SSE 展示进度（节点增量里无 requirement_analysis 时必需）
    generation_errors: list

    # 评审循环
    merged_result: dict
    review_score: float
    review_feedback: str
    review_issues: list
    iteration_count: int

    # Token 累计
    total_usage: dict

    # 控制
    node_trace: list
    current_node: str
    is_complete: bool
    error: str

    # 合并评审元数据（写入 DB agent_state）
    dedupe_report: dict
    review_rubric: dict
    review_dimension_scores: dict


def _coerce_merged_from_review(review_data: dict, fallback: dict) -> dict:
    """优先使用评审返回的 merged_result，否则保留分模块合并前的结构。"""
    mr = review_data.get("merged_result") if isinstance(review_data, dict) else None
    if isinstance(mr, dict) and isinstance(mr.get("modules"), list):
        if not mr.get("title"):
            mr["title"] = (fallback or {}).get("title", "测试用例")
        return mr
    return fallback


def _accumulate_usage(state: dict, usage: dict) -> dict:
    prev = state.get('total_usage') or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return {
        "prompt_tokens": prev["prompt_tokens"] + usage.get("prompt_tokens", 0),
        "completion_tokens": prev["completion_tokens"] + usage.get("completion_tokens", 0),
        "total_tokens": prev["total_tokens"] + usage.get("total_tokens", 0),
    }


async def _run_validated_with_router(
    *,
    stage: str,
    messages: list,
    use_thinking: bool,
    max_retries: int = 2,
) -> dict:
    """
    统一：多模型路由 + 非流式 JSON 解析 + 重试。
    Returns:
      {"success": bool, "data": dict|None, "raw": str, "usage": dict, "error": str|None, "model": str, "cost_usd": float}
    """
    from pydantic import ValidationError
    from apps.ai_testcase.services.model_router import TestcaseModelRouter

    router = TestcaseModelRouter()
    model = router.select_model(stage)
    client = router.get_client(model, async_=True)

    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    conv = list(messages)
    last_raw = ""

    extra_body = (
        {"thinking": {"type": "enabled", "budget_tokens": 10000}}
        if use_thinking
        else {"thinking": {"type": "disabled"}}
    )

    for attempt in range(1 + max_retries):
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=conv,
                extra_body=extra_body,
                stream=False,
            )
            content = resp.choices[0].message.content or ""
            last_raw = content
            if resp.usage:
                usage = {
                    "prompt_tokens": resp.usage.prompt_tokens or 0,
                    "completion_tokens": resp.usage.completion_tokens or 0,
                    "total_tokens": resp.usage.total_tokens or 0,
                }
                total_usage["prompt_tokens"] += usage["prompt_tokens"]
                total_usage["completion_tokens"] += usage["completion_tokens"]
                total_usage["total_tokens"] += usage["total_tokens"]
            else:
                usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

            parsed = router.parse_json(content)
            if parsed is not None:
                return {
                    "success": True,
                    "data": parsed,
                    "raw": content,
                    "usage": total_usage,
                    "error": None,
                    "model": model,
                    "cost_usd": router.calculate_cost_usd(model, total_usage["prompt_tokens"], total_usage["completion_tokens"]),
                }

            if attempt < max_retries:
                conv.append({"role": "assistant", "content": content})
                conv.append({"role": "user", "content": "你的输出不是合法的 JSON，请重新输出，只返回纯 JSON，不要有任何 markdown 标记或额外文字。"})
                continue

            return {
                "success": False,
                "data": None,
                "raw": last_raw,
                "usage": total_usage,
                "error": "JSON 解析失败",
                "model": model,
                "cost_usd": router.calculate_cost_usd(model, total_usage["prompt_tokens"], total_usage["completion_tokens"]),
            }
        except Exception as e:
            return {
                "success": False,
                "data": None,
                "raw": last_raw,
                "usage": total_usage,
                "error": str(e),
                "model": model,
                "cost_usd": router.calculate_cost_usd(model, total_usage["prompt_tokens"], total_usage["completion_tokens"]),
            }

    return {
        "success": False,
        "data": None,
        "raw": last_raw,
        "usage": total_usage,
        "error": "超过最大重试次数",
        "model": model,
        "cost_usd": router.calculate_cost_usd(model, total_usage["prompt_tokens"], total_usage["completion_tokens"]),
    }


# ============ 节点 1：需求分析 ============

async def analyze_requirement_node(state: TestcaseAgentState) -> dict:
    from apps.ai_testcase.services.agent_prompts import build_analyze_messages
    from apps.ai_testcase.services.agent_result_normalize import normalize_requirement_analysis

    await emit_node_start('analyze_requirement')

    messages = build_analyze_messages(
        state['requirement'],
        state.get('extracted_texts'),
        state.get('images'),
        mode=state.get('mode') or 'comprehensive',
    )

    start = time.time()
    try:
        result = await asyncio.wait_for(
            _run_validated_with_router(stage='analyze', messages=messages, use_thinking=state.get('use_thinking', False)),
            timeout=MODULE_TIMEOUT,
        )
    except asyncio.TimeoutError:
        return {'error': '需求分析超时', 'current_node': 'error'}

    elapsed = int((time.time() - start) * 1000)
    logger.info(f"[Agent] analyze_requirement 完成, 耗时 {elapsed}ms")

    if not result['success']:
        return {'error': f"需求分析失败: {result['error']}", 'current_node': 'error'}

    analysis = normalize_requirement_analysis(result['data'] or {})

    return {
        'requirement_analysis': analysis,
        'current_node': 'plan_test_strategy',
        'quality_tier': state.get('quality_tier') or 'cheap',
        'force_strong_generate': bool(state.get('force_strong_generate') or False),
        'node_trace': (state.get('node_trace') or []) + [{
            'node': 'analyze_requirement',
            'elapsed_ms': elapsed,
            'usage': result.get('usage', {}),
            'model': result.get('model'),
            'cost_usd': result.get('cost_usd'),
        }],
        'total_usage': _accumulate_usage(state, result['usage']),
    }


# ============ 节点 2：策略规划 ============

async def plan_test_strategy_node(state: TestcaseAgentState) -> dict:
    from apps.ai_testcase.services.agent_prompts import build_plan_strategy_messages

    await emit_node_start('plan_test_strategy')

    messages = build_plan_strategy_messages(
        state['requirement_analysis'],
        mode=state.get('mode') or 'comprehensive',
    )

    start = time.time()
    try:
        result = await asyncio.wait_for(
            _run_validated_with_router(stage='plan', messages=messages, use_thinking=False),
            timeout=MODULE_TIMEOUT,
        )
    except asyncio.TimeoutError:
        return {'error': '策略规划超时', 'current_node': 'error'}

    elapsed = int((time.time() - start) * 1000)
    logger.info(f"[Agent] plan_test_strategy 完成, 耗时 {elapsed}ms")

    if not result['success']:
        return {'error': f"策略规划失败: {result['error']}", 'current_node': 'error'}

    return {
        'test_strategy': result['data'],
        'current_node': 'generate_by_module',
        'current_module_index': 0,
        'modules_generated': [],
        'generation_errors': [],
        'node_trace': (state.get('node_trace') or []) + [{
            'node': 'plan_test_strategy',
            'elapsed_ms': elapsed,
            'usage': result.get('usage', {}),
            'model': result.get('model'),
            'cost_usd': result.get('cost_usd'),
        }],
        'total_usage': _accumulate_usage(state, result['usage']),
    }


# ============ 节点 3：分模块生成 ============

async def generate_by_module_node(state: TestcaseAgentState) -> dict:
    from apps.ai_testcase.services.agent_prompts import build_generate_module_messages

    analysis = state['requirement_analysis']
    strategy_data = state['test_strategy']
    modules = analysis.get('modules', [])
    idx = state.get('current_module_index', 0)

    if idx >= len(modules):
        return {'current_node': 'merge_and_review'}

    module_info = modules[idx]
    module_name = module_info['name']

    await emit_node_start(f'generate_module:{module_name}')

    strategy_list = strategy_data.get('strategies', [])
    module_strategy = next((s for s in strategy_list if s.get('module_name') == module_name), {})

    use_thinking = bool(state.get('use_thinking', False))
    # 质量闭环：第二轮仍低分则强制提升生成强度（可配合更强模型/更深思考）
    if bool(state.get('force_strong_generate') or False):
        use_thinking = True
    messages = build_generate_module_messages(
        module_info=module_info,
        strategy=module_strategy,
        requirement=state['requirement'],
        global_rules=analysis.get('global_rules'),
        implied_rules=analysis.get('implied_rules'),
        extracted_texts=state.get('extracted_texts'),
        images=state.get('images'),
        mode=state.get('mode') or 'comprehensive',
    )

    start = time.time()
    try:
        result = await asyncio.wait_for(
            _run_validated_with_router(stage='generate', messages=messages, use_thinking=use_thinking),
            timeout=MODULE_TIMEOUT,
        )
    except asyncio.TimeoutError:
        elapsed = int((time.time() - start) * 1000)
        errors = list(state.get('generation_errors') or [])
        errors.append({'module': module_name, 'error': '生成超时'})
        return {
            'current_module_index': idx + 1,
            'module_total': len(modules),
            'generation_errors': errors,
            'node_trace': (state.get('node_trace') or []) + [{'node': f'generate_module:{module_name}', 'elapsed_ms': elapsed, 'status': 'timeout'}],
            'total_usage': state.get('total_usage') or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    elapsed = int((time.time() - start) * 1000)
    logger.info(f"[Agent] generate_module({module_name}) 完成, 耗时 {elapsed}ms, success={result['success']}")

    generated = list(state.get('modules_generated') or [])
    errors = list(state.get('generation_errors') or [])

    if result['success'] and result['data']:
        module_data = result['data']
        module_data['name'] = module_name
        generated.append(module_data)
    else:
        errors.append({'module': module_name, 'error': result.get('error', '未知错误')})

    return {
        'modules_generated': generated,
        'current_module_index': idx + 1,
        'module_total': len(modules),
        'generation_errors': errors,
        'node_trace': (state.get('node_trace') or []) + [{
            'node': f'generate_module:{module_name}',
            'elapsed_ms': elapsed,
            'status': 'ok' if result['success'] else 'error',
            'usage': result.get('usage', {}),
                'model': result.get('model'),
                'cost_usd': result.get('cost_usd'),
        }],
        'total_usage': _accumulate_usage(state, result['usage']),
    }


# ============ 节点 4：合并 + 评审 ============

async def merge_and_review_node(state: TestcaseAgentState) -> dict:
    from apps.ai_testcase.services.agent_prompts import build_review_messages

    await emit_node_start('merge_and_review')

    modules = state.get('modules_generated', [])
    title = state.get('requirement_analysis', {}).get('title', '测试用例')

    merged = state.get('merged_result')
    if merged is None:
        merged = {"title": f"{title}_测试用例", "modules": modules}

    messages = build_review_messages(merged, state['requirement'], mode=state.get('mode') or 'comprehensive')

    start = time.time()
    try:
        result = await asyncio.wait_for(
            _run_validated_with_router(stage='review', messages=messages, use_thinking=True),
            timeout=REVIEW_TIMEOUT,
        )
    except asyncio.TimeoutError:
        return {
            'merged_result': merged,
            'review_score': 0.75,
            'review_feedback': '评审超时，使用当前结果',
            'review_issues': [],
            'dedupe_report': None,
            'review_rubric': None,
            'review_dimension_scores': None,
            'current_node': 'finalize',
            'total_usage': state.get('total_usage') or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    elapsed = int((time.time() - start) * 1000)
    logger.info(f"[Agent] merge_and_review 完成, 耗时 {elapsed}ms")

    if not result['success']:
        return {
            'merged_result': merged,
            'review_score': 0.75,
            'review_feedback': f"评审调用失败: {result['error']}",
            'review_issues': [],
            'dedupe_report': None,
            'review_rubric': None,
            'review_dimension_scores': None,
            'current_node': 'finalize',
            'node_trace': (state.get('node_trace') or []) + [{'node': 'merge_and_review', 'elapsed_ms': elapsed, 'status': 'error'}],
            'total_usage': _accumulate_usage(state, result['usage']),
        }

    review_data = result['data'] or {}
    merged_out = _coerce_merged_from_review(review_data, merged)
    score = review_data.get('score', 0.8)
    issues = review_data.get('issues', [])
    summary = review_data.get('summary', '')
    dedupe_report = review_data.get('dedupe_report')
    review_rubric = review_data.get('rubric') or review_data.get('dimension_scores')
    review_dimension_scores = review_data.get('dimension_scores')
    iteration = (state.get('iteration_count') or 0) + 1

    # ============ Phase 4：轻量自适应模式 ============
    # 目标：当用户选择 focused，但评审显示明显不达标/重复严重时，
    # 将后续 refine 的“有效模式”升级为 comprehensive，以便补漏与去重更彻底。
    requested_mode = (state.get('mode') or 'comprehensive').strip().lower()
    effective_mode = (state.get('effective_mode') or requested_mode).strip().lower()
    switch_reason = state.get('mode_switch_reason')

    if requested_mode == 'focused' and effective_mode == 'focused':
        dedupe_removed = 0
        dup_ratio = 0.0
        if isinstance(dedupe_report, dict):
            # 兼容不同字段命名
            dedupe_removed = int(dedupe_report.get('removed', 0) or dedupe_report.get('duplicates_removed', 0) or 0)
            dup_ratio = float(dedupe_report.get('dup_ratio', 0.0) or dedupe_report.get('duplicate_ratio', 0.0) or 0.0)

        # 触发条件（可随业务再调）：低分 或 去重后仍显著重复
        should_upgrade = (score < 0.75) or (dup_ratio >= 0.2) or (dedupe_removed >= 10)
        if should_upgrade:
            effective_mode = 'comprehensive'
            switch_reason = f"auto_upgrade: requested=focused score={score:.2f} dup_ratio={dup_ratio:.2f} removed={dedupe_removed}"

    return {
        'merged_result': merged_out,
        'review_score': score,
        'review_feedback': summary,
        'review_issues': issues,
        'dedupe_report': dedupe_report,
        'review_rubric': review_rubric,
        'review_dimension_scores': review_dimension_scores,
        'iteration_count': iteration,
        'effective_mode': effective_mode,
        'mode_switch_reason': switch_reason,
        'review_model': result.get('model'),
        'review_usage': result.get('usage', {}),
        'review_cost_usd': result.get('cost_usd'),
        'node_trace': (state.get('node_trace') or []) + [{
            'node': 'merge_and_review',
            'elapsed_ms': elapsed,
            'score': score,
            'iteration': iteration,
            'usage': result.get('usage', {}),
            'model': result.get('model'),
            'cost_usd': result.get('cost_usd'),
        }],
        'total_usage': _accumulate_usage(state, result['usage']),
    }


# ============ 节点 5：修订 ============

async def refine_cases_node(state: TestcaseAgentState) -> dict:
    from apps.ai_testcase.services.agent_prompts import build_refine_messages
    from apps.ai_testcase.views import _apply_review_changes

    merged = state['merged_result']
    issues = state.get('review_issues', [])

    if not issues:
        return {'current_node': 'finalize'}

    await emit_node_start('refine_cases')

    mode_for_refine = state.get('effective_mode') or state.get('mode') or 'comprehensive'
    messages = build_refine_messages(merged, issues, mode=mode_for_refine)
    # 质量闭环：第一轮低分时升级 refine（更强模型/开启思考）
    use_thinking = bool(state.get('quality_tier') == 'strong')

    start = time.time()
    try:
        result = await asyncio.wait_for(
            _run_validated_with_router(stage='refine', messages=messages, use_thinking=use_thinking),
            timeout=MODULE_TIMEOUT,
        )
    except asyncio.TimeoutError:
        return {
            'current_node': 'finalize',
            'total_usage': state.get('total_usage') or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    elapsed = int((time.time() - start) * 1000)
    logger.info(f"[Agent] refine_cases 完成, 耗时 {elapsed}ms")

    if not result['success']:
        return {
            'current_node': 'merge_and_review',
            'node_trace': (state.get('node_trace') or []) + [{'node': 'refine_cases', 'elapsed_ms': elapsed, 'status': 'error'}],
            'total_usage': _accumulate_usage(state, result['usage']),
        }

    change_data = result['data']
    changes = change_data.get('changes', []) if isinstance(change_data, dict) else (change_data if isinstance(change_data, list) else [])

    if changes:
        try:
            new_data, apply_summary = _apply_review_changes(merged, changes)
            logger.info(f"[Agent] refine_cases 应用变更: {apply_summary}")
            merged = new_data
        except Exception as e:
            logger.warning(f"[Agent] refine_cases 应用变更失败: {e}")

    return {
        'merged_result': merged,
        'current_node': 'merge_and_review',
        'node_trace': (state.get('node_trace') or []) + [{
            'node': 'refine_cases',
            'elapsed_ms': elapsed,
            'changes': len(changes),
            'usage': result.get('usage', {}),
            'model': result.get('model'),
            'cost_usd': result.get('cost_usd'),
        }],
        'total_usage': _accumulate_usage(state, result['usage']),
    }


# ============ 路由函数 ============

def route_after_generate(state: TestcaseAgentState) -> str:
    """生成节点后路由：还有模块未生成则继续，否则进入评审"""
    modules = state.get('requirement_analysis', {}).get('modules', [])
    idx = state.get('current_module_index', 0)
    if idx < len(modules):
        return 'generate_by_module'
    return 'merge_and_review'


def route_after_review(state: TestcaseAgentState) -> str:
    """评审后路由：达标或达到迭代上限则完成，否则修订"""
    score = state.get('review_score', 1.0)
    iteration = state.get('iteration_count', 0)

    if score >= REVIEW_THRESHOLD or iteration >= MAX_REVISIONS:
        return 'finalize'

    # 质量闭环策略升级：
    # - 第 1 轮低分：升级 refine（强模型/思考）
    # - 第 2 轮仍低：强制重新分模块生成（强模型/思考），再进入评审
    if iteration == 1:
        state['quality_tier'] = 'strong'
        return 'refine_cases'
    if iteration >= 2:
        state['force_strong_generate'] = True
        state['modules_generated'] = []
        state['generation_errors'] = []
        state['current_module_index'] = 0
        return 'generate_by_module'
    return 'refine_cases'


# ============ 终态节点 ============

async def finalize_node(state: TestcaseAgentState) -> dict:
    await emit_node_start('finalize')
    return {
        'is_complete': True,
        'current_node': 'finalize',
        'node_trace': (state.get('node_trace') or []) + [{'node': 'finalize'}],
    }


# ============ 构建图 ============

def get_testcase_agent_workflow() -> StateGraph:
    workflow = StateGraph(TestcaseAgentState)

    workflow.add_node('analyze_requirement', analyze_requirement_node)
    workflow.add_node('plan_test_strategy', plan_test_strategy_node)
    workflow.add_node('generate_by_module', generate_by_module_node)
    workflow.add_node('merge_and_review', merge_and_review_node)
    workflow.add_node('refine_cases', refine_cases_node)
    workflow.add_node('finalize', finalize_node)

    workflow.set_entry_point('analyze_requirement')

    workflow.add_edge('analyze_requirement', 'plan_test_strategy')
    workflow.add_edge('plan_test_strategy', 'generate_by_module')

    workflow.add_conditional_edges(
        'generate_by_module',
        route_after_generate,
        {'generate_by_module': 'generate_by_module', 'merge_and_review': 'merge_and_review'},
    )

    workflow.add_conditional_edges(
        'merge_and_review',
        route_after_review,
        {'refine_cases': 'refine_cases', 'finalize': 'finalize'},
    )

    workflow.add_edge('refine_cases', 'merge_and_review')
    workflow.add_edge('finalize', END)

    return workflow.compile()
