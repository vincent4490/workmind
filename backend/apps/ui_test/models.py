# -*- coding: utf-8 -*-
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model

from .constants import DeviceStatus, ExecutionStatus, TestType

User = get_user_model()


class Device(models.Model):
    """设备模型 - 整合了slot_game_automation的设备管理功能"""
    STATUS_CHOICES = [
        (DeviceStatus.AVAILABLE, '可用'),
        (DeviceStatus.LOCKED, '已锁定'),
        (DeviceStatus.ONLINE, '在线'),
        (DeviceStatus.OFFLINE, '离线'),
    ]
    
    CONNECTION_TYPE_CHOICES = [
        ('emulator', '本地模拟器'),
        ('remote_emulator', '远程模拟器'),
    ]
    
    device_id = models.CharField(max_length=255, verbose_name='设备序列号')
    name = models.CharField(max_length=255, blank=True, default='', verbose_name='设备名称')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline', verbose_name='状态')
    android_version = models.CharField(max_length=50, blank=True, default='', verbose_name='Android版本')
    connection_type = models.CharField(max_length=20, choices=CONNECTION_TYPE_CHOICES, default='emulator', verbose_name='连接类型')
    ip_address = models.CharField(max_length=50, blank=True, default='', verbose_name='IP地址')
    port = models.IntegerField(default=5555, verbose_name='端口')
    
    # 设备锁定相关字段
    locked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='locked_devices', verbose_name='锁定用户')
    locked_at = models.DateTimeField(null=True, blank=True, verbose_name='锁定时间')
    max_allocation_time = models.IntegerField(default=28800, verbose_name='最大分配时间(秒)')
    
    # 设备规格信息
    device_specs = models.JSONField(default=dict, verbose_name='设备规格', help_text='RAM, CPU, 分辨率等信息')
    description = models.TextField(blank=True, default='', verbose_name='设备描述')
    location = models.CharField(max_length=200, blank=True, default='', verbose_name='设备位置')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'ui_test_device'
        verbose_name = '设备'
        verbose_name_plural = verbose_name
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.name or self.device_id} ({self.status})"


class UiTestConfig(models.Model):
    """UI测试配置"""
    adb_path = models.CharField(max_length=500, default='adb', verbose_name='ADB路径')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'ui_test_config'
        verbose_name = 'UI测试配置'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return "UI测试配置"


class UiTestCase(models.Model):
    """UI测试用例"""
    TEST_TYPE_CHOICES = [
        (TestType.API, 'API测试'),
        (TestType.UI, 'UI测试'),
    ]
    
    name = models.CharField(max_length=200, verbose_name='用例名称')
    test_type = models.CharField(max_length=20, choices=TEST_TYPE_CHOICES, verbose_name='测试类型')
    yaml_file = models.CharField(max_length=500, blank=True, default='', verbose_name='YAML文件路径')
    case_data = models.JSONField(default=dict, verbose_name='用例数据')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'ui_test_case'
        verbose_name = 'UI测试用例'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return self.name


class UiComponentDefinition(models.Model):
    """UI组件/动作定义, 用于UI场景编排与校验"""
    name = models.CharField(max_length=100, verbose_name='组件名称')
    type = models.CharField(max_length=50, unique=True, verbose_name='组件类型')
    category = models.CharField(max_length=50, blank=True, default='', verbose_name='类别')
    description = models.TextField(blank=True, default='', verbose_name='描述')
    schema = models.JSONField(default=dict, verbose_name='配置Schema')
    default_config = models.JSONField(default=dict, verbose_name='默认配置')
    enabled = models.BooleanField(default=True, verbose_name='是否启用')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'ui_component_definition'
        verbose_name = 'UI组件定义'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', '-updated_at']

    def __str__(self):
        return f"{self.name} ({self.type})"


class UiComponentPackage(models.Model):
    """UI组件包(用于导入/安装组件定义)"""
    SOURCE_CHOICES = [
        ('upload', '上传'),
        ('market', '市场'),
        ('local', '本地'),
    ]

    name = models.CharField(max_length=100, verbose_name='包名称')
    version = models.CharField(max_length=50, blank=True, default='', verbose_name='版本')
    description = models.TextField(blank=True, default='', verbose_name='描述')
    author = models.CharField(max_length=100, blank=True, default='', verbose_name='作者')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='upload', verbose_name='来源')
    manifest = models.JSONField(default=dict, verbose_name='包清单')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='创建人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'ui_component_package'
        verbose_name = 'UI组件包'
        verbose_name_plural = verbose_name
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} ({self.version})"


