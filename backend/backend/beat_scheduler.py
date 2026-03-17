# -*- coding: utf-8 -*-
"""
自定义 Beat 调度器：修复 USE_TZ=False 时“上次运行”被当成 UTC 导致下次运行算到明天的问题，
并取消“小时窗口”排除，避免 Crontab 任务到点不触发。
"""
import datetime
from django.conf import settings
from django.db.models import Q
from django.utils import timezone as django_tz
from django_celery_beat.schedulers import DatabaseScheduler, ModelEntry
from django_celery_beat.utils import now
from celery import schedules


class WorkmindModelEntry(ModelEntry):
    """
    当 USE_TZ=False 时，DB 的 last_run_at/date_changed 是 naive 本地时间，
    但 maybe_make_aware 会把 naive 当 UTC，导致“下次运行”被算到明天。此处将 naive 按项目时区解释。
    """

    def is_due(self):
        if not self.model.enabled:
            return schedules.schedstate(False, 5.0)
        if self.model.start_time is not None:
            now_ = self._default_now()
            if getattr(settings, "DJANGO_CELERY_BEAT_TZ_AWARE", True):
                from celery.utils.time import maybe_make_aware
                now_ = maybe_make_aware(now_)
            if now_ < self.model.start_time:
                tz = now_.tzinfo
                start_time = self.model.due_start_time(tz)
                import math
                delay = math.ceil((start_time - now_).total_seconds())
                return schedules.schedstate(False, delay)
        if self.model.expires is not None:
            now_ = self._default_now()
            if now_ >= self.model.expires:
                self._disable(self.model)
                from django_celery_beat.utils import NEVER_CHECK_TIMEOUT
                return schedules.schedstate(False, NEVER_CHECK_TIMEOUT)
        if self.model.one_off and self.model.enabled and self.model.total_run_count > 0:
            self.model.enabled = False
            self.model.total_run_count = 0
            self.model.no_changes = False
            self.model.save()
            from django_celery_beat.utils import NEVER_CHECK_TIMEOUT
            return schedules.schedstate(False, NEVER_CHECK_TIMEOUT)

        tz = self.app.timezone
        last = self.last_run_at
        # USE_TZ=False 时 DB 存的是本地时间（naive），按项目时区解释，否则会被 maybe_make_aware 当 UTC
        if last is not None and django_tz.is_naive(last):
            if getattr(settings, "USE_TZ", True):
                last_in_tz = django_tz.make_aware(last, django_tz.get_default_timezone()).astimezone(tz)
            else:
                try:
                    from zoneinfo import ZoneInfo
                except ImportError:
                    from backports.zoneinfo import ZoneInfo
                local_tz = ZoneInfo(getattr(settings, "TIME_ZONE", "UTC"))
                last_in_tz = last.replace(tzinfo=local_tz).astimezone(tz)
        else:
            from celery.utils.time import maybe_make_aware
            last_in_tz = maybe_make_aware(last).astimezone(tz)
        return self.schedule.is_due(last_in_tz)


class WorkmindDatabaseScheduler(DatabaseScheduler):
    """使用修复 naive 时间的 Entry，且不按“小时窗口”排除 crontab。"""

    Entry = WorkmindModelEntry

    def enabled_models_qs(self):
        from django_celery_beat.models import PeriodicTask

        next_schedule_sync = now() + datetime.timedelta(seconds=300)
        exclude_clock_tasks_query = Q(
            clocked__isnull=False,
            clocked__clocked_time__gt=next_schedule_sync,
        )
        return PeriodicTask.objects.enabled().exclude(exclude_clock_tasks_query)
