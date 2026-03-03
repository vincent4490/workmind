# -*- coding: utf-8 -*-
from rest_framework import serializers
from .models import (
    Device, UiTestConfig, UiTestCase,
    FunctionalRequirement, FunctionalTestCase, Task,
    TestPlan, TestPlanCase, TestPlanCaseOperationLog,
    UiComponentDefinition, UiCustomComponentDefinition, UiComponentPackage,
    UiTestExecution, AppPackage, UiElement
)


class DeviceSerializer(serializers.ModelSerializer):
    """设备序列化器"""
    locked_by_username = serializers.SerializerMethodField()
    
    class Meta:
        model = Device
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
    
    def get_locked_by_username(self, obj):
        """获取锁定用户名"""
        return obj.locked_by.username if obj.locked_by else None
    


class UiTestConfigSerializer(serializers.ModelSerializer):
    """UI测试配置序列化器"""
    
    class Meta:
        model = UiTestConfig
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class UiTestCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = UiTestCase
        fields = '__all__'


class UiComponentDefinitionSerializer(serializers.ModelSerializer):
    """UI组件定义序列化器"""

    class Meta:
        model = UiComponentDefinition
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class UiCustomComponentDefinitionSerializer(serializers.ModelSerializer):
    """UI自定义组件定义序列化器"""

    class Meta:
        model = UiCustomComponentDefinition
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class UiComponentPackageSerializer(serializers.ModelSerializer):
    """UI组件包序列化器"""

    class Meta:
        model = UiComponentPackage
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class FunctionalRequirementSerializer(serializers.ModelSerializer):
    """功能测试需求序列化器"""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)

    class Meta:
        model = FunctionalRequirement
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class TaskSerializer(serializers.ModelSerializer):
    """任务管理序列化器"""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)

    class Meta:
        model = Task
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class FunctionalTestCaseSerializer(serializers.ModelSerializer):
    """功能测试用例序列化器（与 AI 结构一致）"""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)

    class Meta:
        model = FunctionalTestCase
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class TestPlanSerializer(serializers.ModelSerializer):
    """测试计划序列化器"""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)
    case_count = serializers.SerializerMethodField()
    
    class Meta:
        model = TestPlan
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'created_by']
    
    def get_case_count(self, obj):
        """获取测试计划中的用例数量"""
        return obj.plan_cases.count()


class TestPlanCaseSerializer(serializers.ModelSerializer):
    """测试计划用例序列化器"""
    test_case_detail = FunctionalTestCaseSerializer(source='test_case', read_only=True)
    marked_by_username = serializers.CharField(source='marked_by.username', read_only=True)
    
    class Meta:
        model = TestPlanCase
        fields = '__all__'
        read_only_fields = ['created_at', 'marked_at', 'marked_by']


class TestPlanCaseOperationLogSerializer(serializers.ModelSerializer):
    """测试计划用例操作记录序列化器"""
    operator_username = serializers.CharField(source='operator.username', read_only=True)
    test_case_name = serializers.CharField(source='plan_case.test_case.name', read_only=True)

    class Meta:
        model = TestPlanCaseOperationLog
        fields = '__all__'
        read_only_fields = ['created_at', 'operator']


class UiTestExecutionSerializer(serializers.ModelSerializer):
    """UI测试执行记录序列化器"""
    case_name = serializers.CharField(source='case.name', read_only=True)
    device_name = serializers.CharField(source='device.device_id', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = UiTestExecution
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'user']


class AppPackageSerializer(serializers.ModelSerializer):
    """应用包名序列化器"""
    
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = AppPackage
        fields = [
            'id',
            'name',
            'package_name',
            'created_by',
            'created_by_name',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']
    
    def get_created_by_name(self, obj):
        """获取创建人姓名，无姓名时回退为 username"""
        if not obj.created_by:
            return ''
        return getattr(obj.created_by, 'name', None) or obj.created_by.username or ''
    
    def validate_package_name(self, value):
        """验证包名格式"""
        if not value:
            raise serializers.ValidationError("应用包名不能为空")
        
        # 简单的包名格式验证
        if not all(c.isalnum() or c in '._' for c in value):
            raise serializers.ValidationError("应用包名只能包含字母、数字、点和下划线")
        
        if '..' in value:
            raise serializers.ValidationError("应用包名不能包含连续的点")
        
        return value


class UiElementSerializer(serializers.ModelSerializer):
    """UI元素序列化器（完整版）"""
    
    created_by_name = serializers.SerializerMethodField()
    element_type_display = serializers.CharField(source='get_element_type_display', read_only=True)
    
    class Meta:
        model = UiElement
        fields = [
            'id', 'name', 'element_type', 'element_type_display',
            'tags', 'config', 'resolution_configs',
            'usage_count', 'last_used_at',
            'created_by', 'created_by_name',
            'created_at', 'updated_at', 'is_active'
        ]
        read_only_fields = ['id', 'usage_count', 'last_used_at', 'created_at', 'updated_at', 'created_by']

    def get_created_by_name(self, obj):
        """获取创建人姓名，无姓名时回退为 username"""
        if not obj.created_by:
            return ''
        return getattr(obj.created_by, 'name', None) or obj.created_by.username or ''
    
    def validate_name(self, value):
        """验证元素名称唯一性"""
        if self.instance:
            # 更新时排除自己
            if UiElement.objects.filter(name=value, is_active=True).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("元素名称已存在")
        else:
            # 创建时检查
            if UiElement.objects.filter(name=value, is_active=True).exists():
                raise serializers.ValidationError("元素名称已存在")
        return value
    
    def validate(self, attrs):
        """验证配置格式"""
        element_type = attrs.get('element_type') or (self.instance.element_type if self.instance else None)
        config = attrs.get('config', {})
        
        if element_type == 'image':
            if 'image_path' not in config:
                raise serializers.ValidationError({'config': '图片元素必须包含 image_path'})
            if 'threshold' not in config:
                config['threshold'] = 0.7  # 默认阈值
        
        elif element_type == 'pos':
            if 'x' not in config or 'y' not in config:
                raise serializers.ValidationError({'config': '坐标元素必须包含 x 和 y'})
            # 验证坐标值是否为整数
            try:
                int(config['x'])
                int(config['y'])
            except (ValueError, TypeError):
                raise serializers.ValidationError({'config': '坐标值必须为整数'})
        
        elif element_type == 'region':
            required_keys = ['x1', 'y1', 'x2', 'y2']
            if not all(k in config for k in required_keys):
                raise serializers.ValidationError({'config': '区域元素必须包含 x1, y1, x2, y2'})
            # 验证坐标值是否为整数
            try:
                for key in required_keys:
                    int(config[key])
            except (ValueError, TypeError):
                raise serializers.ValidationError({'config': '坐标值必须为整数'})
        
        attrs['config'] = config
        return attrs


class UiElementListSerializer(serializers.ModelSerializer):
    """UI元素列表序列化器（简化版，用于列表展示）"""
    
    element_type_display = serializers.CharField(source='get_element_type_display', read_only=True)
    preview_url = serializers.SerializerMethodField()
    
    class Meta:
        model = UiElement
        fields = [
            'id', 'name', 'element_type', 'element_type_display',
            'tags', 'usage_count', 'preview_url',
            'config', 'created_at'
        ]
    
    def get_preview_url(self, obj):
        """获取预览URL"""
        if obj.element_type == 'image':
            # 使用 request 构建完整 URL
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(f"/api/ui_test/elements/{obj.id}/preview/")
            return f"/api/ui_test/elements/{obj.id}/preview/"
        return None
