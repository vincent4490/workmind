# -*- coding: utf-8 -*-
"""
多智能体协作工作流 —— Supervisor 模式

4 个角色 Agent（作为节点）：
- PM Agent：需求理解、PRD 撰写、用户故事
- Architect Agent：技术可行性、架构设计、风险
- TestAnalyst Agent：可测性分析、测试策略、功能点拆解
- Researcher Agent：竞品调研、技术资料

Supervisor 节点做路由决策，按 SOP 流程编排 + 动态调整。
"""
import asyncio
import json
import logging
import time
from typing import Optional

from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

logger = logging.getLogger(__name__)

LLM_TIMEOUT_SECONDS = 180
MAX_SUPERVISOR_ROUNDS = 8

# SOP 标准流程：研究 → PM → 架构师 → 测试分析师 → 人工 → 完成
SOP_SEQUENCE = ['research', 'pm', 'architect', 'test', 'human', 'done']


class MultiAgentState(TypedDict, total=False):
    input: str
    use_thinking: bool
    current_phase: str
    pm_output: Optional[dict]
    architect_output: Optional[dict]
    test_analyst_output: Optional[dict]
    research_output: Optional[dict]
    supervisor_decision: str
    supervisor_reasoning: str
    human_checkpoints: list
    human_approval: Optional[bool]
    approval_comment: Optional[str]
    iteration_count: int
    node_trace: list
    error: Optional[str]
    is_complete: bool
    final_output: Optional[dict]


async def researcher_node(state: MultiAgentState) -> dict:
    """竞品调研 Agent"""
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
            'research_output': data,
            'node_trace': state.get('node_trace', []) + [{
                'agent': 'researcher', 'status': 'success',
                'elapsed_ms': elapsed_ms,
                'tokens': result.get('usage', {}).get('total_tokens', 0),
            }],
        }
    except asyncio.TimeoutError:
        return {
            'research_output': {'error': 'timeout'},
            'node_trace': state.get('node_trace', []) + [{'agent': 'researcher', 'status': 'timeout'}],
        }
    except Exception as e:
        logger.exception(f'[MultiAgent] Researcher 异常: {e}')
        return {
            'research_output': {'error': str(e)},
            'node_trace': state.get('node_trace', []) + [{'agent': 'researcher', 'status': 'error', 'msg': str(e)}],
        }


