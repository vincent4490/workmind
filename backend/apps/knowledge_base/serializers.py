# -*- coding: utf-8 -*-
from rest_framework import serializers
from .models import KnowledgeDocument, KnowledgeConversation, KnowledgeMessage


class KnowledgeDocumentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeDocument
        fields = [
            "id", "title", "category", "file", "file_url", "file_name",
            "file_type", "file_size", "status", "summary", "tags",
            "error_message", "chunk_count", "created_by", "created_by_name",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "status", "summary", "error_message", "chunk_count",
            "created_by", "created_at", "updated_at",
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return getattr(obj.created_by, "name", None) or obj.created_by.username
        return ""

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return ""


class KnowledgeDocumentListSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeDocument
        fields = [
            "id", "title", "category", "file_name", "file_type", "file_size",
            "status", "summary", "tags", "chunk_count",
            "created_by_name", "created_at",
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return getattr(obj.created_by, "name", None) or obj.created_by.username
        return ""


class KnowledgeMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeMessage
        fields = ["id", "role", "content", "sources", "created_at"]
        read_only_fields = ["id", "created_at"]


class KnowledgeConversationSerializer(serializers.ModelSerializer):
    messages = KnowledgeMessageSerializer(many=True, read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeConversation
        fields = [
            "id", "title", "doc_filter", "category_filter",
            "created_by_name", "created_at", "updated_at", "messages",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return getattr(obj.created_by, "name", None) or obj.created_by.username
        return ""


class KnowledgeConversationListSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeConversation
        fields = ["id", "title", "doc_filter", "category_filter", "created_at", "updated_at", "last_message"]

    def get_last_message(self, obj):
        msg = obj.messages.order_by("-created_at").first()
        if msg:
            return {"role": msg.role, "content": msg.content[:100], "created_at": msg.created_at}
        return None
