# -*- coding: utf-8 -*-
from rest_framework import serializers
from .models import (
    AiRequirementTask, AiRequirementFeedback,
    PromptVersion, EvalDataset, EvalRun, WorkflowRun,
)


class AiRequirementTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = AiRequirementTask
        fields = '__all__'
        read_only_fields = [
            'status', 'result_json', 'result_md', 'raw_content',
            'error_message', 'confidence_score',
            'schema_validated', 'validation_retries',
            'model_used', 'prompt_version',
            'prompt_tokens', 'completion_tokens', 'total_tokens', 'cost_usd',
            'pii_detected', 'downstream_testcases',
            'created_at', 'updated_at',
        ]


class RunStreamRequestSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=['product', 'dev', 'test'])
    task_type = serializers.ChoiceField(choices=[
        'competitive_analysis', 'prd_draft', 'prd_refine',
        'requirement_analysis', 'tech_design',
        'test_requirement_analysis', 'feature_breakdown',
    ])
    requirement_input = serializers.CharField(
        required=False, default='', allow_blank=True, max_length=50000,
    )
    use_thinking = serializers.BooleanField(required=False, default=False)
    output_format = serializers.ChoiceField(
        choices=['json', 'markdown', 'both'], required=False, default='both',
    )
    security_level = serializers.ChoiceField(
        choices=['public', 'internal', 'confidential'], required=False, default='internal',
    )
    session_id = serializers.CharField(
        required=False, default='', allow_blank=True, max_length=50,
    )
    context = serializers.DictField(required=False, default=dict)


class FeedbackSerializer(serializers.Serializer):
    task_id = serializers.IntegerField()
    rating = serializers.ChoiceField(choices=['positive', 'negative'])
    issue_type = serializers.ChoiceField(
        choices=['hallucination', 'missing', 'format_error', 'irrelevant', 'other'],
        required=False, allow_null=True,
    )
    comment = serializers.CharField(
        required=False, default='', allow_blank=True, max_length=2000,
    )


# ============ Prompt 版本管理 ============

class PromptVersionSerializer(serializers.ModelSerializer):
    usage_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = PromptVersion
        fields = '__all__'
        read_only_fields = [
            'accuracy_score', 'avg_output_tokens', 'avg_latency_ms',
            'hallucination_rate', 'schema_compliance_rate', 'created_at',
        ]


class PromptVersionActivateSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=['activate', 'deactivate', 'set_ab'],
        help_text="操作类型"
    )
    ab_traffic_ratio = serializers.FloatField(
        required=False, default=0, min_value=0, max_value=1,
        help_text="A/B 分流比例（仅 set_ab 时需要）"
    )


# ============ 评估 ============

class EvalDatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvalDataset
        fields = '__all__'


class EvalRunSerializer(serializers.ModelSerializer):
    prompt_version_display = serializers.StringRelatedField(
        source='prompt_version', read_only=True
    )

    class Meta:
        model = EvalRun
        fields = '__all__'
        read_only_fields = [
            'status', 'completed_samples', 'avg_accuracy',
            'avg_hallucination', 'avg_schema_compliance',
            'avg_stability', 'avg_tokens', 'avg_latency_ms', 'total_cost_usd',
            'baseline_run', 'regression_detected',
            'detail_results', 'started_at', 'completed_at', 'created_at',
        ]


# ============ 工作流管理 ============

class WorkflowRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowRun
        fields = '__all__'
        read_only_fields = [
            'status', 'thread_id', 'current_node',
            'iteration_count', 'node_trace',
            'competitive_analysis', 'prd_draft', 'review_score',
            'review_feedback', 'final_prd', 'error_message',
            'human_approval', 'approval_comment', 'approved_by',
            'total_tokens', 'total_cost_usd',
            'created_at', 'updated_at',
        ]


class WorkflowStartSerializer(serializers.Serializer):
    requirement_input = serializers.CharField(max_length=50000)
    use_thinking = serializers.BooleanField(required=False, default=False)


class WorkflowApproveSerializer(serializers.Serializer):
    approved = serializers.BooleanField()
    comment = serializers.CharField(required=False, default='', allow_blank=True, max_length=2000)
