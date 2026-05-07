# -*- coding: utf-8 -*-
from django.db import models
from django.conf import settings


class KnowledgeDocument(models.Model):
    """知识库文档"""

    CATEGORY_CHOICES = [
        ("requirement", "需求文档"),
        ("tech_design", "技术方案"),
        ("test_case", "测试用例"),
        ("business", "业务知识"),
        ("generated", "AI生成用例"),
        ("other", "其他"),
    ]

    STATUS_CHOICES = [
        ("pending", "待处理"),
        ("processing", "解析中"),
        ("ready", "可用"),
        ("failed", "失败"),
    ]

    FILE_TYPE_CHOICES = [
        ("pdf", "PDF"),
        ("docx", "Word文档"),
        ("xlsx", "Excel表格"),
        ("image", "图片"),
        ("md", "Markdown"),
        ("txt", "文本"),
        ("other", "其他"),
    ]

    title = models.CharField(max_length=255, verbose_name="文档标题")
    category = models.CharField(
        max_length=30, choices=CATEGORY_CHOICES, default="other", verbose_name="文档分类"
    )
    file = models.FileField(upload_to="knowledge/", null=True, blank=True, verbose_name="文件")
    file_name = models.CharField(max_length=255, blank=True, verbose_name="原始文件名")
    file_type = models.CharField(
        max_length=20, choices=FILE_TYPE_CHOICES, blank=True, verbose_name="文件类型"
    )
    file_size = models.BigIntegerField(default=0, verbose_name="文件大小(字节)")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="状态"
    )
    summary = models.TextField(blank=True, verbose_name="AI摘要")
    tags = models.JSONField(default=list, verbose_name="标签")
    error_message = models.TextField(blank=True, verbose_name="错误信息")
    chunk_count = models.IntegerField(default=0, verbose_name="分块数量")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="knowledge_documents",
        verbose_name="创建人",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "knowledge_document"
        ordering = ["-created_at"]
        verbose_name = "知识库文档"
        verbose_name_plural = "知识库文档"

    def __str__(self):
        return self.title


class KnowledgeConversation(models.Model):
    """知识库问答会话"""

    title = models.CharField(max_length=255, blank=True, verbose_name="会话标题")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="knowledge_conversations",
        verbose_name="创建人",
    )
    # 限定检索范围的文档ID列表，空列表表示全库
    doc_filter = models.JSONField(default=list, verbose_name="文档范围过滤")
    # 限定分类过滤，空列表表示全部
    category_filter = models.JSONField(default=list, verbose_name="分类过滤")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "knowledge_conversation"
        ordering = ["-updated_at"]
        verbose_name = "问答会话"
        verbose_name_plural = "问答会话"

    def __str__(self):
        return self.title or f"会话#{self.id}"


class KnowledgeMessage(models.Model):
    """知识库问答消息"""

    ROLE_CHOICES = [
        ("user", "用户"),
        ("assistant", "助手"),
    ]

    conversation = models.ForeignKey(
        KnowledgeConversation,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="所属会话",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name="角色")
    content = models.TextField(verbose_name="内容")
    # 引用来源：[{doc_id, doc_title, chunk_content, page_num, score}, ...]
    sources = models.JSONField(default=list, verbose_name="引用来源")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "knowledge_message"
        ordering = ["created_at"]
        verbose_name = "问答消息"
        verbose_name_plural = "问答消息"
