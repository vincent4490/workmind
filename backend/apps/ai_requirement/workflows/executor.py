# -*- coding: utf-8 -*-
"""
工作流执行器 —— 连接 LangGraph 图与 Django 模型

职责：
- 启动工作流并驱动到下一个暂停点（人工审批 / 完成）
- 同步持久化每个节点的状态到 WorkflowRun 模型
- 提供 SSE 事件流用于前端步骤可视化
- 处理人工审批后的 resume
"""
import asyncio
import json
import logging
import uuid
from decimal import Decimal

from asgiref.sync import sync_to_async

from apps.ai_requirement.models import WorkflowRun
from .prd_workflow import get_prd_workflow, PRDWorkflowState

logger = logging.getLogger(__name__)

WORKFLOW_NODES_ORDER = ['research', 'draft', 'review', 'human_approval', 'finalize']

PAUSE_NODES = {'waiting_approval'}


class WorkflowExecutor:
    """工作流执行与生命周期管理"""

    @staticmethod
    async def start_workflow(requirement_input: str, use_thinking: bool = False) -> WorkflowRun:
        """创建并启动 PRD 深度工作流"""
        thread_id = str(uuid.uuid4())

        run = await sync_to_async(WorkflowRun.objects.create)(
            workflow_type='prd_deep',
            status='running',
            thread_id=thread_id,
            requirement_input=requirement_input,
            use_thinking=use_thinking,
            current_node='research',
        )

        return run

    @staticmethod
    async def execute_workflow(run: WorkflowRun):
        """
        执行工作流直到暂停点或完成。

        Yields:
            dict: SSE 事件 {"type": "node_start"|"node_done"|"workflow_pause"|"workflow_done"|"error", ...}
        """
        graph = await get_prd_workflow()
        config = {'configurable': {'thread_id': run.thread_id}}

        initial_state: PRDWorkflowState = {
            'input': run.requirement_input,
            'role': 'product',
            'use_thinking': run.use_thinking,
            'competitive_analysis': None,
            'prd_draft': None,
            'review_feedback': None,
            'review_score': None,
            'final_prd': None,
            'iteration_count': 0,
            'human_approval': None,
            'approval_comment': None,
            'error': None,
            'node_trace': [],
            'current_node': 'research',
            'is_complete': False,
        }

        yield {
            'type': 'workflow_start',
            'workflow_id': run.id,
            'thread_id': run.thread_id,
            'nodes': WORKFLOW_NODES_ORDER,
        }

        prev_node = None

        try:
            async for event in graph.astream(initial_state, config, stream_mode='updates'):
                for node_name, node_output in event.items():
                    if not isinstance(node_output, dict):
                        continue

                    yield {
                        'type': 'node_done',
                        'node': node_name,
                        'current_node': node_output.get('current_node', node_name),
                        'iteration_count': node_output.get('iteration_count'),
                        'review_score': node_output.get('review_score'),
                        'error': node_output.get('error'),
                    }

                    await _sync_state_to_db(run, node_output)

                    if node_output.get('current_node') in PAUSE_NODES:
                        await _update_run_status(run, 'waiting_approval')
                        yield {
                            'type': 'workflow_pause',
                            'workflow_id': run.id,
                            'current_node': node_output.get('current_node'),
                            'message': '工作流等待人工审批',
                            'prd_draft': node_output.get('final_prd') or run.prd_draft,
                            'review_score': run.review_score,
                            'review_feedback': run.review_feedback,
                            'iteration_count': run.iteration_count,
                        }
                        return

                    if node_output.get('is_complete'):
                        final_status = 'failed' if node_output.get('error') else 'completed'
                        await _update_run_status(run, final_status)
                        yield {
                            'type': 'workflow_done',
                            'workflow_id': run.id,
                            'status': final_status,
                            'final_prd': run.final_prd or run.prd_draft,
                            'error': node_output.get('error'),
                            'node_trace': run.node_trace,
                            'total_tokens': _sum_tokens(run.node_trace),
                        }
                        return

            await _update_run_status(run, 'completed')
            yield {
                'type': 'workflow_done',
                'workflow_id': run.id,
                'status': 'completed',
                'final_prd': run.final_prd or run.prd_draft,
                'node_trace': run.node_trace,
                'total_tokens': _sum_tokens(run.node_trace),
            }

        except Exception as e:
            logger.exception(f'[WorkflowExecutor] 执行异常: {e}')
            await _update_run_status(run, 'failed', str(e))
            yield {
                'type': 'error',
                'workflow_id': run.id,
                'error': str(e),
            }

    @staticmethod
    async def resume_after_approval(
        run: WorkflowRun,
        approved: bool,
        comment: str = '',
    ):
        """
        人工审批后恢复工作流。

        Yields:
            dict: SSE 事件
        """
        if run.status != 'waiting_approval':
            yield {
                'type': 'error',
                'error': f'工作流状态不正确，当前状态: {run.status}，需要: waiting_approval',
            }
            return

        graph = await get_prd_workflow()
        config = {'configurable': {'thread_id': run.thread_id}}

        run.human_approval = approved
        run.approval_comment = comment
        await sync_to_async(run.save)(update_fields=['human_approval', 'approval_comment', 'updated_at'])
        await _update_run_status(run, 'running')

        resume_state = {
            'human_approval': approved,
            'approval_comment': comment,
        }

        yield {
            'type': 'approval_received',
            'approved': approved,
            'comment': comment,
        }

        try:
            async for event in graph.astream(resume_state, config, stream_mode='updates'):
                for node_name, node_output in event.items():
                    if not isinstance(node_output, dict):
                        continue

                    yield {
                        'type': 'node_done',
                        'node': node_name,
                        'current_node': node_output.get('current_node', node_name),
                        'iteration_count': node_output.get('iteration_count'),
                        'review_score': node_output.get('review_score'),
                        'error': node_output.get('error'),
                    }

                    await _sync_state_to_db(run, node_output)

                    if node_output.get('current_node') in PAUSE_NODES:
                        await _update_run_status(run, 'waiting_approval')
                        yield {
                            'type': 'workflow_pause',
                            'workflow_id': run.id,
                            'current_node': node_output.get('current_node'),
                            'message': '工作流再次等待人工审批',
                            'prd_draft': node_output.get('final_prd') or run.prd_draft,
                            'review_score': run.review_score,
                            'iteration_count': run.iteration_count,
                        }
                        return

                    if node_output.get('is_complete'):
                        final_status = 'failed' if node_output.get('error') else 'completed'
                        await _update_run_status(run, final_status)
                        yield {
                            'type': 'workflow_done',
                            'workflow_id': run.id,
                            'status': final_status,
                            'final_prd': run.final_prd or run.prd_draft,
                            'error': node_output.get('error'),
                            'node_trace': run.node_trace,
                        }
                        return

            await _update_run_status(run, 'completed')
            yield {
                'type': 'workflow_done',
                'workflow_id': run.id,
                'status': 'completed',
                'final_prd': run.final_prd or run.prd_draft,
                'node_trace': run.node_trace,
            }

        except Exception as e:
            logger.exception(f'[WorkflowExecutor] resume 异常: {e}')
            await _update_run_status(run, 'failed', str(e))
            yield {'type': 'error', 'workflow_id': run.id, 'error': str(e)}


