# -*- coding: utf-8 -*-
"""
查看「提测延期标签同步」定时任务在 Beat 中的下次运行时间，用于排查到点不触发。
用法：python manage.py show_delayed_tag_beat_next_run
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "查看提测延期标签同步定时任务的下次运行时间（供排查 Beat 不触发）"

    def handle(self, *args, **options):
        try:
            from django_celery_beat.models import PeriodicTask
            from celery import current_app
            from celery.utils.time import maybe_make_aware
        except ImportError as e:
            self.stderr.write(f"依赖缺失: {e}")
            return

        label = "需求管理-提测延期标签同步"
        try:
            task = PeriodicTask.objects.get(name=label)
        except PeriodicTask.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"未找到定时任务: {label}，请先执行 python manage.py setup_delayed_tag_beat"))
            return

        crontab = getattr(task, "crontab", None)
        if not crontab:
            self.stdout.write(self.style.ERROR("该任务未绑定 Crontab schedule"))
            return

        self.stdout.write(f"任务: {task.name}")
        self.stdout.write(f"  enabled: {task.enabled}")
        self.stdout.write(f"  crontab: minute={crontab.minute}, hour={crontab.hour}, timezone={crontab.timezone}")
        self.stdout.write(f"  last_run_at (DB): {task.last_run_at}")

        app = current_app._get_current_object()
        tz = app.timezone
        # 与 ModelEntry 一致：用 Beat 的“当前时间”
        from django.conf import settings
        if getattr(settings, "DJANGO_CELERY_BEAT_TZ_AWARE", True):
            from datetime import datetime
            now = datetime.now(tz)
        else:
            from datetime import datetime
            import datetime as dt
            now = dt.datetime.utcnow()
        self.stdout.write(f"  Beat 使用的当前时间: {now} (tz={getattr(tz, 'key', tz)})")

        # 与 ModelEntry.is_due 一致：last_run_at 转成 tz 后传给 schedule.is_due
        schedule = crontab.schedule
        last = task.last_run_at or now
        last_in_tz = maybe_make_aware(last).astimezone(tz)
        try:
            is_due, next_run_in_secs = schedule.is_due(last_in_tz)
            from datetime import timedelta
            next_dt = now + timedelta(seconds=next_run_in_secs) if next_run_in_secs else now
            self.stdout.write(self.style.SUCCESS(f"  is_due: {is_due}，{next_run_in_secs:.0f} 秒后下次运行 -> {next_dt}"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  is_due 推算失败: {e}"))

        self.stdout.write("")
        self.stdout.write("若 Beat 到点未触发，请确认：")
        self.stdout.write("  1. 修改时间后已重启 Beat（或等约 5 分钟自动同步）")
        self.stdout.write("  2. Worker 已用 -Q beat_tasks,work_queue 启动")
