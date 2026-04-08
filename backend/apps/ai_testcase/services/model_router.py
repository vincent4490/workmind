# -*- coding: utf-8 -*-
"""
P2：AI 用例智能体多模型路由层

目的：
- 按阶段选择模型（generate/review/refine/analyze/plan）
- DeepSeek key 缺失时自动回退到 Kimi
- 提供成本估算（$/M tokens）
"""
import json
import logging
from decimal import Decimal

from django.conf import settings
from openai import OpenAI, AsyncOpenAI

logger = logging.getLogger(__name__)


class TestcaseModelRouter:
    # 模型计费（$/M tokens）
    COST_TABLE = {
        'kimi-k2.5': {'input': Decimal('0.45'), 'output': Decimal('0.90')},
        'deepseek-r1': {'input': Decimal('0.14'), 'output': Decimal('0.28')},
        'deepseek-reasoner': {'input': Decimal('0.14'), 'output': Decimal('0.28')},
        'deepseek-chat': {'input': Decimal('0.14'), 'output': Decimal('0.28')},
    }

    def __init__(self):
        kimi_key = getattr(settings, 'KIMI_API_KEY', '')
        kimi_url = getattr(settings, 'KIMI_BASE_URL', 'https://api.moonshot.cn/v1')
        if not kimi_key:
            raise ValueError("请在 settings.py 中配置 KIMI_API_KEY")

        self.kimi_client = OpenAI(api_key=kimi_key, base_url=kimi_url)
        self.kimi_async = AsyncOpenAI(api_key=kimi_key, base_url=kimi_url)

        ds_key = getattr(settings, 'DEEPSEEK_API_KEY', '')
        ds_url = getattr(settings, 'DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')
        self.deepseek_client = OpenAI(api_key=ds_key, base_url=ds_url) if ds_key else None
        self.deepseek_async = AsyncOpenAI(api_key=ds_key, base_url=ds_url) if ds_key else None

    def select_model(self, stage: str) -> str:
        """
        stage: generate/review/refine/analyze/plan
        """
        stage = (stage or 'generate').strip().lower()
        if stage == 'review':
            model = getattr(settings, 'AI_TESTCASE_MODEL_REVIEW', 'kimi-k2.5')
        elif stage == 'refine':
            model = getattr(settings, 'AI_TESTCASE_MODEL_REFINE', 'kimi-k2.5')
        elif stage in ('analyze', 'plan'):
            # 默认沿用 review 模型，后续可单独拆分配置
            model = getattr(settings, 'AI_TESTCASE_MODEL_REVIEW', 'kimi-k2.5')
        else:
            model = getattr(settings, 'AI_TESTCASE_MODEL_GENERATE', 'deepseek-chat')

        # 关键：如果选择了 deepseek 但没配 key，必须连同 model 一起回退到 Kimi，
        # 否则会出现 “用 Kimi client 请求 deepseek model” → 404(model not found)。
        if 'deepseek' in (model or '') and not self._has_deepseek():
            fallback_model = getattr(settings, 'KIMI_MODEL', 'kimi-k2.5')
            logger.info(f"[ai_testcase] model_router.fallback | from={model} to={fallback_model}")
            return fallback_model
        return model

    def _has_deepseek(self) -> bool:
        return self.deepseek_client is not None and self.deepseek_async is not None

    def get_client(self, model: str, *, async_: bool):
        """
        返回 OpenAI/AsyncOpenAI client（根据 model 决定走 Kimi 或 DeepSeek）。
        """
        if 'deepseek' in (model or ''):
            if self._has_deepseek():
                return self.deepseek_async if async_ else self.deepseek_client
            # model 已在 select_model 中做回退，这里兜底返回 Kimi client
            return self.kimi_async if async_ else self.kimi_client
        return self.kimi_async if async_ else self.kimi_client

    def calculate_cost_usd(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        rates = self.COST_TABLE.get(model, self.COST_TABLE['kimi-k2.5'])
        cost = (
            Decimal(int(prompt_tokens)) / Decimal('1000000') * rates['input']
            + Decimal(int(completion_tokens)) / Decimal('1000000') * rates['output']
        )
        return float(cost.quantize(Decimal('0.000001')))

    @staticmethod
    def parse_json(content: str) -> dict | None:
        """
        解析 AI 返回的 JSON（兼容 markdown 代码块包裹、末尾多余文字或重复 JSON）。
        """
        text = (content or '').strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取第一个 JSON 对象，避免 Extra data
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
                        try:
                            return json.loads(text[start:i + 1])
                        except json.JSONDecodeError:
                            return None
            return None

