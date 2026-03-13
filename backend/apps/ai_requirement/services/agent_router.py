# -*- coding: utf-8 -*-
"""
需求智能体核心路由层

role + task_type → 选择 Prompt 版本 → 选择模型 → 流式/验证输出
"""
import json
import logging
import random
from decimal import Decimal

from django.conf import settings
from openai import AsyncOpenAI

from .security import SecurityMiddleware, SecurityError
from .schemas import SCHEMA_REGISTRY

logger = logging.getLogger(__name__)


class RequirementAgentRouter:
    """
    单智能体多任务路由。

    提供两种调用方式：
    - run_stream:    流式输出（前端实时展示），不做 Schema 验证
    - run_validated: 非流式 + Pydantic 强校验 + 重试（下游系统消费）
    """

    MODEL_CONFIG = {
        'default': 'kimi-k2.5',
        'tech_design_deep': 'deepseek-r1',
        'fallback': 'deepseek-chat',
        'confidential': 'deepseek-chat',  # 机密级默认走 DeepSeek，可被 settings 覆盖
    }

    # 模型计费（$/M tokens）
    COST_TABLE = {
        'kimi-k2.5': {'input': Decimal('0.45'), 'output': Decimal('0.90')},
        'deepseek-r1': {'input': Decimal('0.14'), 'output': Decimal('0.28')},
        'deepseek-chat': {'input': Decimal('0.14'), 'output': Decimal('0.28')},
    }

    def __init__(self):
        self.security = SecurityMiddleware()

        # Kimi 客户端（主模型）
        api_key = getattr(settings, 'KIMI_API_KEY', '')
        base_url = getattr(settings, 'KIMI_BASE_URL', 'https://api.moonshot.cn/v1')
        if not api_key:
            raise ValueError("请在 settings.py 中配置 KIMI_API_KEY")

        self.async_client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        # DeepSeek 客户端（备选/增强，可选配置）
        ds_key = getattr(settings, 'DEEPSEEK_API_KEY', '')
        ds_url = getattr(settings, 'DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')
        self.deepseek_client = (
            AsyncOpenAI(api_key=ds_key, base_url=ds_url)
            if ds_key else None
        )

    def select_model(
        self,
        role: str,
        task_type: str,
        use_thinking: bool = False,
        security_level: str = 'internal',
    ) -> str:
        # 机密数据强制路由到指定模型（如本地/私有化部署）
        if security_level == 'confidential':
            confidential_model = getattr(
                settings, 'AI_REQUIREMENT_CONFIDENTIAL_MODEL', None
            ) or self.MODEL_CONFIG.get('confidential') or self.MODEL_CONFIG['fallback']
            return confidential_model
        if task_type == 'tech_design' and use_thinking and self.deepseek_client:
            return self.MODEL_CONFIG['tech_design_deep']
        return self.MODEL_CONFIG['default']

    def _get_client(self, model: str) -> AsyncOpenAI:
        if 'deepseek' in model and self.deepseek_client:
            return self.deepseek_client
        return self.async_client

    def get_prompt(self, role: str, task_type: str) -> str:
        """
        获取 Prompt 文本，优先从数据库 PromptVersion 加载（支持版本管理/A/B 测试），
        否则降级到代码内置 Prompt。
        """
        try:
            from apps.ai_requirement.models import PromptVersion
            active = PromptVersion.objects.filter(
                task_type=task_type, is_active=True
            ).first()

            if active:
                # A/B 测试分流
                candidate = PromptVersion.objects.filter(
                    task_type=task_type, is_ab_candidate=True
                ).first()
                if candidate and random.random() < candidate.ab_traffic_ratio:
                    return candidate.system_prompt, candidate.version
                return active.system_prompt, active.version
        except Exception:
            pass

        # 降级：从代码内置 Prompt 加载
        from .prompts import PROMPT_REGISTRY
        prompt_obj = PROMPT_REGISTRY.get((role, task_type))
        if prompt_obj is None:
            raise ValueError(f"不支持的任务类型: {role}/{task_type}")
        return prompt_obj.get_full_system_prompt(), 'builtin'

    def build_messages(
        self,
        system_prompt: str,
        requirement_input: str,
        extracted_texts: list = None,
        images: list = None,
    ) -> list:
        """构建消息列表（兼容多模态）"""
        messages = [{"role": "system", "content": system_prompt}]

        user_content = []

        # 文本输入
        text_parts = []
        if requirement_input:
            text_parts.append(requirement_input)
        if extracted_texts:
            for t in extracted_texts:
                text_parts.append(f"\n--- 文件: {t['source']} ---\n{t['content']}")
        if text_parts:
            user_content.append({
                "type": "text",
                "text": "\n".join(text_parts),
            })

        # 图片输入
        if images:
            for img in images:
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{img['mime']};base64,{img['data']}"
                    },
                })

        if not user_content:
            raise ValueError("至少需要文本输入或上传文件")

        # 如果只有纯文本且无图片，用简单格式
        if len(user_content) == 1 and user_content[0]["type"] == "text":
            messages.append({"role": "user", "content": user_content[0]["text"]})
        else:
            messages.append({"role": "user", "content": user_content})

        return messages

    def estimate_cost_usd(
        self,
        role: str,
        task_type: str,
        requirement_input: str,
        extracted_texts: list = None,
        images: list = None,
        use_thinking: bool = False,
        security_level: str = 'internal',
    ) -> float:
        """
        预估单次任务成本（USD）。用于超阈值时要求前端确认。
        输入 token 估算：文本约 0.5 字符/token，每图约 500 token；输出固定 2000 token。
        """
        text_len = len(requirement_input or '')
        if extracted_texts:
            text_len += sum(len((t.get('content') or '')) for t in extracted_texts)
        num_images = len(images or [])
        prompt_tokens = int(text_len * 0.5) + num_images * 500
        completion_tokens = 2000
        model = self.select_model(role, task_type, use_thinking, security_level)
        cost = self.calculate_cost(model, prompt_tokens, completion_tokens)
        return float(cost)

    async def run_stream(
        self,
        role: str,
        task_type: str,
        requirement_input: str,
        extracted_texts: list = None,
        images: list = None,
        use_thinking: bool = False,
        security_level: str = 'internal',
    ):
        """
        流式生成（前端实时展示），不做 Schema 验证。

        Yields:
            dict: {"type": "chunk"/"done"/"error", ...}
        """
        # 安全检查
        context = self.security.pre_process({
            'requirement_input': requirement_input,
            'security_level': security_level,
        })
        requirement_input = context['requirement_input']

        system_prompt, prompt_ver = self.get_prompt(role, task_type)
        # P2-4 RAG：注入历史 PRD/术语表片段
        try:
            from asgiref.sync import sync_to_async
            from .rag import get_rag_context
            rag_context = await sync_to_async(get_rag_context)(requirement_input, task_type)
            if rag_context:
                system_prompt = system_prompt + "\n\n" + rag_context
        except Exception as e:
            logger.debug("RAG context inject skip: %s", e)

        model = self.select_model(role, task_type, use_thinking, security_level)
        client = self._get_client(model)

        messages = self.build_messages(
            system_prompt, requirement_input, extracted_texts, images
        )

        extra_body = {}
        if use_thinking:
            extra_body = {"thinking": {"type": "enabled", "budget_tokens": 10000}}
        else:
            extra_body = {"thinking": {"type": "disabled"}}

        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                extra_body=extra_body,
                stream=True,
                stream_options={"include_usage": True},
                temperature=0.6,  # Kimi k2.5 仅支持 0.6
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

            yield {
                "type": "done",
                "content": full_content,
                "usage": usage,
                "model": model,
                "prompt_version": prompt_ver,
            }

        except Exception as e:
            logger.error(f"[RequirementAgent] 流式调用失败: {e}")
            yield {"type": "error", "error": str(e)}

    async def run_validated(
        self,
        role: str,
        task_type: str,
        requirement_input: str,
        extracted_texts: list = None,
        images: list = None,
        use_thinking: bool = False,
        security_level: str = 'internal',
        max_retries: int = 2,
        system_prompt_override: str = None,
        prompt_version_override: str = None,
    ) -> dict:
        """
        非流式 + Pydantic 强校验 + 自动重试。
        用于下游系统消费（如桥接至用例智能体）。

        校验失败时将错误信息反馈给 LLM 重新生成（最多 max_retries 次）。

        Returns:
            dict: {
                "validated": True/False,
                "data": Pydantic model dict (if validated),
                "raw": str,
                "retries": int,
                "usage": dict,
                "model": str,
                "prompt_version": str,
            }
        """
        from pydantic import ValidationError

        schema_cls = SCHEMA_REGISTRY.get(task_type)

        context = self.security.pre_process({
            'requirement_input': requirement_input,
            'security_level': security_level,
        })
        requirement_input = context['requirement_input']

        if system_prompt_override is not None and prompt_version_override is not None:
            system_prompt, prompt_ver = system_prompt_override, prompt_version_override
        else:
            system_prompt, prompt_ver = self.get_prompt(role, task_type)
        # P2-4 RAG：注入历史 PRD/术语表片段
        try:
            from asgiref.sync import sync_to_async
            from .rag import get_rag_context
            rag_context = await sync_to_async(get_rag_context)(requirement_input, task_type)
            if rag_context:
                system_prompt = system_prompt + "\n\n" + rag_context
        except Exception as e:
            logger.debug("RAG context inject skip: %s", e)

        model = self.select_model(role, task_type, use_thinking, security_level)
        client = self._get_client(model)

        messages = self.build_messages(
            system_prompt, requirement_input, extracted_texts, images
        )

        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        last_raw = ""
        retries = 0

        for attempt in range(1 + max_retries):
            extra_body = (
                {"thinking": {"type": "enabled", "budget_tokens": 10000}}
                if use_thinking
                else {"thinking": {"type": "disabled"}}
            )

            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                extra_body=extra_body,
                stream=False,
                temperature=0.6,  # Kimi k2.5 仅支持 0.6
            )

            content = response.choices[0].message.content or ""
            last_raw = content

            if response.usage:
                total_usage["prompt_tokens"] += response.usage.prompt_tokens or 0
                total_usage["completion_tokens"] += response.usage.completion_tokens or 0
                total_usage["total_tokens"] += response.usage.total_tokens or 0

            parsed = self.parse_json(content)
            if parsed is None:
                if attempt < max_retries:
                    retries += 1
                    messages.append({"role": "assistant", "content": content})
                    messages.append({
                        "role": "user",
                        "content": "你的输出不是合法的 JSON。请严格按照要求只输出 JSON，不要有其他文字。",
                    })
                    continue
                return {
                    "validated": False, "data": None, "raw": last_raw,
                    "retries": retries, "usage": total_usage,
                    "model": model, "prompt_version": prompt_ver,
                    "error": "JSON 解析失败",
                }

            if schema_cls is None:
                return {
                    "validated": True, "data": parsed, "raw": last_raw,
                    "retries": retries, "usage": total_usage,
                    "model": model, "prompt_version": prompt_ver,
                }

            try:
                validated_obj = schema_cls.model_validate(parsed)
                return {
                    "validated": True, "data": validated_obj.model_dump(by_alias=True),
                    "raw": last_raw, "retries": retries, "usage": total_usage,
                    "model": model, "prompt_version": prompt_ver,
                }
            except ValidationError as ve:
                if attempt < max_retries:
                    retries += 1
                    error_msg = "; ".join(
                        f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}"
                        for e in ve.errors()[:5]
                    )
                    messages.append({"role": "assistant", "content": content})
                    messages.append({
                        "role": "user",
                        "content": f"你的 JSON 有以下字段校验错误，请修正后重新输出完整 JSON：\n{error_msg}",
                    })
                    continue
                return {
                    "validated": False, "data": parsed, "raw": last_raw,
                    "retries": retries, "usage": total_usage,
                    "model": model, "prompt_version": prompt_ver,
                    "error": str(ve),
                }

        return {
            "validated": False, "data": None, "raw": last_raw,
            "retries": retries, "usage": total_usage,
            "model": model, "prompt_version": prompt_ver,
            "error": "超过最大重试次数",
        }

    async def run_dual_model_verified(
        self,
        role: str,
        task_type: str,
        requirement_input: str,
        extracted_texts: list = None,
        images: list = None,
        security_level: str = 'internal',
    ):
        """
        DeepSeek-R1 双模型验证（仅用于 tech_design）

        流程：
        1. 主模型（Kimi K2.5）生成初稿
        2. DeepSeek-R1 对初稿做深度推理验证，输出补充分析和风险评估

        Yields:
            dict: {"type": "phase1_start"|"phase1_chunk"|"phase2_start"|"phase2_chunk"|"done"|"error", ...}
        """
        security_level = security_level or 'internal'
        if not self.deepseek_client:
            async for event in self.run_stream(role, task_type, requirement_input, extracted_texts, images, False, security_level):
                yield event
            return

        yield {'type': 'phase1_start', 'message': '阶段一：主模型生成技术方案...'}

        phase1_content = ''
        phase1_usage = {}
        phase1_model = ''

        async for event in self.run_stream(role, task_type, requirement_input, extracted_texts, images, False, security_level):
            if event['type'] == 'chunk':
                phase1_content += event['content']
                yield {'type': 'phase1_chunk', 'content': event['content']}
            elif event['type'] == 'done':
                phase1_content = event['content']
                phase1_usage = event.get('usage', {})
                phase1_model = event.get('model', '')
            elif event['type'] == 'error':
                yield event
                return

        yield {'type': 'phase2_start', 'message': '阶段二：DeepSeek-R1 深度推理验证...'}

        verify_prompt = (
            '你是一位资深架构师，请对以下技术方案进行深度审查。'
            '请使用深度推理能力，重点关注：\n'
            '1. 架构合理性和可扩展性\n'
            '2. 潜在技术风险和性能瓶颈\n'
            '3. 安全隐患\n'
            '4. 遗漏的边界条件\n'
            '5. 改进建议\n\n'
            '请输出 JSON 格式：\n'
            '{"verification_score": 0-1, "risks": [...], "improvements": [...], '
            '"missing_concerns": [...], "overall_assessment": "..."}\n\n'
            f'--- 技术方案 ---\n{phase1_content[:8000]}'
        )

        r1_model = self.MODEL_CONFIG.get('tech_design_deep', 'deepseek-r1')
        phase2_content = ''
        phase2_usage = {}

        try:
            stream = await self.deepseek_client.chat.completions.create(
                model=r1_model,
                messages=[
                    {'role': 'system', 'content': '你是资深技术架构师，负责审查技术方案。请使用深度推理。'},
                    {'role': 'user', 'content': verify_prompt},
                ],
                stream=True,
                stream_options={'include_usage': True},
                temperature=0.6,  # Kimi k2.5 仅支持 0.6
            )

            async for chunk in stream:
                if chunk.usage:
                    phase2_usage = {
                        'prompt_tokens': chunk.usage.prompt_tokens or 0,
                        'completion_tokens': chunk.usage.completion_tokens or 0,
                        'total_tokens': chunk.usage.total_tokens or 0,
                    }
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        phase2_content += delta.content
                        yield {'type': 'phase2_chunk', 'content': delta.content}

        except Exception as e:
            logger.warning(f'[RequirementAgent] R1 验证失败，降级使用主模型结果: {e}')
            yield {'type': 'phase2_fallback', 'message': f'R1 验证跳过: {e}'}

        merged_usage = {
            'prompt_tokens': phase1_usage.get('prompt_tokens', 0) + phase2_usage.get('prompt_tokens', 0),
            'completion_tokens': phase1_usage.get('completion_tokens', 0) + phase2_usage.get('completion_tokens', 0),
            'total_tokens': phase1_usage.get('total_tokens', 0) + phase2_usage.get('total_tokens', 0),
        }

        verification_json = self.parse_json(phase2_content)

        full_output = phase1_content
        if phase2_content:
            full_output += '\n\n---\n## DeepSeek-R1 深度验证报告\n\n' + phase2_content

        yield {
            'type': 'done',
            'content': full_output,
            'usage': merged_usage,
            'model': f'{phase1_model}+{r1_model}',
            'prompt_version': 'dual_verified',
            'verification': verification_json,
        }

    def calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> Decimal:
        rates = self.COST_TABLE.get(model, self.COST_TABLE['kimi-k2.5'])
        cost = (
            Decimal(prompt_tokens) / Decimal('1000000') * rates['input']
            + Decimal(completion_tokens) / Decimal('1000000') * rates['output']
        )
        return cost.quantize(Decimal('0.000001'))

    @staticmethod
    def _extract_first_json_object(text: str) -> str | None:
        """从字符串中提取第一个完整 JSON 对象（按花括号匹配），避免 Extra data 解析失败。"""
        start = text.find('{')
        if start < 0:
            return None
        depth = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        return None

    @staticmethod
    def parse_json(content: str) -> dict | None:
        """解析 AI 返回的 JSON（兼容 markdown 代码块包裹、末尾多余文字或重复 JSON）"""
        text = content.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            if "Extra data" in str(e) or "expecting value" in str(e).lower():
                first = RequirementAgentRouter._extract_first_json_object(text)
                if first:
                    try:
                        return json.loads(first)
                    except json.JSONDecodeError:
                        pass
            logger.error(f"[RequirementAgent] JSON 解析失败: {e}, 前200字: {text[:200]}")
            return None
