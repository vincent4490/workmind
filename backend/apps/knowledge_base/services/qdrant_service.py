# -*- coding: utf-8 -*-
"""
Qdrant 向量存储服务
- Qdrant 为唯一向量存储，不做 MySQL 降级
- 连接失败直接抛出异常，由上层决定如何处理（Celery 任务重试）
"""
import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "workmind_knowledge"

# 不同 Embedding 模型的向量维度
_VECTOR_SIZE_MAP = {
    "moonshot-v1-embedding": 1536,
    "text-embedding-ada-002": 1536,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "BAAI/bge-large-zh-v1.5": 1024,
    "BAAI/bge-m3": 1024,
    "BAAI/bge-large-en-v1.5": 1024,
}


def get_vector_size() -> int:
    model = getattr(settings, "KNOWLEDGE_EMBEDDING_MODEL", "moonshot-v1-embedding")
    return _VECTOR_SIZE_MAP.get(model, 1536)


def get_embeddings_batch(texts: list[str], batch_size: int = 32) -> list[Optional[list[float]]]:
    """
    批量获取 Embedding，每次最多发 batch_size 条，显著减少 API 请求次数。
    返回与 texts 等长的列表，失败项为 None。
    """
    if not texts:
        return []
    api_key = (
        getattr(settings, "KNOWLEDGE_EMBEDDING_KEY", "")
        or getattr(settings, "KIMI_API_KEY", "")
        or getattr(settings, "OPENAI_API_KEY", "")
    )
    base_url = (
        getattr(settings, "KNOWLEDGE_EMBEDDING_BASE_URL", "")
        or getattr(settings, "KIMI_BASE_URL", "https://api.moonshot.cn/v1")
    )
    model = getattr(settings, "KNOWLEDGE_EMBEDDING_MODEL", "moonshot-v1-embedding")
    if not api_key:
        logger.error("[knowledge_base] 未配置 Embedding API Key")
        return [None] * len(texts)

    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)

    results: list[Optional[list[float]]] = [None] * len(texts)
    for start in range(0, len(texts), batch_size):
        batch = [t.strip()[:6000] for t in texts[start:start + batch_size]]
        try:
            resp = client.embeddings.create(input=batch, model=model)
            for item in resp.data:
                results[start + item.index] = item.embedding
        except Exception as e:
            logger.error(f"[knowledge_base] get_embeddings_batch failed (batch {start}): {e}")
    return results


def get_embedding(text: str) -> Optional[list[float]]:
    """对文本求 Embedding 向量，失败返回 None。
    优先读取 KNOWLEDGE_EMBEDDING_KEY / KNOWLEDGE_EMBEDDING_BASE_URL / KNOWLEDGE_EMBEDDING_MODEL，
    未配置则回退到 KIMI_API_KEY + moonshot-v1-embedding。
    """
    if not text or not text.strip():
        return None
    api_key = (
        getattr(settings, "KNOWLEDGE_EMBEDDING_KEY", "")
        or getattr(settings, "KIMI_API_KEY", "")
        or getattr(settings, "OPENAI_API_KEY", "")
    )
    base_url = (
        getattr(settings, "KNOWLEDGE_EMBEDDING_BASE_URL", "")
        or getattr(settings, "KIMI_BASE_URL", "https://api.moonshot.cn/v1")
    )
    model = getattr(settings, "KNOWLEDGE_EMBEDDING_MODEL", "moonshot-v1-embedding")
    if not api_key:
        logger.error("[knowledge_base] 未配置 Embedding API Key，无法生成 Embedding")
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        text = text.strip()[:6000]
        r = client.embeddings.create(input=[text], model=model)
        if r.data:
            return r.data[0].embedding
    except Exception as e:
        logger.error(f"[knowledge_base] get_embedding failed: {e}")
    return None


