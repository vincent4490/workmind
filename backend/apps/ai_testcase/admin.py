# -*- coding: utf-8 -*-
from django.contrib import admin
from .models import AiTestcaseGeneration


@admin.register(AiTestcaseGeneration)
class AiTestcaseGenerationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'created_by', 'requirement_short', 'status', 'generation_mode', 'case_strategy_mode',
        'module_count', 'case_count',
        'total_tokens', 'created_at'
    ]
    list_filter = ['status', 'use_thinking', 'generation_mode', 'case_strategy_mode', 'created_at']
    search_fields = ['requirement']
    readonly_fields = ['result_json', 'raw_content', 'created_at', 'updated_at']
    ordering = ['-created_at']

    def requirement_short(self, obj):
        return obj.requirement[:60] + '...' if len(obj.requirement) > 60 else obj.requirement
    requirement_short.short_description = '需求描述'
