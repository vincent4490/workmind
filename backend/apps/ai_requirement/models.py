# -*- coding: utf-8 -*-
from django.db import models
from django.conf import settings


class AiRequirementTask(models.Model):
    """AI 需求智能体任务记录"""

    ROLE_CHOICES = [
        ('product', '产品'),
        ('dev', '开发'),
        ('test', '测试'),
    ]

    TASK_TYPE_CHOICES = [
        ('competitive_analysis', '竞品分析'),
        ('prd_draft', 'PRD撰写'),
        ('prd_refine', '需求完善'),
        ('requirement_analysis', '需求分析'),
        ('tech_design', '技术方案'),
        ('test_requirement_analysis', '测试需求分析'),
        ('feature_breakdown', '功能点梳理'),
    ]

    STATUS_CHOICES = [
        ('pending', '等待中'),
        ('generating', '生成中'),
        ('success', '成功'),
        ('failed', '失败'),
    ]

    OUTPUT_FORMAT_CHOICES = [
        ('json', 'JSON'),
        ('markdown', 'Markdown'),
        ('both', '双形态'),
    ]

    SECURITY_LEVEL_CHOICES = [
        ('public', '公开'),
        ('internal', '内部'),
        ('confidential', '机密'),
    ]

    # ---- 基础信息 ----
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES,
        verbose_name="角色"
    )
    task_type = models.CharField(
        max_length=50, choices=TASK_TYPE_CHOICES,
        verbose_name="任务类型"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending',
        verbose_name="状态"
    )

    # ---- 输入 ----
    requirement_input = models.TextField(
        verbose_name="需求描述",
        help_text="用户输入的文本描述"
    )
    source_files = models.JSONField(
        null=True, blank=True,
        verbose_name="源文件路径列表"
    )
    session_id = models.CharField(
        max_length=50, null=True, blank=True,
        verbose_name="多轮对话会话ID"
    )
    use_thinking = models.BooleanField(
        default=False, verbose_name="深度推理模式"
    )
    output_format = models.CharField(
        max_length=20, choices=OUTPUT_FORMAT_CHOICES, default='both',
        verbose_name="输出格式"
    )

    # ---- 输出 ----
    result_json = models.JSONField(
        null=True, blank=True,
        verbose_name="结构化结果(JSON)"
    )
    result_md = models.TextField(
        null=True, blank=True,
        verbose_name="Markdown结果"
    )
    raw_content = models.TextField(
        null=True, blank=True,
        verbose_name="AI原始返回"
    )
    error_message = models.TextField(
        null=True, blank=True,
        verbose_name="错误信息"
    )
    confidence_score = models.FloatField(
        null=True, blank=True,
        verbose_name="置信度评分"
    )
    schema_validated = models.BooleanField(
        default=False,
        verbose_name="是否通过Schema验证"
    )
    validation_retries = models.IntegerField(
        default=0,
        verbose_name="Schema验证重试次数"
    )

    # ---- 模型与成本 ----
    model_used = models.CharField(
        max_length=50, default='', blank=True,
        verbose_name="使用的模型"
    )
    prompt_version = models.CharField(
        max_length=20, null=True, blank=True,
        verbose_name="Prompt版本号"
    )
    prompt_tokens = models.IntegerField(default=0, verbose_name="输入Token")
    completion_tokens = models.IntegerField(default=0, verbose_name="输出Token")
    total_tokens = models.IntegerField(default=0, verbose_name="总Token")
    cost_usd = models.DecimalField(
        max_digits=10, decimal_places=6, default=0,
        verbose_name="成本(USD)"
    )

    # ---- 血缘追踪 ----
    parent_task = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='child_tasks',
        verbose_name="父任务(修订链)"
    )
    downstream_testcases = models.JSONField(
        default=list, blank=True,
        verbose_name="下游用例任务ID列表"
    )

    # ---- 安全 ----
    security_level = models.CharField(
        max_length=20, choices=SECURITY_LEVEL_CHOICES, default='internal',
        verbose_name="数据安全等级"
    )
    pii_detected = models.BooleanField(
        default=False,
        verbose_name="是否检测到PII"
    )

    # ---- 审计 ----
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
        verbose_name="创建人"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = 'ai_requirement_task'
        verbose_name = 'AI需求任务'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['role', 'task_type']),
            models.Index(fields=['status']),
            models.Index(fields=['session_id']),
        ]

    def __str__(self):
        return f"[{self.get_role_display()}/{self.get_task_type_display()}] {self.requirement_input[:50]}"


