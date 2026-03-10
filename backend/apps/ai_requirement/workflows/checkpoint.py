# -*- coding: utf-8 -*-
"""
LangGraph 持久化 Checkpointer（SQLite）

- 进程重启后工作流状态可恢复，支持 resume 继续执行
- 使用 AsyncSqliteSaver 以配合 graph.astream()
- 首次使用会创建表（setup），数据库文件目录自动创建
"""
import logging
import os

from django.conf import settings

logger = logging.getLogger(__name__)

_async_checkpointer = None


def _get_checkpoint_db_path() -> str:
    path = getattr(settings, "LANGGRAPH_CHECKPOINT_DB_PATH", None)
    if path:
        return path
    base = getattr(settings, "BASE_DIR", os.getcwd())
    return os.path.join(base, "data", "langgraph_checkpoints.sqlite")


async def get_async_checkpointer():
    """
    返回单例 AsyncSqliteSaver，供 PRD 工作流与多智能体工作流共用。

    首次调用时创建 DB 文件目录、打开连接并执行 setup()。
    """
    global _async_checkpointer
    if _async_checkpointer is not None:
        return _async_checkpointer

    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    except ImportError:
        logger.warning(
            "langgraph-checkpoint-sqlite 未安装，工作流将使用内存 Checkpointer（重启后不可恢复）。"
            " 安装: pip install langgraph-checkpoint-sqlite"
        )
        from langgraph.checkpoint.memory import MemorySaver
        _async_checkpointer = MemorySaver()
        return _async_checkpointer

    db_path = _get_checkpoint_db_path()
    dirname = os.path.dirname(db_path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)

    # SQLite 连接串：文件路径即可（或 file:path?mode=rwc）
    conn_string = db_path
    _async_checkpointer = AsyncSqliteSaver.from_conn_string(conn_string)
    await _async_checkpointer.__aenter__()
    if hasattr(_async_checkpointer, "setup"):
        import asyncio
        setup_fn = getattr(_async_checkpointer, "setup")
        if asyncio.iscoroutinefunction(setup_fn):
            await setup_fn()
        else:
            await asyncio.to_thread(setup_fn)
    logger.info("LangGraph Checkpointer 已就绪: %s", db_path)
    return _async_checkpointer
