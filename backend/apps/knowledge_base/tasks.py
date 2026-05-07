# -*- coding: utf-8 -*-
"""
知识库文档处理 Celery 任务
1. 解析文档（PDF/Word/Excel/图片/文本）—— 在独立子进程中执行，OOM 不影响 worker
2. 分块并生成 Embedding
3. 存入 Qdrant
4. AI 生成文档摘要和标签
"""
import json
import logging
import os
import subprocess
import sys
import tempfile

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


def _parse_document_in_subprocess(file_path: str, file_type: str,
                                   api_key: str, base_url: str, model: str,
                                   timeout: int = 300) -> list[dict]:
    """
    在独立子进程中解析文档，子进程 OOM/崩溃不会污染 Celery worker 主进程内存。
    结果通过临时 JSON 文件传回。
    """
    out_fd, out_path = tempfile.mkstemp(suffix=".json")
    os.close(out_fd)

    # 找到 backend 目录（manage.py 所在目录）
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # document_parser.py 是纯 Python 模块，不依赖 Django ORM/settings，
    # 直接按文件路径导入即可，避免 django.setup() 加载所有 App 导致内存暴涨。
    parser_path = os.path.join(
        backend_dir, "apps", "knowledge_base", "services", "document_parser.py"
    )
    script = f"""
import sys, os, json, importlib.util

spec = importlib.util.spec_from_file_location("document_parser", {json.dumps(parser_path)})
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

chunks = mod.parse_document(
    file_path={json.dumps(file_path)},
    file_type={json.dumps(file_type)},
    api_key={json.dumps(api_key)},
    base_url={json.dumps(base_url)},
    model={json.dumps(model)},
)
with open({json.dumps(out_path)}, 'w', encoding='utf-8') as _f:
    json.dump(chunks, _f, ensure_ascii=False)
"""

    script_fd, script_path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(script_fd, "w", encoding="utf-8") as sf:
            sf.write(script)

        proc = subprocess.run(
            [sys.executable, script_path],
            timeout=timeout,
            capture_output=True,
        )

        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"解析子进程异常退出(code={proc.returncode}): {stderr[-500:]}")

        with open(out_path, "r", encoding="utf-8") as f:
            return json.load(f)

    finally:
        for p in (script_path, out_path):
            try:
                os.unlink(p)
            except OSError:
                pass


def _summarize_document(chunks: list[dict], title: str, api_key: str, base_url: str, model: str) -> tuple[str, list[str]]:
    """使用 AI 生成文档摘要和标签"""
    if not chunks or not api_key:
        return "", []
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)

        # 取前3块拼接作为摘要输入
        sample = "\n\n".join(c["content"] for c in chunks[:3])[:3000]

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": f"""请对以下文档内容生成：
1. 一段100字以内的摘要
2. 3-8个关键标签（如：登录、支付、测试用例、需求等）

文档标题：{title}
文档内容（节选）：
{sample}