class PromptVersion(models.Model):
    """Prompt 版本注册表"""

    task_type = models.CharField(
        max_length=50,
        verbose_name="任务类型"
    )
    version = models.CharField(
        max_length=20,
        verbose_name="版本号"
    )
    system_prompt = models.TextField(
        verbose_name="System Prompt 完整文本"
    )
    change_log = models.TextField(
        default='', blank=True,
        verbose_name="变更说明"
    )
    eval_dataset_id = models.CharField(
        max_length=50, null=True, blank=True,
        verbose_name="关联评估数据集ID"
    )

    # ---- 性能指标（由评估流水线填充）----
    accuracy_score = models.FloatField(null=True, blank=True, verbose_name="准确率")
    avg_output_tokens = models.IntegerField(null=True, blank=True, verbose_name="平均输出Token")
    avg_latency_ms = models.IntegerField(null=True, blank=True, verbose_name="平均延迟(ms)")
    hallucination_rate = models.FloatField(null=True, blank=True, verbose_name="幻觉率")
    schema_compliance_rate = models.FloatField(null=True, blank=True, verbose_name="Schema合规率")

    # ---- 发布控制 ----
    is_active = models.BooleanField(
        default=False,
        verbose_name="当前生产版本"
    )
    is_ab_candidate = models.BooleanField(
        default=False,
        verbose_name="A/B测试候选"
    )
    ab_traffic_ratio = models.FloatField(
        default=0,
        verbose_name="A/B分流比例(0-1)"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = 'ai_requirement_prompt_version'
        verbose_name = 'Prompt版本'
        verbose_name_plural = verbose_name
        unique_together = ('task_type', 'version')
        ordering = ['-created_at']

    def __str__(self):
        active = " [ACTIVE]" if self.is_active else ""
        return f"{self.task_type} v{self.version}{active}"


class AiRequirementFeedback(models.Model):
    """用户反馈（驱动 Prompt 迭代）"""

    RATING_CHOICES = [
        ('positive', '👍'),
        ('negative', '👎'),
    ]
    ISSUE_TYPE_CHOICES = [
        ('hallucination', '幻觉'),
        ('missing', '遗漏'),
        ('format_error', '格式错误'),
        ('irrelevant', '不相关'),
        ('other', '其他'),
    ]

    task = models.ForeignKey(
        AiRequirementTask, on_delete=models.CASCADE,
        related_name='feedbacks',
        verbose_name="关联任务"
    )
    rating = models.CharField(
        max_length=10, choices=RATING_CHOICES,
        verbose_name="评价"
    )
    issue_type = models.CharField(
        max_length=30, choices=ISSUE_TYPE_CHOICES,
        null=True, blank=True,
        verbose_name="问题类型"
    )
    comment = models.TextField(
        null=True, blank=True,
        verbose_name="详细说明"
    )
    prompt_version = models.CharField(
        max_length=20, default='', blank=True,
        verbose_name="当时的Prompt版本"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
        verbose_name="反馈人"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = 'ai_requirement_feedback'
        verbose_name = '需求智能体反馈'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.rating}] Task#{self.task_id} - {self.issue_type or 'N/A'}"


class EvalDataset(models.Model):
    """评估数据集样本 —— 用于 Prompt 版本迭代对比"""

    task_type = models.CharField(max_length=50, verbose_name="任务类型")
    title = models.CharField(max_length=200, verbose_name="样本标题")
    input_text = models.TextField(verbose_name="输入文本")
    expected_key_facts = models.JSONField(
        default=list, verbose_name="期望关键事实列表"
    )
    expected_schema_snapshot = models.JSONField(
        null=True, blank=True,
        verbose_name="期望输出 Schema 快照"
    )
    difficulty = models.CharField(
        max_length=10, default='medium',
        verbose_name="难度 easy/medium/hard"
    )
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = 'ai_requirement_eval_dataset'
        verbose_name = '评估数据集'
        verbose_name_plural = verbose_name
        ordering = ['task_type', '-created_at']

    def __str__(self):
        return f"[{self.task_type}] {self.title}"


