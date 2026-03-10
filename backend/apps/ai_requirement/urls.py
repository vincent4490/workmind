# -*- coding: utf-8 -*-
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AiRequirementTaskViewSet,
    PromptVersionViewSet,
    EvalDatasetViewSet,
    EvalRunViewSet,
    WorkflowRunViewSet,
    run_stream_view,
    run_sync_view,
    feedback_view,
    chat_stream_view,
    clarify_and_continue_view,
    bridge_to_testcase_view,
    sync_to_jira_view,
    sync_to_confluence_view,
    stats_overview,
    workflow_start_view,
    workflow_approve_view,
    multi_agent_start_view,
    multi_agent_approve_view,
    kimi_ping_view,
    task_export_view,
)

router = DefaultRouter()
router.register(r'tasks', AiRequirementTaskViewSet, basename='ai-requirement-task')
router.register(r'prompts', PromptVersionViewSet, basename='ai-requirement-prompt')
router.register(r'eval-datasets', EvalDatasetViewSet, basename='ai-requirement-eval-dataset')
router.register(r'eval-runs', EvalRunViewSet, basename='ai-requirement-eval-run')
router.register(r'workflows', WorkflowRunViewSet, basename='ai-requirement-workflow')

urlpatterns = [
    path('kimi-ping/', kimi_ping_view, name='ai-requirement-kimi-ping'),
    path('run-stream/', run_stream_view, name='ai-requirement-run-stream'),
    path('run/', run_sync_view, name='ai-requirement-run'),
    path('feedback/', feedback_view, name='ai-requirement-feedback'),
    path('chat/', chat_stream_view, name='ai-requirement-chat'),
    path('clarify-and-continue/', clarify_and_continue_view, name='ai-requirement-clarify-continue'),
    path('bridge-to-testcase/', bridge_to_testcase_view, name='ai-requirement-bridge'),
    path('sync-to-jira/', sync_to_jira_view, name='ai-requirement-sync-jira'),
    path('sync-to-confluence/', sync_to_confluence_view, name='ai-requirement-sync-confluence'),
    path('stats/overview/', stats_overview, name='ai-requirement-stats'),
    path('workflow/start/', workflow_start_view, name='ai-requirement-workflow-start'),
    path('workflow/<int:workflow_id>/approve/', workflow_approve_view, name='ai-requirement-workflow-approve'),
    path('multi-agent/start/', multi_agent_start_view, name='ai-requirement-multi-agent-start'),
    path('multi-agent/<int:workflow_id>/approve/', multi_agent_approve_view, name='ai-requirement-multi-agent-approve'),
    # 导出接口显式注册，避免 router 未注册 detail action 时 404
    path('tasks/<int:pk>/export/', task_export_view, name='ai-requirement-task-export'),
    path('', include(router.urls)),
]
