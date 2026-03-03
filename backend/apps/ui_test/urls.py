# -*- coding: utf-8 -*-
from django.urls import path, include, re_path
from rest_framework.routers import DefaultRouter
from .views import (
    DeviceViewSet, UiTestConfigViewSet,
    UiTestCaseViewSet,
    UiComponentDefinitionViewSet, UiCustomComponentDefinitionViewSet,
    UiComponentPackageViewSet,
    FunctionalRequirementViewSet, FunctionalTestCaseViewSet, TaskViewSet, TestPlanViewSet,
    functional_case_export,
    UiTestExecutionViewSet,
    AppPackageViewSet,
    UiElementViewSet,  # 元素管理
    serve_report_file,  # 报告视图
    dashboard_stats  # Dashboard 统计
)

router = DefaultRouter()
router.register(r'devices', DeviceViewSet, basename='device')
router.register(r'configs', UiTestConfigViewSet, basename='ui-test-config')
router.register(r'cases', UiTestCaseViewSet, basename='ui-test-case')
router.register(r'ui-components', UiComponentDefinitionViewSet, basename='ui-component-definition')
router.register(r'ui-custom-components', UiCustomComponentDefinitionViewSet, basename='ui-custom-component-definition')
router.register(r'ui-component-packages', UiComponentPackageViewSet, basename='ui-component-package')

router.register(r'functional-requirements', FunctionalRequirementViewSet, basename='functional-requirement')
router.register(r'functional-cases', FunctionalTestCaseViewSet, basename='functional-test-case')
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'test-plans', TestPlanViewSet, basename='test-plan')
router.register(r'executions', UiTestExecutionViewSet, basename='ui-test-execution')
router.register(r'app-packages', AppPackageViewSet, basename='app-package')
router.register(r'elements', UiElementViewSet, basename='ui-element')  # 元素管理

urlpatterns = [
    # 报告访问路由（必须在 router.urls 之前，以免被覆盖）
    re_path(
        r'^executions/(?P<execution_id>\d+)/report/$',
        serve_report_file,
        name='ui-test-report-index'
    ),
    re_path(
        r'^executions/(?P<execution_id>\d+)/report/(?P<file_path>.+)$',
        serve_report_file,
        name='ui-test-report-file'
    ),
    
    # Dashboard 统计路由
    path('dashboard/stats/', dashboard_stats, name='dashboard-stats'),

    path('functional-cases/export/', functional_case_export, name='functional-test-case-export'),

    path('', include(router.urls)),
]

