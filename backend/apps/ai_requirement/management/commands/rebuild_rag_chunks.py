# -*- coding: utf-8 -*-
"""
对历史成功任务批量重建 RAG 索引。

用法：
  python manage.py rebuild_rag_chunks
  python manage.py rebuild_rag_chunks --task-type prd_draft --task-type feature_breakdown
  python manage.py rebuild_rag_chunks --since 2025-01-01 --limit 100
  python manage.py rebuild_rag_chunks --clear
  python manage.py rebuild_rag_chunks --dry-run
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from datetime import datetime


class Command(BaseCommand):
    help = "对历史 AiRequirementTask 成功任务批量重建 RAG 索引（RequirementChunk + embedding）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--task-type",
            action="append",
            dest="task_types",
            metavar="TYPE",
            help="只处理指定任务类型，可多次指定（如 --task-type prd_draft --task-type feature_breakdown）",
        )
        parser.add_argument(
            "--since",
            metavar="DATE",
            help="只处理该日期及之后创建的任务，格式 YYYY-MM-DD",
        )
        parser.add_argument(
            "--until",
            metavar="DATE",
            help="只处理该日期之前创建的任务，格式 YYYY-MM-DD",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="重建前先删除该任务已有 chunk，再重新索引（默认跳过已有 chunk 的任务）",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="仅打印将要处理的 task_id，不执行索引",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            metavar="N",
            help="最多处理 N 条任务，0 表示不限制",
        )

    def handle(self, *args, **options):
        if not getattr(settings, "AI_REQUIREMENT_RAG_ENABLED", False):
            self.stderr.write(
                self.style.ERROR("未开启 RAG：请设置 AI_REQUIREMENT_RAG_ENABLED=true")
            )
            return
        key = getattr(settings, "OPENAI_API_KEY", "") or ""
        if not key.strip():
            self.stderr.write(
                self.style.ERROR("未配置 OPENAI_API_KEY，无法生成 embedding")
            )
            return

        from apps.ai_requirement.models import AiRequirementTask, RequirementChunk
        from apps.ai_requirement.services.rag import index_task

        qs = AiRequirementTask.objects.filter(status="success")
        if options.get("task_types"):
            qs = qs.filter(task_type__in=options["task_types"])
        if options.get("since"):
            try:
                since = datetime.strptime(options["since"], "%Y-%m-%d")
                if timezone.is_naive(since):
                    since = timezone.make_aware(since)
                qs = qs.filter(created_at__date__gte=since.date())
            except ValueError:
                self.stderr.write(self.style.ERROR("--since 格式须为 YYYY-MM-DD"))
                return
        if options.get("until"):
            try:
                until = datetime.strptime(options["until"], "%Y-%m-%d")
                if timezone.is_naive(until):
                    until = timezone.make_aware(until)
                qs = qs.filter(created_at__date__lt=until.date())
            except ValueError:
                self.stderr.write(self.style.ERROR("--until 格式须为 YYYY-MM-DD"))
                return
        qs = qs.order_by("id")
        limit = options.get("limit") or 0
        if limit > 0:
            qs = qs[:limit]
        task_ids = list(qs.values_list("id", flat=True))

        if not task_ids:
            self.stdout.write("没有符合条件的历史任务，无需重建。")
            return

        self.stdout.write(f"符合条件任务数: {len(task_ids)}")
        if options.get("dry_run"):
            self.stdout.write("dry-run，将处理的 task_id: " + ", ".join(str(i) for i in task_ids[:50]))
            if len(task_ids) > 50:
                self.stdout.write(f"  ... 等共 {len(task_ids)} 条")
            return

        clear = options.get("clear", False)
        ok, fail = 0, 0
        total_chunks = 0
        for i, task_id in enumerate(task_ids, 1):
            try:
                if clear:
                    RequirementChunk.objects.filter(task_id=task_id).delete()
                n = index_task(task_id)
                if n > 0:
                    ok += 1
                    total_chunks += n
                if i % 50 == 0 or i == len(task_ids):
                    self.stdout.write(f"  进度 {i}/{len(task_ids)}")
            except Exception as e:
                fail += 1
                self.stderr.write(self.style.WARNING(f"task_id={task_id} 失败: {e}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"完成: 已索引 {ok} 个任务、共 {total_chunks} 个 chunk，失败 {fail} 个任务"
            )
        )
