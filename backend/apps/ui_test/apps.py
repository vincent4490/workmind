# -*- coding: utf-8 -*-
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class UiTestConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ui_test'
    verbose_name = 'UI测试'
    
    def ready(self):
        try:
            import apps.ui_test.tasks
        except ImportError:
            pass