class UiCustomComponentDefinition(models.Model):
    """UI自定义组件定义, 由基础组件组合而成"""
    name = models.CharField(max_length=100, verbose_name='组件名称')
    type = models.CharField(max_length=50, unique=True, verbose_name='组件类型')
    description = models.TextField(blank=True, default='', verbose_name='描述')
    schema = models.JSONField(default=dict, verbose_name='参数Schema')
    default_config = models.JSONField(default=dict, verbose_name='默认参数')
    steps = models.JSONField(default=list, verbose_name='组合步骤')
    enabled = models.BooleanField(default=True, verbose_name='是否启用')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'ui_custom_component_definition'
        verbose_name = 'UI自定义组件定义'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', '-updated_at']

    def __str__(self):
        return f"{self.name} ({self.type})"


class FunctionalRequirement(models.Model):
    """功能测试需求"""
    name = models.CharField(max_length=200, verbose_name='需求名称')
    link = models.TextField(blank=True, default='', verbose_name='需求链接')
    product_owner = models.CharField(max_length=100, blank=True, default='', verbose_name='产品负责人')
    status = models.CharField(max_length=20, blank=True, default='未开始', verbose_name='状态')
    tags = models.CharField(max_length=200, blank=True, default='', verbose_name='标签')
    remark = models.TextField(blank=True, default='', verbose_name='备注')
    developers = models.CharField(max_length=200, blank=True, default='', verbose_name='开发人员')
    dev_man_days = models.CharField(max_length=50, blank=True, default='', verbose_name='开发人日')
    dev_time = models.CharField(max_length=50, blank=True, default='', verbose_name='开发时间')
    testers = models.CharField(max_length=200, blank=True, default='', verbose_name='测试人员')
    test_team = models.CharField(max_length=200, blank=True, default='', verbose_name='测试团队')
    test_man_days = models.CharField(max_length=50, blank=True, default='', verbose_name='测试人日')
    submit_test_time = models.CharField(max_length=50, blank=True, default='', verbose_name='提测时间')
    test_time = models.CharField(max_length=50, blank=True, default='', verbose_name='测试时间')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_functional_requirements', verbose_name='创建人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'functional_requirement'
        verbose_name = '功能测试需求'
        verbose_name_plural = verbose_name
        ordering = ['-updated_at']
    
    def __str__(self):
        return self.name


class FunctionalTestCase(models.Model):
    """功能测试用例"""
    PRIORITY_CHOICES = [
        ('P0', 'P0-最高优先级'),
        ('P1', 'P1-高优先级'),
        ('P2', 'P2-中优先级'),
        ('P3', 'P3-低优先级'),
    ]
    
    requirement_name = models.CharField(max_length=200, verbose_name='需求名称', help_text='需求名称')
    feature_name = models.CharField(max_length=200, verbose_name='功能模块', help_text='功能模块')
    name = models.CharField(max_length=200, verbose_name='用例名称')
    preconditions = models.TextField(blank=True, default='', verbose_name='前置条件')
    test_steps = models.JSONField(default=list, verbose_name='操作步骤', help_text='步骤列表, 每个步骤包含: 操作步骤(step)和预期结果(expected_result)')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='P2', verbose_name='优先级')
    tags = models.JSONField(default=list, verbose_name='标签', help_text='标签列表')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_functional_cases', verbose_name='创建人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'functional_test_case'
        verbose_name = '功能测试用例'
        verbose_name_plural = verbose_name
        ordering = ['-updated_at']
    
    def __str__(self):
        return self.name


class TestPlan(models.Model):
    """测试计划"""
    name = models.CharField(max_length=200, verbose_name='计划名称')
    description = models.TextField(blank=True, default='', verbose_name='计划描述')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_test_plans', verbose_name='创建人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'test_plan'
        verbose_name = '测试计划'
        verbose_name_plural = verbose_name
        ordering = ['-updated_at']
    
    def __str__(self):
        return self.name


class TestPlanCase(models.Model):
    """测试计划与用例关联表"""
    STATUS_CHOICES = [
        ('pending', '未执行'),
        ('passed', '通过'),
        ('failed', '失败'),
        ('skipped', '跳过'),
    ]

    test_plan = models.ForeignKey(TestPlan, on_delete=models.CASCADE, related_name='plan_cases', verbose_name='测试计划')
    test_case = models.ForeignKey(FunctionalTestCase, on_delete=models.CASCADE, related_name='plan_relations', verbose_name='测试用例')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='执行状态')
    result_message = models.TextField(blank=True, default='', verbose_name='执行备注')
    marked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='marked_plan_cases', verbose_name='标记人')
    marked_at = models.DateTimeField(null=True, blank=True, verbose_name='标记时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        db_table = 'test_plan_case'
        verbose_name = '测试计划用例'
        verbose_name_plural = verbose_name
        unique_together = ['test_plan', 'test_case']
        ordering = ['id']
    
    def __str__(self):
        return f"{self.test_plan.name} - {self.test_case.name}"


class TestPlanCaseOperationLog(models.Model):
    """测试计划用例操作记录"""
    STATUS_CHOICES = [
        ('pending', '未执行'),
        ('passed', '通过'),
        ('failed', '失败'),
        ('skipped', '跳过'),
    ]

    plan_case = models.ForeignKey(TestPlanCase, on_delete=models.CASCADE, related_name='operation_logs', verbose_name='测试计划用例')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name='操作状态')
    message = models.TextField(blank=True, default='', verbose_name='备注')
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='test_plan_case_logs', verbose_name='操作人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='操作时间')

    class Meta:
        db_table = 'test_plan_case_log'
        verbose_name = '测试计划用例操作记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.plan_case} - {self.status}"


