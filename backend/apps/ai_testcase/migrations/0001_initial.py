# -*- coding: utf-8 -*-
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AiTestcaseGeneration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'created_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='ai_testcase_generations',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='创建人',
                        help_text='记录创建人，用于权限隔离',
                    ),
                ),
                (
                    'idempotency_key',
                    models.CharField(
                        blank=True,
                        db_index=True,
                        help_text='用于避免同一用户重复提交导致重复消耗',
                        max_length=64,
                        null=True,
                        verbose_name='幂等键',
                    ),
                ),
                (
                    'prompt_version',
                    models.CharField(
                        blank=True,
                        help_text='用于追踪生成/评审使用的提示词版本',
                        max_length=50,
                        null=True,
                        verbose_name='提示词版本',
                    ),
                ),
                ('requirement', models.TextField(help_text='输入的功能需求描述', verbose_name='需求描述')),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('pending', '等待中'),
                            ('generating', '生成中'),
                            ('success', '成功'),
                            ('failed', '失败'),
                            ('cancelled', '已取消'),
                        ],
                        default='pending',
                        max_length=20,
                        verbose_name='状态',
                    ),
                ),
                ('use_thinking', models.BooleanField(default=False, verbose_name='思考模式')),
                ('cancelled_at', models.DateTimeField(blank=True, null=True, verbose_name='取消时间')),
                ('result_json', models.JSONField(blank=True, null=True, verbose_name='结构化用例数据')),
                ('raw_content', models.TextField(blank=True, null=True, verbose_name='AI原始返回')),
                ('error_message', models.TextField(blank=True, null=True, verbose_name='错误信息')),
                ('prompt_tokens', models.IntegerField(default=0, verbose_name='输入Token')),
                ('completion_tokens', models.IntegerField(default=0, verbose_name='输出Token')),
                ('total_tokens', models.IntegerField(default=0, verbose_name='总Token')),
                (
                    'source_files',
                    models.JSONField(
                        blank=True,
                        help_text='["/path/to/file1.pdf", "/path/to/file2.png"]',
                        null=True,
                        verbose_name='源文件路径列表',
                    ),
                ),
                ('xmind_file', models.CharField(blank=True, max_length=500, null=True, verbose_name='XMind文件路径')),
                (
                    'generation_mode',
                    models.CharField(
                        choices=[('direct', '直接生成'), ('agent', '智能体生成')],
                        default='direct',
                        max_length=10,
                        verbose_name='生成模式',
                    ),
                ),
                (
                    'case_strategy_mode',
                    models.CharField(
                        choices=[('comprehensive', '全覆盖'), ('focused', '聚焦')],
                        default='comprehensive',
                        help_text='与 generation_mode（direct/agent）正交：控制用例条数与去重强度',
                        max_length=20,
                        verbose_name='用例策略模式',
                    ),
                ),
                (
                    'agent_state',
                    models.JSONField(
                        blank=True,
                        help_text='LangGraph 图执行的快照状态',
                        null=True,
                        verbose_name='Agent 工作流中间状态',
                    ),
                ),
                ('iteration_count', models.IntegerField(default=0, verbose_name='评审-修订迭代次数')),
                ('review_score', models.FloatField(blank=True, null=True, verbose_name='最终评审分数')),
                ('review_feedback', models.TextField(blank=True, null=True, verbose_name='评审反馈内容')),
                ('module_count', models.IntegerField(default=0, verbose_name='模块数')),
                ('case_count', models.IntegerField(default=0, verbose_name='用例数')),
                ('current_stage', models.CharField(blank=True, max_length=50, null=True, verbose_name='当前阶段')),
                ('progress', models.IntegerField(default=0, verbose_name='进度百分比')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': 'AI用例生成记录',
                'verbose_name_plural': 'AI用例生成记录',
                'db_table': 'ai_testcase_generation',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AiTestcaseEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(max_length=30, verbose_name='事件类型')),
                ('payload', models.JSONField(default=dict, verbose_name='事件载荷')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                (
                    'generation',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='events',
                        to='ai_testcase.aitestcasegeneration',
                        verbose_name='生成记录',
                    ),
                ),
            ],
            options={
                'db_table': 'ai_testcase_event',
                'ordering': ['id'],
            },
        ),
        migrations.AddIndex(
            model_name='aitestcaseevent',
            index=models.Index(fields=['generation', 'id'], name='ai_tc_event_gen_id_idx'),
        ),
        migrations.AddIndex(
            model_name='aitestcaseevent',
            index=models.Index(fields=['generation', 'created_at'], name='ai_tc_event_gen_ct_idx'),
        ),
    ]
