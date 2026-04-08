# -*- coding: utf-8 -*-
"""
Agent 节点生命周期事件（与 LangGraph 解耦）

在节点函数内 await emit_node_start(...) 后，执行器通过 asyncio.Queue 与 graph.astream
合并为统一事件流，使前端在 LLM 调用返回前即可收到「阶段开始」。
"""
from __future__ import annotations

import asyncio
from typing import Optional

_event_queue: Optional[asyncio.Queue] = None


def attach_event_queue(q: asyncio.Queue) -> None:
    global _event_queue
    _event_queue = q


def detach_event_queue() -> None:
    global _event_queue
    _event_queue = None


async def emit_node_start(node_name: str) -> None:
    """在节点内、调用 LLM 之前调用，通知「已进入该节点」。"""
    if _event_queue is not None:
        await _event_queue.put(('node_start', node_name))
