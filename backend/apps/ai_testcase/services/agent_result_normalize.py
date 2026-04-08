# -*- coding: utf-8 -*-
"""
Agent 节点 JSON 归一化：兼容旧版字符串列表，补齐 rule_id 等锚点。
"""


def normalize_requirement_analysis(data: dict) -> dict:
    """将需求分析结果规范为带 rule_id / risk_id 的结构，便于去重与覆盖追踪。"""
    if not isinstance(data, dict):
        return data

    def _norm_rules(items, prefix: str):
        out = []
        for i, item in enumerate(items or []):
            if isinstance(item, str):
                out.append({"rule_id": f"{prefix}{i + 1}", "text": item.strip()})
            elif isinstance(item, dict):
                rid = item.get("rule_id") or f"{prefix}{i + 1}"
                txt = item.get("text") or item.get("description") or ""
                row = {"rule_id": str(rid), "text": str(txt).strip()}
                if item.get("risk"):
                    row["risk"] = item["risk"]
                out.append(row)
        return out

    def _norm_risks(items):
        out = []
        for i, item in enumerate(items or []):
            if isinstance(item, str):
                out.append({"risk_id": f"K{i + 1}", "text": item.strip(), "risk": "med"})
            elif isinstance(item, dict):
                rid = item.get("risk_id") or f"K{i + 1}"
                txt = item.get("text") or item.get("description") or ""
                row = {"risk_id": str(rid), "text": str(txt).strip()}
                row["risk"] = item.get("risk", "med")
                out.append(row)
        return out

    for mod in data.get("modules", []) or []:
        if not isinstance(mod, dict):
            continue
        kr = mod.get("key_rules")
        if kr and isinstance(kr[0], str):
            mod["key_rules"] = _norm_rules(kr, "R")
        ra = mod.get("risk_areas")
        if ra and isinstance(ra[0], str):
            mod["risk_areas"] = _norm_risks(ra)

    gr = data.get("global_rules")
    if gr and isinstance(gr[0], str):
        data["global_rules"] = _norm_rules(gr, "G")

    ir = data.get("implied_rules")
    if ir and isinstance(ir[0], str):
        data["implied_rules"] = _norm_rules(ir, "I")

    return data
