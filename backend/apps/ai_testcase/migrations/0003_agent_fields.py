# Generated manually for agent workflow fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_testcase', '0002_aitestcasegeneration_source_files'),
    ]

    operations = [
        migrations.AddField(
            model_name='aitestcasegeneration',
            name='generation_mode',
            field=models.CharField(
                choices=[('direct', '直接生成'), ('agent', '智能体生成')],
                default='direct', max_length=10, verbose_name='生成模式',
            ),
        ),
        migrations.AddField(
            model_name='aitestcasegeneration',
            name='agent_state',
            field=models.JSONField(
                blank=True, null=True,
                help_text='LangGraph 图执行的快照状态',
                verbose_name='Agent 工作流中间状态',
            ),
        ),
        migrations.AddField(
            model_name='aitestcasegeneration',
            name='iteration_count',
            field=models.IntegerField(default=0, verbose_name='评审-修订迭代次数'),
        ),
        migrations.AddField(
            model_name='aitestcasegeneration',
            name='review_score',
            field=models.FloatField(blank=True, null=True, verbose_name='最终评审分数'),
        ),
        migrations.AddField(
            model_name='aitestcasegeneration',
            name='review_feedback',
            field=models.TextField(blank=True, null=True, verbose_name='评审反馈内容'),
        ),
    ]
