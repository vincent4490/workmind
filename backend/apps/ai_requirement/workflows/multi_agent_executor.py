# -*- coding: utf-8 -*-
"""
多智能体协作工作流执行器

与 executor.py（单工作流 PRD 深度模式）类似，
但驱动的是 Supervisor 路由的多 Agent 工作流。
"""
import json
import logging
import uuid

from asgiref.sync import sync_to_async

from apps.ai_requirement.models import WorkflowRun
from .multi_agent import get_multi_agent_workflow, MultiAgentState

logger = logging.getLogger(__name__)

AGENT_LABELS = {
    'supervisor': '协调中心',
    'research': '竞品调研',
    'pm': '产品经理',
    'architect': '架构师',
    'test': '测试分析师',
    'human': '人工审核',
    'finalize': '汇总完成',
}

PAUSE_PHASES = {'waiting_approval'}


class MultiAgentExecutor:
    """多智能体工作流生命周期管理"""

    @staticmethod
    async def start_workflow(requirement_input: str, use_thinking: bool = False) -> WorkflowRun:
        thread_id = f'ma-{uuid.uuid4()}'

        run = await sync_to_async(WorkflowRun.objects.create)(
            workflow_type='multi_agent',
            status='running',
            thread_id=thread_id,
            requirement_input=requirement_input,
            use_thinking=use_thinking,
            current_node='supervisor',
        )
        return run

    @staticmethod
    async def execute_workflow(run: WorkflowRun):
        """
        执行多智能体工作流直到暂停或完成。

        Yields:
            dict: SSE 事件
        """
        graph = await get_multi_agent_workflow()
        config = {'configurable': {'thread_id': run.thread_id}}

        initial_state: MultiAgentState = {
            'input': run.requirement_input,
            'use_thinking': run.use_thinking,
            'current_phase': 'starting',
            'pm_output': None,
            'architect_output': None,
            'test_analyst_output': None,
            'research_output': None,
            'supervisor_decision': '',
            'supervisor_reasoning': '',
            'human_checkpoints': [],
            'human_approval': None,
            'approval_comment': None,
            'iteration_count': 0,
            'node_trace': [],
            'error': None,
            'is_complete': False,
            'final_output': None,
        }

        yield {
            'type': 'workflow_start',
            'workflow_id': run.id,
            'workflow_type': 'multi_agent',
            'agents': list(AGENT_LABELS.keys()),
            'agent_labels': AGENT_LABELS,
        }

        try:
            async for event in graph.astream(initial_state, config, stream_mode='updates'):
                for node_name, node_output in event.items():
                    if not isinstance(node_output, dict):
                        continue

                    agent_label = AGENT_LABELS.get(node_name, node_name)

                    yield {
                        'type': 'agent_done',
                        'agent': node_name,
                        'agent_label': agent_label,
                        'supervisor_decision': node_output.get('supervisor_decision'),
                        'supervisor_reasoning': node_output.get('supervisor_reasoning'),
                        'iteration_count': node_output.get('iteration_count'),
                        'current_phase': node_output.get('current_phase'),
                    }

                    await _sync_multi_agent_state(run, node_name, node_output)

                    if node_output.get('current_phase') in PAUSE_PHASES:
                        await _update_run_status(run, 'waiting_approval')
                        yield {
                            'type': 'workflow_pause',
                            'workflow_id': run.id,
                            'message': '多智能体分析完毕，等待人工审核',
                            'agents_completed': _agents_completed(run),
                        }
                        return

                    if node_output.get('is_complete'):
                        final_status = 'failed' if node_output.get('error') else 'completed'
                        await _update_run_status(run, final_status)
                        yield {
                            'type': 'workflow_done',
                            'workflow_id': run.id,
                            'status': final_status,
                            'final_output': node_output.get('final_output'),
                            'node_trace': run.node_trace,
                            'total_tokens': _sum_tokens(run.node_trace),
                        }
                        return

            await _update_run_status(run, 'completed')
            yield {
                'type': 'workflow_done',
                'workflow_id': run.id,
                'status': 'completed',
                'final_output': run.final_prd,
                'node_trace': run.node_trace,
            }

        except Exception as e:
            logger.exception(f'[MultiAgentExecutor] 执行异常: {e}')
            await _update_run_status(run, 'failed', str(e))
            yield {'type': 'error', 'workflow_id': run.id, 'error': str(e)}

    @staticmethod
    async def resume_after_approval(run: WorkflowRun, approved: bool, comment: str = ''):
        """人工审核后恢复多智能体工作流"""
        if run.status != 'waiting_approval':
            yield {
                'type': 'error',
                'error': f'当前状态 {run.status}，需要 waiting_approval',
            }
            return

        graph = await get_multi_agent_workflow()
        config = {'configurable': {'thread_id': run.thread_id}}

        run.human_approval = approved
        run.approval_comment = comment
        await sync_to_async(run.save)(update_fields=['human_approval', 'approval_comment', 'updated_at'])
        await _update_run_status(run, 'running')

        resume_state = {
            'human_approval': approved,
            'approval_comment': comment,
        }

        yield {'type': 'approval_received', 'approved': approved, 'comment': comment}

        try:
            async for event in graph.astream(resume_state, config, stream_mode='updates'):
                for node_name, node_output in event.items():
                    if not isinstance(node_output, dict):
                        continue

                    yield {
                        'type': 'agent_done',
                        'agent': node_name,
                        'agent_label': AGENT_LABELS.get(node_name, node_name),
                        'supervisor_decision': node_output.get('supervisor_decision'),
                        'supervisor_reasoning': node_output.get('supervisor_reasoning'),
                        'iteration_count': node_output.get('iteration_count'),
                    }

                    await _sync_multi_agent_state(run, node_name, node_output)

                    if node_output.get('current_phase') in PAUSE_PHASES:
                        await _update_run_status(run, 'waiting_approval')
                        yield {
                            'type': 'workflow_pause',
                            'workflow_id': run.id,
                            'message': '再次等待人工审核',
                        }
                        return

                    if node_output.get('is_complete'):
                        final_status = 'failed' if node_output.get('error') else 'completed'
                        await _update_run_status(run, final_status)
                        yield {
                            'type': 'workflow_done',
                            'workflow_id': run.id,
                            'status': final_status,
                            'final_output': node_output.get('final_output'),
                            'node_trace': run.node_trace,
                        }
                        return

            await _update_run_status(run, 'completed')
            yield {
                'type': 'workflow_done',
                'workflow_id': run.id,
                'status': 'completed',
                'final_output': run.final_prd,
                'node_trace': run.node_trace,
            }

        except Exception as e:
            logger.exception(f'[MultiAgentExecutor] resume 异常: {e}')
            await _update_run_status(run, 'failed', str(e))
            yield {'type': 'error', 'workflow_id': run.id, 'error': str(e)}


