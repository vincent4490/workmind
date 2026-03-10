# -*- coding: utf-8 -*-
from django.contrib import admin
from .models import (
    AiRequirementTask, PromptVersion, AiRequirementFeedback,
    AiAuditLog, EvalDataset, EvalRun, WorkflowRun, LlmCallLog,
    RequirementChunk,
)


@admin.register(AiRequirementTask)
class AiRequirementTaskAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'role', 'task_type', 'status', 'model_used',
        'prompt_version', 'confidence_score', 'schema_validated',
        'total_tokens', 'cost_usd', 'created_at',
    ]
    list_filter = ['role', 'task_type', 'status', 'schema_validated', 'security_level']
    search_fields = ['requirement_input']
    readonly_fields = [
        'result_json', 'result_md', 'raw_content',
        'prompt_tokens', 'completion_tokens', 'total_tokens', 'cost_usd',
        'created_at', 'updated_at',
    ]


@admin.register(PromptVersion)
class PromptVersionAdmin(admin.ModelAdmin):
    list_display = [
        'task_type', 'version', 'is_active', 'is_ab_candidate',
        'ab_traffic_ratio', 'accuracy_score', 'schema_compliance_rate',
        'created_at',
    ]
    list_filter = ['task_type', 'is_active', 'is_ab_candidate']


@admin.register(AiRequirementFeedback)
class AiRequirementFeedbackAdmin(admin.ModelAdmin):
    list_display = ['task', 'rating', 'issue_type', 'prompt_version', 'created_at']
    list_filter = ['rating', 'issue_type']


@admin.register(EvalDataset)
class EvalDatasetAdmin(admin.ModelAdmin):
    list_display = ['task_type', 'title', 'difficulty', 'is_active', 'created_at']
    list_filter = ['task_type', 'difficulty', 'is_active']
    search_fields = ['title', 'input_text']


@admin.register(EvalRun)
class EvalRunAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'prompt_version', 'status', 'total_samples', 'completed_samples',
        'avg_accuracy', 'avg_hallucination', 'avg_schema_compliance', 'avg_stability',
        'is_baseline', 'regression_detected', 'total_cost_usd', 'created_at',
    ]
    list_filter = ['status', 'is_baseline', 'regression_detected']


@admin.register(WorkflowRun)
class WorkflowRunAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'workflow_type', 'status', 'current_node',
        'iteration_count', 'review_score', 'human_approval',
        'total_tokens', 'created_at',
    ]
    list_filter = ['workflow_type', 'status']
    search_fields = ['requirement_input']
    readonly_fields = [
        'thread_id', 'node_trace', 'competitive_analysis', 'prd_draft',
        'final_prd', 'total_tokens', 'total_cost_usd', 'created_at', 'updated_at',
    ]


@admin.register(AiAuditLog)
class AiAuditLogAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'user', 'task_id', 'ip_address', 'created_at']
    list_filter = ['event_type']
    search_fields = ['detail']


@admin.register(LlmCallLog)
class LlmCallLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'task_id', 'span_type', 'model', 'prompt_tokens', 'completion_tokens', 'latency_ms', 'error_type', 'created_at']
    list_filter = ['span_type', 'error_type']
    search_fields = ['model', 'error_type']
    readonly_fields = ['created_at']


@admin.register(RequirementChunk)
class RequirementChunkAdmin(admin.ModelAdmin):
    list_display = ['id', 'task_id', 'content_type', 'created_at']
    list_filter = ['content_type']
    search_fields = ['content_text']
    readonly_fields = ['embedding', 'created_at']