请按以下格式返回：
摘要：xxx
标签：标签1,标签2,标签3""",
                }
            ],
            max_tokens=300,
        )

        content = response.choices[0].message.content or ""
        summary = ""
        tags = []
        for line in content.strip().split("\n"):
            if line.startswith("摘要："):
                summary = line[3:].strip()
            elif line.startswith("标签："):
                tags = [t.strip() for t in line[3:].split(",") if t.strip()]
        return summary, tags
    except Exception as e:
        logger.warning(f"[knowledge_base] summarize failed: {e}")
        return "", []


@shared_task(queue="work_queue", bind=True, max_retries=3, default_retry_delay=30)
def process_knowledge_document(self, doc_id: int):
    """
    处理知识库文档的主任务：解析 → 分块 → 向量化 → 存储
    """
    from apps.knowledge_base.models import KnowledgeDocument
    from apps.knowledge_base.services.document_parser import detect_file_type
    from apps.knowledge_base.services.qdrant_service import get_embeddings_batch, upsert_chunks, ensure_collection

    try:
        doc = KnowledgeDocument.objects.get(id=doc_id)
    except KnowledgeDocument.DoesNotExist:
        logger.error(f"[knowledge_base] doc {doc_id} not found")
        return

    doc.status = "processing"
    doc.error_message = ""
    doc.save(update_fields=["status", "error_message"])

    api_key = getattr(settings, "KIMI_API_KEY", "")
    base_url = getattr(settings, "KIMI_BASE_URL", "https://api.moonshot.ai/v1")
    model = getattr(settings, "KIMI_MODEL", "moonshot-v1-8k")

    try:
        file_path = doc.file.path if doc.file else None
        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        file_type = doc.file_type or detect_file_type(doc.file_name or "")

        # 1. 解析文档（子进程隔离，防止大文件 OOM 污染 worker 主进程）
        logger.info(f"[knowledge_base] parsing doc {doc_id}: {file_type}")
        raw_chunks = _parse_document_in_subprocess(
            file_path=file_path,
            file_type=file_type,
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=300,
        )

        if not raw_chunks:
            raise ValueError("文档内容为空，无法解析")

        # 2. 批量生成 Embedding（每批 32 条，大幅减少 API 请求次数）
        logger.info(f"[knowledge_base] embedding {len(raw_chunks)} chunks for doc {doc_id} (batch mode)")
        ensure_collection()

        texts = [chunk["content"] for chunk in raw_chunks]
        embeddings = get_embeddings_batch(texts, batch_size=32)

        chunks_with_emb = []
        for idx, (chunk, emb) in enumerate(zip(raw_chunks, embeddings)):
            chunks_with_emb.append({
                "chunk_index": idx,
                "content": chunk["content"],
                "embedding": emb,
                "page_num": chunk.get("page_num"),
                "has_image": chunk.get("has_image", False),
                "chunk_level": chunk.get("chunk_level", "large"),
                "parent_chunk_index": chunk.get("parent_chunk_index"),
            })

        # 3. 存入向量库
        saved = upsert_chunks(doc_id=doc_id, chunks=chunks_with_emb)
        logger.info(f"[knowledge_base] upserted {saved} chunks for doc {doc_id}")

        # 4. AI 生成摘要和标签
        summary, tags = _summarize_document(raw_chunks, doc.title, api_key, base_url, model)

        # 5. 更新文档状态
        doc.status = "ready"
        doc.chunk_count = len(chunks_with_emb)
        doc.summary = summary
        doc.tags = tags
        doc.save(update_fields=["status", "chunk_count", "summary", "tags"])
        logger.info(f"[knowledge_base] doc {doc_id} processed: {len(chunks_with_emb)} chunks")

    except Exception as e:
        logger.error(f"[knowledge_base] process_document failed for doc {doc_id}: {e}")
        # Qdrant 连接失败或 503 启动中时触发重试（最多3次，间隔30秒）
        is_qdrant_error = (
            "Qdrant" in str(e)
            or "ConnectionError" in type(e).__name__
            or "503" in str(e)
            or "Service Unavailable" in str(e)
            or "Unexpected Response" in str(e)
        )
        if is_qdrant_error:
            try:
                raise self.retry(exc=e)
            except self.MaxRetriesExceededError:
                pass
        doc.status = "failed"
        doc.error_message = str(e)[:500]
        doc.save(update_fields=["status", "error_message"])


@shared_task(queue="work_queue")
def save_generated_cases_to_knowledge(generation_id: int, title: str = "", category: str = "generated"):
    """
    将 AI 生成的测试用例保存到知识库
    """
    from apps.ai_testcase.models import AiTestcaseGeneration
    from apps.knowledge_base.models import KnowledgeDocument
    from apps.knowledge_base.services.document_parser import _split_text
    from apps.knowledge_base.services.qdrant_service import get_embedding, upsert_chunks, ensure_collection
    import json

    try:
        gen = AiTestcaseGeneration.objects.get(id=generation_id)
    except Exception:
        return

    if not gen.result_json:
        return

    doc_title = title or f"AI生成用例-{gen.id}"
    content = json.dumps(gen.result_json, ensure_ascii=False, indent=2)

    doc = KnowledgeDocument.objects.create(
        title=doc_title,
        category=category,
        file_type="txt",
        status="processing",
        created_by=gen.created_by if hasattr(gen, "created_by") else None,
    )

    try:
        raw_chunks = _split_text(content)
        ensure_collection()

        chunks_with_emb = []
        for idx, chunk_text in enumerate(raw_chunks):
            emb = get_embedding(chunk_text)
            chunks_with_emb.append({
                "chunk_index": idx,
                "content": chunk_text,
                "embedding": emb,
                "page_num": None,
                "has_image": False,
            })

        upsert_chunks(doc_id=doc.id, chunks=chunks_with_emb)

        doc.status = "ready"
        doc.chunk_count = len(chunks_with_emb)
        doc.summary = f"AI生成测试用例，共{gen.case_count or 0}条用例"
        doc.save(update_fields=["status", "chunk_count", "summary"])
    except Exception as e:
        doc.status = "failed"
        doc.error_message = str(e)[:500]
        doc.save(update_fields=["status", "error_message"])