async def _sync_multi_agent_state(run: WorkflowRun, node_name: str, output: dict):
    """将多智能体节点输出同步到 WorkflowRun（复用 JSON 字段）"""
    fields = ['updated_at']

    if 'node_trace' in output:
        run.node_trace = output['node_trace']
        fields.append('node_trace')

    if 'iteration_count' in output and output['iteration_count'] is not None:
        run.iteration_count = output['iteration_count']
        fields.append('iteration_count')

    if 'current_phase' in output:
        run.current_node = output['current_phase']
        fields.append('current_node')
    elif 'supervisor_decision' in output:
        run.current_node = output.get('supervisor_decision', node_name)
        fields.append('current_node')

    # 各 Agent 输出存入 prd_draft JSON 字段（合并）
    agent_data = run.prd_draft or {}
    if node_name == 'research' and 'research_output' in output:
        agent_data['research'] = output['research_output']
    elif node_name == 'pm' and 'pm_output' in output:
        agent_data['pm'] = output['pm_output']
    elif node_name == 'architect' and 'architect_output' in output:
        agent_data['architect'] = output['architect_output']
    elif node_name == 'test' and 'test_analyst_output' in output:
        agent_data['test_analyst'] = output['test_analyst_output']

    if agent_data != (run.prd_draft or {}):
        run.prd_draft = agent_data
        fields.append('prd_draft')

    if 'final_output' in output and output['final_output']:
        run.final_prd = output['final_output']
        fields.append('final_prd')

    if 'error' in output and output['error']:
        run.error_message = output['error']
        fields.append('error_message')

    if len(fields) > 1:
        await sync_to_async(run.save)(update_fields=fields)


async def _update_run_status(run: WorkflowRun, status: str, error: str = None):
    run.status = status
    fields = ['status', 'updated_at']
    if error:
        run.error_message = error
        fields.append('error_message')

    total = _sum_tokens(run.node_trace)
    if total > 0:
        run.total_tokens = total
        fields.append('total_tokens')

    await sync_to_async(run.save)(update_fields=fields)


def _sum_tokens(node_trace: list) -> int:
    return sum(n.get('tokens', 0) for n in (node_trace or []) if isinstance(n, dict))


def _agents_completed(run: WorkflowRun) -> list:
    """从 prd_draft 中判断哪些 Agent 已完成"""
    data = run.prd_draft or {}
    completed = []
    for key in ('research', 'pm', 'architect', 'test_analyst'):
        if key in data:
            completed.append(key)
    return completed
