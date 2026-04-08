# -*- coding: utf-8 -*-
"""
评审输入压缩（Phase 2）

目标：把大 result_json 压缩为“摘要 + 少量样例”，减少 token、提升评审稳定性。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _s(v: Any) -> str:
    return "" if v is None else str(v).strip()


def _pick_case_sample(case: dict) -> dict:
    """保留评审最有用的最小字段集。"""
    return {
        "name": _s(case.get("name")),
        "priority": _s(case.get("priority")) or "P1",
        "scenario_type": _s(case.get("scenario_type")),
        "dedupe_key": _s(case.get("dedupe_key")),
        "expected": _s(case.get("expected"))[:120],
    }


@dataclass
class CompactResult:
    summary: dict
    sample: dict

    def to_dict(self) -> dict:
        return {"summary": self.summary, "sample": self.sample}


def compact_result_json(
    result_json: dict,
    *,
    max_modules: int = 20,
    max_functions_per_module: int = 20,
    max_cases_per_function: int = 3,
    max_total_sample_cases: int = 80,
) -> CompactResult:
    if not isinstance(result_json, dict):
        return CompactResult(summary={}, sample={})

    title = _s(result_json.get("title"))
    modules = result_json.get("modules") if isinstance(result_json.get("modules"), list) else []

    summary_modules = []
    sample_modules = []

    total_case_count = 0
    sample_case_count = 0

    for mod in modules[:max_modules]:
        if not isinstance(mod, dict):
            continue
        mod_name = _s(mod.get("name"))
        functions = mod.get("functions") if isinstance(mod.get("functions"), list) else []

        sum_funcs = []
        samp_funcs = []

        for func in functions[:max_functions_per_module]:
            if not isinstance(func, dict):
                continue
            func_name = _s(func.get("name"))
            cases = func.get("cases") if isinstance(func.get("cases"), list) else []

            # 统计
            total_case_count += len(cases)

            # 摘要：只保留数量与优先级分布（轻量）
            pr_dist = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
            for c in cases:
                if not isinstance(c, dict):
                    continue
                pr = _s(c.get("priority")) or "P1"
                if pr in pr_dist:
                    pr_dist[pr] += 1
            sum_funcs.append(
                {
                    "name": func_name,
                    "case_count": len(cases),
                    "priority_dist": pr_dist,
                }
            )

            # 样例：每功能点取前 N 条，且总样例数上限
            if cases and sample_case_count < max_total_sample_cases:
                picked = []
                for c in cases[:max_cases_per_function]:
                    if sample_case_count >= max_total_sample_cases:
                        break
                    if isinstance(c, dict):
                        picked.append(_pick_case_sample(c))
                        sample_case_count += 1
                if picked:
                    samp_funcs.append({"name": func_name, "cases": picked})

        summary_modules.append({"name": mod_name, "functions": sum_funcs})
        if samp_funcs:
            sample_modules.append({"name": mod_name, "functions": samp_funcs})

    summary = {
        "title": title,
        "module_count": len(summary_modules),
        "case_count": total_case_count,
        "modules": summary_modules,
    }
    sample = {"title": title, "modules": sample_modules, "sample_case_count": sample_case_count}
    return CompactResult(summary=summary, sample=sample)

