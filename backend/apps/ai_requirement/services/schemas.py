# -*- coding: utf-8 -*-
"""
Pydantic Schema 定义 —— 结构化输出验证的核心

每个任务类型对应一个 Schema，由 instructor 库在 LLM 调用后自动验证。
验证失败时 instructor 会将错误反馈给 LLM 并重试（最多 max_retries 次）。
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ============ PRD 撰写 (prd_draft) ============

class AcceptanceCriterion(BaseModel):
    id: str = Field(description="验收标准ID，如AC-001")
    predicate: str = Field(
        description="谓词语法：当...时，系统应...",
        min_length=10
    )
    testable: bool = Field(description="是否可自动化测试")
    automated_test_hint: Optional[str] = Field(
        default=None,
        description="自动化测试建议"
    )
    dependencies: Optional[list[str]] = Field(
        default=None,
        description="依赖的其他用户故事ID"
    )

    @field_validator('predicate')
    @classmethod
    def predicate_must_follow_pattern(cls, v):
        if '当' not in v and '应' not in v and 'when' not in v.lower():
            raise ValueError('验收标准必须使用"当...时，系统应..."的谓词语法')
        return v


class ExampleIO(BaseModel):
    input: str = Field(description="具体输入描述")
    expected_output: str = Field(description="预期输出描述")


class StateTransition(BaseModel):
    from_state: str = Field(alias="from", description="起始状态")
    event: str = Field(description="触发事件")
    to_state: str = Field(alias="to", description="目标状态")

    model_config = {"populate_by_name": True}


class StateMachine(BaseModel):
    states: list[str] = Field(min_length=2, description="状态枚举列表")
    transitions: list[StateTransition] = Field(
        min_length=1,
        description="状态转换列表"
    )


class ErrorMapping(BaseModel):
    code: int = Field(description="HTTP状态码或业务错误码")
    condition: str = Field(description="触发条件")
    user_message: str = Field(description="用户提示信息")
    action: Optional[str] = Field(default=None, description="前端动作")


class UserStory(BaseModel):
    id: str = Field(description="用户故事ID，如US-001")
    role: str = Field(description="角色，如：作为管理员")
    action: str = Field(description="行为描述")
    benefit: str = Field(description="业务价值")
    acceptance_criteria: list[AcceptanceCriterion] = Field(min_length=1)
    example_io: Optional[list[ExampleIO]] = Field(
        default=None,
        description="输入/输出示例"
    )
    state_machine: Optional[StateMachine] = Field(
        default=None,
        description="功能状态机（涉及交互时必填）"
    )
    error_mapping: Optional[list[ErrorMapping]] = Field(
        default=None,
        description="错误码映射"
    )


class PRDMeta(BaseModel):
    version: str = Field(default="v1.0")
    snapshot_id: Optional[str] = Field(default=None)
    confidence_score: float = Field(ge=0, le=1, description="置信度 0-1")
    requires_clarification: bool = Field(default=False)
    clarification_questions: Optional[list[str]] = Field(default=None)


class PRDIntent(BaseModel):
    problem_statement: str = Field(min_length=10, description="用户痛点描述")
    success_criteria: list[str] = Field(min_length=1)
    out_of_scope: Optional[list[str]] = Field(default=None)


class NonFunctional(BaseModel):
    performance: Optional[dict] = None
    security: Optional[dict] = None
    architectural_constraints: Optional[dict] = None


class AgenticPRDSchema(BaseModel):
    """Agentic PRD 完整输出 Schema"""
    prd_meta: PRDMeta
    intent: PRDIntent
    user_stories: list[UserStory] = Field(min_length=1)
    non_functional: Optional[NonFunctional] = None
    glossary: Optional[dict[str, str]] = Field(default_factory=dict)
    markdown_full: str = Field(
        min_length=100,
        description="完整 PRD Markdown 正文"
    )


# ============ 其他任务 Schema（Phase 1 后期补充）============

class CompetitiveAnalysisSchema(BaseModel):
    """竞品分析输出 Schema"""
    comparison_matrix: list[dict] = Field(min_length=1)
    swot: Optional[dict] = None
    ui_analysis: Optional[str] = None
    confidence_score: float = Field(ge=0, le=1)


class RequirementAnalysisSchema(BaseModel):
    """需求分析输出 Schema"""
    functional_decomposition: list[dict] = Field(min_length=1)
    technical_impact: Optional[list[dict]] = None
    risks: Optional[list[dict]] = None
    confidence_score: float = Field(ge=0, le=1)


class TechDesignSchema(BaseModel):
    """技术方案输出 Schema"""
    architecture: dict
    api_contracts: Optional[list[dict]] = None
    mermaid_diagram: Optional[str] = None
    risks: Optional[list[dict]] = None
    confidence_score: float = Field(ge=0, le=1)


class TestReqAnalysisSchema(BaseModel):
    """测试需求分析输出 Schema"""
    testability_assessment: list[dict] = Field(min_length=1)
    untestable_items: Optional[list[dict]] = None
    risk_areas: Optional[list[dict]] = None
    confidence_score: float = Field(ge=0, le=1)


class PRDRefineSchema(BaseModel):
    """PRD 修订输出 Schema"""
    changes: list[dict] = Field(min_length=1)
    updated_prd: dict
    change_summary: str
    confidence_score: float = Field(ge=0, le=1)


SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    'prd_draft': AgenticPRDSchema,
    'competitive_analysis': CompetitiveAnalysisSchema,
    'requirement_analysis': RequirementAnalysisSchema,
    'tech_design': TechDesignSchema,
    'test_requirement_analysis': TestReqAnalysisSchema,
    'prd_refine': PRDRefineSchema,
}
