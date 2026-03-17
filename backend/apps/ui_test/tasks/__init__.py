# -*- coding: utf-8 -*-
"""
Celery tasks for UI testing
导入任务以确保 Celery 自动发现机制能够注册它们
"""
from . import device_tasks, test_tasks, requirement_tasks

__all__ = ['device_tasks', 'test_tasks', 'requirement_tasks']
