# Generated manually for created_by ownership field

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ai_testcase', '0003_agent_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='aitestcasegeneration',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='ai_testcase_generations',
                to=settings.AUTH_USER_MODEL,
                verbose_name='创建人',
                help_text='记录创建人，用于权限隔离',
            ),
        ),
    ]

