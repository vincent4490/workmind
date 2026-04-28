# -*- coding: utf-8 -*-
"""
Agent 节点生命周期事件（与 LangGraph 解耦）

在节点函数内 await emit_node_start(...) 后，执行器通过 asyncio.Queue 与 graph.astream
合并为统一事件流，使前端在 LLM 调用返回前即可收到「阶段开始」。
"""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
from typing import Optional

_event_queue: ContextVar[Optional[asyncio.Queue]] = ContextVar('agent_event_queue', default=None)


def attach_event_queue(q: asyncio.Queue) -> None:
    _event_queue.set(q)


def detach_event_queue() -> None:
    _event_queue.set(None)


async def emit_node_start(node_name: str) -> None:
    """在节点内、调用 LLM 之前调用，通知「已进入该节点」。"""
    q = _event_queue.get()
    if q is not None:
        await q.put(('node_start', node_name))
