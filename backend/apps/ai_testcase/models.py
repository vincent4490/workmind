# -*- coding: utf-8 -*-
from django.db import models


class AiTestcaseGeneration(models.Model):
    """AI 用例生成记录"""

    STATUS_CHOICES = [
        ('pending', '等待中'),
        ('generating', '生成中'),
        ('success', '成功'),
        ('failed', '失败'),
    ]

    requirement = models.TextField(verbose_name="需求描述", help_text="输入的功能需求描述")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending',
        verbose_name="状态"
    )
    use_thinking = models.BooleanField(default=False, verbose_name="思考模式")

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

    # 统计
    module_count = models.IntegerField(default=0, verbose_name="模块数")
    case_count = models.IntegerField(default=0, verbose_name="用例数")

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
