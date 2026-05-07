# -*- coding: utf-8 -*-
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"documents", views.KnowledgeDocumentViewSet, basename="knowledge-document")
router.register(r"conversations", views.KnowledgeConversationViewSet, basename="knowledge-conversation")

urlpatterns = [
    path("", include(router.urls)),
    path("chat-stream/", views.knowledge_chat_stream, name="knowledge-chat-stream"),
]
