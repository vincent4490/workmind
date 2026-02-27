# -*- coding: utf-8 -*-
"""
UI测试应用常量定义
"""

class ExecutionStatus:
    PENDING = 'pending'
    RUNNING = 'running'
    SUCCESS = 'success'
    FAILED = 'failed'
    STOPPED = 'stopped'

class DeviceStatus:
    AVAILABLE = 'available'
    LOCKED = 'locked'
    OFFLINE = 'offline'
    ONLINE = 'online'

class TestType:
    UI = 'ui'
    API = 'api'