class EvalRun(models.Model):
    """评估运行记录"""

    prompt_version = models.ForeignKey(
        PromptVersion, on_delete=models.CASCADE,
        related_name='eval_runs',
        verbose_name="Prompt版本"
    )
    status = models.CharField(
        max_length=20, default='pending',
        verbose_name="状态 pending/running/completed/failed"
    )
    total_samples = models.IntegerField(default=0, verbose_name="总样本数")
    completed_samples = models.IntegerField(default=0, verbose_name="已完成样本数")
    trials_per_sample = models.IntegerField(default=3, verbose_name="每样本运行次数")

    # 聚合指标
    avg_accuracy = models.FloatField(null=True, blank=True, verbose_name="平均准确率")
    avg_hallucination = models.FloatField(null=True, blank=True, verbose_name="平均幻觉率")
    avg_schema_compliance = models.FloatField(null=True, blank=True, verbose_name="Schema合规率")
    avg_tokens = models.IntegerField(null=True, blank=True, verbose_name="平均Token")
    avg_latency_ms = models.IntegerField(null=True, blank=True, verbose_name="平均延迟ms")
    total_cost_usd = models.DecimalField(
        max_digits=10, decimal_places=4, default=0,
        verbose_name="总评估成本USD"
    )
    # P1-2：CLASSIC 稳定性 + 回归基线
    avg_stability = models.FloatField(
        null=True, blank=True,
        verbose_name="稳定性(1-样本准确率标准差)"
    )
    is_baseline = models.BooleanField(
        default=False,
        verbose_name="是否为基线（用于回归对比）"
    )
    baseline_run = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='comparison_runs',
        verbose_name="对比的基线运行"
    )
    regression_detected = models.BooleanField(
        default=False,
        verbose_name="是否检测到回归"
    )

    detail_results = models.JSONField(
        null=True, blank=True,
        verbose_name="逐样本详细结果"
    )
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = 'ai_requirement_eval_run'
        verbose_name = '评估运行'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"Eval #{self.id} - {self.prompt_version} ({self.status})"


class WorkflowRun(models.Model):
    """LangGraph 工作流执行记录"""

    WORKFLOW_TYPE_CHOICES = [
        ('prd_deep', 'PRD深度撰写'),
        ('multi_agent', '多智能体协作'),
    ]

    STATUS_CHOICES = [
        ('pending', '等待中'),
        ('running', '运行中'),
        ('waiting_approval', '待审批'),
        ('completed', '已完成'),
        ('failed', '失败'),
        ('cancelled', '已取消'),
    ]

    workflow_type = models.CharField(
        max_length=30, choices=WORKFLOW_TYPE_CHOICES, default='prd_deep',
        verbose_name="工作流类型"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending',
        verbose_name="状态"
    )
    thread_id = models.CharField(
        max_length=64, unique=True, db_index=True,
        verbose_name="LangGraph thread_id"
    )
    requirement_input = models.TextField(verbose_name="原始需求输入")
    use_thinking = models.BooleanField(default=False, verbose_name="深度推理")

    current_node = models.CharField(
        max_length=50, default='pending',
        verbose_name="当前节点"
    )
    iteration_count = models.IntegerField(default=0, verbose_name="迭代轮次")
    node_trace = models.JSONField(default=list, verbose_name="节点执行轨迹")

    competitive_analysis = models.JSONField(null=True, blank=True, verbose_name="竞品分析结果")
    prd_draft = models.JSONField(null=True, blank=True, verbose_name="PRD草稿")
    review_score = models.FloatField(null=True, blank=True, verbose_name="评审分数")
    review_feedback = models.TextField(null=True, blank=True, verbose_name="评审反馈")
    final_prd = models.JSONField(null=True, blank=True, verbose_name="最终PRD")
    error_message = models.TextField(null=True, blank=True, verbose_name="错误信息")

    human_approval = models.BooleanField(null=True, blank=True, verbose_name="人工审批结果")
    approval_comment = models.TextField(null=True, blank=True, verbose_name="审批意见")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='approved_workflows',
        verbose_name="审批人"
    )

    total_tokens = models.IntegerField(default=0, verbose_name="总Token消耗")
    total_cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0, verbose_name="总成本USD")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='created_workflows',
        verbose_name="创建人"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = 'ai_requirement_workflow_run'
        verbose_name = '工作流执行记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['workflow_type', 'status']),
        ]

    def __str__(self):
        return f'Workflow#{self.id} [{self.get_status_display()}] {self.current_node}'


