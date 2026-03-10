# P1-2: 评估基线 + 回归检测 + 稳定性指标

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ai_requirement', '0005_requirementchunk'),
    ]

    operations = [
        migrations.AddField(
            model_name='evalrun',
            name='avg_stability',
            field=models.FloatField(blank=True, null=True, verbose_name='稳定性(1-样本准确率标准差)'),
        ),
        migrations.AddField(
            model_name='evalrun',
            name='is_baseline',
            field=models.BooleanField(default=False, verbose_name='是否为基线（用于回归对比）'),
        ),
        migrations.AddField(
            model_name='evalrun',
            name='regression_detected',
            field=models.BooleanField(default=False, verbose_name='是否检测到回归'),
        ),
        migrations.AddField(
            model_name='evalrun',
            name='baseline_run',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='comparison_runs',
                to='ai_requirement.evalrun',
                verbose_name='对比的基线运行',
            ),
        ),
    ]
