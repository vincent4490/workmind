# -*- coding: utf-8 -*-
"""
PRD 深度撰写工作流 —— 基于 LangGraph StateGraph

流程：研究(竞品分析) → 撰写(PRD) → AI评审 → [通过→人工审批 / 未通过→修订] → 完成
迭代上限保护：最多 MAX_REVISIONS 轮自动修订，超限强制人工介入。
"""
import asyncio
import logging
import time
from typing import Optional

from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

logger = logging.getLogger(__name__)

MAX_REVISIONS = 3
LLM_TIMEOUT_SECONDS = 180


class PRDWorkflowState(TypedDict, total=False):
    input: str
    role: str
    use_thinking: bool
    competitive_analysis: Optional[dict]
    prd_draft: Optional[dict]
    review_feedback: Optional[str]
    review_score: Optional[float]
    final_prd: Optional[dict]
    iteration_count: int
    human_approval: Optional[bool]
    approval_comment: Optional[str]
    error: Optional[str]
    node_trace: list
    current_node: str
    is_complete: bool


async def competitive_analysis_node(state: PRDWorkflowState) -> dict:
    """竞品分析节点"""
    from apps.ai_requirement.services.agent_router import RequirementAgentRouter

    router = RequirementAgentRouter()
    start = time.time()
    try:
        result = await asyncio.wait_for(
            router.run_validated(
                role='product',
                task_type='competitive_analysis',
                requirement_input=state['input'],
                use_thinking=state.get('use_thinking', False),
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )
        elapsed_ms = int((time.time() - start) * 1000)
        data = result.get('data') if result.get('validated') else {'raw': result.get('raw', '')}
        return {
            'competitive_analysis': data,
            'current_node': 'draft',
            'node_trace': state.get('node_trace', []) + [{
                'node': 'research', 'status': 'success',
                'elapsed_ms': elapsed_ms,
                'tokens': result.get('usage', {}).get('total_tokens', 0),
            }],
        }
    except asyncio.TimeoutError:
        return {
            'error': f'竞品分析超时（>{LLM_TIMEOUT_SECONDS}s）',
            'current_node': 'error',
            'is_complete': True,
            'node_trace': state.get('node_trace', []) + [{'node': 'research', 'status': 'timeout'}],
        }
    except Exception as e:
        logger.exception(f'[Workflow] 竞品分析节点异常: {e}')
        return {
            'error': str(e),
            'current_node': 'error',
            'is_complete': True,
            'node_trace': state.get('node_trace', []) + [{'node': 'research', 'status': 'error', 'msg': str(e)}],
        }


async def prd_draft_node(state: PRDWorkflowState) -> dict:
    """PRD 撰写节点（带竞品分析上下文 + 超时保护）"""
    from apps.ai_requirement.services.agent_router import RequirementAgentRouter

    router = RequirementAgentRouter()
    start = time.time()

    context_parts = [state['input']]
    if state.get('competitive_analysis'):
        import json
        context_parts.append(
            '\n\n--- 竞品分析参考 ---\n'
            + json.dumps(state['competitive_analysis'], ensure_ascii=False, indent=2)[:4000]
        )
    if state.get('review_feedback'):
        context_parts.append(
            f'\n\n--- 评审反馈（请据此修订） ---\n{state["review_feedback"]}'
        )

    requirement_input = '\n'.join(context_parts)

    try:
        result = await asyncio.wait_for(
            router.run_validated(
                role='product',
                task_type='prd_draft',
                requirement_input=requirement_input,
                use_thinking=state.get('use_thinking', False),
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )
        elapsed_ms = int((time.time() - start) * 1000)
        data = result.get('data') if result.get('validated') else {'raw': result.get('raw', '')}
        return {
            'prd_draft': data,
            'iteration_count': state.get('iteration_count', 0) + 1,
            'current_node': 'review',
            'node_trace': state.get('node_trace', []) + [{
                'node': 'draft', 'status': 'success',
                'iteration': state.get('iteration_count', 0) + 1,
                'elapsed_ms': elapsed_ms,
                'tokens': result.get('usage', {}).get('total_tokens', 0),
            }],
        }
    except asyncio.TimeoutError:
        return {
            'error': f'PRD 生成超时（>{LLM_TIMEOUT_SECONDS}s），请简化输入后重试',
            'current_node': 'error',
            'is_complete': True,
            'node_trace': state.get('node_trace', []) + [{'node': 'draft', 'status': 'timeout'}],
        }
    except Exception as e:
        logger.exception(f'[Workflow] PRD 撰写节点异常: {e}')
        return {
            'error': str(e),
            'current_node': 'error',
            'is_complete': True,
            'node_trace': state.get('node_trace', []) + [{'node': 'draft', 'status': 'error', 'msg': str(e)}],
        }


async def review_agent_node(state: PRDWorkflowState) -> dict:
    """AI 评审节点 —— 用 prd_refine prompt 对 PRD 做自我评审"""
    from apps.ai_requirement.services.agent_router import RequirementAgentRouter
    import json

    router = RequirementAgentRouter()
    start = time.time()

    prd_text = json.dumps(state.get('prd_draft', {}), ensure_ascii=False, indent=2)[:6000]
    review_input = (
        f'请评审以下 PRD，给出评审意见和分数（0-1）。'
        f'如果分数 >= 0.8 则认为通过，否则给出具体修改建议。\n\n'
        f'--- PRD 内容 ---\n{prd_text}'
    )

    try:
        result = await asyncio.wait_for(
            router.run_validated(
                role='product',
                task_type='prd_refine',
                requirement_input=review_input,
                use_thinking=state.get('use_thinking', False),
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )
        elapsed_ms = int((time.time() - start) * 1000)
        data = result.get('data', {})

        review_score = 0.0
        feedback_text = None

        if isinstance(data, dict):
            review_score = data.get('confidence_score', 0.5)
            change_summary = data.get('change_summary', '')
            changes = data.get('changes', [])
            if review_score < 0.8 and (change_summary or changes):
                parts = []
                if change_summary:
                    parts.append(change_summary)
                for c in changes[:5]:
                    if isinstance(c, dict):
                        parts.append(f"- {c.get('description', c.get('field', str(c)))}")
                feedback_text = '\n'.join(parts)

        return {
            'review_score': review_score,
            'review_feedback': feedback_text,
            'current_node': 'review_done',
            'node_trace': state.get('node_trace', []) + [{
                'node': 'review', 'status': 'success',
                'review_score': review_score,
                'elapsed_ms': elapsed_ms,
                'tokens': result.get('usage', {}).get('total_tokens', 0),
            }],
        }
    except Exception as e:
        logger.warning(f'[Workflow] 评审节点异常，默认通过: {e}')
        return {
            'review_score': 0.85,
            'review_feedback': None,
            'current_node': 'review_done',
            'node_trace': state.get('node_trace', []) + [{
                'node': 'review', 'status': 'fallback_pass', 'msg': str(e),
            }],
        }


def route_after_review(state: PRDWorkflowState) -> str:
    """路由：通过 / 修订 / 超限强制人工"""
    if state.get('error'):
        return END

    iteration = state.get('iteration_count', 0)
    score = state.get('review_score', 0)
    feedback = state.get('review_feedback')

    if iteration >= MAX_REVISIONS:
        return 'force_human_review'
    if score >= 0.8 or feedback is None:
        return 'human_approval'
    return 'revise'


async def revision_node(state: PRDWorkflowState) -> dict:
    """修订节点 —— 将评审反馈注入后重新调用 prd_draft"""
    return {
        'current_node': 'draft',
        'node_trace': state.get('node_trace', []) + [{
            'node': 'revise', 'status': 'redirecting',
            'iteration': state.get('iteration_count', 0),
        }],
    }


async def human_approval_node(state: PRDWorkflowState) -> dict:
    """
    人工审批节点 —— 工作流在此暂停，等待前端调用 approve API。
    LangGraph 的 interrupt 机制：该节点返回后工作流暂停，
    直到外部注入 human_approval 字段后 resume。
    """
    return {
        'current_node': 'waiting_approval',
        'final_prd': state.get('prd_draft'),
        'node_trace': state.get('node_trace', []) + [{
            'node': 'human_approval', 'status': 'waiting',
        }],
    }


def route_after_approval(state: PRDWorkflowState) -> str:
    """人工审批后路由"""
    if state.get('human_approval') is True:
        return 'finalize'
    return 'revise'


async def finalize_node(state: PRDWorkflowState) -> dict:
    """终态节点"""
    return {
        'final_prd': state.get('prd_draft'),
        'is_complete': True,
        'current_node': 'completed',
        'node_trace': state.get('node_trace', []) + [{
            'node': 'finalize', 'status': 'completed',
        }],
    }


async def force_review_node(state: PRDWorkflowState) -> dict:
    """超过迭代上限，强制人工审核"""
    return {
        'final_prd': state.get('prd_draft'),
        'current_node': 'waiting_approval',
        'error': f'已自动修订 {state.get("iteration_count", 0)} 轮仍未完全通过评审，请人工审核',
        'node_trace': state.get('node_trace', []) + [{
            'node': 'force_review', 'status': 'escalated',
            'iteration': state.get('iteration_count', 0),
        }],
    }


def build_prd_workflow(checkpointer):
    """
    构建 PRD 深度撰写工作流（StateGraph），使用传入的持久化 checkpointer。

    Returns:
        compiled graph（支持进程重启后按 thread_id 恢复）
    """
    workflow = StateGraph(PRDWorkflowState)

    workflow.add_node('research', competitive_analysis_node)
    workflow.add_node('draft', prd_draft_node)
    workflow.add_node('review', review_agent_node)
    workflow.add_node('revise', revision_node)
    workflow.add_node('human_approval', human_approval_node)
    workflow.add_node('force_human_review', force_review_node)
    workflow.add_node('finalize', finalize_node)

    workflow.set_entry_point('research')
    workflow.add_edge('research', 'draft')
    workflow.add_edge('draft', 'review')

    workflow.add_conditional_edges(
        'review',
        route_after_review,
        {
            'human_approval': 'human_approval',
            'revise': 'revise',
            'force_human_review': 'force_human_review',
            END: END,
        },
    )

    workflow.add_edge('revise', 'draft')
    workflow.add_edge('force_human_review', 'human_approval')

    workflow.add_conditional_edges(
        'human_approval',
        route_after_approval,
        {
            'finalize': 'finalize',
            'revise': 'revise',
        },
    )

    workflow.add_edge('finalize', END)

    return workflow.compile(checkpointer=checkpointer)


# 单例 workflow graph（编译一次复用）
_prd_workflow_graph = None


async def get_prd_workflow():
    """返回 PRD 工作流图（使用持久化 SQLite checkpointer，重启可恢复）"""
    global _prd_workflow_graph
    if _prd_workflow_graph is None:
        from .checkpoint import get_async_checkpointer
        cp = await get_async_checkpointer()
        _prd_workflow_graph = build_prd_workflow(cp)
    return _prd_workflow_graph
