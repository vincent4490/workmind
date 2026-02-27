# -*- coding: utf-8 -*-
"""
WebSocket 路由配置
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/test-execution/(?P<execution_id>\d+)/$', consumers.TestExecutionConsumer.as_asgi()),
]
