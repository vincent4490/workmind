# -*- coding: utf-8 -*-
from .base import BasePrompt
from .prd_draft import PRDDraftPrompt
from .feature_breakdown import FeatureBreakdownPrompt
from .competitive_analysis import CompetitiveAnalysisPrompt
from .prd_refine import PRDRefinePrompt
from .requirement_analysis import RequirementAnalysisPrompt
from .tech_design import TechDesignPrompt
from .test_requirement_analysis import TestRequirementAnalysisPrompt

PROMPT_REGISTRY = {
    ('product', 'competitive_analysis'): CompetitiveAnalysisPrompt(),
    ('product', 'prd_draft'): PRDDraftPrompt(),
    ('product', 'prd_refine'): PRDRefinePrompt(),
    ('dev', 'requirement_analysis'): RequirementAnalysisPrompt(),
    ('dev', 'tech_design'): TechDesignPrompt(),
    ('test', 'test_requirement_analysis'): TestRequirementAnalysisPrompt(),
    ('test', 'feature_breakdown'): FeatureBreakdownPrompt(),
}

__all__ = [
    'BasePrompt',
    'PRDDraftPrompt', 'FeatureBreakdownPrompt',
    'CompetitiveAnalysisPrompt', 'PRDRefinePrompt',
    'RequirementAnalysisPrompt', 'TechDesignPrompt',
    'TestRequirementAnalysisPrompt',
    'PROMPT_REGISTRY',
]