def get_qdrant_client():
    """
    获取 Qdrant 客户端。
    连接失败直接抛出异常 —— 让调用方（Celery 任务）感知并重试，而不是静默降级。
    """
    host = getattr(settings, "QDRANT_HOST", "localhost")
    port = int(getattr(settings, "QDRANT_PORT", 6333))
    api_key = getattr(settings, "QDRANT_API_KEY", None) or None
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(host=host, port=port, api_key=api_key, timeout=10)
        return client
    except Exception as e:
        raise ConnectionError(f"Qdrant 连接失败 ({host}:{port}): {e}") from e


def ensure_collection():
    """确保 Qdrant 集合存在且维度匹配，否则重建。连接失败直接上抛。"""
    client = get_qdrant_client()
    from qdrant_client.models import VectorParams, Distance
    vector_size = get_vector_size()
    collections = {c.name: c for c in client.get_collections().collections}
    if COLLECTION_NAME in collections:
        # 检查维度是否匹配，不匹配则删除重建
        info = client.get_collection(COLLECTION_NAME)
        existing_size = info.config.params.vectors.size
        if existing_size != vector_size:
            logger.warning(
                f"[knowledge_base] 集合维度不匹配 (existing={existing_size}, "
                f"expected={vector_size})，重建集合"
            )
            client.delete_collection(COLLECTION_NAME)
            collections = {}
    if COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        logger.info(f"[knowledge_base] Qdrant collection '{COLLECTION_NAME}' created (dim={vector_size})")
    return client


def upsert_chunks(doc_id: int, chunks: list[dict]) -> int:
    """
    将文档分块写入 Qdrant。
    chunks: [{chunk_index, content, embedding, page_num, has_image,
              chunk_level("large"|"small"), parent_chunk_index}]
    返回写入成功的数量，连接失败上抛异常。
    """
    client = ensure_collection()
    from qdrant_client.models import PointStruct

    points = []
    for chunk in chunks:
        emb = chunk.get("embedding")
        if not emb:
            continue
        point_id = doc_id * 100000 + chunk["chunk_index"]
        points.append(
            PointStruct(
                id=point_id,
                vector=emb,
                payload={
                    "doc_id": doc_id,
                    "chunk_index": chunk["chunk_index"],
                    "content": chunk["content"],
                    "page_num": chunk.get("page_num"),
                    "has_image": chunk.get("has_image", False),
                    "chunk_level": chunk.get("chunk_level", "large"),
                    "parent_chunk_index": chunk.get("parent_chunk_index"),
                },
            )
        )
    if not points:
        return 0
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    logger.info(f"[knowledge_base] upserted {len(points)} chunks for doc {doc_id}")
    return len(points)


def delete_doc_chunks(doc_id: int):
    """删除文档的所有向量。"""
    client = get_qdrant_client()
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
        ),
    )
    logger.info(f"[knowledge_base] deleted chunks for doc {doc_id}")


