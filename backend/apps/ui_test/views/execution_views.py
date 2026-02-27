# -*- coding: utf-8 -*-
"""
UI测试执行记录视图
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from loguru import logger

from ..models import UiTestExecution, UiTestCase, Device
from ..serializers import UiTestExecutionSerializer
from ..constants import ExecutionStatus, TestType
from backend.utils import pagination


class UiTestExecutionViewSet(viewsets.ModelViewSet):
    """UI测试执行记录视图集"""
    queryset = UiTestExecution.objects.all()
    serializer_class = UiTestExecutionSerializer
    pagination_class = pagination.MyPageNumberPagination
    
    def get_queryset(self):
        """过滤查询集"""
        queryset = super().get_queryset()
        
        # UI流程用例过滤
        ui_flow_only = self.request.query_params.get('ui_flow_only')
        if ui_flow_only == '1':
            queryset = queryset.filter(
                case__test_type=TestType.UI
            ).filter(
                Q(case__case_data__has_key='ui_flow') | Q(case__case_data__ui_flow__isnull=False)
            )
        
        return queryset.select_related('case', 'device', 'user').order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        """获取测试执行记录列表（支持分页）"""
        queryset = self.filter_queryset(self.get_queryset())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            # 包装为统一格式
            return Response({
                'code': 0,
                'msg': 'success',
                'data': paginated_response.data
            })
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'code': 0,
            'msg': 'success',
            'data': serializer.data
        })
    
    @action(detail=False, methods=['post'], url_path='start')
    def start(self, request):
        """启动测试执行"""
        case_id = request.data.get('case_id')
        device_id = request.data.get('device_id')
        package_name = request.data.get('package_name')  # 执行时传入的包名（可选）
        
        if not case_id or not device_id:
            return Response({
                'code': 1,
                'msg': '请提供用例ID和设备ID'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            case = get_object_or_404(UiTestCase, id=case_id)
            device = get_object_or_404(Device, id=device_id)
            
            # 设备锁定检查
            if device.locked_by:
                locked_by = device.locked_by.username
                locked_at = device.locked_at.strftime('%Y-%m-%d %H:%M:%S') if device.locked_at else '未知时间'
                error_msg = f'设备 {device.device_id} 已被 {locked_by} 锁定 ({locked_at})'
                logger.warning(error_msg)
                return Response({'code': 1, 'msg': error_msg}, status=status.HTTP_400_BAD_REQUEST)
            
            # 创建执行记录
            execution = UiTestExecution.objects.create(
                case=case,
                device=device,
                user=request.user if request.user.is_authenticated else None,
                status=ExecutionStatus.PENDING,
                progress=0,
                started_at=timezone.now()
            )
            
            # 如果执行时提供了包名，临时覆盖case_data中的包名
            runtime_package_name = package_name if package_name else None
            
            # 启动 Celery 任务
            try:
                from ..tasks.test_tasks import execute_ui_test
                engineer_username = request.user.username if request.user.is_authenticated else 'system'
                # 使用位置参数传递
                task = execute_ui_test.delay(
                    execution.id,
                    engineer_username,
                    runtime_package_name  # 运行时包名
                )
                
                execution.task_id = task.id
                execution.save()
                
                logger.info(f"提交测试任务: execution_id={execution.id}, task_id={task.id}")
                
                return Response({
                    'code': 0,
                    'msg': '测试任务已提交',
                    'data': {
                        **self.get_serializer(execution).data,
                        'websocket_url': f'/ws/test-execution/{execution.id}/',
                    }
                }, status=status.HTTP_202_ACCEPTED)
            except Exception as e:
                logger.error(f"提交 Celery 任务失败: {e}")
                execution.status = ExecutionStatus.FAILED
                execution.error_message = f'提交测试任务失败: {str(e)}'
                execution.save()
                return Response({'code': 1, 'msg': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"启动测试失败: {e}")
            return Response({'code': 1, 'msg': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], url_path='stop')
    def stop(self, request, pk=None):
        """停止测试执行"""
        execution = get_object_or_404(UiTestExecution, id=pk)
        
        if execution.status not in [ExecutionStatus.PENDING, ExecutionStatus.RUNNING]:
            return Response({
                'code': 1,
                'msg': f'状态为 {execution.get_status_display()}，无法停止'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            execution.status = ExecutionStatus.FAILED
            execution.finished_at = timezone.now()
            execution.error_message = '用户手动停止'
            execution.save()
            
            if execution.task_id:
                from celery import current_app
                current_app.control.revoke(execution.task_id, terminate=True)
                logger.info(f"已停止任务: task_id={execution.task_id}")
            
            # WebSocket 通知
            try:
                from ..tasks.test_tasks import send_test_progress
                send_test_progress(execution.id, 0, ExecutionStatus.FAILED, '测试已被用户停止', execution.finished_at)
            except Exception: pass
            
            # 设备解锁
            if execution.device:
                from ..managers.device_resource_pool import DeviceResourcePool
                engineer_username = request.user.username if request.user.is_authenticated else 'system'
                DeviceResourcePool().unlock_device(execution.device.device_id, engineer_username)
            
            return Response({'code': 0, 'msg': '测试已停止'})
        except Exception as e:
            logger.error(f"停止测试失败: {e}")
            return Response({'code': 1, 'msg': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
