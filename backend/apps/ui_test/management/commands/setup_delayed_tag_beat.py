# -*- coding: utf-8 -*-
"""
创建「提测延期标签同步」的 Celery Beat 定时任务：每天 10:40 执行。
执行一次即可：python manage.py setup_delayed_tag_beat
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "创建/更新提测延期标签同步定时任务（每天 10:40）"

    def handle(self, *args, **options):
        try:
            from django_celery_beat.models import CrontabSchedule, PeriodicTask
        except ImportError:
            self.stderr.write("需要安装 django-celery-beat")
            return

        task_name = "apps.ui_test.tasks.requirement_tasks.sync_delayed_requirement_tags"
        label = "需求管理-提测延期标签同步"

        # 10:40 = minute=40, hour=10（改时间后重跑本命令会更新同一条任务）
        crontab, _ = CrontabSchedule.objects.get_or_create(
            minute="10",
            hour="00",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone="Asia/Shanghai",
        )
        task, created = PeriodicTask.objects.update_or_create(
            name=label,
            defaults={
                "task": task_name,
                "crontab": crontab,
                "enabled": True,
                "queue": "beat_tasks",
                "last_run_at": None,  # 让 Beat 重新计算“下次运行”时间
            },
        )
        from django_celery_beat.models import PeriodicTasks
        PeriodicTasks.update_changed()  # 通知已运行的 Beat 重新加载 schedule
        if created:
            self.stdout.write(self.style.SUCCESS(f"已创建定时任务: {label}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"已更新定时任务: {label}"))
        h, m = str(crontab.hour), str(crontab.minute)
        if m.isdigit():
            m = m.zfill(2)
        self.stdout.write(f"  执行时间: 每天 {h}:{m} (Asia/Shanghai)")
        self.stdout.write(f"  Task: {task_name}")
        self.stdout.write(self.style.WARNING("  若 Beat 已在运行，需重启 Beat 后新时间才会生效。"))
