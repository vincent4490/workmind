# -*- coding: utf-8 -*-
"""
设备管理相关的Celery任务
"""
from celery import shared_task
from django.utils import timezone
import logging

from apps.ui_test.managers.device_resource_pool import DeviceResourcePool

logger = logging.getLogger(__name__)


@shared_task
def auto_unlock_timeout_devices():
    """
    自动解锁超时设备任务
    可以设置为定时任务，定期执行
    """
    try:
        pool = DeviceResourcePool()
        unlocked_count = pool.auto_unlock_timeout_devices()
        logger.info(f"自动解锁超时设备完成，解锁了 {unlocked_count} 个设备")
        return {
            'success': True,
            'unlocked_count': unlocked_count,
        }
    except Exception as e:
        logger.error(f"自动解锁超时设备失败: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
        }