async def _sync_state_to_db(run: WorkflowRun, output: dict):
    """将节点输出同步到数据库"""
    fields_to_update = ['updated_at']

    if 'competitive_analysis' in output and output['competitive_analysis'] is not None:
        run.competitive_analysis = output['competitive_analysis']
        fields_to_update.append('competitive_analysis')

    if 'prd_draft' in output and output['prd_draft'] is not None:
        run.prd_draft = output['prd_draft']
        fields_to_update.append('prd_draft')

    if 'review_score' in output and output['review_score'] is not None:
        run.review_score = output['review_score']
        fields_to_update.append('review_score')

    if 'review_feedback' in output:
        run.review_feedback = output['review_feedback']
        fields_to_update.append('review_feedback')

    if 'final_prd' in output and output['final_prd'] is not None:
        run.final_prd = output['final_prd']
        fields_to_update.append('final_prd')

    if 'iteration_count' in output and output['iteration_count'] is not None:
        run.iteration_count = output['iteration_count']
        fields_to_update.append('iteration_count')

    if 'current_node' in output:
        run.current_node = output['current_node']
        fields_to_update.append('current_node')

    if 'node_trace' in output:
        run.node_trace = output['node_trace']
        fields_to_update.append('node_trace')

    if 'error' in output and output['error']:
        run.error_message = output['error']
        fields_to_update.append('error_message')

    if len(fields_to_update) > 1:
        await sync_to_async(run.save)(update_fields=fields_to_update)


async def _update_run_status(run: WorkflowRun, status: str, error: str = None):
    """更新工作流状态"""
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
    """汇总所有节点消耗的 token"""
    return sum(n.get('tokens', 0) for n in (node_trace or []) if isinstance(n, dict))
