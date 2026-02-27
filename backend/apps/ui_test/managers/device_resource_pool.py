# -*- coding: utf-8 -*-
"""
设备资源池管理器 - 整合slot_game_automation的DeviceResourcePool功能
支持多工程设备分配、状态监控、资源隔离
"""
from typing import Dict, Any, Optional, List
from django.utils import timezone
from django.contrib.auth import get_user_model
from loguru import logger

from apps.ui_test.models import Device
from ..constants import DeviceStatus

User = get_user_model()


class DeviceResourcePool:
    """设备资源池管理器 - Django版本"""
    
    def __init__(self):
        """初始化设备资源池管理器"""
        logger.debug("初始化设备资源池管理器")
    
    def is_device_available(self, device_id: str) -> bool:
        """检查设备是否可用"""
        try:
            device = Device.objects.filter(device_id=device_id).first()
            if not device:
                return False
            
            # 检查设备状态和锁定状态
            if device.status == DeviceStatus.AVAILABLE and not device.locked_by:
                return True
            
            # 如果设备被锁定，检查是否超时
            if device.locked_by and device.locked_at:
                elapsed_time = (timezone.now() - device.locked_at).total_seconds()
                if elapsed_time > device.max_allocation_time:
                    # 超时，自动解锁
                    logger.warning(f"设备 {device_id} 锁定超时，自动解锁")
                    self.unlock_device(device_id, device.locked_by.username)
                    return True
            
            return False
        except Exception as e:
            logger.error(f"检查设备可用性失败: {e}")
            return False
    
    def lock_device(
        self, 
        device_id: str, 
        username: str,
        note: Optional[str] = None
    ) -> bool:
        """锁定设备"""
        try:
            device = Device.objects.filter(device_id=device_id).first()
            if not device:
                logger.error(f"设备不存在: {device_id}")
                return False
            
            # 检查设备是否可用
            if not self.is_device_available(device_id):
                logger.warning(f"设备不可用: {device_id}")
                return False
            
            # 锁定设备
            user = User.objects.get(username=username)
            device.locked_by = user
            device.locked_at = timezone.now()
            device.status = DeviceStatus.LOCKED
            device.note = note or f"由 {username} 锁定"
            device.save()
            
            logger.info(f"设备 {device_id} 已被 {username} 锁定")
            return True
            
        except User.DoesNotExist:
            logger.error(f"用户不存在: {username}")
            return False
        except Exception as e:
            logger.error(f"锁定设备失败: {e}")
            return False
    
    def unlock_device(
        self, 
        device_id: str, 
        username: str,
        allow_admin: bool = False
    ) -> bool:
        """解锁设备"""
        try:
            device = Device.objects.filter(device_id=device_id).first()
            if not device:
                logger.error(f"设备不存在: {device_id}")
                return False
            
            # 检查是否由该用户锁定，或者是否允许管理员解锁
            if device.locked_by and device.locked_by.username != username:
                if allow_admin:
                    user = User.objects.get(username=username)
                    if user.is_superuser or user.is_staff:
                        logger.info(f"管理员 {username} 解锁设备 {device_id}（原锁定用户: {device.locked_by.username}）")
                    else:
                        logger.warning(f"设备 {device_id} 不是由 {username} 锁定的，且用户不是管理员")
                        return False
                else:
                    logger.warning(f"设备 {device_id} 不是由 {username} 锁定的")
                    return False
            
            # 解锁设备
            device.locked_by = None
            device.locked_at = None
            device.status = DeviceStatus.AVAILABLE
            device.note = f"由 {username} 解锁"
            device.save()
            
            logger.info(f"设备 {device_id} 已被 {username} 解锁")
            return True
            
        except Exception as e:
            logger.error(f"解锁设备失败: {e}")
            return False
    
    def get_device_status(
        self, 
        device_id: str
    ) -> Optional[Dict[str, Any]]:
        """获取设备状态信息"""
        try:
            device = Device.objects.filter(device_id=device_id).first()
            if not device:
                return None
            
            locked_duration = None
            if device.locked_at:
                locked_duration = (timezone.now() - device.locked_at).total_seconds()
            
            return {
                'device_id': device.device_id,
                'status': device.status,
                'locked_by': device.locked_by.username if device.locked_by else None,
                'locked_at': device.locked_at.isoformat() if device.locked_at else None,
                'locked_duration': locked_duration,
                'max_allocation_time': device.max_allocation_time,
                'note': getattr(device, 'note', None)
            }
            
        except Exception as e:
            logger.error(f"获取设备状态失败: {e}")
            return None
    
    def auto_unlock_timeout_devices(self) -> int:
        """自动解锁超时设备"""
        try:
            query = Device.objects.filter(
                locked_by__isnull=False,
                locked_at__isnull=False
            )
            
            unlocked_count = 0
            for device in query:
                elapsed_time = (timezone.now() - device.locked_at).total_seconds()
                if elapsed_time > device.max_allocation_time:
                    username = device.locked_by.username if device.locked_by else 'system'
                    if self.unlock_device(device.device_id, username):
                        unlocked_count += 1
            
            if unlocked_count > 0:
                logger.info(f"自动解锁了 {unlocked_count} 个超时设备")
            
            return unlocked_count
            
        except Exception as e:
            logger.error(f"自动解锁超时设备失败: {e}")
            return 0
    
    def get_available_devices(
        self, 
        device_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取可用设备列表"""
        try:
            query = Device.objects.filter(status=DeviceStatus.AVAILABLE, locked_by__isnull=True)
            if device_type:
                query = query.filter(device_type=device_type)
            
            devices = []
            for device in query:
                devices.append({
                    'id': device.id,
                    'device_id': device.device_id,
                    'name': device.name,
                    'connection_type': device.connection_type,
                    'android_version': device.android_version,
                })
            
            return devices
            
        except Exception as e:
            logger.error(f"获取可用设备列表失败: {e}")
            return []
