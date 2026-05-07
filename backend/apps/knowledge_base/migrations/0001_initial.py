# -*- coding: utf-8 -*-
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="KnowledgeDocument",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255, verbose_name="文档标题")),
                ("category", models.CharField(
                    choices=[
                        ("requirement", "需求文档"),
                        ("tech_design", "技术方案"),
                        ("test_case", "测试用例"),
                        ("business", "业务知识"),
                        ("generated", "AI生成用例"),
                        ("other", "其他"),
                    ],
                    default="other", max_length=30, verbose_name="文档分类",
                )),
                ("file", models.FileField(blank=True, null=True, upload_to="knowledge/", verbose_name="文件")),
                ("file_name", models.CharField(blank=True, max_length=255, verbose_name="原始文件名")),
                ("file_type", models.CharField(
                    blank=True, max_length=20, verbose_name="文件类型",
                    choices=[
                        ("pdf", "PDF"), ("docx", "Word文档"), ("xlsx", "Excel表格"),
                        ("image", "图片"), ("md", "Markdown"), ("txt", "文本"), ("other", "其他"),
                    ],
                )),
                ("file_size", models.BigIntegerField(default=0, verbose_name="文件大小(字节)")),
                ("status", models.CharField(
                    choices=[
                        ("pending", "待处理"), ("processing", "解析中"),
                        ("ready", "可用"), ("failed", "失败"),
                    ],
                    default="pending", max_length=20, verbose_name="状态",
                )),
                ("summary", models.TextField(blank=True, verbose_name="AI摘要")),
                ("tags", models.JSONField(default=list, verbose_name="标签")),
                ("error_message", models.TextField(blank=True, verbose_name="错误信息")),
                ("chunk_count", models.IntegerField(default=0, verbose_name="分块数量")),
                ("created_by", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="knowledge_documents", to=settings.AUTH_USER_MODEL, verbose_name="创建人",
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={"db_table": "knowledge_document", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="KnowledgeConversation",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(blank=True, max_length=255, verbose_name="会话标题")),
                ("doc_filter", models.JSONField(default=list, verbose_name="文档范围过滤")),
                ("category_filter", models.JSONField(default=list, verbose_name="分类过滤")),
                ("created_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="knowledge_conversations", to=settings.AUTH_USER_MODEL, verbose_name="创建人",
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={"db_table": "knowledge_conversation", "ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="KnowledgeMessage",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(
                    choices=[("user", "用户"), ("assistant", "助手")], max_length=20, verbose_name="角色",
                )),
                ("content", models.TextField(verbose_name="内容")),
                ("sources", models.JSONField(default=list, verbose_name="引用来源")),
                ("conversation", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="messages", to="knowledge_base.knowledgeconversation", verbose_name="所属会话",
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
            ],
            options={"db_table": "knowledge_message", "ordering": ["created_at"]},
        ),
    ]
