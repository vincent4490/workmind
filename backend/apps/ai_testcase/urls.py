# -*- coding: utf-8 -*-
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AiTestcaseViewSet,
    generate_stream_view,
    regenerate_module_stream_view,
    review_stream_view,
    apply_review_stream_view,
)

router = DefaultRouter()
router.register(r'generations', AiTestcaseViewSet, basename='ai-testcase-generation')

urlpatterns = [
    path('generate-stream/', generate_stream_view, name='ai-testcase-generate-stream'),
    path('regenerate-module-stream/', regenerate_module_stream_view, name='ai-testcase-regenerate-module-stream'),
    path('review-stream/', review_stream_view, name='ai-testcase-review-stream'),
    path('apply-review-stream/', apply_review_stream_view, name='ai-testcase-apply-review-stream'),
    path('', include(router.urls)),
]
