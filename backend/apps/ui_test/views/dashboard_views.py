# -*- coding: utf-8 -*-
"""
Dashboard 统计视图
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q
import logging

from ..models import UiTestExecution, UiTestCase, Device
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
