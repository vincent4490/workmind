# -*- coding: utf-8 -*-
import logging
import os
import sys
from typing import Optional


def setup_test_logging(engineer_name: Optional[str] = None):
    """
    为测试设置日志配置

    Args:
        engineer_name: 工程师名称，用于区分不同工程师的日志文件
                      如果提供，则日志会保存在 logs/{engineer_name}/ 目录下
                      文件名格式: logs_{engineer_name}_{YYYYMMDD}.log
                      如果不提供，则保存在 logs/ 目录下
                      文件名格式: logs_{YYYYMMDD}.log
    """
    # 获取根日志器
    root_logger = logging.getLogger()
    
    # 清除现有的处理器，避免重复
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 创建格式化器 - 使用更详细的格式
    formatter = logging.Formatter(
        '[%(asctime)s] %(name)s->%(funcName)s line:%(lineno)d [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 配置根日志器
    root_logger.setLevel(logging.INFO)
    
    # 添加控制台处理器 - 确保输出到控制台
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 添加文件处理器 - 使用 game_test/logs 目录，按工程师区分
    # 获取当前文件所在目录，然后找到 game_test/logs
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # current_dir 是 backend/apps/game_test/utils，需要向上一级到 game_test
    game_test_dir = os.path.dirname(current_dir)
    base_log_dir = os.path.join(game_test_dir, 'logs')

    # 如果有工程师名称，为每个工程师创建单独的目录
    if engineer_name:
        log_dir = os.path.join(base_log_dir, engineer_name)
    else:
        log_dir = base_log_dir

    os.makedirs(log_dir, exist_ok=True)

    # 使用当前日期作为文件名，如果有工程师名称则包含在文件名中
    import time
    if engineer_name:
        log_filename = f"logs_{engineer_name}_{time.strftime('%Y%m%d', time.localtime())}.log"
    else:
        log_filename = f"logs_{time.strftime('%Y%m%d', time.localtime())}.log"
    
    file_handler = logging.FileHandler(
        os.path.join(log_dir, log_filename), 
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # 添加一个测试日志，确认配置生效
    test_logger = logging.getLogger("logger_config")
    if engineer_name:
        test_logger.info(f"日志系统配置完成！工程师: {engineer_name}")
    else:
        test_logger.info("日志系统配置完成！")


def get_test_logger(name: str) -> logging.Logger:
    """
    获取测试日志器

    Args:
        name: 日志器名称

    Returns:
        logging.Logger: 日志器实例
    """
    return logging.getLogger(name)