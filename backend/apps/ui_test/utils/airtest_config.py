# -*- coding: utf-8 -*-
"""
Airtest 配置文件
提供 Airtest 和设备连接的默认配置
"""

# Airtest 配置
AIRTEST_CONFIG = {
    # 查找超时时间（秒）
    'FIND_TIMEOUT': 20,
    # 点击延迟（秒）
    'CLICK_DELAY': 0.5,
    # 重试次数
    'RETRY_COUNT': 3,
    # 重试间隔（秒）
    'RETRY_INTERVAL': 5,
    # 设备连接超时（秒）
    'DEVICE_CONNECT_TIMEOUT': 10,
    # 日志目录
    'LOG_DIR': 'logs',
    # 录制位置（用于截图记录）
    'RECORD_POS': (0.5, 0.5),
    # 分辨率
    'RESOLUTION': (1920, 1080),
}

# 设备ID（默认为空，运行时指定）
DEVICE_ID = ""

# 模拟器路径（可选）
EMULATOR_PATH = ""
