# -*- coding: utf-8 -*-
"""
Celery任务 - 执行UI测试
支持多工程师并发执行和实时进度更新
"""
import os
import threading
import time
from celery import shared_task
from django.utils import timezone
from asgiref.sync import async_to_sync
from loguru import logger
from typing import Optional, List, Dict, Any

from ..models import UiTestExecution, UiTestCase
from ..executors.test_executor import UiTestExecutor
from ..constants import ExecutionStatus, DeviceStatus, TestType
from ..managers.device_resource_pool import DeviceResourcePool


def get_channel_layer():
    """获取 Channel Layer（延迟导入，避免循环依赖）"""
    try:
        from channels.layers import get_channel_layer as _get_channel_layer
        channel_layer = _get_channel_layer()
        if channel_layer is None:
            logger.warning("Channel Layer 为 None，WebSocket 功能不可用")
        return channel_layer
    except ImportError as e:
        logger.warning(f"无法导入 Channel Layer（channels 未安装）: {e}")
        return None
    except Exception as e:
        logger.warning(f"无法获取 Channel Layer: {e}")
        return None


def send_test_progress(execution_id: int, progress: int, status: str, message: Optional[str] = None, finished_at=None, report_path=None):
    """发送测试进度更新到WebSocket，并同步更新数据库的progress字段"""
    try:
        # 先更新数据库中的progress字段
        try:
            execution = UiTestExecution.objects.get(id=execution_id)
            execution.progress = progress
            # 如果状态发生变化，也更新状态
            if status and execution.status != status:
                execution.status = status
            # 如果提供了结束时间，更新finished_at
            if finished_at:
                execution.finished_at = finished_at
            # 如果提供了报告路径，更新report_path
            if report_path:
                execution.report_path = report_path
            execution.save(update_fields=['progress', 'status', 'finished_at', 'report_path'])
            logger.debug(f"数据库进度已更新: execution_id={execution_id}, progress={progress}%, status={status}")
        except UiTestExecution.DoesNotExist:
            logger.warning(f"执行记录不存在，无法更新进度: execution_id={execution_id}")
        except Exception as db_error:
            logger.error(f"更新数据库进度失败: execution_id={execution_id}, error={db_error}")
        
        # 发送WebSocket消息
        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.error(f"❌ Channel Layer 不可用，无法发送 WebSocket 消息: execution_id={execution_id}")
            return
        
        # 构建消息数据
        message_data = {
            'type': 'test_progress',
            'execution_id': int(execution_id),
            'progress': progress,
            'status': status,
            'message': message,
            'timestamp': timezone.now().isoformat(),
        }
        
        if finished_at:
            message_data['finished_at'] = finished_at.isoformat() if hasattr(finished_at, 'isoformat') else finished_at
        
        if report_path:
            message_data['report_path'] = report_path
        
        async_to_sync(channel_layer.group_send)(
            f'test_execution_{execution_id}',
            message_data
        )
        logger.info(f"✅ WebSocket 消息已发送: execution_id={execution_id}, status={status}, progress={progress}%")
    except Exception as e:
        logger.error(f"❌ 发送测试进度更新失败: {e}")


def _unlock_device_helper(device_id: str, engineer_username: str, context: str):
    """解锁设备的辅助函数，减少代码重复"""
    if not device_id:
        return
    try:
        pool = DeviceResourcePool()
        if pool.unlock_device(device_id, engineer_username, allow_admin=True):
            logger.info(f"✅ [{context}] 设备已解锁: device_id={device_id}, engineer={engineer_username}")
        else:
            logger.warning(f"⚠️ [{context}] 设备解锁失败: device_id={device_id}, engineer={engineer_username}")
    except Exception as e:
        logger.error(f"❌ [{context}] 设备解锁异常: device_id={device_id}, error={e}")


