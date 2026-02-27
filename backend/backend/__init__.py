# 使用 PyMySQL 替代 mysqlclient（Windows 兼容性更好）
import pymysql

# 让 PyMySQL 模拟 MySQLdb
pymysql.install_as_MySQLdb()

# 导入 Celery 应用，确保 Celery 在 Django 启动时被加载
from .celery import app as celery_app

__all__ = ('celery_app',)