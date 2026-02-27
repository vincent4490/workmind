# -*- coding: utf-8 -*-
"""
设备管理视图
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from loguru import logger

from ..models import Device, UiTestConfig
from ..serializers import DeviceSerializer
from ..constants import DeviceStatus


class DeviceViewSet(viewsets.ModelViewSet):
    """设备管理视图集"""
    queryset = Device.objects.all()  # type: ignore[attr-defined]
    serializer_class = DeviceSerializer
    
    def get_queryset(self):
        """获取设备列表"""
        return Device.objects.all()  # type: ignore[attr-defined]
    
    def list(self, request, *args, **kwargs):
        """获取设备列表"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'code': 0,
            'msg': 'success',
            'data': serializer.data
        })

    def destroy(self, request, *args, **kwargs):
        """删除设备"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'code': 0,
            'msg': '删除成功'
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='refresh')
    def refresh(self, request):
        """刷新设备列表"""
        logger.info("刷新设备列表请求")
        
        # 获取项目配置
        try:
            config = UiTestConfig.objects.first()  # type: ignore[attr-defined]
            if config:
                adb_path = config.adb_path
                logger.info(f"使用配置的ADB路径: {adb_path}")
            else:
                adb_path = 'adb'
                logger.info(f"未找到项目配置，使用默认ADB路径: {adb_path}")
        except Exception as e:
            adb_path = 'adb'
            logger.warning(f"获取配置失败: {e}，使用默认ADB路径: {adb_path}")
        
        # 使用 DeviceManager 获取设备列表
        try:
            from ..managers.device_manager import DeviceManager
            logger.info("初始化DeviceManager")
            device_manager = DeviceManager(adb_path=adb_path)
            logger.info("获取设备列表")
            devices_info = device_manager.list_devices()
            logger.info(f"获取到 {len(devices_info)} 个设备")
            
            # 更新数据库中的设备信息
            # 获取当前所有设备ID
            current_device_ids = [d['device_id'] for d in devices_info]
            
            # 更新或创建设备
            for device_info in devices_info:
                # 确定连接类型：只保留本地模拟器和远程模拟器
                device_id = device_info['device_id']
                if ':' in device_id:
                    # 包含冒号，识别为远程模拟器
                    connection_type = 'remote_emulator'
                else:
                    # 不包含冒号，识别为本地模拟器
                    connection_type = 'emulator'
                
                # 检查数据库中是否已存在该设备
                existing_device = Device.objects.filter(  # type: ignore[attr-defined]
                    device_id=device_info['device_id']
                ).first()
                
                # 确定状态
                device_status = device_info.get('status', DeviceStatus.ONLINE)
                if device_status == DeviceStatus.ONLINE:
                    # 如果设备在线，检查是否被锁定
                    if existing_device and existing_device.locked_by:
                        device_status = DeviceStatus.LOCKED  # 保持锁定状态
                    else:
                        device_status = DeviceStatus.AVAILABLE  # 设为可用
                elif device_status == DeviceStatus.OFFLINE:
                    # 如果设备离线，但之前被锁定，保持锁定状态（可能只是暂时离线）
                    if existing_device and existing_device.locked_by:
                        device_status = DeviceStatus.LOCKED
                
                # 准备更新数据
                update_data = {
                    'name': device_info.get('name') or '',
                    'android_version': device_info.get('android_version') or '',
                    'connection_type': connection_type,
                    'ip_address': device_info.get('ip_address') or '',
                    'port': device_info.get('port', 5555)
                }
                
                # 只有在设备状态变化时才更新状态（避免覆盖锁定状态）
                if existing_device:
                    # 如果设备之前被锁定，且现在在线，保持锁定状态
                    if existing_device.locked_by and device_status == DeviceStatus.AVAILABLE:
                        device_status = DeviceStatus.LOCKED
                    update_data['status'] = device_status
                else:
                    # 新设备，直接设置状态
                    update_data['status'] = device_status
                
                device, created = Device.objects.update_or_create(  # type: ignore[attr-defined]
                    device_id=device_info['device_id'],
                    defaults=update_data
                )
            
            # 将不在当前列表中的设备标记为离线
            Device.objects.exclude(  # type: ignore[attr-defined]
                device_id__in=current_device_ids
            ).update(status=DeviceStatus.OFFLINE)
            
            # 返回更新后的设备列表
            devices = Device.objects.all()  # type: ignore[attr-defined]
            serializer = DeviceSerializer(devices, many=True)
            logger.info(f"刷新成功，返回 {devices.count()} 个设备")
            
            return Response({
                'code': 0,
                'msg': '刷新成功',
                'data': serializer.data
            })
            
        except Exception as e:
            logger.error(f"刷新设备列表失败: {str(e)}", exc_info=True)
            return Response({
                'code': 1,
                'msg': f'刷新设备列表失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], url_path='connect')
    def connect(self, request):
        """连接远程设备"""
        ip_address = request.data.get('ip_address')
        port = request.data.get('port', 5555)
        if not ip_address:
            return Response({
                'code': 1,
                'msg': 'IP地址不能为空'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 获取项目配置
        try:
            config = UiTestConfig.objects.first()  # type: ignore[attr-defined]
            adb_path = config.adb_path
        except UiTestConfig.DoesNotExist:  # type: ignore[attr-defined]
            adb_path = 'adb'
        
        # 使用 DeviceManager 连接设备
        try:
            from ..managers.device_manager import DeviceManager
            device_manager = DeviceManager(adb_path=adb_path)
            device_info = device_manager.connect_device(ip_address, port)
            
            if not device_info:
                return Response({
                    'code': 1,
                    'msg': '连接设备失败，请检查设备网络和ADB设置'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # 保存设备信息到数据库
            device, created = Device.objects.update_or_create(  # type: ignore[attr-defined]
                device_id=device_info['device_id'],
                defaults={
                    'name': device_info.get('name'),
                    'status': DeviceStatus.ONLINE,
                    'android_version': device_info.get('android_version'),
                    'connection_type': 'remote_emulator',
                    'ip_address': ip_address,
                    'port': port
                }
            )
            
            device_serializer = DeviceSerializer(device)
            
            return Response({
                'code': 0,
                'msg': '连接成功' if created else '设备已连接',
                'data': device_serializer.data
            })
            
        except Exception as e:
            return Response({
                'code': 1,
                'msg': f'连接设备失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['delete'], url_path='disconnect')
    def disconnect(self, request, pk=None):
        """断开设备连接"""
        device = self.get_object()
        
        # 获取配置
        try:
            config = UiTestConfig.objects.first()
            adb_path = config.adb_path
        except UiTestConfig.DoesNotExist:
            adb_path = 'adb'
        
        # 使用 DeviceManager 断开设备
        try:
            from ..managers.device_manager import DeviceManager
            device_manager = DeviceManager(adb_path=adb_path)
            success = device_manager.disconnect_device(device.device_id)
            
            if success:
                # 更新设备状态为离线
                device.status = DeviceStatus.OFFLINE
                device.save()
                
                return Response({
                    'code': 0,
                    'msg': 'Device disconnected'
                })
            else:
                return Response({
                    'code': 1,
                    'msg': 'Failed to disconnect device'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            return Response({
                'code': 1,
                'msg': f'Failed to disconnect device: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], url_path='lock')
    def lock(self, request, pk=None):
        """锁定设备"""
        device = self.get_object()
        
        # 使用 DeviceResourcePool 锁定设备
        try:
            from ..managers.device_resource_pool import DeviceResourcePool
            pool = DeviceResourcePool()
            success = pool.lock_device(device.device_id, request.user.username)
            
            if success:
                device.refresh_from_db()
                serializer = DeviceSerializer(device)
                return Response({
                    'code': 0,
                    'msg': '设备已锁定',
                    'data': serializer.data
                })
            else:
                return Response({
                    'code': 1,
                    'msg': '锁定设备失败，设备可能已被其他用户锁定'
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"锁定设备失败: {e}", exc_info=True)
            return Response({
                'code': 1,
                'msg': f'锁定设备失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], url_path='unlock')
    def unlock(self, request, pk=None):
        """解锁设备"""
        device = self.get_object()
        
        # 使用 DeviceResourcePool 解锁设备
        try:
            from ..managers.device_resource_pool import DeviceResourcePool
            pool = DeviceResourcePool()
            # 允许管理员或锁定用户解锁设备
            is_admin = request.user.is_superuser or request.user.is_staff
            # 传入allow_admin=True，允许管理员解锁任何设备
            success = pool.unlock_device(device.device_id, request.user.username, allow_admin=True)
            
            if success:
                device.refresh_from_db()
                serializer = DeviceSerializer(device)
                return Response({
                    'code': 0,
                    'msg': '设备已解锁',
                    'data': serializer.data
                })
            else:
                # 刷新设备状态
                device.refresh_from_db()
                
                # 检查是否是权限问题
                if device.locked_by and device.locked_by.username != request.user.username and not is_admin:
                    return Response({
                        'code': 1,
                        'msg': '解锁设备失败，设备不是由当前用户锁定的，且当前用户不是管理员'
                    }, status=status.HTTP_403_FORBIDDEN)
                else:
                    # 如果设备未被锁定，返回成功（幂等性）
                    if not device.locked_by:
                        serializer = DeviceSerializer(device)
                        return Response({
                            'code': 0,
                            'msg': '设备已解锁（设备原本未被锁定）',
                            'data': serializer.data
                        })
                    else:
                        return Response({
                            'code': 1,
                            'msg': '解锁设备失败，请检查设备状态或联系管理员'
                        }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"解锁设备失败: {e}", exc_info=True)
            return Response({
                'code': 1,
                'msg': f'解锁设备失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], url_path='auto-unlock-timeout')
    def auto_unlock_timeout(self, request):
        """自动解锁超时设备"""
        try:
            from ..managers.device_resource_pool import DeviceResourcePool
            pool = DeviceResourcePool()
            unlocked_count = pool.auto_unlock_timeout_devices()
            
            return Response({
                'code': 0,
                'msg': f'已自动解锁 {unlocked_count} 个超时设备',
                'data': {'unlocked_count': unlocked_count}
            })
        except Exception as e:
            logger.error(f"自动解锁超时设备失败: {e}", exc_info=True)
            return Response({
                'code': 1,
                'msg': f'自动解锁超时设备失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
