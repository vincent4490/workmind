# -*- coding: utf-8 -*-
"""
Kimi K2.5 API 客户端封装
"""
import json
import logging
from django.conf import settings
from openai import OpenAI, AsyncOpenAI
from json_repair import repair_json

from .prompts import (
    get_testcase_prompt,
    get_testcase_prompt_multimodal,
    get_module_regenerate_prompt,
    get_module_regenerate_prompt_multimodal,
    get_function_regenerate_prompt,
    get_apply_review_prompt,
    get_dimension_review_prompt,
    get_dimension_review_prompt_multimodal,
)

logger = logging.getLogger(__name__)


class KimiClient:
    """Kimi K2.5 API 客户端"""

    def __init__(self):
        self.api_key = getattr(settings, 'KIMI_API_KEY', '')
        self.base_url = getattr(settings, 'KIMI_BASE_URL', 'https://api.moonshot.cn/v1')
        self.model = getattr(settings, 'KIMI_MODEL', 'kimi-k2.5')

        if not self.api_key:
            raise ValueError("请在 settings.py 中配置 KIMI_API_KEY")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )
        self.async_client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def generate_testcases(self, requirement: str, use_thinking: bool = False, mode: str = 'comprehensive') -> dict:
        """
        调用 Kimi API 生成测试用例

        Args:
            requirement: 功能需求描述
            use_thinking: 是否启用思考模式
            mode: 生成模式 ('comprehensive', 'focused')

        Returns:
            dict: {
                "success": bool,
                "data": {...} | None,
                "raw_content": str,
                "usage": {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int},
                "error": str | None
            }
        """
        logger.info(f"[Kimi] 开始生成用例, 模式: {mode}, 需求: {requirement[:100]}...")

        messages = get_testcase_prompt(requirement, mode)

        if use_thinking:
            extra_body = {"thinking": {"type": "enabled", "budget_tokens": 10000}}
        else:
            extra_body = {"thinking": {"type": "disabled"}}

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                extra_body=extra_body
            )

            content = response.choices[0].message.content
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

            logger.info(f"[Kimi] 生成完成, Token: 输入={usage['prompt_tokens']}, 输出={usage['completion_tokens']}")

            # 解析 JSON
            data = self._parse_json(content)
            if data is None:
                return {
                    "success": False,
                    "data": None,
                    "raw_content": content,
                    "usage": usage,
                    "error": "AI 返回的内容无法解析为 JSON"
                }

            return {
                "success": True,
                "data": data,
                "raw_content": content,
                "usage": usage,
                "error": None
            }

        except Exception as e:
            logger.error(f"[Kimi] API 调用失败: {e}")
            return {
                "success": False,
                "data": None,
                "raw_content": "",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "error": str(e)
            }

    async def generate_testcases_stream_async(self, requirement: str, use_thinking: bool = False, mode: str = 'comprehensive'):
        """
        异步流式调用 Kimi API 生成测试用例

        Args:
            requirement: 功能需求描述
            use_thinking: 是否启用思考模式
            mode: 生成模式 ('comprehensive', 'focused')

        Yields:
            dict: {"type": "chunk", "content": "..."} 或
                  {"type": "done", "content": "完整内容", "usage": {...}} 或
                  {"type": "error", "error": "..."}
        """
        logger.info(f"[Kimi] 开始流式生成用例, 模式: {mode}, 需求: {requirement[:100]}...")

        messages = get_testcase_prompt(requirement, mode)

        if use_thinking:
            extra_body = {"thinking": {"type": "enabled", "budget_tokens": 10000}}
        else:
            extra_body = {"thinking": {"type": "disabled"}}

        try:
            stream = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                extra_body=extra_body,
                stream=True,
                stream_options={"include_usage": True}
            )

            full_content = ""
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

            async for chunk in stream:
                # 提取 usage（通常在最后一个 chunk）
                if chunk.usage:
                    usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens or 0,
                        "completion_tokens": chunk.usage.completion_tokens or 0,
                        "total_tokens": chunk.usage.total_tokens or 0,
                    }

                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        full_content += delta.content
                        yield {"type": "chunk", "content": delta.content}

            yield {"type": "done", "content": full_content, "usage": usage}

        except Exception as e:
            logger.error(f"[Kimi] 流式 API 调用失败: {e}")
            yield {"type": "error", "error": str(e)}

    async def generate_testcases_multimodal_stream_async(
        self,
        requirement: str,
        extracted_texts: list,
        images: list,
        use_thinking: bool = False,
        mode: str = 'comprehensive'
    ):
        """
        多模态流式生成测试用例（文字 + 图片）

        Args:
            requirement: 用户手动输入的需求描述
            extracted_texts: [{"source": "文件名", "content": "提取的文字"}]
            images: [{"source": "文件名", "data": "base64", "mime": "image/jpeg"}]
            use_thinking: 是否启用思考模式
            mode: 生成模式 ('comprehensive', 'focused')

        Yields:
            dict: {"type": "chunk"/"done"/"error", ...}
        """
        # 根据是否有附件选择不同的 prompt
        if extracted_texts or images:
            messages = get_testcase_prompt_multimodal(requirement, extracted_texts, images, mode)
            text_summary = requirement[:50] if requirement else (extracted_texts[0]['source'] if extracted_texts else 'images')
            logger.info(f"[Kimi] 开始多模态流式生成, 模式: {mode}, 文本数={len(extracted_texts)}, 图片数={len(images)}, 摘要: {text_summary}...")
        else:
            messages = get_testcase_prompt(requirement, mode)
            logger.info(f"[Kimi] 开始流式生成用例 (纯文本), 模式: {mode}, 需求: {requirement[:100]}...")

        if use_thinking:
            extra_body = {"thinking": {"type": "enabled", "budget_tokens": 10000}}
        else:
            extra_body = {"thinking": {"type": "disabled"}}

        try:
            stream = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                extra_body=extra_body,
                stream=True,
                stream_options={"include_usage": True}
            )

            full_content = ""
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

            async for chunk in stream:
                if chunk.usage:
                    usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens or 0,
                        "completion_tokens": chunk.usage.completion_tokens or 0,
                        "total_tokens": chunk.usage.total_tokens or 0,
                    }

                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        full_content += delta.content
                        yield {"type": "chunk", "content": delta.content}

            yield {"type": "done", "content": full_content, "usage": usage}

        except Exception as e:
            logger.error(f"[Kimi] 多模态流式 API 调用失败: {e}")
            yield {"type": "error", "error": str(e)}

    async def regenerate_module_stream_async(
        self,
        module_name: str,
        existing_module_json: dict,
        module_requirement: str = '',
        adjustment: str = '',
        extracted_texts: list = None,
        images: list = None,
        requirement: str = '',
        use_thinking: bool = False
    ):
        """
        模块级重新生成 — 异步流式

        Args:
            module_name: 要重新生成的模块名称
            existing_module_json: 该模块当前已有的用例 JSON
            module_requirement: 该模块的补充需求说明（可选）
            adjustment: 用户的调整意见（可选）
            extracted_texts: [{"source": "文件名", "content": "提取的文字"}]
            images: [{"source": "文件名", "data": "base64", "mime": "image/jpeg"}]
            requirement: 用户原始需求描述
            use_thinking: 是否启用思考模式

        Yields:
            dict: {"type": "chunk"/"done"/"error", ...}
        """
        extracted_texts = extracted_texts or []
        images = images or []

        has_attachments = bool(extracted_texts or images)

        if has_attachments:
            messages = get_module_regenerate_prompt_multimodal(
                module_name, existing_module_json,
                extracted_texts, images,
                module_requirement=module_requirement,
                adjustment=adjustment,
                requirement=requirement
            )
            logger.info(f"[Kimi] 开始多模态模块重新生成, 模块={module_name}, 文本数={len(extracted_texts)}, 图片数={len(images)}")
        else:
            messages = get_module_regenerate_prompt(
                module_name, existing_module_json,
                module_requirement=module_requirement,
                adjustment=adjustment,
                requirement=requirement
            )
            logger.info(f"[Kimi] 开始纯文本模块重新生成, 模块={module_name}")

        if use_thinking:
            extra_body = {"thinking": {"type": "enabled", "budget_tokens": 10000}}
        else:
            extra_body = {"thinking": {"type": "disabled"}}

        try:
            stream = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                extra_body=extra_body,
                stream=True,
                stream_options={"include_usage": True}
            )

            full_content = ""
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

            async for chunk in stream:
                if chunk.usage:
                    usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens or 0,
                        "completion_tokens": chunk.usage.completion_tokens or 0,
                        "total_tokens": chunk.usage.total_tokens or 0,
                    }

                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        full_content += delta.content
                        yield {"type": "chunk", "content": delta.content}

            yield {"type": "done", "content": full_content, "usage": usage}

        except Exception as e:
            logger.error(f"[Kimi] 模块重新生成流式 API 调用失败: {e}")
            yield {"type": "error", "error": str(e)}

    async def regenerate_function_stream_async(
        self,
        module_name: str,
        function_name: str,
        existing_function_json: dict,
        function_requirement: str = '',
        adjustment: str = '',
        requirement: str = '',
        use_thinking: bool = False
    ):
        """
        功能点级重新生成 — 异步流式。只重新生成该功能点的 cases。
        """
        messages = get_function_regenerate_prompt(
            module_name=module_name,
            function_name=function_name,
            existing_function_json=existing_function_json,
            function_requirement=function_requirement,
            adjustment=adjustment,
            requirement=requirement
        )
        if use_thinking:
            extra_body = {"thinking": {"type": "enabled", "budget_tokens": 10000}}
        else:
            extra_body = {"thinking": {"type": "disabled"}}
        try:
            stream = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                extra_body=extra_body,
                stream=True,
                stream_options={"include_usage": True}
            )
            full_content = ""
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            async for chunk in stream:
                if chunk.usage:
                    usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens or 0,
                        "completion_tokens": chunk.usage.completion_tokens or 0,
                        "total_tokens": chunk.usage.total_tokens or 0,
                    }
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        full_content += delta.content
                        yield {"type": "chunk", "content": delta.content}
            yield {"type": "done", "content": full_content, "usage": usage}
        except Exception as e:
            logger.error(f"[Kimi] 功能点重新生成流式 API 调用失败: {e}")
            yield {"type": "error", "error": str(e)}

    async def review_testcases_stream_async(
        self,
        result_json: dict,
        extracted_texts: list = None,
        images: list = None,
        requirement: str = '',
        use_thinking: bool = False
    ):
        """
        用例评审 — 异步流式（方案 A：用分维度评审替代旧的全局评审）

        Args:
            result_json: 完整的用例 JSON（所有模块）
            extracted_texts: 从源文件提取的文本
            images: 从源文件提取的图片
            requirement: 用户原始需求描述
            use_thinking: 是否启用思考模式
        """
        extracted_texts = extracted_texts or []
        images = images or []

        has_attachments = bool(extracted_texts or images)
        dimensions = ["missing", "duplicate", "redundant", "structure"]

        logger.info(
            f"[Kimi] 开始用例评审（维度合并）dimensions={dimensions}, 多模态={has_attachments}, thinking={use_thinking}"
        )

        merged_items: list[dict] = []
        merged_summary_parts: list[str] = []
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        try:
            for dim in dimensions:
                if has_attachments:
                    messages = get_dimension_review_prompt_multimodal(
                        dim, result_json, extracted_texts, images, requirement
                    )
                else:
                    messages = get_dimension_review_prompt(dim, result_json, requirement)

                # 维度评审比旧全局评审更“聚焦”，但仍可能需要思考以提升质量
                ret = await self.run_validated_async(messages, use_thinking=use_thinking)
                total_usage["prompt_tokens"] += (ret.get("usage") or {}).get("prompt_tokens", 0)
                total_usage["completion_tokens"] += (ret.get("usage") or {}).get("completion_tokens", 0)
                total_usage["total_tokens"] += (ret.get("usage") or {}).get("total_tokens", 0)

                if not ret.get("success"):
                    merged_summary_parts.append(f"{dim}: 评审失败({ret.get('error')})")
                    continue

                data = ret.get("data") or {}
                items = data.get("items") if isinstance(data, dict) else None
                if isinstance(items, list):
                    merged_items.extend(items)
                    merged_summary_parts.append(f"{dim}: {len(items)}项")
                else:
                    merged_summary_parts.append(f"{dim}: 输出格式异常")

            # 合并为一个兼容的“全局评审”输出（供前端/调用方展示）
            merged_out = {
                "summary": "；".join(merged_summary_parts) if merged_summary_parts else "维度评审完成",
                "total_issues": len(merged_items),
                "items": merged_items,
            }

            out_text = json.dumps(merged_out, ensure_ascii=False, indent=2)

            # 保持流式语义：把最终 JSON 分片 yield 出去
            chunk_size = 800
            for i in range(0, len(out_text), chunk_size):
                yield {"type": "chunk", "content": out_text[i : i + chunk_size]}
            yield {"type": "done", "content": out_text, "usage": total_usage}

        except Exception as e:
            logger.error(f"[Kimi] 用例评审（维度合并）失败: {e}")
            yield {"type": "error", "error": str(e)}

    async def review_dimension_stream_async(
        self,
        dimension_key: str,
        result_json: dict,
        extracted_texts: list = None,
        images: list = None,
        requirement: str = '',
    ):
        """
        单维度评审 — 异步流式（不启用思考模式以加速，每个维度 Prompt 已经很聚焦）
        """
        extracted_texts = extracted_texts or []
        images = images or []

        has_attachments = bool(extracted_texts or images)

        if has_attachments:
            messages = get_dimension_review_prompt_multimodal(
                dimension_key, result_json, extracted_texts, images, requirement
            )
        else:
            messages = get_dimension_review_prompt(dimension_key, result_json, requirement)

        logger.info(f"[Kimi] 开始维度评审: {dimension_key}, 多模态={has_attachments}")

        # 维度评审默认启用思考模式（深入分析）
        extra_body = {"thinking": {"type": "enabled", "budget_tokens": 10000}}

        try:
            stream = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                extra_body=extra_body,
                stream=True,
                stream_options={"include_usage": True}
            )

            full_content = ""
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

            async for chunk in stream:
                if chunk.usage:
                    usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens or 0,
                        "completion_tokens": chunk.usage.completion_tokens or 0,
                        "total_tokens": chunk.usage.total_tokens or 0,
                    }

                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        full_content += delta.content
                        yield {"type": "chunk", "content": delta.content}

            yield {"type": "done", "content": full_content, "usage": usage}

        except Exception as e:
            logger.error(f"[Kimi] 维度评审 {dimension_key} 流式 API 调用失败: {e}")
            yield {"type": "error", "error": str(e)}

    async def apply_review_stream_async(
        self,
        result_json: dict,
        selected_items: list,
        use_thinking: bool = False
    ):
        """
        采纳评审意见 — 异步流式

        Args:
            result_json: 当前完整的用例 JSON
            selected_items: 用户选定要采纳的评审项列表
            use_thinking: 是否启用思考模式
        """
        messages = get_apply_review_prompt(result_json, selected_items)
        logger.info(f"[Kimi] 开始采纳评审意见, 选中 {len(selected_items)} 项")

        # 采纳步骤强制关闭思考模式：输出是结构化变更指令，不需要深度推理
        extra_body = {"thinking": {"type": "disabled"}}

        try:
            stream = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                extra_body=extra_body,
                stream=True,
                stream_options={"include_usage": True}
            )

            full_content = ""
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

            async for chunk in stream:
                if chunk.usage:
                    usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens or 0,
                        "completion_tokens": chunk.usage.completion_tokens or 0,
                        "total_tokens": chunk.usage.total_tokens or 0,
                    }

                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        full_content += delta.content
                        yield {"type": "chunk", "content": delta.content}

            yield {"type": "done", "content": full_content, "usage": usage}

        except Exception as e:
            logger.error(f"[Kimi] 采纳评审意见流式 API 调用失败: {e}")
            yield {"type": "error", "error": str(e)}

    async def run_validated_async(
        self,
        messages: list,
        use_thinking: bool = False,
        max_retries: int = 2,
    ) -> dict:
        """
        非流式调用 + JSON 解析 + 校验重试（Agent 节点使用）。

        如果 LLM 返回的内容无法解析为 JSON，会把解析错误追加到对话中
        让模型修正输出，最多重试 max_retries 次。

        Returns:
            {"success": bool, "data": dict|None, "raw": str, "usage": dict, "error": str|None}
        """
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        if use_thinking:
            extra_body = {"thinking": {"type": "enabled", "budget_tokens": 10000}}
        else:
            extra_body = {"thinking": {"type": "disabled"}}

        conv = list(messages)
        last_raw = ""

        for attempt in range(1 + max_retries):
            try:
                response = await self.async_client.chat.completions.create(
                    model=self.model,
                    messages=conv,
                    extra_body=extra_body,
                )
                content = response.choices[0].message.content or ""
                last_raw = content
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens or 0,
                    "completion_tokens": response.usage.completion_tokens or 0,
                    "total_tokens": response.usage.total_tokens or 0,
                }
                total_usage["prompt_tokens"] += usage["prompt_tokens"]
                total_usage["completion_tokens"] += usage["completion_tokens"]
                total_usage["total_tokens"] += usage["total_tokens"]

                data = self._parse_json(content)
                if data is not None:
                    return {"success": True, "data": data, "raw": content, "usage": total_usage, "error": None}

                if attempt < max_retries:
                    conv.append({"role": "assistant", "content": content})
                    conv.append({"role": "user", "content": "你的输出不是合法的 JSON，请重新输出，只返回纯 JSON，不要有任何 markdown 标记或额外文字。"})
                    logger.warning(f"[Kimi] run_validated 第 {attempt+1} 次 JSON 解析失败，重试中...")

            except Exception as e:
                logger.error(f"[Kimi] run_validated API 调用失败 (attempt {attempt+1}): {e}")
                return {"success": False, "data": None, "raw": last_raw, "usage": total_usage, "error": str(e)}

        return {"success": False, "data": None, "raw": last_raw, "usage": total_usage, "error": "多次重试后仍无法解析为合法 JSON"}

    @staticmethod
    def _parse_json(content: str) -> dict | None:
        """
        解析 AI 返回的 JSON（使用 json_repair 增强容错能力）
        
        处理流程：
        1. 去除 markdown 代码块标记
        2. 尝试标准 json.loads()
        3. 失败时使用 json_repair 修复并重试
        """
        text = content.strip()
        
        # 去掉 markdown 代码块标记
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # 尝试标准解析
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"[Kimi] 标准 JSON 解析失败: {e}, 尝试使用 json_repair 修复...")
            
            # 使用 json_repair 修复并重试
            try:
                repaired_text = repair_json(text)
                result = json.loads(repaired_text)
                logger.info(f"[Kimi] JSON 修复成功")
                return result
            except Exception as repair_error:
                logger.error(f"[Kimi] JSON 修复失败: {repair_error}, 内容前200字: {text[:200]}")
                return None
