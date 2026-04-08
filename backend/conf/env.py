# -*- coding: utf-8 -*-
"""
@File    : env.py
@Time    : 2023/6/29 15:53
@Author  : geekbing
@LastEditTime : -
@LastEditors : -
@Description : 本地开发配置（使用本地安装的服务，不依赖 Docker）
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# 获取项目根目录（backend 的父目录）
BASE_DIR = Path(__file__).resolve().parent.parent.parent
# 加载项目根目录下的 .env 文件
# 关键：override=True 确保以 .env 为准（避免系统环境变量残留导致读取到旧值）
load_dotenv(BASE_DIR / ".env", override=True)

# ================================================= #
# ************** mysql数据库 配置  ************** #
# ================================================= #
# 数据库地址
DATABASE_HOST = os.getenv("DATABASE_HOST", "localhost")
# 数据库端口
DATABASE_PORT = int(os.getenv("DATABASE_PORT", "3306"))
# 数据库用户名
DATABASE_USER = os.getenv("DATABASE_USER")
# 数据库密码
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
# 数据库名
DATABASE_NAME = os.getenv("DATABASE_NAME")

# ================================================= #
# ************** RabbitMQ配置 ************** #
# ================================================= #
MQ_USER = os.getenv("MQ_USER", "guest")
MQ_PASSWORD = os.getenv("MQ_PASSWORD", "guest")
MQ_HOST = os.getenv("MQ_HOST", "127.0.0.1")
MQ_PORT = os.getenv("MQ_PORT", "5672")
MQ_URL = f"amqp://{MQ_USER}:{MQ_PASSWORD}@{MQ_HOST}:{MQ_PORT}//"

# ================================================= #
# ************** Redis配置 ************** #
# ================================================= #
REDIS_ON = os.getenv("REDIS_ON", "True") == "True"
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
# 默认无密码，与服务器保持一致（如果.env中设置了密码则使用.env中的值）
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "") or None
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_DB = os.getenv("REDIS_DB", "0")

# ================================================= #
# ************** 其他 配置  ************** #
# ================================================= #
SECRET_KEY = os.getenv("SECRET_KEY", "^v68x$m2x($7!z@8lt548otbgev)@on&tntu3qts^s2z3xx(_a")
DEBUG = os.getenv("DEBUG", "True") == "True"

# 启动登录日志记录(通过调用api获取ip详细地址。如果是内网，关闭即可)
ENABLE_LOGIN_ANALYSIS_LOG = True

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

# CSRF 受信任来源（与 ALLOWED_HOSTS 配合，解决通过 IP:端口 访问时的 403）
# 格式示例: "http://172.136.230:9000,http://localhost:9000"
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "http://172.136.230:9000").split(",")
    if origin.strip()
]

BASE_REPORT_URL = os.getenv("BASE_REPORT_URL")

IM_REPORT_SETTING = {
    "base_url": os.getenv("IM_REPORT_BASE_URL"),
    "port": os.getenv("IM_REPORT_PORT", 8000),
    "report_title": os.getenv("IM_REPORT_TITLE")
}

# ================================================= #
# ************** 监控告警企微机器人配置  ************** #
# ================================================= #
QY_WEB_HOOK = os.getenv("QY_WEB_HOOK")  # 测试环境不需要机器人通知

# ================================================= #
# ************** 发送邮件配置  ************** #
# ================================================= #
# 使用 SMTP 服务器发送邮件
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND")
# SMTP 服务器地址
EMAIL_HOST = os.getenv("EMAIL_HOST")
# SMTP 服务器端口
EMAIL_PORT = os.getenv("EMAIL_PORT")
# 发件人邮箱账号
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL")
# 发件人邮箱密码
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
# 是否使用 TLS
EMAIL_USE_TL = False
# 是否使用 SSL
EMAIL_USE_SSL = True

# ================================================= #
# ************** 录制流量代理配置  ************** #
# ================================================= #
# PROXY Server
PROXY_ON = os.getenv("PROXY_ON", "True") == "True"  # 是否开启代理
PROXY_PORT = int(os.getenv("PROXY_PORT", "7778"))  # 代理端口，默认 7778
