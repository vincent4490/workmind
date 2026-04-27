# -*- coding: utf-8 -*-
"""
Dashboard 统计视图
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from django.db.models.functions import TruncDate
import logging

from ..models import (
    UiTestExecution,
    UiTestCase,
    Device,
    FunctionalRequirement,
    Task,
)
from ..constants import ExecutionStatus

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """
    获取 Dashboard 统计数据
    
    返回：
    - 今日测试次数和成功率
    - 本周测试次数和成功率
    - 测试用例总数和 UI 场景用例数
    - 在线设备数和总设备数
    """
    try:
        # 时间范围
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())  # 本周一
        
        # 1. 今日测试统计
        today_executions = UiTestExecution.objects.filter(
            started_at__gte=today_start
        )
        today_total = today_executions.count()
        today_success = today_executions.filter(status=ExecutionStatus.SUCCESS).count()
        today_success_rate = round((today_success / today_total * 100), 1) if today_total > 0 else 0
        
        # 2. 本周测试统计
        week_executions = UiTestExecution.objects.filter(
            started_at__gte=week_start
        )
        week_total = week_executions.count()
        week_success = week_executions.filter(status=ExecutionStatus.SUCCESS).count()
        week_success_rate = round((week_success / week_total * 100), 1) if week_total > 0 else 0
        
        # 3. 测试用例统计
        total_cases = UiTestCase.objects.count()
        ui_flow_cases = UiTestCase.objects.filter(
            test_type='ui',
            case_data__has_key='ui_flow'
        ).count()
        
        # 4. 设备统计
        from ..managers.device_resource_pool import DeviceResourcePool
        pool = DeviceResourcePool()
        
        total_devices = Device.objects.count()
        online_devices = 0
        
        # 遍历所有设备，检查实际状态
        for device in Device.objects.all():
            device_status_info = pool.get_device_status(device.device_id)
            if device_status_info and device_status_info.get('status') in ['available', 'locked']:
                online_devices += 1
        
        data = {
            'todayTests': today_total,
            'todaySuccessRate': today_success_rate,
            'weekTests': week_total,
            'weekSuccessRate': week_success_rate,
            'totalCases': total_cases,
            'uiFlowCases': ui_flow_cases,
            'onlineDevices': online_devices,
            'totalDevices': total_devices
        }
        
        logger.info(f"Dashboard 统计数据: {data}")
        
        return Response({
            'code': 0,
            'msg': 'success',
            'data': data
        })
        
    except Exception as e:
        logger.error(f"获取 Dashboard 统计数据失败: {e}", exc_info=True)
        return Response({
            'code': 1,
            'msg': f'获取统计数据失败: {str(e)}',
            'data': {
                'todayTests': 0,
                'todaySuccessRate': 0,
                'weekTests': 0,
                'weekSuccessRate': 0,
                'totalCases': 0,
                'uiFlowCases': 0,
                'onlineDevices': 0,
                'totalDevices': 0
            }
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def functional_task_stats(request):
    """
    功能测试：需求管理 + 任务管理统计聚合（一期）。

    GET /api/ui_test/dashboard/functional-task-stats/?test_team=&tester=&owner=&requirement_status=&task_status=&requirement_keyword=&task_keyword=
    """
    try:
        # 该接口不返回任何“区间/趋势”字段，但允许传日期区间用于筛选统计口径。

        test_time_after = (request.query_params.get("test_time_after") or "").strip()
        test_time_before = (request.query_params.get("test_time_before") or "").strip()
        task_time_after = (request.query_params.get("task_time_after") or "").strip()
        task_time_before = (request.query_params.get("task_time_before") or "").strip()

        test_team = (request.query_params.get("test_team") or "").strip()
        tester = (request.query_params.get("tester") or "").strip()
        owner = (request.query_params.get("owner") or "").strip()
        requirement_status = (request.query_params.get("requirement_status") or "").strip()
        task_status = (request.query_params.get("task_status") or "").strip()
        requirement_keyword = (request.query_params.get("requirement_keyword") or "").strip()
        task_keyword = (request.query_params.get("task_keyword") or "").strip()

        # ---- Requirements queryset (filter aligned with FunctionalRequirementViewSet) ----
        req_qs = FunctionalRequirement.objects.all()
        if requirement_keyword:
            req_qs = req_qs.filter(name__icontains=requirement_keyword)
        if test_team:
            req_qs = req_qs.filter(test_team=test_team)
        if tester:
            req_qs = req_qs.filter(testers__icontains=tester)
        if requirement_status:
            req_qs = req_qs.filter(status=requirement_status)
        if test_time_after or test_time_before:
            from ..tasks.requirement_tasks import filter_functional_requirements_by_test_time

            req_qs = filter_functional_requirements_by_test_time(
                req_qs, test_time_after or None, test_time_before or None
            )

        # ---- Tasks queryset (filter aligned with TaskViewSet) ----
        task_qs = Task.objects.all()
        if task_keyword:
            task_qs = task_qs.filter(name__icontains=task_keyword)
        if owner:
            task_qs = task_qs.filter(owner__icontains=owner)
        if task_status:
            task_qs = task_qs.filter(status=task_status)
        # 任务与需求用字符串关联：用 requirement_keyword/test_team/tester 只做“弱筛选”
        if requirement_keyword:
            task_qs = task_qs.filter(requirement_name__icontains=requirement_keyword)
        if task_time_after or task_time_before:
            from ..tasks.requirement_tasks import filter_tasks_by_task_time

            task_qs = filter_tasks_by_task_time(
                task_qs, task_time_after or None, task_time_before or None
            )

        # ---- KPIs ----
        req_total = req_qs.count()
        task_total = task_qs.count()

        # ---- Distributions ----
        req_by_status = list(
            req_qs.values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        task_by_status = list(
            task_qs.values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        data = {
            "kpis": {
                "requirements_total": req_total,
                "tasks_total": task_total,
            },
            "requirements_by_status": req_by_status,
            "tasks_by_status": task_by_status,
        }

        return Response({"code": 0, "msg": "success", "data": data})
    except Exception as e:
        logger.error(f"功能测试统计失败: {e}", exc_info=True)
        return Response({"code": 1, "msg": f"统计失败: {str(e)}", "data": {}}, status=500)