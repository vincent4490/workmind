# Generated migration: 功能测试用例表重构为 AI 结构，不考虑历史数据

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ai_testcase', '0001_initial'),
        ('ui_test', '0003_add_task_model'),
    ]

    operations = [
        # 新增字段
        migrations.AddField(
            model_name='functionaltestcase',
            name='title',
            field=models.CharField(blank=True, default='', max_length=200, verbose_name='需求名称_测试用例'),
        ),
        migrations.AddField(
            model_name='functionaltestcase',
            name='module_name',
            field=models.CharField(blank=True, default='', max_length=200, verbose_name='模块名称'),
        ),
        migrations.AddField(
            model_name='functionaltestcase',
            name='function_name',
            field=models.CharField(blank=True, default='', max_length=200, verbose_name='功能点名称'),
        ),
        migrations.AddField(
            model_name='functionaltestcase',
            name='precondition',
            field=models.TextField(blank=True, default='', verbose_name='前置条件'),
        ),
        migrations.AddField(
            model_name='functionaltestcase',
            name='steps',
            field=models.TextField(blank=True, default='', verbose_name='测试步骤'),
        ),
        migrations.AddField(
            model_name='functionaltestcase',
            name='expected',
            field=models.TextField(blank=True, default='', verbose_name='预期结果'),
        ),
        migrations.AddField(
            model_name='functionaltestcase',
            name='source',
            field=models.CharField(choices=[('manual', '手动'), ('ai', 'AI导入')], default='manual', max_length=20, verbose_name='来源'),
        ),
        migrations.AddField(
            model_name='functionaltestcase',
            name='ai_generation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='imported_functional_cases', to='ai_testcase.aitestcasegeneration', verbose_name='AI生成记录'),
        ),
        # 删除旧字段
        migrations.RemoveField(model_name='functionaltestcase', name='requirement_name'),
        migrations.RemoveField(model_name='functionaltestcase', name='feature_name'),
        migrations.RemoveField(model_name='functionaltestcase', name='preconditions'),
        migrations.RemoveField(model_name='functionaltestcase', name='test_steps'),
        migrations.RemoveField(model_name='functionaltestcase', name='tags'),
    ]
