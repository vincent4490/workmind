# -*- coding: utf-8 -*-
"""
知识库 API 视图
"""
import json
import logging
import os

from django.http import StreamingHttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import KnowledgeDocument, KnowledgeConversation, KnowledgeMessage
from .serializers import (
    KnowledgeDocumentSerializer,
    KnowledgeDocumentListSerializer,
    KnowledgeConversationSerializer,
    KnowledgeConversationListSerializer,
    KnowledgeMessageSerializer,
)
from .services.document_parser import detect_file_type
from .tasks import process_knowledge_document

logger = logging.getLogger(__name__)


class KnowledgeDocumentViewSet(viewsets.ModelViewSet):
    """知识库文档管理"""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = KnowledgeDocument.objects.all()
        category = self.request.query_params.get("category")
        status_filter = self.request.query_params.get("status")
        search = self.request.query_params.get("search")
        if category:
            qs = qs.filter(category=category)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if search:
            qs = qs.filter(title__icontains=search)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return KnowledgeDocumentListSerializer
        return KnowledgeDocumentSerializer

    def perform_create(self, serializer):
        file = self.request.FILES.get("file")
        file_name = ""
        file_type = ""
        file_size = 0

        if file:
            file_name = file.name
            file_type = detect_file_type(file_name)
            file_size = file.size

        doc = serializer.save(
            created_by=self.request.user,
            file_name=file_name,
            file_type=file_type,
            file_size=file_size,
            status="pending",
        )
        # 异步处理文档
        process_knowledge_document.delay(doc.id)

    def perform_destroy(self, instance):
        # 删除文档时同步删除向量
        try:
            from .services.qdrant_service import delete_doc_chunks
            delete_doc_chunks(instance.id)
        except Exception as e:
            logger.warning(f"[knowledge_base] delete vectors failed: {e}")
        instance.delete()

    @action(detail=True, methods=["post"])
    def reprocess(self, request, pk=None):
        """重新处理文档（解析+向量化）"""
        doc = self.get_object()
        if doc.status == "processing":
            return Response({"detail": "文档正在处理中，请稍后"}, status=status.HTTP_400_BAD_REQUEST)
        doc.status = "pending"
        doc.error_message = ""
        doc.save(update_fields=["status", "error_message"])
        process_knowledge_document.delay(doc.id)
        return Response({"detail": "已重新提交处理"})

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """知识库统计信息"""
        from django.db.models import Count, Sum
        stats_data = KnowledgeDocument.objects.values("category").annotate(
            count=Count("id"),
            total_chunks=Sum("chunk_count"),
        )
        ready_count = KnowledgeDocument.objects.filter(status="ready").count()
        total_count = KnowledgeDocument.objects.count()
        return Response({
            "total": total_count,
            "ready": ready_count,
            "by_category": list(stats_data),
        })

    @action(detail=False, methods=["get"])
    def health(self, request):
        """Qdrant 连接健康检查"""
        from .services.qdrant_service import get_qdrant_client, COLLECTION_NAME
        try:
            client = get_qdrant_client()
            info = client.get_collection(COLLECTION_NAME)
            return Response({
                "qdrant": "ok",
                "collection": COLLECTION_NAME,
                "vectors_count": info.vectors_count,
            })
        except Exception as e:
            return Response({"qdrant": "error", "detail": str(e)}, status=503)


class KnowledgeConversationViewSet(viewsets.ModelViewSet):
    """知识库问答会话管理"""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return KnowledgeConversation.objects.filter(
            created_by=self.request.user
        ).prefetch_related("messages")

    def get_serializer_class(self):
        if self.action == "list":
            return KnowledgeConversationListSerializer
        return KnowledgeConversationSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["delete"])
    def clear_messages(self, request, pk=None):
        """清空会话消息"""
        conv = self.get_object()
        conv.messages.all().delete()
        return Response({"detail": "消息已清空"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def knowledge_chat_stream(request):
    """
    知识库 RAG 流式问答（SSE）
    POST /api/knowledge/chat-stream/
    Body: {
        conversation_id: int,   // 可选，新对话可不传
        question: str,
        doc_ids: [int],         // 可选，限定文档范围
        category_filter: [str]  // 可选，限定分类
    }
    """
    import asyncio
    from .services.rag_chat import stream_rag_answer

    data = request.data
    question = (data.get("question") or "").strip()
    if not question:
        return Response({"detail": "问题不能为空"}, status=status.HTTP_400_BAD_REQUEST)

    conversation_id = data.get("conversation_id")
    doc_ids = data.get("doc_ids") or []
    category_filter = data.get("category_filter") or []

    # 获取或创建会话
    if conversation_id:
        try:
            conv = KnowledgeConversation.objects.get(id=conversation_id, created_by=request.user)
        except KnowledgeConversation.DoesNotExist:
            return Response({"detail": "会话不存在"}, status=status.HTTP_404_NOT_FOUND)
    else:
        conv = KnowledgeConversation.objects.create(
            created_by=request.user,
            title=question[:50],
            doc_filter=doc_ids,
            category_filter=category_filter,
        )

    # 获取历史消息
    history = list(conv.messages.values("role", "content").order_by("created_at"))

    # 保存用户消息
    KnowledgeMessage.objects.create(
        conversation=conv,
        role="user",
        content=question,
    )

    def _sse_generator():
        """SSE 事件流生成器"""
        answer_parts = []
        sources = []

        # 先返回会话 ID
        yield f"data: {json.dumps({'type': 'conversation_id', 'conversation_id': conv.id}, ensure_ascii=False)}\n\n"

        async def _run():
            async for event in stream_rag_answer(
                question=question,
                history=history,
                doc_ids=doc_ids if doc_ids else None,
                category_filter=category_filter if category_filter else None,
            ):
                yield event

        loop = asyncio.new_event_loop()

        async def collect():
            nonlocal sources
            async for event in _run():
                if event["type"] == "chunk":
                    answer_parts.append(event["content"])
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                elif event["type"] == "sources":
                    sources = event.get("sources", [])
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                elif event["type"] == "done":
                    yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                elif event["type"] == "error":
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        try:
            gen = collect()
            while True:
                try:
                    chunk = loop.run_until_complete(gen.__anext__())
                    yield chunk
                except StopAsyncIteration:
                    break
        finally:
            loop.close()

        # 保存助手回复
        full_answer = "".join(answer_parts)
        if full_answer:
            KnowledgeMessage.objects.create(
                conversation=conv,
                role="assistant",
                content=full_answer,
                sources=sources,
            )
            # 更新会话时间
            conv.save(update_fields=["updated_at"])

    response = StreamingHttpResponse(
        _sse_generator(),
        content_type="text/event-stream; charset=utf-8",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
