# -*- coding: utf-8 -*-
"""
统一的“生成模式/用例策略”定义与渲染。

目标：
- direct + agent 共用同一套模式说明块，避免口径漂移
- 不依赖 Django（便于在多处引用）
"""

from __future__ import annotations

from dataclasses import dataclass


def normalize_case_strategy_mode(mode: str | None) -> str:
    m = (mode or "").strip().lower()
    if m == "focused":
        return "focused"
    return "comprehensive"


@dataclass(frozen=True)
class ModePolicy:
    mode: str  # focused|comprehensive
    label_zh: str
    goal: str
    count_rule: str
    coverage_rule: str
    dedupe_rule: str


def get_mode_policy(mode: str | None) -> ModePolicy:
    m = normalize_case_strategy_mode(mode)
    if m == "focused":
        return ModePolicy(
            mode="focused",
            label_zh="FOCUSED（聚焦）",
            goal="高信噪比、可执行；禁止换汤不换药的重复用例。",
            count_rule="按模块风险给出建议预算；不是硬性上下限。覆盖优先，简单模块可少于预算，critical 模块可超过预算。",
            coverage_rule="主流程 + 关键业务规则 + 关键边界/异常；不做穷举矩阵。",
            dedupe_rule="同一覆盖点（rule_id + scenario_type + 预期类别）只保留 1 条代表；仅数据差异请用参数化或合并描述。",
        )
    return ModePolicy(
        mode="comprehensive",
        label_zh="COMPREHENSIVE（全覆盖）",
        goal="尽量覆盖需求中的规则与风险；仍须控制冗余。",
        count_rule="按模块复杂度与风险给出建议预算；不是硬性上下限。覆盖优先，高风险模块可更细，低风险模块不凑数。",
        coverage_rule="主流程 + 异常/边界 + 状态/权限/一致性（按模块适用）。",
        dedupe_rule="允许同 rule_id 多条，但必须 scenario_type 或预期类别不同；否则合并或参数化。",
    )


def render_mode_guide_for_agent(mode: str | None) -> str:
    """给 agent 各节点 system 注入的“模式片段”."""
    p = get_mode_policy(mode)
    return (
        f"\n【用例策略：{p.label_zh}】\n"
        f"- 目标：{p.goal}\n"
        f"- 条数/预算：{p.count_rule}\n"
        f"- 覆盖：{p.coverage_rule}\n"
        f"- 去重：{p.dedupe_rule}\n"
    )


def render_mode_note_for_direct(mode: str | None) -> str:
    """
    给 direct system prompt 用的简短模式说明。
    注意：direct 的覆盖维度仍以原 prompt 的 requirements 为准；条数只作为预算建议。
    """
    p = get_mode_policy(mode)
    if p.mode == "focused":
        return (
            "【聚焦模式】\n"
            "- 目标：少而精，用最小用例集覆盖最大业务风险\n"
            "- 用例预算：根据业务风险动态决定，预算不是硬性上下限，覆盖优先\n"
            "- 覆盖：核心主流程 + 关键业务规则 + 高频异常 + 关键边界\n"
            "- 去重：同类场景优先参数化/合并，禁止堆重复条目\n"
        )
    return (
        "【全覆盖模式】\n"
        "- 目标：尽量不漏重要场景，但禁止低价值重复\n"
        "- 用例预算：根据复杂度与风险动态决定，预算不是硬性上下限，覆盖优先\n"
        "- 覆盖：主流程 + 关键分支 + 常见异常/边界 + 权限/状态（按模块适用）\n"
        "- 去重：同类场景优先参数化/合并，禁止堆重复条目\n"
    )