async def pm_agent_node(state: MultiAgentState) -> dict:
    """产品经理 Agent —— PRD 撰写"""
    from apps.ai_requirement.services.agent_router import RequirementAgentRouter

    router = RequirementAgentRouter()
    start = time.time()

    context_parts = [state['input']]
    if state.get('research_output') and not state['research_output'].get('error'):
        context_parts.append(
            '\n\n--- 竞品调研结果 ---\n'
            + json.dumps(state['research_output'], ensure_ascii=False, indent=2)[:4000]
        )
    if state.get('architect_output') and not state['architect_output'].get('error'):
        context_parts.append(
            '\n\n--- 架构师反馈 ---\n'
            + json.dumps(state['architect_output'], ensure_ascii=False, indent=2)[:3000]
        )

    try:
        result = await asyncio.wait_for(
            router.run_validated(
                role='product',
                task_type='prd_draft',
                requirement_input='\n'.join(context_parts),
                use_thinking=state.get('use_thinking', False),
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )
        elapsed_ms = int((time.time() - start) * 1000)
        data = result.get('data') if result.get('validated') else {'raw': result.get('raw', '')}
        return {
            'pm_output': data,
            'node_trace': state.get('node_trace', []) + [{
                'agent': 'pm', 'status': 'success',
                'elapsed_ms': elapsed_ms,
                'tokens': result.get('usage', {}).get('total_tokens', 0),
            }],
        }
    except asyncio.TimeoutError:
        return {
            'pm_output': {'error': 'timeout'},
            'node_trace': state.get('node_trace', []) + [{'agent': 'pm', 'status': 'timeout'}],
        }
    except Exception as e:
        logger.exception(f'[MultiAgent] PM Agent 异常: {e}')
        return {
            'pm_output': {'error': str(e)},
            'node_trace': state.get('node_trace', []) + [{'agent': 'pm', 'status': 'error', 'msg': str(e)}],
        }


async def architect_agent_node(state: MultiAgentState) -> dict:
    """架构师 Agent —— 技术可行性评估"""
    from apps.ai_requirement.services.agent_router import RequirementAgentRouter

    router = RequirementAgentRouter()
    start = time.time()

    context_parts = [state['input']]
    if state.get('pm_output') and not state['pm_output'].get('error'):
        context_parts.append(
            '\n\n--- PRD 内容（请评估技术可行性） ---\n'
            + json.dumps(state['pm_output'], ensure_ascii=False, indent=2)[:5000]
        )

    try:
        result = await asyncio.wait_for(
            router.run_validated(
                role='dev',
                task_type='tech_design',
                requirement_input='\n'.join(context_parts),
                use_thinking=state.get('use_thinking', False),
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )
        elapsed_ms = int((time.time() - start) * 1000)
        data = result.get('data') if result.get('validated') else {'raw': result.get('raw', '')}
        return {
            'architect_output': data,
            'node_trace': state.get('node_trace', []) + [{
                'agent': 'architect', 'status': 'success',
                'elapsed_ms': elapsed_ms,
                'tokens': result.get('usage', {}).get('total_tokens', 0),
            }],
        }
    except asyncio.TimeoutError:
        return {
            'architect_output': {'error': 'timeout'},
            'node_trace': state.get('node_trace', []) + [{'agent': 'architect', 'status': 'timeout'}],
        }
    except Exception as e:
        logger.exception(f'[MultiAgent] Architect Agent 异常: {e}')
        return {
            'architect_output': {'error': str(e)},
            'node_trace': state.get('node_trace', []) + [{'agent': 'architect', 'status': 'error', 'msg': str(e)}],
        }


async def test_analyst_node(state: MultiAgentState) -> dict:
    """测试分析师 Agent —— 可测性分析 + 功能点拆解"""
    from apps.ai_requirement.services.agent_router import RequirementAgentRouter

    router = RequirementAgentRouter()
    start = time.time()

    context_parts = [state['input']]
    if state.get('pm_output') and not state['pm_output'].get('error'):
        context_parts.append(
            '\n\n--- PRD 内容 ---\n'
            + json.dumps(state['pm_output'], ensure_ascii=False, indent=2)[:5000]
        )

    try:
        result = await asyncio.wait_for(
            router.run_validated(
                role='test',
                task_type='test_requirement_analysis',
                requirement_input='\n'.join(context_parts),
                use_thinking=state.get('use_thinking', False),
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )
        elapsed_ms = int((time.time() - start) * 1000)
        data = result.get('data') if result.get('validated') else {'raw': result.get('raw', '')}
        return {
            'test_analyst_output': data,
            'node_trace': state.get('node_trace', []) + [{
                'agent': 'test_analyst', 'status': 'success',
                'elapsed_ms': elapsed_ms,
                'tokens': result.get('usage', {}).get('total_tokens', 0),
            }],
        }
    except asyncio.TimeoutError:
        return {
            'test_analyst_output': {'error': 'timeout'},
            'node_trace': state.get('node_trace', []) + [{'agent': 'test_analyst', 'status': 'timeout'}],
        }
    except Exception as e:
        logger.exception(f'[MultiAgent] TestAnalyst 异常: {e}')
        return {
            'test_analyst_output': {'error': str(e)},
            'node_trace': state.get('node_trace', []) + [{'agent': 'test_analyst', 'status': 'error', 'msg': str(e)}],
        }


async def supervisor_node(state: MultiAgentState) -> dict:
    """
    Supervisor 决策节点 —— 基于 SOP 规则路由

    标准流程: research → pm → architect → test → human → done
    动态调整: 如架构师发现重大风险，可回给 PM 修订
    """
    iteration = state.get('iteration_count', 0) + 1

    if iteration > MAX_SUPERVISOR_ROUNDS:
        return {
            'supervisor_decision': 'done',
            'supervisor_reasoning': f'达到最大轮次 {MAX_SUPERVISOR_ROUNDS}，强制结束',
            'iteration_count': iteration,
            'node_trace': state.get('node_trace', []) + [{
                'agent': 'supervisor', 'decision': 'done', 'reason': 'max_rounds',
            }],
        }

    has_research = state.get('research_output') is not None
    has_pm = state.get('pm_output') is not None
    has_architect = state.get('architect_output') is not None
    has_test = state.get('test_analyst_output') is not None

    # 检查架构师是否发现重大风险需 PM 修订
    if has_architect and has_pm:
        arch = state.get('architect_output', {})
        risks = arch.get('risks', [])
        high_risks = [r for r in (risks or []) if isinstance(r, dict) and r.get('level') in ('high', 'critical')]
        if high_risks and iteration <= 3:
            return {
                'supervisor_decision': 'pm',
                'supervisor_reasoning': f'架构师发现 {len(high_risks)} 个高风险项，回给 PM 修订',
                'iteration_count': iteration,
                'node_trace': state.get('node_trace', []) + [{
                    'agent': 'supervisor', 'decision': 'pm', 'reason': 'high_risk_revision',
                }],
            }

    # SOP 标准流程路由
    if not has_research:
        decision = 'research'
        reasoning = '启动竞品调研'
    elif not has_pm:
        decision = 'pm'
        reasoning = '基于调研结果撰写 PRD'
    elif not has_architect:
        decision = 'architect'
        reasoning = '评估 PRD 技术可行性'
    elif not has_test:
        decision = 'test'
        reasoning = '分析 PRD 可测性并拆解功能点'
    elif state.get('human_approval') is None:
        decision = 'human'
        reasoning = '所有 Agent 分析完毕，提交人工审核'
    else:
        decision = 'done'
        reasoning = '人工已审批，流程结束'

    return {
        'supervisor_decision': decision,
        'supervisor_reasoning': reasoning,
        'iteration_count': iteration,
        'node_trace': state.get('node_trace', []) + [{
            'agent': 'supervisor', 'decision': decision, 'reason': reasoning,
        }],
    }


def route_supervisor(state: MultiAgentState) -> str:
    """根据 Supervisor 决策路由到对应 Agent"""
    decision = state.get('supervisor_decision', 'done')
    if decision == 'done':
        return 'finalize'
    return decision


async def human_review_node(state: MultiAgentState) -> dict:
    """人工审核节点 —— 暂停工作流"""
    return {
        'current_phase': 'waiting_approval',
        'node_trace': state.get('node_trace', []) + [{
            'agent': 'human_review', 'status': 'waiting',
        }],
    }


def route_after_human(state: MultiAgentState) -> str:
    """人工审核后路由"""
    if state.get('human_approval') is True:
        return 'supervisor'
    return 'supervisor'


async def finalize_node(state: MultiAgentState) -> dict:
    """终态节点 —— 汇总所有 Agent 输出"""
    final = {
        'research': state.get('research_output'),
        'prd': state.get('pm_output'),
        'tech_design': state.get('architect_output'),
        'test_analysis': state.get('test_analyst_output'),
        'approved': state.get('human_approval'),
        'approval_comment': state.get('approval_comment', ''),
    }
    return {
        'final_output': final,
        'is_complete': True,
        'current_phase': 'completed',
        'node_trace': state.get('node_trace', []) + [{
            'agent': 'finalize', 'status': 'completed',
        }],
    }


def build_multi_agent_workflow(checkpointer):
    """
    构建多智能体协作工作流（Supervisor 模式），使用传入的持久化 checkpointer。

    Returns:
        compiled graph with MemorySaver
    """
    graph = StateGraph(MultiAgentState)

    graph.add_node('supervisor', supervisor_node)
    graph.add_node('research', researcher_node)
    graph.add_node('pm', pm_agent_node)
    graph.add_node('architect', architect_agent_node)
    graph.add_node('test', test_analyst_node)
    graph.add_node('human', human_review_node)
    graph.add_node('finalize', finalize_node)

    graph.set_entry_point('supervisor')

    graph.add_conditional_edges(
        'supervisor',
        route_supervisor,
        {
            'research': 'research',
            'pm': 'pm',
            'architect': 'architect',
            'test': 'test',
            'human': 'human',
            'finalize': 'finalize',
        },
    )

    for agent_node in ['research', 'pm', 'architect', 'test']:
        graph.add_edge(agent_node, 'supervisor')

    graph.add_conditional_edges(
        'human',
        route_after_human,
        {'supervisor': 'supervisor'},
    )

    graph.add_edge('finalize', END)

    return graph.compile(checkpointer=checkpointer)


_multi_agent_graph = None


async def get_multi_agent_workflow():
    """返回多智能体工作流图（使用持久化 SQLite checkpointer，重启可恢复）"""
    global _multi_agent_graph
    if _multi_agent_graph is None:
        from .checkpoint import get_async_checkpointer
        cp = await get_async_checkpointer()
        _multi_agent_graph = build_multi_agent_workflow(cp)
    return _multi_agent_graph
