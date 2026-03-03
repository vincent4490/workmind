# -*- coding: utf-8 -*-
"""
ui_test views package
"""
from .device_views import DeviceViewSet
from .ui_test_views import (
    UiTestConfigViewSet,
    UiTestCaseViewSet,
    UiComponentDefinitionViewSet,
    UiCustomComponentDefinitionViewSet,
    UiComponentPackageViewSet,
)
from .functional_test_views import (
    FunctionalRequirementViewSet,
    FunctionalTestCaseViewSet,
    TaskViewSet,
    TestPlanViewSet,
    functional_case_export,
)
from .execution_views import UiTestExecutionViewSet
from .app_package_views import AppPackageViewSet
from .element_views import UiElementViewSet  # 新增：元素管理
from .report_views import serve_report_file
from .dashboard_views import dashboard_stats

__all__ = [
    'DeviceViewSet',
    'UiTestConfigViewSet',
    'UiTestCaseViewSet',
    'UiComponentDefinitionViewSet',
    'UiCustomComponentDefinitionViewSet',
    'UiComponentPackageViewSet',
    'FunctionalRequirementViewSet',
    'FunctionalTestCaseViewSet',
    'TaskViewSet',
    'TestPlanViewSet',
    'functional_case_export',
    'UiTestExecutionViewSet',
    'AppPackageViewSet',
    'UiElementViewSet',  # 新增：元素管理
    'serve_report_file',
    'dashboard_stats',
]

