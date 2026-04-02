# -*- coding: utf-8 -*-
"""
RAG 长期记忆（P2-4）：历史 PRD / 术语表向量检索

- 成功任务落库后索引为 RequirementChunk（embedding 存 JSONField）
- 生成前按用户输入做相似度检索，将 top-k 片段注入 system prompt
"""
import logging
import math
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


def _embedding_client():
    """若已配置 OpenAI API Key 且 RAG 开启，返回用于调 embedding 的 client（同步）。"""
    if not getattr(settings, "AI_REQUIREMENT_RAG_ENABLED", False):
        return None
    key = getattr(settings, "OPENAI_API_KEY", "") or ""
    if not key.strip():
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=key)
    except Exception as e:
        logger.warning("RAG: OpenAI client init failed: %s", e)
        return None


def get_embedding(text: str) -> Optional[list[float]]:
    """对单段文本求 embedding；未配置或失败返回 None。"""
    if not text or not text.strip():
        return None
    client = _embedding_client()
    if not client:
        return None
    model = getattr(settings, "AI_REQUIREMENT_EMBEDDING_MODEL", "text-embedding-3-small")
    max_chars = getattr(settings, "AI_REQUIREMENT_RAG_MAX_CHARS", 8000)
    t = (text.strip()[:max_chars]) if max_chars else text.strip()
    try:
        r = client.embeddings.create(input=[t], model=model)
        if r.data and len(r.data) > 0:
            return r.data[0].embedding
    except Exception as e:
        logger.warning("RAG: embedding create failed: %s", e)
    return None


def _cosine_sim(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


def index_task(task_id: int) -> int:
    """
    将任务内容索引为 RAG 片段。仅处理 status=success 且有 result_md 或 result_json 的任务。
    返回写入的 chunk 数量；RAG 未开启或无 embedding 时返回 0。
    """
    from apps.ai_requirement.models import AiRequirementTask, RequirementChunk

    if not getattr(settings, "AI_REQUIREMENT_RAG_ENABLED", False):
        return 0
    try:
        task = AiRequirementTask.objects.get(id=task_id)
    except AiRequirementTask.DoesNotExist:
        return 0
    if task.status != "success":
        return 0

    # 避免重复索引：该任务已存在 chunk 则跳过
    if RequirementChunk.objects.filter(task_id=task_id).exists():
        return 0

    chunks_to_save = []
    # 1) 全文：result_md 或 result_json 中的 Markdown（含 prd_refine 的 updated_prd.markdown_full）
    content_text = None
    content_type = "other"
    if task.task_type == "prd_draft":
        content_type = "prd_full"
    if task.task_type == "prd_refine":
        content_type = "prd_full"
    if task.result_md and task.result_md.strip():
        content_text = task.result_md.strip()
    elif task.result_json and isinstance(task.result_json, dict):
        from apps.ai_requirement.services.schemas import extract_prd_markdown_from_result_json

        content_text = extract_prd_markdown_from_result_json(task.result_json)
    if content_text:
        chunks_to_save.append((content_type, content_text))

    # 2) 术语表：根级 glossary 或需求完善 updated_prd.glossary
    if task.result_json and isinstance(task.result_json, dict):
        rj = task.result_json
        glossary = rj.get("glossary")
        if not glossary and isinstance(rj.get("updated_prd"), dict):
            glossary = rj["updated_prd"].get("glossary")
        if isinstance(glossary, dict) and glossary:
            lines = [f"{k}: {v}" for k, v in glossary.items()]
            if lines:
                chunks_to_save.append(("glossary", "\n".join(lines)))

    if not chunks_to_save:
        return 0

    created = 0
    for ctype, ctext in chunks_to_save:
        emb = get_embedding(ctext)
        RequirementChunk.objects.create(
            task_id=task_id,
            content_type=ctype,
            content_text=ctext[: getattr(settings, "AI_REQUIREMENT_RAG_MAX_CHARS", 8000)],
            embedding=emb,
        )
        created += 1
    return created


def get_rag_context(
    query: str,
    task_type: Optional[str] = None,
    top_k: Optional[int] = None,
) -> str:
    """
    根据 query 检索最相似的 RAG 片段，拼成一段「参考上下文」字符串。
    RAG 未开启或无数据时返回空字符串。供 agent_router 注入 system prompt。
    """
    if not query or not query.strip():
        return ""
    if not getattr(settings, "AI_REQUIREMENT_RAG_ENABLED", False):
        return ""
    top_k = top_k or getattr(settings, "AI_REQUIREMENT_RAG_TOP_K", 5)
    q_emb = get_embedding(query)
    if not q_emb:
        return ""

    from apps.ai_requirement.models import RequirementChunk

    qs = RequirementChunk.objects.filter(embedding__isnull=False).exclude(embedding=[])
    # 可选：按 content_type 与 task_type 对齐（如 prd_draft 时只看 prd_full/glossary）
    if task_type == "prd_draft":
        qs = qs.filter(content_type__in=("prd_full", "glossary"))
    chunks = list(qs.order_by("-created_at")[: 200])  # 最多取 200 条再算相似度，避免全表
    if not chunks:
        return ""

    scored = []
    for c in chunks:
        emb = c.embedding
        if not emb or len(emb) != len(q_emb):
            continue
        score = _cosine_sim(q_emb, emb)
        scored.append((score, c.content_text))
    scored.sort(key=lambda x: -x[0])
    top = scored[:top_k]
    if not top:
        return ""
    parts = [f"- {(text[:1500] + '...' if len(text) > 1500 else text)}" for _, text in top]
    return "## 参考：历史需求/PRD 片段\n\n" + "\n\n".join(parts)
