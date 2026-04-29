# -*- coding: utf-8 -*-

from apps.ai_testcase.services.agent_prompts import (
    GENERATE_MODULE_SYSTEM,
    PLAN_TEST_STRATEGY_SYSTEM,
)
from apps.ai_testcase.services.mode_policy import render_mode_guide_for_agent
from apps.ai_testcase.services.prompts import (
    TESTCASE_SYSTEM_PROMPT_COMPREHENSIVE,
    TESTCASE_SYSTEM_PROMPT_FOCUSED,
    TESTCASE_SYSTEM_PROMPT_WITH_ATTACHMENTS_COMPREHENSIVE,
    TESTCASE_SYSTEM_PROMPT_WITH_ATTACHMENTS_FOCUSED,
)
from apps.ai_testcase.testcase_config import build_quantity_instruction


def test_mode_guide_uses_flexible_budget_not_hard_case_range():
    guide = render_mode_guide_for_agent("focused")

    assert "建议预算" in guide
    assert "不是硬性上下限" in guide
    assert "覆盖优先" in guide
    assert "case_count_range" not in guide


def test_agent_prompts_use_only_case_budget_without_legacy_count_fields():
    assert "建议预算" in PLAN_TEST_STRATEGY_SYSTEM
    assert "case_budget" in PLAN_TEST_STRATEGY_SYSTEM
    assert "case_count_target" not in PLAN_TEST_STRATEGY_SYSTEM
    assert "case_count_range" not in PLAN_TEST_STRATEGY_SYSTEM
    assert "case_count_range" not in GENERATE_MODULE_SYSTEM
    assert "严格遵循策略中指定的测试方法和 case_count_range" not in GENERATE_MODULE_SYSTEM


def test_direct_prompts_do_not_use_fixed_per_function_case_limits():
    prompts = [
        TESTCASE_SYSTEM_PROMPT_COMPREHENSIVE,
        TESTCASE_SYSTEM_PROMPT_FOCUSED,
        TESTCASE_SYSTEM_PROMPT_WITH_ATTACHMENTS_COMPREHENSIVE,
        TESTCASE_SYSTEM_PROMPT_WITH_ATTACHMENTS_FOCUSED,
    ]

    for prompt in prompts:
        assert "每个功能点生成 5-15 个用例" not in prompt
        assert "每个功能点生成 3-10 个用例" not in prompt
        assert "用例预算" in prompt
        assert "不能为了凑数量生成低价值重复用例" in prompt


def test_legacy_quantity_instruction_uses_budget_language():
    instruction = build_quantity_instruction("medium")

    assert "建议预算" in instruction
    assert "硬性上下限" in instruction or "不为凑数量" in instruction
    assert "每个功能点生成" not in instruction
