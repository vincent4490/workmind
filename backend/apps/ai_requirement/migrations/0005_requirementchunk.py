# Generated manually for P2-4 RAG

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ai_requirement', '0004_llmcalllog'),
    ]

    operations = [
        migrations.CreateModel(
            name='RequirementChunk',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_type', models.CharField(choices=[('prd_full', 'PRD 全文'), ('feature_breakdown', '功能点梳理'), ('glossary', '术语表'), ('other', '其他')], default='other', max_length=32, verbose_name='内容类型')),
                ('content_text', models.TextField(verbose_name='检索文本')),
                ('embedding', models.JSONField(blank=True, help_text='由 embedding 模型生成，用于相似度检索', null=True, verbose_name='向量(JSON list of floats)')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rag_chunks', to='ai_requirement.airequirementtask', verbose_name='关联任务')),
            ],
            options={
                'verbose_name': '需求RAG片段',
                'verbose_name_plural': '需求RAG片段',
                'db_table': 'ai_requirement_requirement_chunk',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='requirementchunk',
            index=models.Index(fields=['content_type'], name='ai_req_chunk_content_idx'),
        ),
        migrations.AddIndex(
            model_name='requirementchunk',
            index=models.Index(fields=['task_id'], name='ai_req_chunk_task_id_idx'),
        ),
    ]
