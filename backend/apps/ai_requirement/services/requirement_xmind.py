# -*- coding: utf-8 -*-
"""
需求智能体：将任务 result_json 导出为 XMind（.xmind）
主要支持测试需求分析等结构化结果。
"""
import json
import zipfile
import tempfile
import os
import uuid
import logging

logger = logging.getLogger(__name__)


def _make_id():
    return uuid.uuid4().hex[:26]


def _topic(title, children=None):
    t = {"id": _make_id(), "class": "topic", "title": str(title or "")}
    if children:
        t["children"] = {"attached": children}
    return t


def _build_test_requirement_analysis(data: dict) -> list:
    """从测试需求分析 result_json 构建 topic 子树"""
    nodes = []

    # 可测试性评估
    assessment = data.get("testability_assessment") or []
    if assessment:
        children = []
        for i, item in enumerate(assessment):
            if not isinstance(item, dict):
                continue
            req = item.get("requirement", "")
            testability = item.get("testability", "")
            reason = item.get("reason", "")
            suggestion = item.get("improvement_suggestion", "")
            title = f"{req} [{testability}]" if req else f"项{i+1} [{testability}]"
            sub = [_topic(f"理由: {reason}")]
            if suggestion:
                sub.append(_topic(f"改进建议: {suggestion}"))
            children.append(_topic(title, sub if sub else None))
        nodes.append(_topic("可测试性评估", children))

    # 不可测项
    untestable = data.get("untestable_items") or []
    if untestable:
        children = []
        for item in untestable:
            if isinstance(item, dict):
                title = item.get("item", "")
                reason = item.get("reason", "")
                rec = item.get("recommendation", "")
                sub = [_topic(f"原因: {reason}")]
                if rec:
                    sub.append(_topic(f"建议: {rec}"))
                children.append(_topic(title, sub if sub else None))
            else:
                children.append(_topic(str(item)))
        nodes.append(_topic("不可测项", children))

    # 测试策略
    strategy = data.get("test_strategy")
    if strategy and isinstance(strategy, dict):
        strategy_children = []
        for level in strategy.get("test_levels") or []:
            if isinstance(level, dict):
                strategy_children.append(_topic(
                    level.get("level", "") or "",
                    [_topic(f"覆盖: {level.get('coverage_focus', '')}"), _topic(f"工具: {level.get('tools', '')}")]
                ))
            else:
                strategy_children.append(_topic(str(level)))
        for env in strategy.get("test_environments") or []:
            strategy_children.append(_topic(f"环境: {env}"))
        for data_req in strategy.get("test_data_requirements") or []:
            strategy_children.append(_topic(f"数据: {data_req}"))
        if strategy_children:
            nodes.append(_topic("测试策略", strategy_children))

    # 风险区域
    risks = data.get("risk_areas") or []
    if risks:
        children = []
        for r in risks:
            if isinstance(r, dict):
                area = r.get("area", "")
                risk_type = r.get("risk_type", "")
                approach = r.get("test_approach", "")
                title = f"{area} [{risk_type}]" if area else str(r)
                sub = [_topic(f"测试方法: {approach}")] if approach else []
                children.append(_topic(title, sub) if sub else _topic(title))
            else:
                children.append(_topic(str(r)))
        nodes.append(_topic("风险区域", children))

    # 缺失需求
    missing = data.get("missing_requirements") or []
    if missing:
        nodes.append(_topic("缺失需求", [_topic(m) for m in missing if m]))

    # 测试人日估算
    effort = data.get("estimated_test_effort")
    if effort and isinstance(effort, dict):
        total = effort.get("total_man_days")
        breakdown = effort.get("breakdown") or []
        effort_children = [_topic(f"总人日: {total}")] if total is not None else []
        for b in breakdown:
            if isinstance(b, dict):
                effort_children.append(_topic(
                    f"{b.get('phase', '')} - {b.get('man_days', 0)}人日",
                    [_topic(b.get("description", ""))] if b.get("description") else None
                ))
        if effort_children:
            nodes.append(_topic("测试人日估算", effort_children))

    # 置信度
    score = data.get("confidence_score")
    if score is not None:
        nodes.append(_topic(f"置信度: {score}"))

    return nodes


def build_sheets_from_task(task) -> list:
    """根据任务类型从 task.result_json 构建 XMind sheets"""
    data = getattr(task, "result_json", None) or {}
    title = (getattr(task, "requirement_input", "") or "")[:50].strip() or "需求分析"
    task_type = getattr(task, "task_type", "")
    sheet_title = f"{title}_测试需求分析" if task_type == "test_requirement_analysis" else title

    if task_type == "test_requirement_analysis":
        root_children = _build_test_requirement_analysis(data)
    else:
        # 其他任务类型：简单键值树
        root_children = []
        for k, v in (data or {}).items():
            if v is None:
                continue
            if isinstance(v, list):
                root_children.append(_topic(k, [_topic(str(i)) for i in v[:20]]))
            elif isinstance(v, dict):
                sub = [_topic(f"{kk}: {str(vv)[:80]}") for kk, vv in list(v.items())[:15]]
                root_children.append(_topic(k, sub))
            else:
                root_children.append(_topic(f"{k}: {str(v)[:100]}"))

    root_topic = _topic(sheet_title, root_children)
    root_topic["structureClass"] = "org.xmind.ui.logic.right"

    theme = {
        "id": _make_id(),
        "centralTopic": {"type": "topic", "properties": {"fo:font-family": "NSimSun, 新宋体", "svg:fill": "#3F51B5"}},
        "mainTopic": {"type": "topic", "properties": {"fo:font-family": "NSimSun, 新宋体"}},
        "subTopic": {"type": "topic", "properties": {"fo:font-family": "NSimSun, 新宋体"}},
    }
    sheets = [{
        "id": _make_id(),
        "class": "sheet",
        "title": sheet_title,
        "rootTopic": root_topic,
        "theme": theme,
    }]
    return sheets


def build_to_bytes(task) -> bytes:
    """构建并返回 .xmind 文件字节"""
    sheets = build_sheets_from_task(task)
    content_json = json.dumps(sheets, ensure_ascii=False)
    metadata_json = json.dumps({
        "creator": {"name": "WorkMind", "version": "1.0.0"},
        "dataStructureVersion": "2"
    }, ensure_ascii=False)
    manifest_json = json.dumps({
        "file-entries": {"content.json": {}, "metadata.json": {}}
    }, ensure_ascii=False)

    tmp = tempfile.NamedTemporaryFile(suffix=".xmind", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_STORED) as zf:
            zf.writestr("content.json", content_json)
            zf.writestr("metadata.json", metadata_json)
            zf.writestr("manifest.json", manifest_json)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