@shared_task(bind=True)
def execute_ui_test(self, execution_id: int, engineer_username: Optional[str] = None, runtime_package_name: Optional[str] = None):
    """
    执行UI测试任务（Celery异步任务）
    
    Args:
        execution_id: 执行记录ID
        engineer_username: 工程师用户名
        runtime_package_name: 运行时指定的应用包名（优先级高于case_data中的包名）
    """
    logger.info(f"=== 开始执行UI测试任务: execution_id={execution_id}, engineer={engineer_username} ===")
    if runtime_package_name:
        logger.info(f"运行时包名: {runtime_package_name}")
    
    if not engineer_username:
        raise ValueError("必须提供 engineer_username 参数，无法执行测试")
    
    os.environ['TEST_ENGINEER'] = engineer_username
    
    device_id = None
    device_locked = False
    execution = None
    
    try:
        execution = UiTestExecution.objects.get(id=execution_id)
        case = execution.case
        
        # 1. 准备阶段
        execution.status = ExecutionStatus.RUNNING
        execution.save()
        send_test_progress(execution_id, 0, ExecutionStatus.RUNNING, '测试开始执行...')
        send_test_progress(execution_id, 5, ExecutionStatus.RUNNING, '正在准备测试环境...')
        
        # 2. 设备锁定
        if execution.device:
            device_id = execution.device.device_id
            pool = DeviceResourcePool()
            if pool.lock_device(device_id, engineer_username):
                device_locked = True
                logger.info(f"✅ UI测试设备已锁定: device_id={device_id}")
                send_test_progress(execution_id, 8, ExecutionStatus.RUNNING, f'设备 {device_id} 已锁定')
            else:
                error_msg = f'设备 {device_id} 锁定失败，可能已被其他用户锁定'
                _handle_execution_failure(execution, error_msg)
                return {'execution_id': execution_id, 'success': False, 'error': error_msg}

        # 3. 创建执行器并启动进度线程
        executor = UiTestExecutor()
        
        progress_thread_running = threading.Event()
        progress_thread_running.set()
        
        def update_progress_periodically():
            while progress_thread_running.is_set():
                try:
                    curr = UiTestExecution.objects.get(id=execution_id)
                    if curr.status != ExecutionStatus.RUNNING:
                        break
                    progress = executor._calculate_test_progress(str(execution_id), is_running=True)
                    send_test_progress(execution_id, progress, ExecutionStatus.RUNNING, f'测试执行中... ({progress}%)')
                    if progress_thread_running.wait(timeout=3):
                        break
                except Exception as e:
                    logger.error(f"更新进度线程异常: {e}")
                    if progress_thread_running.wait(timeout=3):
                        break

        progress_thread = threading.Thread(target=update_progress_periodically, daemon=True)
        progress_thread.start()
        
        # 4. 执行测试
        try:
            # 检查是否已停止
            execution.refresh_from_db()
            if execution.status != ExecutionStatus.RUNNING:
                return _handle_stopped_execution(execution, device_id, engineer_username, device_locked, progress_thread_running, progress_thread)

            # 运行时包名优先，如果没有则使用case_data中的包名
            final_package_name = runtime_package_name if runtime_package_name else case.case_data.get('package_name')
            
            result = executor.run_tests(
                device_id=device_id,
                package_name=final_package_name,
                test_id=str(execution_id),
                user_id=case.case_data.get('user_id'),
                password=case.case_data.get('password'),
                execution_id=execution_id,
            )
        finally:
            progress_thread_running.clear()
            progress_thread.join(timeout=1)

        # 5. 处理结果
        execution.refresh_from_db()
        if execution.status != ExecutionStatus.RUNNING:
            return _handle_stopped_execution(execution, device_id, engineer_username, device_locked)

        _handle_execution_result(execution, result)
        
        # 6. 清理
        if device_locked:
            _unlock_device_helper(device_id, engineer_username, "完成")
            
        return {
            'execution_id': execution_id,
            'success': result.get('success'),
            'report_path': result.get('report_path'),
        }

    except UiTestExecution.DoesNotExist:
        logger.error(f"❌ 测试执行记录不存在: execution_id={execution_id}")
        return {'execution_id': execution_id, 'success': False, 'error': '执行记录不存在'}
    except Exception as e:
        logger.exception(f"❌ 执行测试任务发生未捕获异常: {e}")
        if execution:
            _handle_execution_failure(execution, str(e))
            if device_locked:
                _unlock_device_helper(device_id, engineer_username, "异常清理")
        return {'execution_id': execution_id, 'success': False, 'error': str(e)}
    finally:
        os.environ.pop('TEST_ENGINEER', None)


def _handle_execution_result(execution: UiTestExecution, result: Dict[str, Any]):
    """处理测试执行结果并更新数据库"""
    test_results = result.get('test_results', {})
    total = test_results.get('total', 0)
    passed = test_results.get('passed', 0)
    failed = test_results.get('failed', 0)
    skipped = test_results.get('skipped', 0)
    
    if result.get('success'):
        execution.status = ExecutionStatus.SUCCESS
        status_msg = f'测试执行成功 (总计: {total}, 通过: {passed}, 失败: {failed}, 跳过: {skipped})'
    else:
        execution.status = ExecutionStatus.FAILED
        error_msg = result.get('error', '测试执行失败')
        execution.error_message = error_msg
        status_msg = f'测试执行失败: {error_msg} (总计: {total}, 通过: {passed}, 失败: {failed}, 跳过: {skipped})'
    
    execution.report_path = result.get('report_path', '')
    execution.finished_at = timezone.now()
    execution.save()
    
    send_test_progress(
        execution.id, 100, execution.status, status_msg, 
        execution.finished_at, execution.report_path
    )


def _handle_execution_failure(execution: UiTestExecution, error_msg: str):
    """处理执行过程中的失败情况"""
    execution.status = ExecutionStatus.FAILED
    execution.error_message = error_msg
    execution.finished_at = timezone.now()
    execution.save()
    send_test_progress(execution.id, 100, ExecutionStatus.FAILED, f'执行失败: {error_msg}', execution.finished_at)


def _handle_stopped_execution(execution, device_id, username, device_locked, event=None, thread=None):
    """处理测试被停止的情况"""
    if event: event.clear()
    if thread: thread.join(timeout=1)
    
    logger.info(f"任务已被停止: execution_id={execution.id}")
    if not execution.finished_at:
        execution.finished_at = timezone.now()
        execution.save()
        
    if device_locked:
        _unlock_device_helper(device_id, username, "停止清理")
        
    send_test_progress(execution.id, 0, execution.status, '测试已被用户停止', execution.finished_at)
    return {'success': False, 'error': '测试已被用户停止'}
