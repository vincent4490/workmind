# -*- coding: utf-8 -*-


def normalize_case_strategy_mode(mode) -> str:
    """将前端/请求中的 mode 规范为 focused 或 comprehensive。"""
    m = (mode or "comprehensive").strip().lower()
    if m == "focused":
        return "focused"
    return "comprehensive"
