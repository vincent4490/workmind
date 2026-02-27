# -*- coding: utf-8 -*-
"""
UI场景编排校验工具
"""
import copy
import re
from typing import Any, Dict, List, Tuple, Optional

_BRACE_PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_\.]+)\s*\}\}")
_DOLLAR_PLACEHOLDER = re.compile(r"\$\{\s*([A-Za-z0-9_\.]+)\s*\}")

_CONTROL_FLOW_FIELDS = {
    "if": ["then_steps", "else_steps"],
    "loop": ["steps"],
    "sequence": ["steps"],
    "parallel": ["branches"],
    "try": ["try_steps", "catch_steps", "finally_steps"],
}


def _has_placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return "{{" in value or "${" in value


def _is_type(value: Any, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, (int, float))
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "object":
        return isinstance(value, dict)
    return True


def _is_custom_step(step: Dict[str, Any]) -> bool:
    return str(step.get("kind", "")).lower() == "custom"


def _render_value(value: Any, params: Dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: _render_value(val, params) for key, val in value.items()}
    if isinstance(value, list):
        return [_render_value(item, params) for item in value]
    if isinstance(value, str):
        def _replace(match: re.Match) -> str:
            key = match.group(1)
            if key not in params:
                return match.group(0)
            return str(params.get(key))

        value = _BRACE_PLACEHOLDER.sub(_replace, value)
        value = _DOLLAR_PLACEHOLDER.sub(_replace, value)
        return value
    return value


def _validate_config(config: Any, schema: Dict[str, Any], errors: List[str], prefix: str) -> None:
    if not isinstance(config, dict):
        errors.append(f"{prefix} 缺少 config 或 config 非对象")
        return

    required_fields = schema.get("required", [])
    properties = schema.get("properties", {})
    assert_type = str(config.get("assert_type", "")).lower()

    for field in required_fields:
        if assert_type == "image" and field in ("ocr_selector_type", "ocr_selector"):
            continue
        if field not in config or config.get(field) in ("", None):
            errors.append(f"{prefix} 缺少必填字段: {field}")

    for field, rule in properties.items():
        if field not in config:
            continue
        expected_type = rule.get("type")
        value = config.get(field)
        if expected_type and not _is_type(value, expected_type):
            if _has_placeholder(value):
                continue
            errors.append(f"{prefix} 字段类型错误: {field} 期望 {expected_type}")


def _validate_steps(
    steps: Any,
    component_defs: Dict[str, Any],
    custom_component_defs: Dict[str, Any],
    errors: List[str],
    prefix: str = ""
) -> None:
    if not isinstance(steps, list):
        errors.append(f"{prefix} 必须是列表")
        return

    expanded_flow = expand_ui_flow(steps, custom_component_defs, errors)
    if errors:
        return

    for index, step in enumerate(expanded_flow):
        if not isinstance(step, dict):
            errors.append(f"{prefix}步骤[{index}] 必须是对象")
            continue

        step_type = step.get("type")
        config = step.get("config")

        if not step_type:
            errors.append(f"{prefix}步骤[{index}] 缺少 type")
            continue

        if step_type not in component_defs:
            errors.append(f"{prefix}步骤[{index}] 组件类型无效: {step_type}")
            continue

        schema = component_defs[step_type].schema or {}
        _validate_config(config, schema, errors, f"{prefix}步骤[{index}]")

        flow_fields = _CONTROL_FLOW_FIELDS.get(str(step_type))
        if not flow_fields or not isinstance(config, dict):
            continue

        for field in flow_fields:
            nested = config.get(field)
            if not nested:
                continue
            if step_type == "parallel" and field == "branches":
                if not isinstance(nested, list):
                    errors.append(f"{prefix}步骤[{index}] branches 必须是列表")
                    continue
                for branch_index, branch_steps in enumerate(nested):
                    _validate_steps(
                        branch_steps,
                        component_defs,
                        custom_component_defs,
                        errors,
                        prefix=f"{prefix}步骤[{index}].branches[{branch_index}]."
                    )
            else:
                _validate_steps(
                    nested,
                    component_defs,
                    custom_component_defs,
                    errors,
                    prefix=f"{prefix}步骤[{index}].{field}."
                )


