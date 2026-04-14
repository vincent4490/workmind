"""
Django MySQL 驱动选择

- 优先使用 mysqlclient（性能更好，且 Django 4.2+ 会校验 MySQLdb 版本）
- 若环境未安装 mysqlclient，则回退到 PyMySQL（用于部分环境的兼容）
"""

try:
    import MySQLdb  # noqa: F401
except Exception:
    import pymysql

    pymysql.install_as_MySQLdb()

# 导入 Celery 应用，确保 Celery 在 Django 启动时被加载
from .celery import app as celery_app

__all__ = ('celery_app',)