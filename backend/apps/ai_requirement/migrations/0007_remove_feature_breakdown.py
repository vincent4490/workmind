# Generated manually: 移除功能点梳理 (feature_breakdown) 任务类型与 RAG 内容类型

from django.db import migrations, models


def content_type_feature_breakdown_to_other(apps, schema_editor):
    """将历史 RAG 片段中 content_type=feature_breakdown 改为 other"""
    RequirementChunk = apps.get_model('ai_requirement', 'RequirementChunk')
    RequirementChunk.objects.filter(content_type='feature_breakdown').update(content_type='other')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('ai_requirement', '0006_evalrun_baseline_regression_stability'),
    ]

    operations = [
        migrations.AlterField(
            model_name='airequirementtask',
            name='task_type',
            field=models.CharField(
                choices=[
                    ('competitive_analysis', '竞品分析'),
                    ('prd_draft', 'PRD撰写'),
                    ('prd_refine', '需求完善'),
                    ('requirement_analysis', '需求分析'),
                    ('tech_design', '技术方案'),
                    ('test_requirement_analysis', '测试需求分析'),
                ],
                max_length=50,
                verbose_name='任务类型',
            ),
        ),
        migrations.AlterField(
            model_name='requirementchunk',
            name='content_type',
            field=models.CharField(
                choices=[
                    ('prd_full', 'PRD 全文'),
                    ('glossary', '术语表'),
                    ('other', '其他'),
                ],
                default='other',
                max_length=32,
                verbose_name='内容类型',
            ),
        ),
        migrations.RunPython(content_type_feature_breakdown_to_other, noop),
    ]
