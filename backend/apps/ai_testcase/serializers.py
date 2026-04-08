# -*- coding: utf-8 -*-
from rest_framework import serializers
from .models import AiTestcaseGeneration


class AiTestcaseGenerationSerializer(serializers.ModelSerializer):
    """用例生成记录序列化器"""

    class Meta:
        model = AiTestcaseGeneration
        fields = '__all__'
        read_only_fields = [
            'created_by',
            'idempotency_key',
            'prompt_version',
            'cancelled_at',
            'status', 'result_json', 'raw_content', 'error_message',
            'prompt_tokens', 'completion_tokens', 'total_tokens',
            'xmind_file', 'module_count', 'case_count',
            'created_at', 'updated_at',
        ]


class GenerateRequestSerializer(serializers.Serializer):
    """生成请求序列化器"""
    requirement = serializers.CharField(
        required=True,
        help_text="功能需求描述",
        min_length=2,
        max_length=5000
    )
    use_thinking = serializers.BooleanField(
        required=False,
        default=False,
        help_text="是否启用 AI 思考模式"
    )
    mode = serializers.ChoiceField(
        choices=[
            ('comprehensive', '全覆盖模式'),
            ('focused', '聚焦模式（功能与业务）'),
        ],
        required=False,
        default='comprehensive',
        help_text="生成模式"
    )


class RegenerateModuleRequestSerializer(serializers.Serializer):
    """模块重新生成请求序列化器"""
    record_id = serializers.IntegerField(
        required=True,
        help_text="首次生成的记录 ID"
    )
    module_name = serializers.CharField(
        required=True,
        help_text="要重新生成的模块名称"
    )
    module_requirement = serializers.CharField(
        required=False,
        default='',
        allow_blank=True,
        max_length=20000,
        help_text="该模块的补充需求说明（可选），如：密码必须包含大小写+数字+特殊字符"
    )
    adjustment = serializers.CharField(
        required=False,
        default='',
        allow_blank=True,
        max_length=2000,
        help_text="调整意见（可选），如：补充更多异常场景和边界值用例"
    )
    use_thinking = serializers.BooleanField(
        required=False,
        default=False,
        help_text="是否启用 AI 思考模式"
    )

    def validate(self, attrs):
        module_requirement = attrs.get('module_requirement', '').strip()
        adjustment = attrs.get('adjustment', '').strip()
        if not module_requirement and not adjustment:
            raise serializers.ValidationError('请至少填写「补充需求」或「调整意见」中的一项')
        return attrs


class UpdateCaseRequestSerializer(serializers.Serializer):
    """单条用例编辑请求序列化器"""
    record_id = serializers.IntegerField(required=True, help_text="生成记录 ID")
    module_name = serializers.CharField(required=True, help_text="模块名称")
    function_name = serializers.CharField(required=True, help_text="功能点名称")
    case_index = serializers.IntegerField(required=True, min_value=0, help_text="用例在功能下的下标")
    name = serializers.CharField(required=True, allow_blank=False, max_length=500, help_text="用例标题")
    priority = serializers.CharField(required=False, default="P1", max_length=10, help_text="优先级 P0/P1/P2")
    precondition = serializers.CharField(required=False, default="", allow_blank=True, max_length=2000, help_text="前置条件")
    steps = serializers.CharField(required=False, default="", allow_blank=True, max_length=5000, help_text="测试步骤")
    expected = serializers.CharField(required=False, default="", allow_blank=True, max_length=2000, help_text="预期结果")