class UiTestExecution(models.Model):
    """UI测试执行记录"""
    STATUS_CHOICES = [
        (ExecutionStatus.PENDING, '等待中'),
        (ExecutionStatus.RUNNING, '执行中'),
        (ExecutionStatus.SUCCESS, '成功'),
        (ExecutionStatus.FAILED, '失败'),
    ]
    
    case = models.ForeignKey(UiTestCase, on_delete=models.CASCADE, related_name='executions', verbose_name='测试用例')
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True, related_name='executions', verbose_name='设备')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='test_executions', verbose_name='执行用户')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='执行状态')
    task_id = models.CharField(max_length=255, blank=True, default='', verbose_name='Celery任务ID', help_text='用于停止任务')
    progress = models.IntegerField(default=0, verbose_name='执行进度(0-100)')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    report_path = models.CharField(max_length=500, blank=True, default='', verbose_name='报告路径')
    error_message = models.TextField(blank=True, default='', verbose_name='错误信息')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'ui_test_execution'
        verbose_name = 'UI测试执行记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.case.name} - {self.status}"
    
    @property
    def case_name(self):
        """用例名称"""
        return self.case.name if self.case else ''
    
    @property
    def device_name(self):
        """设备名称"""
        return self.device.device_id if self.device else ''
    
    @property
    def user_name(self):
        """用户名"""
        return self.user.username if self.user else ''


class AppPackage(models.Model):
    """应用包名管理"""
    
    name = models.CharField(
        max_length=100,
        verbose_name='应用名称',
        help_text='友好的应用名称，如：Android设置'
    )
    
    package_name = models.CharField(
        max_length=255,
        unique=True,
        verbose_name='应用包名',
        help_text='Android包名，如：com.android.settings'
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_app_packages',
        verbose_name='创建人'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )
    
    class Meta:
        db_table = 'ui_test_app_package'
        verbose_name = '应用包名'
        verbose_name_plural = '应用包名管理'
        ordering = ['name']
        indexes = [
            models.Index(fields=['package_name']),
            models.Index(fields=['name']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.package_name})"


class UiElement(models.Model):
    """UI元素管理 - 统一管理图片、坐标、区域元素"""
    
    ELEMENT_TYPE_CHOICES = [
        ('image', '图片元素'),
        ('pos', '坐标元素'),
        ('region', '区域元素'),
    ]
    
    # 基础信息
    name = models.CharField(
        max_length=200,
        unique=True,
        verbose_name='元素名称',
        help_text='元素的唯一标识名称'
    )
    
    element_type = models.CharField(
        max_length=10,
        choices=ELEMENT_TYPE_CHOICES,
        verbose_name='元素类型'
    )
    
    # 标签
    tags = models.JSONField(
        default=list,
        verbose_name='标签',
        help_text='标签列表，如：["登录", "大厅", "支付"]'
    )
    
    # 元素配置（根据类型不同，内容不同）
    config = models.JSONField(
        default=dict,
        verbose_name='元素配置',
        help_text="""
        image类型: {"image_category": "common", "image_path": "common/login.png", "threshold": 0.7, "rgb": true}
        pos类型: {"x": 100, "y": 200}
        region类型: {"x1": 100, "y1": 200, "x2": 300, "y2": 400}
        """
    )
    
    # 多分辨率配置（可选）
    resolution_configs = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='分辨率配置',
        help_text='不同分辨率下的配置，如：{"1920x1080": {...}, "1280x720": {...}}'
    )
    
    # 使用统计
    usage_count = models.IntegerField(
        default=0,
        verbose_name='使用次数',
        help_text='该元素被用例引用的次数'
    )
    
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='最后使用时间'
    )
    
    # 元数据
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_elements',
        verbose_name='创建人'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='是否启用',
        help_text='软删除标记'
    )
    
    class Meta:
        db_table = 'ui_element'
        verbose_name = 'UI元素'
        verbose_name_plural = 'UI元素管理'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['element_type'], name='idx_element_type'),
            models.Index(fields=['name'], name='idx_name'),
            models.Index(fields=['is_active'], name='idx_active'),
        ]
    
    def __str__(self):
        return f"[{self.get_element_type_display()}] {self.name}"
    
    def increment_usage(self):
        """增加使用次数"""
        from django.utils import timezone
        self.usage_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['usage_count', 'last_used_at'])
