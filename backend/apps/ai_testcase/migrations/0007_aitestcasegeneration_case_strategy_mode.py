# -*- coding: utf-8 -*-
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_testcase', '0006_p2_events_and_progress'),
    ]

    operations = [
        migrations.AddField(
            model_name='aitestcasegeneration',
            name='case_strategy_mode',
            field=models.CharField(
                choices=[
                    ('comprehensive', '全覆盖'),
                    ('focused', '聚焦'),
                ],
                default='comprehensive',
                max_length=20,
                verbose_name='用例策略模式',
                help_text='与 generation_mode（direct/agent）正交：控制用例条数与去重强度',
            ),
        ),
    ]