class AiAuditLog(models.Model):
    """AI 操作安全审计日志"""

    event_type = models.CharField(
        max_length=50,
        verbose_name="事件类型",
        help_text="prompt_injection_blocked / pii_detected / security_level_reject / ..."
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
        verbose_name="操作人"
    )
    task_id = models.IntegerField(null=True, blank=True, verbose_name="关联任务ID")
    detail = models.TextField(verbose_name="事件详情")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP地址")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = 'ai_audit_log'
        verbose_name = 'AI审计日志'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', 'created_at']),
        ]

    def __str__(self):
        return f"[{self.event_type}] {self.created_at}"


class LlmCallLog(models.Model):
    """
    LLM 调用链路记录（可观测性 P2-2）
    每次 LLM 调用或工作流节点执行写一条，用于链路追踪、耗时与错误类型统计。
    """
    task = models.ForeignKey(
        AiRequirementTask, null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='llm_call_logs',
        verbose_name="关联任务"
    )
    workflow_run_id = models.IntegerField(
        null=True, blank=True,
        verbose_name="工作流运行ID"
    )
    span_type = models.CharField(
        max_length=32,
        choices=[('llm', 'LLM调用'), ('workflow_node', '工作流节点')],
        default='llm',
        verbose_name="类型"
    )
    model = models.CharField(max_length=64, default='', blank=True, verbose_name="模型")
    prompt_tokens = models.IntegerField(default=0, verbose_name="输入Token")
    completion_tokens = models.IntegerField(default=0, verbose_name="输出Token")
    latency_ms = models.IntegerField(null=True, blank=True, verbose_name="耗时(毫秒)")
    error_type = models.CharField(
        max_length=128, null=True, blank=True,
        verbose_name="错误类型",
        help_text="失败时记录错误摘要或类型"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = 'ai_requirement_llm_call_log'
        verbose_name = 'LLM调用记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task_id', 'created_at']),
            models.Index(fields=['span_type', 'created_at']),
            models.Index(fields=['error_type', 'created_at']),
        ]

    def __str__(self):
        return f"{self.span_type} task={self.task_id} model={self.model} {self.latency_ms or 0}ms"


class RequirementChunk(models.Model):
    """
    RAG 向量片段（P2-4 长期记忆）
    将成功任务 result_md / result_json 抽取为可检索文本并存储 embedding，供后续需求分析/PRD 生成时注入上下文。
    """
    CONTENT_TYPE_CHOICES = [
        ('prd_full', 'PRD 全文'),
        ('feature_breakdown', '功能点梳理'),
        ('glossary', '术语表'),
        ('other', '其他'),
    ]

    task = models.ForeignKey(
        AiRequirementTask, on_delete=models.CASCADE,
        related_name='rag_chunks',
        verbose_name="关联任务"
    )
    content_type = models.CharField(
        max_length=32, choices=CONTENT_TYPE_CHOICES, default='other',
        verbose_name="内容类型"
    )
    content_text = models.TextField(verbose_name="检索文本")
    embedding = models.JSONField(
        null=True, blank=True,
        verbose_name="向量(JSON list of floats)",
        help_text="由 embedding 模型生成，用于相似度检索"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = 'ai_requirement_requirement_chunk'
        verbose_name = '需求RAG片段'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['content_type']),
            models.Index(fields=['task_id']),
        ]

    def __str__(self):
        return f"Chunk task={self.task_id} {self.content_type} {self.created_at}"
