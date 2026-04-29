# -*- coding: utf-8 -*-
import os
from copy import deepcopy

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

from apps.ai_testcase.workflows.testcase_agent import route_after_review


def test_route_after_review_keeps_refining_after_second_iteration():
    state = {
        "review_score": 0.5,
        "iteration_count": 2,
        "review_issues": [{"description": "覆盖不足"}],
        "modules_generated": [{"name": "旧模块"}],
        "generation_errors": [{"module": "旧模块", "error": "失败"}],
        "current_module_index": 3,
        "merged_result": {"title": "旧结果", "modules": []},
        "review_feedback": "上一轮反馈",
    }
    before = deepcopy(state)

    assert route_after_review(state) == "refine_cases"
    assert state == before


def test_route_after_review_finalizes_without_actionable_issues():
    assert route_after_review({
        "review_score": 0.5,
        "iteration_count": 1,
        "review_issues": [],
    }) == "finalize"


def test_route_after_review_refines_high_duplicate_even_when_score_passes():
    assert route_after_review({
        "review_score": 0.81,
        "iteration_count": 1,
        "review_issues": [
            {
                "severity": "high",
                "type": "duplicate",
                "description": "升级入口重复",
            }
        ],
    }) == "refine_cases"
