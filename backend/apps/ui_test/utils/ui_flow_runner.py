# -*- coding: utf-8 -*-
"""
UI场景编排执行器（Airtest）
"""
import os
import time
import logging
import json
import re
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Tuple, Optional, Callable

from airtest.core.api import (
    Template,
    wait,
    touch,
    sleep,
    swipe,
    snapshot,
    exists,
    double_click,
)
from airtest.core.api import G, ST

from .ui_flow_validator import expand_ui_flow

logger = logging.getLogger(__name__)

# 导入 UiElement 模型用于使用计数
try:
    from ..models import UiElement
    UI_ELEMENT_AVAILABLE = True
except ImportError:
    UI_ELEMENT_AVAILABLE = False
    logger.warning("无法导入 UiElement 模型，元素使用计数功能将不可用")

import allure


class UiFlowRunner:
    """将 ui_flow 转换为 Airtest 动作并执行"""

    def __init__(self, image_base_dir: Optional[str] = None) -> None:
        if image_base_dir:
            self.image_base_dir = image_base_dir
        else:
            self.image_base_dir = os.environ.get(
                "UI_FLOW_IMAGE_DIR",
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Template")
            )
        self.image_base_dir = os.path.abspath(self.image_base_dir)
        if os.path.basename(self.image_base_dir) == "ui_flow":
            self.image_root_dir = self.image_base_dir
        else:
            self.image_root_dir = os.path.dirname(self.image_base_dir)
        os.makedirs(self.image_base_dir, exist_ok=True)
        self.context: Dict[str, Any] = {}
        self.runtime: Dict[str, Any] = {}

    def _record_element_usage(self, element_name: str) -> None:
        """
        记录元素使用次数
        
        Args:
            element_name: 元素名称
        """
        if not UI_ELEMENT_AVAILABLE:
            return
        
        if not element_name:
            return
        
        try:
            element = UiElement.objects.filter(name=element_name, is_active=True).first()
            if element:
                element.increment_usage()
                logger.debug(f"记录元素使用: {element_name}, 使用次数: {element.usage_count}")
        except Exception as e:
            logger.warning(f"记录元素使用失败: {element_name}, 错误: {e}")

    def _resolve_element_by_id(self, element_id: int) -> Optional[Dict[str, Any]]:
        """
        根据 element_id 从数据库加载元素配置
        
        Args:
            element_id: 元素ID
            
        Returns:
            元素配置字典，如果加载失败则返回 None
        """
        if not UI_ELEMENT_AVAILABLE:
            logger.warning("UiElement 模型不可用，无法解析 element_id")
            return None
        
        try:
            element = UiElement.objects.filter(id=element_id, is_active=True).first()
            if not element:
                logger.warning(f"未找到元素: element_id={element_id}")
                return None
            
            # 记录使用次数
            element.increment_usage()
            logger.debug(f"从元素库加载元素: {element.name} (ID: {element_id})")
            
            # 构建配置
            config = {}
            
            if element.element_type == 'image':
                # 图片类型
                config['selector_type'] = 'image'
                if element.config and 'file_path' in element.config:
                    # 提取文件名
                    file_path = element.config['file_path']
                    config['selector'] = file_path.split('/')[-1]
                    # 设置图片范围
                    if 'scope' in element.config:
                        config['image_scope'] = element.config['scope']
                    else:
                        config['image_scope'] = 'common'
                
            elif element.element_type == 'pos':
                # 坐标类型
                config['selector_type'] = 'pos'
                if element.config and 'x' in element.config and 'y' in element.config:
                    x = element.config['x']
                    y = element.config['y']
                    config['selector'] = f"{x}, {y}"
                    
            elif element.element_type == 'region':
                # 区域类型
                config['selector_type'] = 'region'
                if element.config and all(k in element.config for k in ['x1', 'y1', 'x2', 'y2']):
                    x1 = element.config['x1']
                    y1 = element.config['y1']
                    x2 = element.config['x2']
                    y2 = element.config['y2']
                    config['selector'] = f"{x1}, {y1}, {x2}, {y2}"
            
            # 添加元素名称用于记录
            config['element_name'] = element.name
            
            return config
            
        except Exception as e:
            logger.error(f"解析元素失败: element_id={element_id}, 错误: {e}")
            return None

    def _init_context(self, variables: Optional[List[Dict[str, Any]]] = None, runtime: Optional[Dict[str, Any]] = None) -> None:
        self.context = {
            "global": {},
            "local": {},
            "outputs": {},
            "steps": {}
        }
        self.context["steps"] = self.context["outputs"]
        self.runtime = {
            "retry_times": 0,
            "retry_interval": 0.5
        }
        if runtime and isinstance(runtime, dict):
            self.runtime.update(runtime)
        if variables:
            self._load_variables(variables)

    def _load_variables(self, variables: List[Dict[str, Any]]) -> None:
        for item in variables:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not name:
                continue
            scope = str(item.get("scope") or "local").lower()
            value = item.get("value")
            self._set_variable(str(name), value, scope)

    def _set_variable(self, name: str, value: Any, scope: str = "local") -> None:
        container = self.context.get(scope, self.context.get("local", {}))
        self._set_by_path(container, name, value)

    def _unset_variable(self, name: str, scope: str = "local") -> None:
        container = self.context.get(scope, self.context.get("local", {}))
        if name in container:
            del container[name]
            return
        self._delete_by_path(container, name)

    def _set_by_path(self, data: Dict[str, Any], path: str, value: Any) -> None:
        parts = self._split_path(path)
        if not parts:
            return
        current = data
        for part in parts[:-1]:
            if part not in current or not isinstance(current.get(part), dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    def _delete_by_path(self, data: Dict[str, Any], path: str) -> None:
        parts = self._split_path(path)
        if not parts:
            return
        current = data
        for part in parts[:-1]:
            if not isinstance(current, dict) or part not in current:
                return
            current = current.get(part)
        if isinstance(current, dict) and parts[-1] in current:
            del current[parts[-1]]

    def _split_path(self, path: str) -> List[str]:
        if not path:
            return []
        path = str(path)
        path = re.sub(r"\[(\d+)\]", r".\1", path)
        return [part for part in path.split(".") if part]

    def _get_by_path(self, data: Any, path: str) -> Any:
        parts = self._split_path(path)
        current = data
        for part in parts:
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(part)
                continue
            if isinstance(current, list):
                if part.isdigit():
                    idx = int(part)
                    if 0 <= idx < len(current):
                        current = current[idx]
                        continue
                return None
            return None
        return current

    def _resolve_expression(self, expr: str) -> Any:
        expr = str(expr or "").strip()
        if not expr:
            return None
        if expr.startswith("global."):
            return self._get_by_path(self.context.get("global", {}), expr[len("global."):])
        if expr.startswith("local."):
            return self._get_by_path(self.context.get("local", {}), expr[len("local."):])
        if expr.startswith("outputs."):
            return self._get_by_path(self.context.get("outputs", {}), expr[len("outputs."):])
        if expr.startswith("steps."):
            return self._get_by_path(self.context.get("steps", {}), expr[len("steps."):])
        local_value = self._get_by_path(self.context.get("local", {}), expr)
        if local_value is not None:
            return local_value
        global_value = self._get_by_path(self.context.get("global", {}), expr)
        if global_value is not None:
            return global_value
        return self._get_by_path(self.context.get("outputs", {}), expr)

    def _render_string(self, value: str) -> Any:
        pattern = re.compile(r"\{\{\s*([^}]+)\s*\}\}|\$\{\s*([^}]+)\s*\}")
        matches = list(pattern.finditer(value))
        if len(matches) == 1 and matches[0].span() == (0, len(value)):
            expr = matches[0].group(1) or matches[0].group(2)
            resolved = self._resolve_expression(expr)
            return "" if resolved is None else resolved

        def _replace(match: re.Match) -> str:
            expr = match.group(1) or match.group(2)
            resolved = self._resolve_expression(expr)
            return "" if resolved is None else str(resolved)

        return pattern.sub(_replace, value)

    def _render_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._render_value(val) for key, val in value.items()}
        if isinstance(value, list):
            return [self._render_value(item) for item in value]
        if isinstance(value, str):
            return self._render_string(value)
        return value

    def _to_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "y")
        return bool(value)

    def _normalize_mapping(self, value: Any) -> Any:
        if value is None or value == "":
            return None
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                return json.loads(text)
            except Exception:
                return value
        return value

    def _clone_context(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return copy.deepcopy(context or self.context)

    def _capture_screenshot(self, name_prefix: str) -> Optional[str]:
        filename = f"{name_prefix}_{int(time.time())}.png"
        log_dir = ST.LOG_DIR or "."
        full_path = os.path.join(log_dir, filename)
        logger.info("截图保存路径: %s", full_path)
        result = snapshot(filename=full_path)
        if isinstance(result, dict):
            path = result.get("screen")
            if path and os.path.exists(path):
                return path
        if os.path.exists(full_path):
            return full_path
        return None

    def _attach_allure(self, name: str, step: Optional[Dict[str, Any]] = None) -> None:
        if step is not None:
            try:
                allure.attach(
                    json.dumps(step, ensure_ascii=False, indent=2),
                    name=f"{name}-step",
                    attachment_type=allure.attachment_type.JSON
                )
            except Exception:
                pass
        path = self._capture_screenshot(name)
        if path:
            try:
                allure.attach.file(path, name=name, attachment_type=allure.attachment_type.PNG)
            except Exception:
                logger.exception("Allure 附件写入失败: %s", path)
        else:
            logger.warning("Allure 截图路径为空，无法附加: %s", name)

    def run(
        self,
        ui_flow: List[Dict[str, Any]],
        custom_component_defs: Optional[Dict[str, Any]] = None,
        variables: Optional[List[Dict[str, Any]]] = None,
        runtime: Optional[Dict[str, Any]] = None
    ) -> None:
        if not isinstance(ui_flow, list):
            raise ValueError("ui_flow 必须是列表")

        self._init_context(variables, runtime)

        if custom_component_defs is None:
            try:
                from apps.ui_test.models import UiCustomComponentDefinition
                custom_defs = UiCustomComponentDefinition.objects.filter(enabled=True)  # type: ignore[attr-defined]
                custom_component_defs = {c.type: c for c in custom_defs}
            except Exception:
                custom_component_defs = {}

        self._execute_steps(ui_flow, custom_component_defs, title_prefix="步骤")

    def _execute_steps(
        self,
        steps: List[Dict[str, Any]],
        custom_component_defs: Dict[str, Any],
        title_prefix: str = "步骤"
    ) -> None:
        expanded_flow = expand_ui_flow(steps, custom_component_defs)
        for index, step in enumerate(expanded_flow):
            self._execute_single_step(step, index, custom_component_defs, title_prefix=title_prefix)

    def _execute_single_step(
        self,
        step: Dict[str, Any],
        index: int,
        custom_component_defs: Dict[str, Any],
        title_prefix: str = "步骤"
    ) -> None:
        step_type = step.get("type")
        raw_config = step.get("config", {})
        if step_type == "loop":
            config = copy.deepcopy(raw_config)
        else:
            config = self._render_value(raw_config)
        logger.info("执行%s[%s]: type=%s, config=%s", title_prefix, index + 1, step_type, config)
        step_name = step.get("name") or step_type
        step_title = f"{title_prefix}{index + 1}-{step_name}"
        retry_times = int(config.get("retry_times", self.runtime.get("retry_times", 0)) or 0)
        retry_interval = float(config.get("retry_interval", self.runtime.get("retry_interval", 0.5)) or 0)

        def _execute_step_once() -> Any:
            if step_type == "click":
                return self._step_click(config)
            if step_type == "input":
                return self._step_input(config)
            if step_type == "swipe":
                return self._step_swipe(config)
            if step_type == "wait":
                return self._step_wait(config)
            if step_type == "assert_text":
                return self._step_assert_text(config)
            if step_type == "assert_exists":
                return self._step_assert_exists(config)
            if step_type == "assert":
                return self._step_assert(config)
            if step_type == "screenshot":
                return self._step_screenshot(config)
            if step_type == "long_press":
                return self._step_long_press(config)
            if step_type == "double_click":
                return self._step_double_click(config)
            if step_type == "drag":
                return self._step_drag(config)
            if step_type == "swipe_to":
                return self._step_swipe_to(config)
            if step_type == "foreach_assert":
                return self._step_foreach_assert(config)
            if step_type == "image_exists_click":
                return self._step_image_exists_click(config)
            if step_type == "image_exists_click_chain":
                return self._step_image_exists_click_chain(config)
            if step_type == "set_variable":
                return self._step_set_variable(config)
            if step_type == "unset_variable":
                return self._step_unset_variable(config)
            if step_type == "extract_output":
                return self._step_extract_output(config)
            if step_type == "api_request":
                return self._step_api_request(config)
            if step_type == "if":
                return self._step_if(config, custom_component_defs)
            if step_type == "loop":
                return self._step_loop(config, custom_component_defs)
            if step_type == "sequence":
                return self._step_sequence(config, custom_component_defs)
            if step_type == "parallel":
                return self._step_parallel(config, custom_component_defs)
            if step_type == "try":
                return self._step_try(config, custom_component_defs)
            raise ValueError(f"不支持的步骤类型: {step_type}")

        def _store_output(result: Any) -> None:
            if result is None:
                return
            self.context["outputs"]["last"] = result
            step_id = step.get("id")
            if step_id:
                self.context["steps"][str(step_id)] = result

        attempts = 0
        last_error: Optional[Exception] = None
        while attempts <= retry_times:
            try:
                with allure.step(step_title):
                    result = _execute_step_once()
                    _store_output(result)
                return
            except Exception as exc:
                last_error = exc
                # 失败时始终截图，保存到测试报告
                self._attach_allure(f"{step_title}-error", step)
                if attempts >= retry_times:
                    raise
                attempts += 1
                sleep(retry_interval)

    def _eval_condition(self, left: Any, operator: str, right: Any) -> bool:
        op = str(operator or "==").lower()
        if op in ("truthy", "exists"):
            return bool(left)
        if op in ("falsy", "not_exists"):
            return not bool(left)

        if op == "contains":
            try:
                return str(right) in str(left)
            except Exception:
                return False
        if op == "in":
            try:
                return str(left) in str(right)
            except Exception:
                return False
        if op in ("not_in", "notcontains"):
            try:
                return str(left) not in str(right)
            except Exception:
                return False
        if op in ("regex", "match"):
            try:
                return re.search(str(right), str(left)) is not None
            except Exception:
                return False

        try:
            left_num = float(left)
            right_num = float(right)
            if op in (">", "gt"):
                return left_num > right_num
            if op in (">=", "gte"):
                return left_num >= right_num
            if op in ("<", "lt"):
                return left_num < right_num
            if op in ("<=", "lte"):
                return left_num <= right_num
        except Exception:
            pass

        if op in ("!=", "neq"):
            return str(left) != str(right)
        return str(left) == str(right)

    def _step_if(self, config: Dict[str, Any], custom_component_defs: Dict[str, Any]) -> None:
        left = config.get("left")
        operator = config.get("operator", "==")
        right = config.get("right")
        condition = self._eval_condition(left, operator, right)
        steps = config.get("then_steps") if condition else config.get("else_steps")
        if isinstance(steps, list):
            self._execute_steps(steps, custom_component_defs, title_prefix="分支步骤")

    def _step_sequence(self, config: Dict[str, Any], custom_component_defs: Dict[str, Any]) -> None:
        steps = config.get("steps")
        if isinstance(steps, list):
            self._execute_steps(steps, custom_component_defs, title_prefix="子步骤")

    def _step_loop(self, config: Dict[str, Any], custom_component_defs: Dict[str, Any]) -> None:
        mode = str(self._render_value(config.get("mode", "count")) or "count").lower()
        steps = config.get("steps")
        steps_input = config.get("steps_input")
        if (not isinstance(steps, list) or not steps) and isinstance(steps_input, str) and steps_input.strip():
            try:
                steps = json.loads(steps_input)
                config["steps"] = steps
                logger.info("循环 steps_input 解析成功，steps 数量=%s", len(steps) if isinstance(steps, list) else 0)
            except Exception as exc:
                logger.warning("循环 steps_input JSON 解析失败: %s", exc)
        if not isinstance(steps, list):
            return
        interval = float(self._render_value(config.get("interval", 0)) or 0)
        max_loops = int(self._render_value(config.get("max_loops", 100)) or 100)

        if mode == "foreach":
            items = self._render_value(config.get("items", []))
            items_input = config.get("items_input")
            if (not isinstance(items, list) or not items) and isinstance(items_input, str) and items_input.strip():
                try:
                    items = json.loads(items_input)
                    config["items"] = items
                    logger.info("循环 items_input 解析成功，items 数量=%s", len(items) if isinstance(items, list) else 0)
                except Exception as exc:
                    logger.warning("循环 items_input JSON 解析失败: %s", exc)
            if isinstance(items, str):
                try:
                    items = json.loads(items)
                except Exception as exc:
                    logger.warning("循环 foreach items JSON 解析失败: %s", exc)
                    items = [item.strip() for item in items.split(",") if item.strip()]
            if not isinstance(items, list):
                logger.warning("循环 foreach items 非列表，类型=%s，值=%s", type(items).__name__, items)
                return
            item_var = config.get("item_var", "item")
            item_scope = str(config.get("item_scope", "local")).lower()
            logger.info("循环 foreach items 解析完成: count=%s, item_var=%s, item_scope=%s", len(items), item_var, item_scope)
            for idx, item in enumerate(items):
                if idx >= max_loops:
                    break
                logger.info("循环 foreach 设置变量: index=%s, %s.%s=%s", idx + 1, item_scope, item_var, item)
                self._set_variable(str(item_var), item, item_scope)
                self._execute_steps(steps, custom_component_defs, title_prefix="循环步骤")
                if interval:
                    sleep(interval)
            return

        if mode == "condition":
            for loop_index in range(max_loops):
                left_value = self._render_value(config.get("left"))
                right_value = self._render_value(config.get("right"))
                operator = self._render_value(config.get("operator", "=="))
                if not self._eval_condition(left_value, operator, right_value):
                    break
                self._execute_steps(steps, custom_component_defs, title_prefix="循环步骤")
                if interval:
                    sleep(interval)
            return

        times = int(self._render_value(config.get("times", 1)) or 0)
        if times <= 0:
            return
        for loop_index in range(min(times, max_loops)):
            self._execute_steps(steps, custom_component_defs, title_prefix="循环步骤")
            if interval:
                sleep(interval)

    def _step_parallel(self, config: Dict[str, Any], custom_component_defs: Dict[str, Any]) -> None:
        branches = config.get("branches")
        if not isinstance(branches, list) or not branches:
            return
        merge_strategy = str(config.get("merge_strategy", "last")).lower()
        base_context = self._clone_context()
        branch_contexts: List[Dict[str, Any]] = []
        errors: List[Exception] = []

        def _run_branch(branch_steps: Any, branch_context: Dict[str, Any]) -> None:
            branch_runner = UiFlowRunner(image_base_dir=self.image_base_dir)
            branch_runner.context = branch_context
            branch_runner.runtime = copy.deepcopy(self.runtime)
            branch_runner._execute_steps(branch_steps or [], custom_component_defs, title_prefix="并行步骤")

        with ThreadPoolExecutor(max_workers=min(len(branches), 4)) as executor:
            future_map = {}
            for branch in branches:
                branch_context = self._clone_context(base_context)
                branch_contexts.append(branch_context)
                future = executor.submit(_run_branch, branch, branch_context)
                future_map[future] = branch

            for future in as_completed(future_map):
                try:
                    future.result()
                except Exception as exc:
                    errors.append(exc)

        if errors:
            raise errors[0]

        if merge_strategy == "first":
            self.context = branch_contexts[0] if branch_contexts else base_context
            return

        merged = self._clone_context(base_context)
        for branch_context in branch_contexts:
            for scope in ("global", "local", "outputs", "steps"):
                if scope not in merged:
                    merged[scope] = {}
                if isinstance(merged[scope], dict) and isinstance(branch_context.get(scope), dict):
                    merged[scope].update(branch_context.get(scope, {}))
        self.context = merged

    def _step_try(self, config: Dict[str, Any], custom_component_defs: Dict[str, Any]) -> None:
        try_steps = config.get("try_steps")
        catch_steps = config.get("catch_steps")
        finally_steps = config.get("finally_steps")
        error_var = config.get("error_var")
        error_scope = str(config.get("error_scope", "local")).lower()

        try:
            if isinstance(try_steps, list):
                self._execute_steps(try_steps, custom_component_defs, title_prefix="Try步骤")
        except Exception as exc:
            if error_var:
                self._set_variable(str(error_var), str(exc), error_scope)
            if isinstance(catch_steps, list):
                self._execute_steps(catch_steps, custom_component_defs, title_prefix="Catch步骤")
            else:
                raise
        finally:
            if isinstance(finally_steps, list):
                self._execute_steps(finally_steps, custom_component_defs, title_prefix="Finally步骤")

    def _step_set_variable(self, config: Dict[str, Any]) -> None:
        name = config.get("name")
        if not name:
            raise ValueError("set_variable 需要 name")
        scope = str(config.get("scope", "local")).lower()
        value_type = str(config.get("value_type", "string")).lower()
        value = config.get("value")
        if value_type in ("number", "int", "float"):
            try:
                value = float(value)
                if value_type == "int":
                    value = int(value)
            except Exception:
                value = 0
        elif value_type == "boolean":
            value = self._to_bool(value)
        elif value_type in ("array", "object"):
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except Exception:
                    value = [] if value_type == "array" else {}
        self._set_variable(str(name), value, scope)

    def _step_unset_variable(self, config: Dict[str, Any]) -> None:
        name = config.get("name")
        if not name:
            raise ValueError("unset_variable 需要 name")
        scope = str(config.get("scope", "local")).lower()
        self._unset_variable(str(name), scope)

    def _step_extract_output(self, config: Dict[str, Any]) -> None:
        source = config.get("source", "outputs.last")
        path = config.get("path")
        name = config.get("name")
        if not name or not path:
            raise ValueError("extract_output 需要 name 和 path")
        scope = str(config.get("scope", "local")).lower()
        source_value = self._resolve_expression(str(source))
        value = self._get_by_path(source_value, str(path))
        self._set_variable(str(name), value, scope)

    def _step_api_request(self, config: Dict[str, Any]) -> Dict[str, Any]:
        method = str(config.get("method", "GET")).upper()
        url = config.get("url")
        if not url:
            raise ValueError("api_request 需要 url")
        url = self._render_value(url)
        headers = self._normalize_mapping(self._render_value(config.get("headers")))
        params = self._normalize_mapping(self._render_value(config.get("params")))
        data = self._normalize_mapping(self._render_value(config.get("data")))
        json_body = self._normalize_mapping(self._render_value(config.get("json")))
        timeout = float(config.get("timeout", 10) or 10)
        expected_status = config.get("expected_status")
        response_type = str(config.get("response_type", "auto")).lower()
        save_as = config.get("save_as")
        scope = str(config.get("scope", "local")).lower()
        extracts = self._normalize_mapping(self._render_value(config.get("extracts"))) or []
        if not isinstance(extracts, list):
            extracts = []

        try:
            import requests
        except Exception as exc:
            raise RuntimeError("api_request 需要 requests 依赖") from exc

        url = str(url)
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
            base_url = config.get("base_url")
            if base_url is None:
                base_url = self.runtime.get("base_url")
            if base_url is None:
                base_url = os.environ.get("UI_FLOW_BASE_URL")
            base_url = self._render_value(base_url) if base_url else None
            if base_url:
                from urllib.parse import urljoin
                url = urljoin(str(base_url).rstrip("/") + "/", url.lstrip("/"))

        if headers is None:
            headers = {}
        if isinstance(headers, dict):
            def _normalize_token_value(raw: Any) -> Any:
                if raw is None:
                    return None
                if isinstance(raw, str):
                    cleaned = raw.strip()
                    return cleaned if cleaned else None
                return raw

            global_vars = self.context.get("global", {}) if isinstance(self.context.get("global"), dict) else {}
            global_token = _normalize_token_value(global_vars.get("token"))
            token = None
            token_sources = [
                config.get("token"),
                self.runtime.get("token"),
                os.environ.get("UI_FLOW_TOKEN"),
                global_token,
            ]
            last_output = self.context.get("outputs", {}).get("last")
            if isinstance(last_output, dict):
                if "token" in last_output:
                    token_sources.append(last_output.get("token"))
                else:
                    last_data = last_output.get("data")
                    if isinstance(last_data, dict) and "token" in last_data:
                        token_sources.append(last_data.get("token"))
            for candidate in token_sources:
                normalized = _normalize_token_value(self._render_value(candidate) if candidate is not None else None)
                if normalized is not None:
                    token = normalized
                    break
            token_len = len(token) if isinstance(token, str) else None
            logger.info(
                "api_request 全局变量: keys=%s token_in_global=%s token_type=%s token_len=%s",
                list(global_vars.keys()),
                "token" in global_vars,
                type(global_token).__name__ if global_token is not None else None,
                len(global_token) if isinstance(global_token, str) else None
            )
            logger.info(
                "api_request auth token 解析: present=%s type=%s len=%s",
                token is not None,
                type(token).__name__ if token is not None else None,
                token_len
            )
            if token and (not headers.get("Authorization")):
                token_text = str(token).strip()
                if token_text and not token_text.lower().startswith("bearer "):
                    token_text = f"Bearer {token_text}"
                if token_text:
                    headers["Authorization"] = token_text

        auth_present = isinstance(headers, dict) and "Authorization" in headers
        last_output = self.context.get("outputs", {}).get("last")
        last_output_keys = list(last_output.keys()) if isinstance(last_output, dict) else None
        last_output_data_keys = None
        if isinstance(last_output, dict) and isinstance(last_output.get("data"), dict):
            last_output_data_keys = list(last_output["data"].keys())

        response = requests.request(
            method=method,
            url=url,
            headers=headers if isinstance(headers, dict) else None,
            params=params if isinstance(params, dict) else None,
            data=data if isinstance(data, dict) else data,
            json=json_body if isinstance(json_body, dict) else None,
            timeout=timeout
        )

        if expected_status:
            if isinstance(expected_status, str):
                expected_list = [item.strip() for item in expected_status.split(",") if item.strip()]
            elif isinstance(expected_status, list):
                expected_list = expected_status
            else:
                expected_list = [expected_status]
            valid_codes = [int(x) for x in expected_list if str(x).isdigit()]
            if valid_codes and response.status_code not in valid_codes:
                response_preview = response.text
                if isinstance(response_preview, str) and len(response_preview) > 500:
                    response_preview = response_preview[:500] + "...(truncated)"
                raise AssertionError(
                    "api_request 状态码不匹配: "
                    f"{response.status_code}, method={method}, url={url}, "
                    f"auth_present={auth_present}, "
                    f"last_output_keys={last_output_keys}, "
                    f"last_output_data_keys={last_output_data_keys}, "
                    f"response={response_preview}"
                )

        response_payload: Any
        if response_type == "text":
            response_payload = response.text
        elif response_type == "json":
            response_payload = response.json()
        else:
            try:
                response_payload = response.json()
            except Exception:
                response_payload = response.text

        result = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "data": response_payload,
            "text": response.text
        }

        if save_as:
            self._set_variable(str(save_as), response_payload, scope)

        if isinstance(extracts, list):
            logger.info("api_request 批量提取配置: %s", extracts)
            for item in extracts:
                if not isinstance(item, dict):
                    logger.warning("api_request 批量提取条目格式错误: %s", item)
                    continue
                name = item.get("name")
                path = item.get("path")
                if not name or not path:
                    logger.warning("api_request 批量提取缺少 name/path: %s", item)
                    continue
                item_scope = str(item.get("scope", scope)).lower()
                value = self._get_by_path(response_payload, str(path))
                self._set_variable(str(name), value, item_scope)
                value_len = len(value) if isinstance(value, str) else None
                logger.info(
                    "api_request 批量提取值信息: name=%s type=%s len=%s",
                    name,
                    type(value).__name__,
                    value_len
                )
                logger.info(
                    "api_request 批量提取完成: name=%s scope=%s path=%s value_present=%s",
                    name,
                    item_scope,
                    path,
                    value is not None
                )

        return result

    def _resolve_target(self, config: Dict[str, Any]) -> Tuple[str, Optional[Any]]:
        # 如果有 element_id，先从数据库加载元素配置
        element_id = config.get("element_id")
        if element_id:
            element_config = self._resolve_element_by_id(element_id)
            if element_config:
                # 合并元素配置到当前配置（元素配置优先级较低，不覆盖已有配置）
                merged_config = {**element_config, **config}
                config = merged_config
                logger.debug(f"已应用元素配置: element_id={element_id}, name={element_config.get('element_name')}")
        
        selector_type = config.get("selector_type")
        selector = config.get("selector")
        
        # 记录元素使用（如果提供了 element_name）
        element_name = config.get("element_name")
        if element_name:
            self._record_element_usage(element_name)

        if not selector_type:
            return "none", None

        if selector_type == "image":
            if not selector:
                raise ValueError("image 类型需要 selector(图片路径)")
            path = selector
            if not os.path.isabs(path):
                scope = str(config.get("image_scope", "game")).lower()
                if scope == "common":
                    base_dir = os.path.join(self.image_root_dir, "common")
                elif scope in ("game", "current", ""):
                    base_dir = self.image_base_dir
                else:
                    base_dir = os.path.join(self.image_root_dir, scope)
                path = os.path.join(base_dir, selector)
            threshold = config.get("image_threshold", None)
            if threshold is not None and threshold != "":
                try:
                    threshold_value = float(threshold)
                except Exception:
                    threshold_value = None
            else:
                threshold_value = None
            if threshold_value is not None:
                return "image", Template(path, threshold=threshold_value)
            return "image", Template(path)

        if selector_type == "pos":
            pos = self._parse_pos(selector)
            return "pos", pos

        if selector_type == "region":
            region = self._parse_region(selector)
            return "region", region
        if selector_type == "text":
            if not selector:
                raise ValueError("text 类型需要 selector(文本)")
            return "text", str(selector)

        raise ValueError(f"不支持的 selector_type: {selector_type}")

    def _wait_with_timing(self, target: Any, timeout: float, label: str) -> None:
        start = time.time()
        try:
            wait(target, timeout=timeout)
        finally:
            elapsed = time.time() - start
            logger.info("wait耗时: %.3fs, timeout=%s, %s", elapsed, timeout, label)

    def _parse_pos(self, selector: Any) -> Tuple[int, int]:
        if isinstance(selector, (list, tuple)) and len(selector) == 2:
            return int(selector[0]), int(selector[1])
        if isinstance(selector, str) and "," in selector:
            x_str, y_str = selector.split(",", 1)
            return int(float(x_str.strip())), int(float(y_str.strip()))
        raise ValueError("pos 需要格式为 'x,y' 或 [x, y]")

    def _parse_region(self, selector: Any) -> Tuple[int, int, int, int]:
        if isinstance(selector, (list, tuple)) and len(selector) == 4:
            return tuple(int(v) for v in selector)  # type: ignore[return-value]
        if isinstance(selector, str) and "," in selector:
            parts = [p.strip() for p in selector.split(",")]
            if len(parts) != 4:
                raise ValueError("region 需要格式为 'x1,y1,x2,y2' 或 [x1,y1,x2,y2]")
            return tuple(int(float(p)) for p in parts)  # type: ignore[return-value]
        raise ValueError("region 需要格式为 'x1,y1,x2,y2' 或 [x1,y1,x2,y2]")

    def _step_click(self, config: Dict[str, Any]) -> None:
        selector_type, target = self._resolve_target(config)
        timeout = config.get("timeout", 5)

        if selector_type == "image":
            self._wait_with_timing(
                target,
                timeout,
                f"click image selector={config.get('selector')} scope={config.get('image_scope', 'game')}"
            )
            touch(target)
            return

        if selector_type == "pos":
            touch(target)
            return

        raise ValueError("click 仅支持 selector_type=image/pos")

    def _step_input(self, config: Dict[str, Any]) -> None:
        selector_type, target = self._resolve_target(config)
        value = config.get("value", "")

        if value is None or value == "":
            raise ValueError("input 需要 value")

        if selector_type in ("image", "pos"):
            if selector_type == "image":
                self._wait_with_timing(
                    target,
                    5,
                    f"input image selector={config.get('selector')} scope={config.get('image_scope', 'game')}"
                )
            touch(target)
            from airtest.core.api import text
            text(str(value))
            return

        raise ValueError("input 仅支持 selector_type=image/pos")

    def _step_swipe(self, config: Dict[str, Any]) -> None:
        direction = config.get("direction", "up")
        duration = config.get("duration", 0.5)
        selector_type = config.get("selector_type")
        selector = config.get("selector")

        if selector_type == "pos" and selector:
            parts = self._parse_region(selector)
            swipe((parts[0], parts[1]), (parts[2], parts[3]), duration=duration)
            return

        width = G.DEVICE.display_info.get("width", 1080)
        height = G.DEVICE.display_info.get("height", 1920)
        start = (int(width * 0.5), int(height * 0.7))
        end = (int(width * 0.5), int(height * 0.3))

        if direction == "down":
            start, end = end, start
        elif direction == "left":
            start = (int(width * 0.7), int(height * 0.5))
            end = (int(width * 0.3), int(height * 0.5))
        elif direction == "right":
            start = (int(width * 0.3), int(height * 0.5))
            end = (int(width * 0.7), int(height * 0.5))

        swipe(start, end, duration=duration)

    def _step_wait(self, config: Dict[str, Any]) -> None:
        timeout = config.get("timeout", 3)
        selector_type = config.get("selector_type")
        selector = config.get("selector")

        if selector_type == "image" and selector:
            _, target = self._resolve_target(config)
            self._wait_with_timing(
                target,
                timeout,
                f"wait image selector={selector} scope={config.get('image_scope', 'game')}"
            )
        else:
            sleep(timeout)

    def _step_assert(self, config: Dict[str, Any]) -> None:
        assert_type = str(config.get("assert_type", "text")).lower()
        match_mode = str(config.get("match_mode", "contains")).lower()
        timeout = float(config.get("timeout", 0) or 0)

        if assert_type == "exists":
            selector_type, target = self._resolve_target(config)
            if selector_type != "image":
                raise ValueError("assert 断言存在仅支持 selector_type=image")
            expected_exists = config.get("expected_exists", True)
            def _check_exists() -> Tuple[bool, str]:
                exists_result = bool(exists(target))
                if bool(expected_exists) == exists_result:
                    return True, ""
                return False, "断言失败：元素存在性不匹配"
            success, message = _check_exists()
            if success:
                return
            if timeout > 0:
                end_time = time.time() + timeout
                while time.time() < end_time:
                    sleep(0.5)
                    success, message = _check_exists()
                    if success:
                        return
            raise AssertionError(message)

        if assert_type in ("image",):
            expected = config.get("expected")
            if not expected:
                raise ValueError("assert 图片断言需要 expected")
            image_scope = config.get("image_scope", "game")
            _, image_target = self._resolve_target({
                "selector_type": "image",
                "selector": expected,
                "image_scope": image_scope,
                "image_threshold": config.get("image_threshold")
            })
            def _check_image() -> Tuple[bool, str]:
                if exists(image_target):
                    return True, ""
                return False, f"断言失败：图片不存在 {expected}"
            success, message = _check_image()
            if success:
                return
            if timeout > 0:
                end_time = time.time() + timeout
                while time.time() < end_time:
                    sleep(0.5)
                    success, message = _check_image()
                    if success:
                        return
            raise AssertionError(message)

        if assert_type in ("range", "between"):
            min_value = config.get("min")
            max_value = config.get("max")
            selector_type, _ = self._resolve_target(config)
            if selector_type not in ("pos", "region"):
                raise ValueError("assert 数值范围断言需要 selector_type=pos 或 region")
            def _check_range() -> Tuple[bool, str]:
                actual = self._ocr_from_region(selector_type, config.get("selector"))
                actual_num = float(re.sub(r"[^\d.\-]", "", str(actual)) or 0)
                if min_value is not None and actual_num < float(min_value):
                    return False, f"断言失败：数值低于最小值 {min_value}，实际 {actual_num}"
                if max_value is not None and actual_num > float(max_value):
                    return False, f"断言失败：数值高于最大值 {max_value}，实际 {actual_num}"
                return True, ""
            success, message = _check_range()
            if success:
                return
            if timeout > 0:
                end_time = time.time() + timeout
                while time.time() < end_time:
                    sleep(0.5)
                    success, message = _check_range()
                    if success:
                        return
            raise AssertionError(message)

        expected = config.get("expected")
        if not expected:
            raise ValueError("assert 需要 expected")

        selector_type, _ = self._resolve_target(config)
        if selector_type not in ("pos", "region"):
            raise ValueError("assert 需要 selector_type=pos 或 region")
        def _check_text() -> Tuple[bool, str]:
            actual_text = self._ocr_from_region(selector_type, config.get("selector"))
            if assert_type == "regex":
                if re.search(str(expected), str(actual_text)) is None:
                    return False, f"断言失败：正则未匹配 {expected}，识别结果: {actual_text}"
                return True, ""

            if not self._is_match(str(expected), actual_text, match_mode, assert_type):
                if match_mode == "exact":
                    return False, f"断言失败：未完全匹配{assert_type} '{expected}'，识别结果: {actual_text}"
                return False, f"断言失败：未找到{assert_type} '{expected}'，识别结果: {actual_text}"
            return True, ""

        success, message = _check_text()
        if success:
            return
        if timeout > 0:
            end_time = time.time() + timeout
            while time.time() < end_time:
                sleep(0.5)
                success, message = _check_text()
                if success:
                    return
        raise AssertionError(message)

    def _step_assert_exists(self, config: Dict[str, Any]) -> None:
        self._step_assert({**config, "assert_type": "exists"})

    def _step_assert_text(self, config: Dict[str, Any]) -> None:
        self._step_assert({**config, "assert_type": config.get("assert_type", "text")})

    def _step_screenshot(self, config: Dict[str, Any]) -> None:
        note = config.get("note", "")
        name_prefix = "ui_flow"
        if note:
            safe_note = "".join(c for c in str(note) if c.isalnum() or c in ("-", "_"))
            name_prefix = f"ui_flow_{safe_note}"
        self._capture_screenshot(name_prefix)

    def _is_match(self, expected: str, actual: str, match_mode: str, assert_type: str = "text") -> bool:
        if assert_type == "regex":
            try:
                return re.search(str(expected), str(actual or "")) is not None
            except Exception:
                return False
        if assert_type == "number":
            expected_digits = re.sub(r"\D", "", str(expected))
            actual_digits = re.sub(r"\D", "", str(actual or ""))
            logger.info(f"数字相等断言匹配: type={assert_type}, expected={expected_digits}, actual={actual_digits}, match_mode={match_mode}")
            if not expected_digits:
                return False
            return expected_digits == actual_digits

        raw_text = actual or ""
        expected_str = str(expected)

        if match_mode == "exact":
            if raw_text.strip() == expected_str.strip():
                return True
            expected_text = re.sub(r"\D", "", expected_str)
            actual_text = re.sub(r"\D", "", raw_text)
            logger.info(f"文本相等断言匹配: type={assert_type}, expected={expected_text}, actual={actual_text}, match_mode={match_mode}")
            return bool(expected_text) and expected_text == actual_text

        if expected_str in raw_text:
            return True
        expected_text = re.sub(r"\D", "", expected_str)
        actual_text = re.sub(r"\D", "", raw_text)
        logger.info(f"文本包含断言匹配: type={assert_type}, expected={expected_text}, actual={actual_text}, match_mode={match_mode}")
        return bool(expected_text) and expected_text in actual_text

    def _ocr_from_region(self, selector_type: str, selector: Any) -> str:
        if selector_type not in ("pos", "region"):
            raise ValueError("OCR 仅支持 selector_type=pos 或 region")
        if selector_type == "pos":
            x, y = self._parse_pos(selector)
            region = (max(0, x - 5), max(0, y - 5), x + 5, y + 5)
        else:
            region = self._parse_region(selector)
        from .ocr_parse_text import OCRParseText
        ocr = OCRParseText()
        img = ocr.screen_info(region)
        try:
            return ocr.easyocr_ocr(img)  # type: ignore[arg-type]
        except Exception:
            return ocr.tesseract_ocr(img)  # type: ignore[arg-type]

    def _step_click_until_match(self, config: Dict[str, Any]) -> None:
        expected = config.get("expected")
        if not expected:
            raise ValueError("click_until_match 需要 expected")

        assert_type = str(config.get("assert_type", "text")).lower()
        match_mode = str(config.get("match_mode", "contains")).lower()
        max_loops = int(config.get("max_loops", 5))
        interval = float(config.get("interval", 0.5))
        timeout = float(config.get("timeout", 5))
        loops = max(1, max_loops)

        click_selector_type = config.get("click_selector_type")
        click_selector = config.get("click_selector")
        ocr_selector_type = config.get("ocr_selector_type", "region")
        ocr_selector = config.get("ocr_selector")

        if not click_selector_type or not click_selector:
            raise ValueError("click_until_match 需要 click_selector_type 和 click_selector")
        if assert_type != "image" and not ocr_selector:
            raise ValueError("click_until_match 需要 ocr_selector")

        def _do_click():
            click_type, click_target = self._resolve_target({
                "selector_type": click_selector_type,
                "selector": click_selector,
                "image_scope": config.get("image_scope"),
                "image_threshold": config.get("image_threshold")
            })
            if click_type == "image":
                self._wait_with_timing(
                    click_target,
                    timeout,
                    f"foreach_assert click selector={click_selector} scope={config.get('image_scope', 'game')}"
                )
            touch(click_target)

        if assert_type == "image":
            image_scope = config.get("expected_image_scope") or config.get("image_scope", "game")
            _, image_target = self._resolve_target({
                "selector_type": "image",
                "selector": expected,
                "image_scope": image_scope,
                "image_threshold": config.get("image_threshold")
            })

            def _is_image_match() -> bool:
                return bool(exists(image_target))

            for _ in range(loops):
                _do_click()
                sleep(interval)
                if _is_image_match():
                    return

            raise AssertionError(f"循环点击未找到图片 '{expected}'")

        for _ in range(loops):
            _do_click()
            sleep(interval)
            current_text = self._ocr_from_region(ocr_selector_type, ocr_selector)
            if self._is_match(str(expected), current_text, match_mode, assert_type):
                return

        raise AssertionError(f"循环点击未达到期望{assert_type} '{expected}'，识别结果: {current_text}")

    def _step_image_exists_click(self, config: Dict[str, Any]) -> None:
        selector = config.get("selector")
        fallback_selector = config.get("fallback_selector")
        
        if not selector or not fallback_selector:
            raise ValueError("image_exists_click 需要 selector 和 fallback_selector")

        selector_type = config.get("selector_type", "image")
        fallback_selector_type = config.get("fallback_selector_type", "image")
        image_scope = config.get("image_scope", "common")
        fallback_image_scope = config.get("fallback_image_scope", "common")
        timeout = float(config.get("timeout", 5))

        # 主定位
        _, expected_target = self._resolve_target({
            "selector_type": selector_type,
            "selector": selector,
            "image_scope": image_scope,
            "image_threshold": config.get("image_threshold")
        })
        if exists(expected_target):
            self._wait_with_timing(
                expected_target,
                timeout,
                f"image_exists_click 主定位 type={selector_type} selector={selector} scope={image_scope}"
            )
            touch(expected_target)
            return

        # 备用定位（使用独立的阈值）
        _, fallback_target = self._resolve_target({
            "selector_type": fallback_selector_type,
            "selector": fallback_selector,
            "image_scope": fallback_image_scope,
            "image_threshold": config.get("fallback_image_threshold")
        })
        self._wait_with_timing(
            fallback_target,
            timeout,
            f"image_exists_click 备用定位 type={fallback_selector_type} selector={fallback_selector} scope={fallback_image_scope}"
        )
        touch(fallback_target)

    def _step_image_exists_click_chain(self, config: Dict[str, Any]) -> None:
        selector = config.get("selector")
        fallback_selector = config.get("fallback_selector")
        
        if not selector or not fallback_selector:
            raise ValueError("image_exists_click_chain 需要 selector 和 fallback_selector")

        selector_type = config.get("selector_type", "image")
        fallback_selector_type = config.get("fallback_selector_type", "image")
        image_scope = config.get("image_scope", "common")
        fallback_image_scope = config.get("fallback_image_scope", "common")
        timeout = float(config.get("timeout", 5))

        # 主定位
        _, expected_target = self._resolve_target({
            "selector_type": selector_type,
            "selector": selector,
            "image_scope": image_scope,
            "image_threshold": config.get("image_threshold")
        })
        if exists(expected_target):
            self._wait_with_timing(
                expected_target,
                timeout,
                f"image_exists_click_chain 主定位 type={selector_type} selector={selector} scope={image_scope}"
            )
            touch(expected_target)

        # 备用定位（无论主定位是否存在都会执行，使用独立的阈值）
        _, fallback_target = self._resolve_target({
            "selector_type": fallback_selector_type,
            "selector": fallback_selector,
            "image_scope": fallback_image_scope,
            "image_threshold": config.get("fallback_image_threshold")
        })
        self._wait_with_timing(
            fallback_target,
            timeout,
            f"image_exists_click_chain 备用定位 type={fallback_selector_type} selector={fallback_selector} scope={fallback_image_scope}"
        )
        touch(fallback_target)

    def _parse_expected_list(self, value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            parts = []
            for chunk in value.splitlines():
                parts.extend(chunk.split(","))
            return [part.strip() for part in parts if part.strip()]
        if value is None:
            return []
        return [str(value).strip()]

    def _step_foreach_assert(self, config: Dict[str, Any]) -> None:
        expected_list = self._parse_expected_list(config.get("expected_list"))
        if not expected_list:
            expected_list = self._parse_expected_list(config.get("expected_list_input"))
        if not expected_list:
            raise ValueError("foreach_assert 需要 expected_list")

        for expected in expected_list:
            step_config = dict(config)
            step_config["expected"] = expected
            self._step_click_until_match(step_config)

    def _step_long_press(self, config: Dict[str, Any]) -> None:
        selector_type, target = self._resolve_target(config)
        duration = config.get("duration", 2)

        if selector_type in ("image", "pos"):
            if selector_type == "image":
                self._wait_with_timing(
                    target,
                    config.get("timeout", 5),
                    f"long_press image selector={config.get('selector')} scope={config.get('image_scope', 'game')}"
                )
            touch(target, duration=duration)
            return

        raise ValueError("long_press 仅支持 selector_type=image/pos")

    def _step_double_click(self, config: Dict[str, Any]) -> None:
        selector_type, target = self._resolve_target(config)
        if selector_type in ("image", "pos"):
            if selector_type == "image":
                self._wait_with_timing(
                    target,
                    config.get("timeout", 5),
                    f"double_click image selector={config.get('selector')} scope={config.get('image_scope', 'game')}"
                )
            double_click(target)
            return
        raise ValueError("double_click 仅支持 selector_type=image/pos")

    def _step_drag(self, config: Dict[str, Any]) -> None:
        start_type = config.get("start_selector_type")
        start_selector = config.get("start_selector")
        end_type = config.get("end_selector_type")
        end_selector = config.get("end_selector")
        duration = config.get("duration", 0.7)

        if not start_type or not end_type:
            raise ValueError("drag 需要 start_selector_type 和 end_selector_type")

        start_target = self._resolve_target({
            "selector_type": start_type,
            "selector": start_selector
        })[1]
        end_target = self._resolve_target({
            "selector_type": end_type,
            "selector": end_selector
        })[1]

        if start_type == "image":
            self._wait_with_timing(
                start_target,
                config.get("timeout", 5),
                f"drag start selector={start_selector}"
            )
        if end_type == "image":
            self._wait_with_timing(
                end_target,
                config.get("timeout", 5),
                f"drag end selector={end_selector}"
            )

        swipe(start_target, end_target, duration=duration)

    def _step_swipe_to(self, config: Dict[str, Any]) -> None:
        direction = config.get("direction", "up")
        max_swipes = int(config.get("max_swipes", 5))
        interval = float(config.get("interval", 0.5))
        selector_type = config.get("target_selector_type", "image")
        selector = config.get("target_selector")

        if selector_type != "image" or not selector:
            raise ValueError("swipe_to 仅支持 target_selector_type=image 且需要 target_selector")

        target = self._resolve_target({
            "selector_type": selector_type,
            "selector": selector
        })[1]

        width = G.DEVICE.display_info.get("width", 1080)
        height = G.DEVICE.display_info.get("height", 1920)

        for _ in range(max_swipes):
            if exists(target):
                return
            start = (int(width * 0.5), int(height * 0.7))
            end = (int(width * 0.5), int(height * 0.3))
            if direction == "down":
                start, end = end, start
            elif direction == "left":
                start = (int(width * 0.7), int(height * 0.5))
                end = (int(width * 0.3), int(height * 0.5))
            elif direction == "right":
                start = (int(width * 0.3), int(height * 0.5))
                end = (int(width * 0.7), int(height * 0.5))

            swipe(start, end, duration=config.get("duration", 0.5))
            sleep(interval)

        raise AssertionError("swipe_to 未找到目标元素")