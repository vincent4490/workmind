# -*- coding: utf-8 -*-
from django.db import models
from django.conf import settings
from django.utils import timezone


class AiTestcaseGeneration(models.Model):
    """AI 用例生成记录"""

    STATUS_CHOICES = [
        ('pending', '等待中'),
        ('generating', '生成中'),
        ('success', '成功'),
        ('failed', '失败'),
        ('cancelled', '已取消'),
    ]

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='ai_testcase_generations',
        verbose_name='创建人',
        help_text='记录创建人，用于权限隔离',
    )
    idempotency_key = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        verbose_name='幂等键',
        help_text='用于避免同一用户重复提交导致重复消耗',
    )
    prompt_version = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='提示词版本',
        help_text='用于追踪生成/评审使用的提示词版本',
    )
    requirement = models.TextField(verbose_name="需求描述", help_text="输入的功能需求描述")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending',
        verbose_name="状态"
    )
    use_thinking = models.BooleanField(default=False, verbose_name="思考模式")
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='取消时间')

    # AI 返回结果
    result_json = models.JSONField(null=True, blank=True, verbose_name="结构化用例数据")
    raw_content = models.TextField(null=True, blank=True, verbose_name="AI原始返回")
    error_message = models.TextField(null=True, blank=True, verbose_name="错误信息")

    # Token 消耗
    prompt_tokens = models.IntegerField(default=0, verbose_name="输入Token")
    completion_tokens = models.IntegerField(default=0, verbose_name="输出Token")
    total_tokens = models.IntegerField(default=0, verbose_name="总Token")

    # 源文件路径（首次生成时持久化保存的上传文件路径列表，供模块重新生成时使用）
    source_files = models.JSONField(
        null=True, blank=True,
        verbose_name="源文件路径列表",
        help_text='["/path/to/file1.pdf", "/path/to/file2.png"]'
    )

    # XMind 文件路径
    xmind_file = models.CharField(max_length=500, null=True, blank=True, verbose_name="XMind文件路径")

    # Agent 智能体模式字段
    GENERATION_MODE_CHOICES = [
        ('direct', '直接生成'),
        ('agent', '智能体生成'),
    ]
    generation_mode = models.CharField(
        max_length=10, choices=GENERATION_MODE_CHOICES, default='direct',
        verbose_name="生成模式"
    )
    CASE_STRATEGY_MODE_CHOICES = [
        ('comprehensive', '全覆盖'),
        ('focused', '聚焦'),
    ]
    case_strategy_mode = models.CharField(
        max_length=20,
        choices=CASE_STRATEGY_MODE_CHOICES,
        default='comprehensive',
        verbose_name='用例策略模式',
        help_text='与 generation_mode（direct/agent）正交：控制用例条数与去重强度',
    )
    agent_state = models.JSONField(
        null=True, blank=True,
        verbose_name="Agent 工作流中间状态",
        help_text="LangGraph 图执行的快照状态"
    )
    iteration_count = models.IntegerField(default=0, verbose_name="评审-修订迭代次数")
    review_score = models.FloatField(null=True, blank=True, verbose_name="最终评审分数")
    review_feedback = models.TextField(null=True, blank=True, verbose_name="评审反馈内容")

    # 统计
    module_count = models.IntegerField(default=0, verbose_name="模块数")
    case_count = models.IntegerField(default=0, verbose_name="用例数")
    current_stage = models.CharField(max_length=50, null=True, blank=True, verbose_name="当前阶段")
    progress = models.IntegerField(default=0, verbose_name="进度百分比")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = 'ai_testcase_generation'
        verbose_name = 'AI用例生成记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.status}] {self.requirement[:50]}"

    def count_stats(self):
        """从 result_json 统计模块和用例数"""
        if not self.result_json:
            return
        modules = self.result_json.get('modules', [])
        self.module_count = len(modules)
        total_cases = 0
        for mod in modules:
            for func in mod.get('functions', []):
                total_cases += len(func.get('cases', []))
        self.case_count = total_cases

    def mark_cancelled(self):
        self.status = 'cancelled'
        self.cancelled_at = timezone.now()


class AiTestcaseEvent(models.Model):
    """AI 用例生成事件（P2：任务队列化后用于进度持久化与 SSE 推送）"""

    generation = models.ForeignKey(
        AiTestcaseGeneration,
        on_delete=models.CASCADE,
        related_name='events',
        verbose_name='生成记录',
    )
    event_type = models.CharField(max_length=30, verbose_name='事件类型')
    payload = models.JSONField(default=dict, verbose_name='事件载荷')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'ai_testcase_event'
        ordering = ['id']
        indexes = [
            models.Index(fields=['generation', 'id'], name='ai_tc_event_gen_id_idx'),
            models.Index(fields=['generation', 'created_at'], name='ai_tc_event_gen_ct_idx'),
        ]