def expand_ui_flow(ui_flow: Any, custom_component_defs: Dict[str, Any], errors: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    expanded: List[Dict[str, Any]] = []
    if not isinstance(ui_flow, list):
        if errors is not None:
            errors.append("ui_flow 必须是列表")
        return expanded

    for index, step in enumerate(ui_flow):
        if not isinstance(step, dict):
            if errors is not None:
                errors.append(f"步骤[{index}] 必须是对象")
            continue

        if not _is_custom_step(step):
            expanded.append(step)
            continue

        custom_type = step.get("type")
        if not custom_type:
            if errors is not None:
                errors.append(f"步骤[{index}] 缺少自定义组件 type")
            continue

        custom_def = custom_component_defs.get(custom_type)
        if not custom_def:
            if errors is not None:
                errors.append(f"步骤[{index}] 自定义组件不存在: {custom_type}")
            continue

        params: Dict[str, Any] = {}
        if isinstance(getattr(custom_def, "default_config", None), dict):
            params.update(custom_def.default_config)
        if isinstance(step.get("config"), dict):
            params.update(step.get("config"))
        custom_steps = custom_def.steps or []
        if not isinstance(custom_steps, list):
            if errors is not None:
                errors.append(f"步骤[{index}] 自定义组件 steps 必须是列表")
            continue

        for inner_index, inner_step in enumerate(custom_steps):
            if not isinstance(inner_step, dict):
                if errors is not None:
                    errors.append(f"步骤[{index}] 自定义组件步骤[{inner_index}] 必须是对象")
                continue
            if _is_custom_step(inner_step):
                if errors is not None:
                    errors.append(f"步骤[{index}] 不支持嵌套自定义组件")
                continue
            cloned = copy.deepcopy(inner_step)
            inner_config = cloned.get("config")
            if isinstance(inner_config, dict):
                cloned["config"] = _render_value(inner_config, params)
            expanded.append(cloned)

    return expanded


def validate_ui_flow(
    ui_flow: Any,
    component_defs: Dict[str, Any],
    custom_component_defs: Optional[Dict[str, Any]] = None
) -> Tuple[bool, List[str]]:
    """
    校验 ui_flow 结构与组件schema匹配

    :param ui_flow: 场景步骤列表
    :param component_defs: {type: UiComponentDefinition} 映射
    :return: (is_valid, errors)
    """
    errors: List[str] = []

    if not isinstance(ui_flow, list):
        return False, ["ui_flow 必须是列表"]

    if custom_component_defs is None:
        custom_component_defs = {}

    for index, step in enumerate(ui_flow):
        if not isinstance(step, dict):
            errors.append(f"步骤[{index}] 必须是对象")
            continue

        if not _is_custom_step(step):
            continue

        custom_type = step.get("type")
        if not custom_type:
            errors.append(f"步骤[{index}] 缺少自定义组件 type")
            continue

        custom_def = custom_component_defs.get(custom_type)
        if not custom_def:
            errors.append(f"步骤[{index}] 自定义组件不存在: {custom_type}")
            continue

        schema = custom_def.schema or {}
        merged_config: Dict[str, Any] = {}
        if isinstance(getattr(custom_def, "default_config", None), dict):
            merged_config.update(custom_def.default_config)
        if isinstance(step.get("config"), dict):
            merged_config.update(step.get("config"))
        _validate_config(merged_config, schema, errors, f"步骤[{index}]")

    if errors:
        return False, errors

    _validate_steps(ui_flow, component_defs, custom_component_defs, errors)
    return len(errors) == 0, errors
