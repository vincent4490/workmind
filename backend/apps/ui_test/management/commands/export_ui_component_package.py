# -*- coding: utf-8 -*-
import json
import os
from datetime import datetime

import yaml
from django.core.management.base import BaseCommand, CommandError

from apps.ui_test.models import UiComponentDefinition

class Command(BaseCommand):
    help = "导出当前 UI 组件库为组件包文件（JSON/YAML）"

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True, help="输出文件路径（.json/.yaml/.yml）")
        parser.add_argument("--format", choices=["json", "yaml"], default="yaml", help="导出格式")
        parser.add_argument("--name", default="ui-component-pack", help="组件包名称")
        parser.add_argument("--version", default="", help="组件包版本")
        parser.add_argument("--author", default="", help="作者")
        parser.add_argument("--description", default="导出的组件包", help="描述")
        parser.add_argument("--include-disabled", action="store_true", help="包含未启用组件")

    def handle(self, *args, **options):
        output_path = options["output"]
        export_format = options["format"]

        if not output_path:
            raise CommandError("必须指定 --output")

        output_dir = os.path.dirname(os.path.abspath(output_path))
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        queryset = UiComponentDefinition.objects.all()
        if not options["include_disabled"]:
            queryset = queryset.filter(enabled=True)

        components = []
        for item in queryset.order_by("sort_order", "type"):
            components.append({
                "type": item.type,
                "name": item.name,
                "category": item.category,
                "description": item.description,
                "schema": item.schema or {},
                "default_config": item.default_config or {},
                "enabled": item.enabled,
                "sort_order": item.sort_order,
            })

        manifest = {
            "name": options["name"],
            "version": options["version"] or datetime.now().strftime("%Y.%m.%d"),
            "description": options["description"],
            "author": options["author"],
            "components": components,
        }

        if export_format == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
        else:
            with open(output_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(manifest, f, allow_unicode=True, sort_keys=False)

        self.stdout.write(self.style.SUCCESS(f"组件包已导出: {output_path}"))