# -*- coding: utf-8 -*-
"""
手动执行「提测/测试延期标签同步」任务（与定时任务逻辑一致）。
用于本地测试：python manage.py run_delayed_tag_sync
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "手动执行提测/测试延期标签同步（测试用）"

    def handle(self, *args, **options):
        from apps.ui_test.tasks.requirement_tasks import sync_delayed_requirement_tags

        self.stdout.write("正在执行提测/测试延期标签同步...")
        result = sync_delayed_requirement_tags()
        if result.get("success"):
            self.stdout.write(
                self.style.SUCCESS(f"完成，更新 {result.get('updated_count', 0)} 条需求")
            )
        else:
            self.stdout.write(self.style.ERROR(f"失败: {result.get('error', '未知错误')}"))
