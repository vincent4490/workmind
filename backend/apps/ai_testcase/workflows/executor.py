# -*- coding: utf-8 -*-
"""
测试用例 Agent 执行器 —— 连接 LangGraph 图与 Django 模型

职责：
- 启动工作流并驱动到完成
- 同步持久化每个节点的状态到 AiTestcaseGeneration 模型
- 提供 SSE 事件流用于前端步骤可视化
"""
import json
import logging
import os

from asgiref.sync import sync_to_async
from django.conf import settings

from apps.ai_testcase.models import AiTestcaseGeneration
from apps.ai_testcase.services.xmind_builder import XMindBuilder
from .testcase_agent import get_testcase_agent_workflow, TestcaseAgentState

logger = logging.getLogger(__name__)

XMIND_OUTPUT_DIR = os.path.join(settings.BASE_DIR, 'apps', 'ai_testcase', 'output')

AGENT_NODES_ORDER = [
    'analyze_requirement',
    'plan_test_strategy',
    'generate_by_module',
    'merge_and_review',
    'refine_cases',
    'finalize',
]


class TestcaseAgentExecutor:
    """测试用例 Agent 工作流执行器"""

    @staticmethod
    async def run(record: AiTestcaseGeneration, requirement: str,
                  extracted_texts: list = None, images: list = None,
                  use_thinking: bool = False, mode: str = 'comprehensive'):
        """
        执行 Agent 工作流，yield SSE 事件。

        Yields:
            dict: SSE 事件
        """
        graph = get_testcase_agent_workflow()

        initial_state: TestcaseAgentState = {
            'requirement': requirement,
            'extracted_texts': extracted_texts or [],
            'images': images or [],
            'mode': mode,
            'use_thinking': use_thinking,
            'requirement_analysis': None,
            'test_strategy': None,
            'modules_generated': [],
            'current_module_index': 0,
            'generation_errors': [],
            'merged_result': None,
            'review_score': None,
            'review_feedback': None,
            'review_issues': [],
            'iteration_count': 0,
            'total_usage': {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            'node_trace': [],
            'current_node': 'analyze_requirement',
            'is_complete': False,
            'error': None,
        }

        yield {
            'type': 'agent_start',
            'record_id': record.id,
            'nodes': AGENT_NODES_ORDER,
        }

        node_index = 0
        seen_nodes = set()

        try:
            async for event in graph.astream(initial_state, stream_mode='updates'):
                for node_name, node_output in event.items():
                    if not isinstance(node_output, dict):
                        continue

                    display_node = node_name
                    if node_name == 'generate_by_module':
                        trace = node_output.get('node_trace', [])
                        if trace:
                            last = trace[-1]
                            display_node = last.get('node', node_name)

                    if node_name not in seen_nodes:
                        seen_nodes.add(node_name)
                        node_index += 1

                    node_event = {
                        'type': 'agent_node_done',
                        'node': display_node,
                        'index': node_index,
                        'total': len(AGENT_NODES_ORDER),
                        'current_node': node_output.get('current_node', node_name),
                        'iteration_count': node_output.get('iteration_count'),
                        'review_score': node_output.get('review_score'),
                    }

                    node_event['data'] = _extract_node_data(node_name, node_output)
                    yield node_event

                    if node_output.get('review_score') is not None and node_name == 'merge_and_review':
                        yield {
                            'type': 'agent_review',
                            'score': node_output.get('review_score'),
                            'feedback': node_output.get('review_feedback', ''),
                            'issues': node_output.get('review_issues', []),
                            'issues_count': len(node_output.get('review_issues', [])),
                            'iteration': node_output.get('iteration_count', 0),
                            'max': settings.TESTCASE_AGENT_MAX_REVISIONS if hasattr(settings, 'TESTCASE_AGENT_MAX_REVISIONS') else 3,
                        }

                    if node_name == 'refine_cases':
                        trace = node_output.get('node_trace', [])
                        changes_count = 0
                        if trace:
                            last = trace[-1]
                            changes_count = last.get('changes', 0)
                        yield {
                            'type': 'agent_refining',
                            'iteration': node_output.get('iteration_count', 0),
                            'changes_count': changes_count,
                        }

                    await _sync_state_to_db(record, node_output)

                    if node_output.get('error'):
                        record.status = 'failed'
                        record.error_message = node_output['error']
                        await sync_to_async(record.save)(update_fields=['status', 'error_message'])
                        yield {
                            'type': 'error',
                            'error': node_output['error'],
                            'record_id': record.id,
                        }
                        return

                    if node_output.get('is_complete'):
                        merged = node_output.get('merged_result') or record.result_json
                        if merged is None:
                            merged = getattr(record, '_last_merged', None)

                        await _finalize_record(record, merged, node_output)

                        yield {
                            'type': 'agent_done',
                            'record_id': record.id,
                            'data': record.result_json,
                            'review_score': record.review_score,
                            'iterations': record.iteration_count,
                            'module_count': record.module_count,
                            'case_count': record.case_count,
                            'usage': node_output.get('total_usage', {}),
                        }
                        return

        except Exception as e:
            logger.exception(f"[Agent] 工作流执行异常: {e}")
            record.status = 'failed'
            record.error_message = str(e)
            await sync_to_async(record.save)(update_fields=['status', 'error_message'])
            yield {
                'type': 'error',
                'error': str(e),
                'record_id': record.id,
            }


def _extract_node_data(node_name: str, node_output: dict) -> dict:
    """从节点输出中提取前端可展示的结构化数据"""
    if node_name == 'analyze_requirement':
        analysis = node_output.get('requirement_analysis')
        if analysis:
            return {
                'title': analysis.get('title', ''),
                'modules': [
                    {
                        'name': m.get('name', ''),
                        'description': m.get('description', ''),
                        'complexity': m.get('complexity', 'medium'),
                        'key_rules': m.get('key_rules', []),
                        'risk_areas': m.get('risk_areas', []),
                    }
                    for m in analysis.get('modules', [])
                ],
                'global_rules': analysis.get('global_rules', []),
                'implied_rules': analysis.get('implied_rules', []),
            }

    elif node_name == 'plan_test_strategy':
        strategy = node_output.get('test_strategy')
        if strategy:
            return {
                'strategies': [
                    {
                        'module_name': s.get('module_name', ''),
                        'methods': s.get('methods', []),
                        'case_count_range': s.get('case_count_range', []),
                        'coverage_targets': s.get('coverage_targets', []),
                        'priority_distribution': s.get('priority_distribution', {}),
                        'special_focus': s.get('special_focus', ''),
                    }
                    for s in strategy.get('strategies', [])
                ],
                'integration_scenarios': strategy.get('integration_scenarios', []),
            }

    elif node_name == 'generate_by_module':
        generated = node_output.get('modules_generated', [])
        errors = node_output.get('generation_errors', [])
        # 节点增量输出里通常不含 requirement_analysis，需用节点显式携带的 module_total
        total_modules = int(node_output.get('module_total') or 0)
        if not total_modules:
            analysis = node_output.get('requirement_analysis')
            if analysis:
                total_modules = len(analysis.get('modules', []))
        if generated:
            latest = generated[-1]
            case_count = sum(
                len(f.get('cases', []))
                for f in latest.get('functions', [])
            )
            completed = len(generated)
            total = total_modules or completed
            return {
                'module_name': latest.get('name', ''),
                'function_count': len(latest.get('functions', [])),
                'case_count': case_count,
                'completed': completed,
                'total': total,
                'errors': errors,
            }

    elif node_name == 'merge_and_review':
        merged = node_output.get('merged_result')
        if merged:
            modules = merged.get('modules', [])
            total_cases = sum(
                len(f.get('cases', []))
                for m in modules
                for f in m.get('functions', [])
            )
            return {
                'module_count': len(modules),
                'case_count': total_cases,
            }

    elif node_name == 'refine_cases':
        trace = node_output.get('node_trace', [])
        changes_count = 0
        if trace:
            last = trace[-1]
            changes_count = last.get('changes', 0)
        return {'changes_count': changes_count}

    return {}


async def _sync_state_to_db(record: AiTestcaseGeneration, node_output: dict):
    """将节点输出同步到 DB"""
    update_fields = ['updated_at']

    if 'merged_result' in node_output and node_output['merged_result']:
        record.result_json = node_output['merged_result']
        record._last_merged = node_output['merged_result']
        update_fields.append('result_json')

    if 'review_score' in node_output and node_output['review_score'] is not None:
        record.review_score = node_output['review_score']
        update_fields.append('review_score')

    if 'review_feedback' in node_output and node_output['review_feedback']:
        record.review_feedback = node_output['review_feedback']
        update_fields.append('review_feedback')

    if 'iteration_count' in node_output:
        record.iteration_count = node_output['iteration_count']
        update_fields.append('iteration_count')

    if 'total_usage' in node_output:
        usage = node_output['total_usage']
        record.prompt_tokens = usage.get('prompt_tokens', 0)
        record.completion_tokens = usage.get('completion_tokens', 0)
        record.total_tokens = usage.get('total_tokens', 0)
        update_fields.extend(['prompt_tokens', 'completion_tokens', 'total_tokens'])

    if 'node_trace' in node_output:
        record.agent_state = {'node_trace': node_output['node_trace']}
        update_fields.append('agent_state')

    if len(update_fields) > 1:
        await sync_to_async(record.save)(update_fields=update_fields)


async def _finalize_record(record: AiTestcaseGeneration, merged_result: dict, node_output: dict):
    """工作流完成后最终化记录"""
    if merged_result:
        record.result_json = merged_result
        record.count_stats()

        title = merged_result.get('title', f'testcase_{record.id}')
        xmind_filename = f"{title}.xmind"
        xmind_path = os.path.join(XMIND_OUTPUT_DIR, xmind_filename)
        try:
            await sync_to_async(XMindBuilder.build_and_save)(merged_result, xmind_path)
            record.xmind_file = xmind_path
        except Exception as e:
            logger.warning(f"[Agent] XMind 生成失败: {e}")

    usage = node_output.get('total_usage', {})
    record.prompt_tokens = usage.get('prompt_tokens', 0)
    record.completion_tokens = usage.get('completion_tokens', 0)
    record.total_tokens = usage.get('total_tokens', 0)
    record.review_score = node_output.get('review_score')
    record.review_feedback = node_output.get('review_feedback')
    record.iteration_count = node_output.get('iteration_count', 0)
    record.agent_state = {'node_trace': node_output.get('node_trace', []), 'final': True}
    record.status = 'success'

    await sync_to_async(record.save)()