def search_chunks(
    query: str,
    doc_ids: Optional[list[int]] = None,
    top_k: int = 5,
) -> list[dict]:
    """
    混合检索：向量搜索（召回 top_k*4）→ BM25 重排序 → 返回 top_k。
    优先返回 small 粒度 chunk（精确）；若 small chunk 命中，同时附带其 large 父块。
    连接失败返回空列表（问答场景允许降级为纯 LLM 回答）。
    """
    query_emb = get_embedding(query)
    if not query_emb:
        return []

    try:
        client = get_qdrant_client()
        from qdrant_client.models import Filter, FieldCondition, MatchAny, MatchValue

        # 基础过滤条件
        must_base = []
        if doc_ids:
            must_base.append(FieldCondition(key="doc_id", match=MatchAny(any=doc_ids)))

        # 先召回更大的候选池（top_k * 4），后续 BM25 重排再裁剪
        candidate_limit = max(top_k * 4, 20)
        query_filter = Filter(must=must_base) if must_base else None

        response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_emb,
            query_filter=query_filter,
            limit=candidate_limit,
            with_payload=True,
        )
        candidates = response.points

        if not candidates:
            return []

        # 构建候选 chunk 列表
        doc_cache: dict = {}
        raw_chunks = []
        for r in candidates:
            payload = r.payload or {}
            doc_id = payload.get("doc_id")
            if doc_id not in doc_cache:
                doc_cache[doc_id] = _get_doc_info(doc_id)
            doc_info = doc_cache[doc_id]
            raw_chunks.append({
                "doc_id": doc_id,
                "chunk_index": payload.get("chunk_index"),
                "content": payload.get("content", ""),
                "page_num": payload.get("page_num"),
                "has_image": payload.get("has_image", False),
                "chunk_level": payload.get("chunk_level", "large"),
                "parent_chunk_index": payload.get("parent_chunk_index"),
                "vector_score": round(float(r.score), 4),
                "doc_title": doc_info.get("title", ""),
                "doc_category": doc_info.get("category", ""),
            })

        # BM25 重排序
        reranked = _bm25_rerank(query, raw_chunks)

        # 去重（相同内容只保留分数最高的）
        seen_content: set = set()
        final_chunks = []
        for chunk in reranked[:top_k * 2]:
            content_key = chunk["content"][:100]
            if content_key not in seen_content:
                seen_content.add(content_key)
                final_chunks.append({
                    "doc_id": chunk["doc_id"],
                    "chunk_index": chunk["chunk_index"],
                    "content": chunk["content"],
                    "page_num": chunk["page_num"],
                    "has_image": chunk["has_image"],
                    "score": chunk["hybrid_score"],
                    "doc_title": chunk["doc_title"],
                    "doc_category": chunk["doc_category"],
                })
            if len(final_chunks) >= top_k:
                break

        return final_chunks

    except Exception as e:
        logger.error(f"[knowledge_base] search_chunks failed: {e}")
        return []


def _bm25_rerank(query: str, chunks: list[dict]) -> list[dict]:
    """
    BM25 重排序：对向量检索候选结果用 BM25 打分，
    最终分 = 0.6 × 归一化向量分 + 0.4 × 归一化 BM25 分
    无需外部依赖，使用字符级 TF-IDF 近似实现。
    """
    if not chunks:
        return chunks

    # 尝试用 rank_bm25，不可用时降级为字符重叠
    contents = [c["content"] for c in chunks]

    try:
        from rank_bm25 import BM25Okapi  
        # 中文字符级分词
        tokenized_corpus = [list(doc) for doc in contents]
        tokenized_query = list(query)
        bm25 = BM25Okapi(tokenized_corpus)
        bm25_scores = bm25.get_scores(tokenized_query)
    except ImportError:
        # 降级：简单字符重叠分数
        query_chars = set(query)
        bm25_scores = [
            len(query_chars & set(c)) / max(len(query_chars), 1)
            for c in contents
        ]

    # 归一化两路分数到 [0, 1]
    v_scores = [c["vector_score"] for c in chunks]
    v_min, v_max = min(v_scores), max(v_scores)
    v_range = v_max - v_min or 1e-9

    b_min, b_max = min(bm25_scores), max(bm25_scores)
    b_range = b_max - b_min or 1e-9

    for i, chunk in enumerate(chunks):
        v_norm = (chunk["vector_score"] - v_min) / v_range
        b_norm = (bm25_scores[i] - b_min) / b_range
        chunk["hybrid_score"] = round(0.6 * v_norm + 0.4 * b_norm, 4)

    return sorted(chunks, key=lambda x: x["hybrid_score"], reverse=True)


def _get_doc_info(doc_id: int) -> dict:
    try:
        from apps.knowledge_base.models import KnowledgeDocument
        doc = KnowledgeDocument.objects.filter(id=doc_id).values("title", "category").first()
        return doc or {}
    except Exception:
        return {}
