# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "创建/更新 ai_testcase 事件清理的 Celery Beat 周期任务（终态事件按天清理）"

    def handle(self, *args, **options):
        from django_celery_beat.models import CrontabSchedule, PeriodicTask, PeriodicTasks

        # 每天凌晨 03:10 运行（避开业务高峰）
        crontab, _ = CrontabSchedule.objects.get_or_create(
            minute="10",
            hour="3",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
        )

        task, created = PeriodicTask.objects.update_or_create(
            name="ai_testcase.cleanup_events_daily",
            defaults={
                "task": "apps.ai_testcase.tasks.cleanup_ai_testcase_events",
                "crontab": crontab,
                "enabled": True,
                "kwargs": "{}",
                "queue": "beat_tasks",
            },
        )

        PeriodicTasks.update_changed()

        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if created else 'Updated'} PeriodicTask: {task.name}"
            )
        )

