# -*- coding: utf-8 -*-
from django.contrib import admin
from .models import KnowledgeDocument, KnowledgeConversation, KnowledgeMessage


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "file_type", "status", "chunk_count", "created_by", "created_at"]
    list_filter = ["category", "status", "file_type"]
    search_fields = ["title", "summary"]
    readonly_fields = ["status", "summary", "chunk_count", "error_message", "created_at", "updated_at"]


@admin.register(KnowledgeConversation)
class KnowledgeConversationAdmin(admin.ModelAdmin):
    list_display = ["title", "created_by", "created_at"]


@admin.register(KnowledgeMessage)
class KnowledgeMessageAdmin(admin.ModelAdmin):
    list_display = ["conversation", "role", "created_at"]
    list_filter = ["role"]
