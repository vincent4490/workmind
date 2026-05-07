# -*- coding: utf-8 -*-
"""
知识库 RAG 问答服务
- 检索相关文档片段
- 构建 Prompt 并流式调用 Kimi
- 生成引用来源说明
"""
import logging
from typing import Optional, AsyncGenerator

from django.conf import settings

from .qdrant_service import search_chunks

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个专业的知识库问答助手。请根据提供的知识库内容回答用户问题。

要求：
1. 优先基于知识库内容作答，保持客观准确
2. 知识库片段可能是文档局部内容，即使表述不完整，也要尽力从中提取有用信息作答
3. 只有在知识库内容与问题完全无关时，才说明"知识库中暂未收录相关内容"，并给出通用建议
4. 引用具体内容时，自然地说明来源，如"根据文档..."
5. 回答要条理清晰，适当使用列表和标题
6. 如果问题涉及测试用例，可以给出具体的测试步骤和预期结果"""


def _build_context(chunks: list[dict]) -> str:
    """将检索到的文档片段构建为上下文字符串"""
    if not chunks:
        return ""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        title = chunk.get("doc_title", "未知文档")
        page = f"第{chunk['page_num']}页" if chunk.get("page_num") else ""
        location = f"[{title}{' · ' + page if page else ''}]"
        parts.append(f"### 参考片段 {i} {location}\n{chunk['content']}")
    return "\n\n".join(parts)


async def stream_rag_answer(
    question: str,
    history: list[dict],
    doc_ids: Optional[list[int]] = None,
    category_filter: Optional[list[str]] = None,
    top_k: int = 5,
) -> AsyncGenerator[dict, None]:
    """
    RAG 流式问答
    Yields: {"type": "chunk"|"sources"|"done"|"error", ...}
    """
    # 1. 检索相关片段
    try:
        chunks = search_chunks(
            query=question,
            doc_ids=doc_ids if doc_ids else None,
            top_k=top_k,
        )
    except Exception as e:
        logger.error(f"[knowledge_base] search_chunks failed: {e}")
        chunks = []

    # 2. 准备引用来源（仅保留相关度 > 0.3 的）
    sources = [
        {
            "doc_id": c["doc_id"],
            "doc_title": c.get("doc_title", ""),
            "doc_category": c.get("doc_category", ""),
            "content": c["content"][:200],
            "page_num": c.get("page_num"),
            "score": c.get("score", 0),
        }
        for c in chunks
        if c.get("score", 0) > 0.3
    ]

    # 3. 构建 Prompt
    context = _build_context(chunks)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # 注入上下文
    if context:
        messages.append({
            "role": "system",
            "content": f"## 知识库相关内容\n\n{context}\n\n---\n请基于以上内容回答用户问题。",
        })

    # 注入对话历史（最近5轮）
    for h in history[-10:]:
        messages.append({"role": h["role"], "content": h["content"]})

    # 当前问题
    messages.append({"role": "user", "content": question})

    # 4. 流式调用 Kimi
    api_key = getattr(settings, "KIMI_API_KEY", "")
    base_url = getattr(settings, "KIMI_BASE_URL", "https://api.moonshot.ai/v1")
    model = getattr(settings, "KIMI_MODEL", "moonshot-v1-8k")

    if not api_key:
        yield {"type": "error", "message": "未配置 AI API Key"}
        return

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield {"type": "chunk", "content": chunk.choices[0].delta.content}

        # 5. 流式结束后发送来源
        yield {"type": "sources", "sources": sources}
        yield {"type": "done"}

    except Exception as e:
        logger.error(f"[knowledge_base] stream_rag_answer failed: {e}")
        err_str = str(e)
        if "429" in err_str or "overloaded" in err_str:
            msg = "AI 服务当前繁忙，请稍等片刻后重试。"
        elif "401" in err_str or "authentication" in err_str.lower():
            msg = "AI API Key 配置有误，请联系管理员。"
        else:
            msg = "问答服务暂时异常，请稍后重试。"
        yield {"type": "error", "message": msg}
