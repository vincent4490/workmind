# -*- coding: utf-8 -*-
"""
WebSocket 消费者 - UI测试执行实时通信
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)


class TestExecutionConsumer(AsyncWebsocketConsumer):
    """测试执行进度WebSocket消费者"""
    
    async def connect(self):
        """建立WebSocket连接"""
        self.execution_id = self.scope['url_route']['kwargs']['execution_id']
        self.room_group_name = f'test_execution_{self.execution_id}'
        
        # 加入房间组
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        logger.info(f"WebSocket 已连接: execution_id={self.execution_id}, channel={self.channel_name}")
        
        # 连接后立即发送初始状态
        initial_status = await self.get_execution_status()
        if initial_status:
            await self.send(text_data=json.dumps({
                'type': 'initial_status',
                **initial_status
            }))
    
    async def disconnect(self, close_code):
        """断开WebSocket连接"""
        # 离开房间组
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        logger.info(f"WebSocket 已断开: execution_id={self.execution_id}, code={close_code}")
    
    async def receive(self, text_data):
        """接收客户端消息"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'get_status':
                # 客户端请求最新状态
                status = await self.get_execution_status()
                if status:
                    await self.send(text_data=json.dumps({
                        'type': 'status_response',
                        **status
                    }))
        except json.JSONDecodeError:
            logger.error(f"接收到无效的JSON数据: {text_data}")
        except Exception as e:
            logger.error(f"处理WebSocket消息时出错: {e}")
    
    async def test_progress(self, event):
        """
        从 channel_layer.group_send 接收消息并发送给客户端
        这是后端任务推送进度的入口
        """
        # 发送消息到WebSocket客户端
        await self.send(text_data=json.dumps({
            'type': 'progress_update',
            'execution_id': event['execution_id'],
            'status': event['status'],
            'progress': event['progress'],
            'message': event.get('message', ''),
            'finished_at': event.get('finished_at'),
            'report_path': event.get('report_path'),
        }))
    
    @database_sync_to_async
    def get_execution_status(self):
        """获取执行记录的当前状态"""
        try:
            from .models import UiTestExecution
            execution = UiTestExecution.objects.get(id=self.execution_id)
            
            finished_at_str = None
            if execution.finished_at:
                finished_at_str = execution.finished_at.strftime('%Y-%m-%d %H:%M:%S')
            
            return {
                'execution_id': execution.id,
                'status': execution.status,
                'progress': execution.progress,
                'message': execution.error_message or '',
                'finished_at': finished_at_str,
                'report_path': execution.report_path or '',
            }
        except Exception as e:
            logger.error(f"获取执行状态失败: {e}")
            return None
