# -*- coding: utf-8 -*-
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AiTestcaseViewSet,
    generate_stream_view,
    regenerate_module_stream_view,
    regenerate_function_stream_view,
    update_case_view,
    review_stream_view,
    apply_review_stream_view,
    agent_generate_stream_view,
)

router = DefaultRouter()
router.register(r'generations', AiTestcaseViewSet, basename='ai-testcase-generation')

urlpatterns = [
    path('generate-stream/', generate_stream_view, name='ai-testcase-generate-stream'),
    path('regenerate-module-stream/', regenerate_module_stream_view, name='ai-testcase-regenerate-module-stream'),
    path('regenerate-function-stream/', regenerate_function_stream_view, name='ai-testcase-regenerate-function-stream'),
    path('update-case/', update_case_view, name='ai-testcase-update-case'),
    path('review-stream/', review_stream_view, name='ai-testcase-review-stream'),
    path('apply-review-stream/', apply_review_stream_view, name='ai-testcase-apply-review-stream'),
    path('agent-generate-stream/', agent_generate_stream_view, name='ai-testcase-agent-generate-stream'),
    path('', include(router.urls)),
]
