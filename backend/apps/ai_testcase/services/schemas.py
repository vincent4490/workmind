# -*- coding: utf-8 -*-
"""
ai_testcase 结构化输出 Schema（Pydantic v2）

用于在写库/导出前做强校验，避免“看似 JSON 但结构漂移”导致后续流程崩溃。
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


Priority = Literal["P0", "P1", "P2", "P3"]


class TestcaseCase(BaseModel):
    """核心字段供 XMind/校验；coverage_points 等附加字段允许透传。"""

    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1, max_length=500)
    priority: Priority = "P1"
    precondition: str = ""
    steps: str = ""
    expected: str = ""


class TestcaseFunction(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    cases: list[TestcaseCase] = Field(default_factory=list)


class TestcaseModule(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    functions: list[TestcaseFunction] = Field(default_factory=list)


class TestcaseResult(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    modules: list[TestcaseModule] = Field(default_factory=list)


class ReviewItem(BaseModel):
    id: Optional[int] = None
    severity: Literal["high", "medium", "low"] = "low"
    description: str = Field(min_length=1)
    suggestion: Optional[str] = None
    dimension_key: Optional[str] = None


class ApplyChange(BaseModel):
    action: Literal[
        "delete_case",
        "modify_case",
        "add_case",
        "add_function",
        "delete_function",
        "move_function",
    ]
    module: Optional[str] = None
    function: Optional[str] = None
    function_name: Optional[str] = None
    case_name: Optional[str] = None
    updates: Optional[dict] = None
    case: Optional[dict] = None
    from_module: Optional[str] = None
    to_module: Optional[str] = None


def validate_testcase_result(data: object) -> TestcaseResult:
    return TestcaseResult.model_validate(data)


def validate_review_items(items: object) -> list[ReviewItem]:
    if not isinstance(items, list):
        raise ValueError("review items 必须是列表")
    return [ReviewItem.model_validate(i) for i in items]


def validate_changes(changes: object) -> list[ApplyChange]:
    if not isinstance(changes, list):
        raise ValueError("changes 必须是列表")
    return [ApplyChange.model_validate(c) for c in changes]

