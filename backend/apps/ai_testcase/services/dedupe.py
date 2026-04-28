# -*- coding: utf-8 -*-
"""
确定性去重/轻量参数化（Phase 1）

目标：
- 不破坏 XMindBuilder 依赖的核心字段（name/priority/precondition/steps/expected）
- 优先使用模型输出的 dedupe_key；缺失时用启发式 key
- 同一 key 的重复用例：保留 1 条代表，其余合并为“参数化数据集”说明（写入 expected）
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


_WS_RE = re.compile(r"\s+")


def _norm_text(v: Any) -> str:
    s = "" if v is None else str(v)
    s = s.strip()
    s = _WS_RE.sub(" ", s)
    return s


def _guess_expected_class(expected: str) -> str:
    e = _norm_text(expected).lower()
    if any(k in e for k in ["错误", "失败", "invalid", "error", "forbidden", "unauthorized"]):
        return "error"
    if any(k in e for k in ["成功", "ok", "success", "通过"]):
        return "ok"
    return "other"


def _infer_dedupe_key(case: dict, *, module: str, function: str) -> str:
    dk = _norm_text(case.get("dedupe_key"))
    if dk:
        return dk
    scenario = _norm_text(case.get("scenario_type")) or "general"
    expected_class = _guess_expected_class(case.get("expected", ""))
    # 使用 expected 的前 80 字符避免超长 key
    expected_sig = _norm_text(case.get("expected", ""))[:80]
    return f"{module}|{function}|{scenario}|{expected_class}|{expected_sig}"


def _has_any(text: str, words: list[str]) -> bool:
    return any(w in text for w in words)


def _semantic_signature(case: dict, *, module: str, function: str) -> str | None:
    """
    高置信跨模块语义签名。

    只覆盖很明确、低误删风险的重复动作；模糊场景仍交给评审/人工处理。
    """
    text = _norm_text(" ".join([
        module,
        function,
        case.get("name", ""),
        case.get("steps", ""),
        case.get("expected", ""),
        case.get("dedupe_key", ""),
    ])).lower()

    negative_markers = ["失败", "异常", "不可见", "隐藏", "权限", "未登录", "丢失", "超时", "取消"]

    # 升级入口点击后跳转定价/套餐页的成功场景。
    if (
        "升级" in text
        and _has_any(text, ["定价", "套餐", "订阅", "付费"])
        and _has_any(text, ["跳转", "打开", "进入", "访问", "加载"])
        and not _has_any(text, negative_markers)
    ):
        return "upgrade_entry|navigate|pricing_page|success"

    # 退出登录成功执行场景。排除 token/API/后退/刷新/多端等安全专项验证，避免误删。
    logout_negative = negative_markers + ["token", "api", "后退", "刷新", "多端", "重复", "网络"]
    if (
        _has_any(text, ["退出登录", "登出", "注销登录"])
        and _has_any(text, ["成功", "清除", "清理", "跳转", "未登录", "登录页"])
        and not _has_any(text, logout_negative)
    ):
        return "logout|execute|success"

    return None


def _semantic_rank(signature: str, entry: dict) -> tuple[int, int, int, int]:
    """选择更适合作为代表的用例：专用模块优先，其次高优先级和信息完整度。"""
    module = entry["module"]
    function = entry["function"]
    case = entry["case"]
    text = f"{module} {function} {case.get('name', '')}"

    dedicated = 0
    if signature.startswith("upgrade_entry") and _has_any(text, ["升级", "定价", "套餐"]):
        dedicated = -1
    elif signature.startswith("logout") and _has_any(text, ["退出登录", "登出", "注销"]):
        dedicated = -1

    pr = _norm_text(case.get("priority")) or "P1"
    pr_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(pr, 9)
    coverage_count = len(case.get("coverage_points") or []) if isinstance(case.get("coverage_points"), list) else 0
    detail_len = len(_norm_text(case.get("steps"))) + len(_norm_text(case.get("expected")))
    return (dedicated, pr_rank, -coverage_count, -detail_len)


def _apply_cross_module_semantic_dedupe(modules: list[dict], report: DedupeReport) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    for mod in modules:
        mod_name = _norm_text(mod.get("name")) or "模块"
        for func in mod.get("functions", []) or []:
            if not isinstance(func, dict):
                continue
            func_name = _norm_text(func.get("name")) or "功能点"
            for case in func.get("cases", []) or []:
                if not isinstance(case, dict):
                    continue
                sig = _semantic_signature(case, module=mod_name, function=func_name)
                if sig:
                    buckets.setdefault(sig, []).append({
                        "module": mod_name,
                        "function": func_name,
                        "case": case,
                    })

    remove_case_ids: set[int] = set()
    semantic_removed = []
    for sig, entries in buckets.items():
        if len(entries) <= 1:
            continue
        ranked = sorted(entries, key=lambda e: _semantic_rank(sig, e))
        keeper = ranked[0]
        removed = ranked[1:]
        keeper_case = keeper["case"]
        merged_lines = []
        for item in removed:
            case = item["case"]
            remove_case_ids.add(id(case))
            semantic_removed.append({
                "signature": sig,
                "removed": {
                    "module": item["module"],
                    "function": item["function"],
                    "case_name": _norm_text(case.get("name")),
                },
                "kept": {
                    "module": keeper["module"],
                    "function": keeper["function"],
                    "case_name": _norm_text(keeper_case.get("name")),
                },
            })
            merged_lines.append(
                f"- [{item['module']} / {item['function']}] {_norm_text(case.get('name'))}"
            )

        if merged_lines:
            base_expected = _norm_text(keeper_case.get("expected"))
            keeper_case["expected"] = (
                base_expected
                + ("\n" if base_expected else "")
                + "【跨模块语义去重合并】\n"
                + "\n".join(merged_lines)
            ).strip()

    if not remove_case_ids:
        return modules

    for mod in modules:
        for func in mod.get("functions", []) or []:
            if not isinstance(func, dict):
                continue
            cases = func.get("cases")
            if isinstance(cases, list):
                func["cases"] = [c for c in cases if id(c) not in remove_case_ids]

        mod["functions"] = [
            f for f in (mod.get("functions", []) or [])
            if isinstance(f, dict) and f.get("cases")
        ]

    modules = [m for m in modules if isinstance(m, dict) and m.get("functions")]
    removed_count = len(remove_case_ids)
    report.removed_as_duplicates += removed_count
    report.merged_as_parameterized += removed_count
    report.after_count = max(0, report.after_count - removed_count)

    # 透传额外报告字段，便于前端/日志解释“为什么少了用例”。
    report.semantic_removed = semantic_removed  # type: ignore[attr-defined]
    return modules


@dataclass
class DedupeReport:
    before_count: int = 0
    after_count: int = 0
    merged_as_parameterized: int = 0
    removed_as_duplicates: int = 0

    def to_dict(self) -> dict:
        data = {
            "before_count": self.before_count,
            "after_count": self.after_count,
            "merged_to_parameterized": self.merged_as_parameterized,
            "removed_as_duplicates": self.removed_as_duplicates,
            "notes": [
                "优先使用 dedupe_key；缺失则使用启发式 key（模块/功能点/场景/预期类别/预期摘要）",
                "同 key 重复用例合并为参数化说明（写入 expected），保留 1 条代表用例",
                "对升级入口跳转、退出登录成功执行等高置信场景执行跨模块语义去重",
            ],
        }
        semantic_removed = getattr(self, "semantic_removed", None)
        if semantic_removed:
            data["semantic_removed"] = semantic_removed
        return data


def dedupe_result_json(data: dict, *, mode: str = "comprehensive") -> tuple[dict, dict]:
    """
    对 result_json 做确定性去重。

    Returns:
      (new_data, dedupe_report_dict)
    """
    if not isinstance(data, dict):
        return data, {}
    modules = data.get("modules")
    if not isinstance(modules, list):
        return data, {}

    report = DedupeReport()
    new_modules = []

    for mod in modules:
        if not isinstance(mod, dict):
            continue
        mod_name = _norm_text(mod.get("name")) or "模块"
        functions = mod.get("functions")
        if not isinstance(functions, list):
            new_modules.append(mod)
            continue

        new_funcs = []
        for func in functions:
            if not isinstance(func, dict):
                continue
            func_name = _norm_text(func.get("name")) or "功能点"
            cases = func.get("cases")
            if not isinstance(cases, list) or not cases:
                new_funcs.append(func)
                continue

            report.before_count += len(cases)
            buckets: dict[str, list[dict]] = {}
            for c in cases:
                if not isinstance(c, dict):
                    continue
                key = _infer_dedupe_key(c, module=mod_name, function=func_name)
                buckets.setdefault(key, []).append(c)

            new_cases = []
            for key, group in buckets.items():
                if not group:
                    continue

                # 代表用例：优先 P0/P1，其次 steps/expected 更完整
                def _rank(x: dict) -> tuple[int, int, int]:
                    pr = _norm_text(x.get("priority")) or "P1"
                    pr_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(pr, 9)
                    steps_len = len(_norm_text(x.get("steps")))
                    exp_len = len(_norm_text(x.get("expected")))
                    return (pr_rank, -steps_len, -exp_len)

                group_sorted = sorted(group, key=_rank)
                base = dict(group_sorted[0])
                base.setdefault("dedupe_key", key)

                if len(group_sorted) > 1:
                    # 聚焦模式更强去重：全部合并为参数化说明
                    others = group_sorted[1:]
                    report.merged_as_parameterized += len(others)
                    merged_lines = []
                    for i, o in enumerate(others, start=1):
                        nm = _norm_text(o.get("name")) or f"重复用例{i}"
                        pre = _norm_text(o.get("precondition"))
                        st = _norm_text(o.get("steps"))
                        ex = _norm_text(o.get("expected"))
                        sig = "；".join([s for s in [pre and f"前置:{pre}", st and f"步骤:{st[:60]}", ex and f"预期:{ex[:60]}"] if s])
                        merged_lines.append(f"- {nm}{('（' + sig + '）') if sig else ''}")

                    hint_title = "【参数化/合并】"
                    if (mode or "").lower() == "focused":
                        hint_title = "【合并同类场景】"

                    extra = "\n".join([hint_title, *merged_lines])
                    base_expected = _norm_text(base.get("expected"))
                    base["expected"] = (base_expected + ("\n" if base_expected else "") + extra).strip()

                new_cases.append(base)

            report.after_count += len(new_cases)
            new_func = dict(func)
            new_func["cases"] = new_cases
            new_funcs.append(new_func)

        new_mod = dict(mod)
        new_mod["functions"] = new_funcs
        new_modules.append(new_mod)

    new_data = dict(data)
    new_modules = _apply_cross_module_semantic_dedupe(new_modules, report)
    new_data["modules"] = new_modules

    meta = new_data.get("_meta") if isinstance(new_data.get("_meta"), dict) else {}
    meta = dict(meta)
    meta["dedupe_report"] = report.to_dict()
    new_data["_meta"] = meta

    return new_data, report.to_dict()

