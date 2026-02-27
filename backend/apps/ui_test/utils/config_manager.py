# -*- coding: utf-8 -*-
import os
import yaml
import json
from typing import Dict, Any, Optional
import logging

class ConfigManager:
    """
    配置管理器 - 单例模式
    用于加载和管理应用程序的配置
    支持YAML和JSON格式的配置文件
    """
    _instance = None
    _config = {}
    _logger = logging.getLogger("ConfigManager")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            # 初始化配置
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """初始化配置管理器"""
        self._logger.info("初始化配置管理器")
        # 加载基础配置 - Django应用中的config.py路径
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "config.py")
        self.load_config(config_path)
        # 加载多平台游戏配置
        self.load_platform_config()
        # 登录配置已改为从数据库读取，不再从yaml文件加载

    def load_config(self, config_path: str):
        """加载Python格式的配置文件"""
        try:
            if os.path.exists(config_path):
                self._logger.info(f"加载配置文件: {config_path}")
                # 导入配置文件
                import importlib.util
                spec = importlib.util.spec_from_file_location("config", config_path)
                if spec is None:
                    self._logger.error(f"无法创建模块规范: {config_path}")
                    return
                if spec.loader is None:
                    self._logger.error(f"模块加载器为空: {config_path}")
                    return
                config_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(config_module)
                # 将配置项添加到配置字典
                for name in dir(config_module):
                    if not name.startswith('_') and name.isupper():
                        self._config[name] = getattr(config_module, name)
        except Exception as e:
            self._logger.error(f"加载配置文件失败: {str(e)}")

    def load_platform_config(self):
        """加载多平台游戏配置"""
        # 获取Django应用目录（apps/ui_test）
        app_root = os.path.dirname(os.path.dirname(__file__))
        # 平台配置文件路径
        platform_config_path = os.path.join(app_root, "config", "game_platforms.yaml")
        try:
            if os.path.exists(platform_config_path):
                self._logger.info(f"加载多平台游戏配置: {platform_config_path}")
                with open(platform_config_path, 'r', encoding='utf-8') as file:
                    platform_config = yaml.safe_load(file)
                    self._config['PLATFORMS'] = platform_config.get('PLATFORMS', [])
                    self._config['ACTIVE_PLATFORM'] = platform_config.get('ACTIVE_PLATFORM', '')
                    # 构建平台映射，方便快速查找
                    self._config['PLATFORM_MAP'] = {}
                    for platform in self._config['PLATFORMS']:
                        self._config['PLATFORM_MAP'][platform['platform_name']] = platform
        except Exception as e:
            self._logger.error(f"加载多平台游戏配置失败: {str(e)}")

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self._config.get(key, default)

    def get_platform(self, platform_name: Optional[str] = None) -> Dict[str, Any]:
        """获取指定平台的配置，如果未指定则返回活动平台"""
        if platform_name is None:
            # 优先从环境变量获取平台名称
            import os
            platform_name = os.environ.get('PLATFORM_NAME', self._config.get('ACTIVE_PLATFORM', ''))
        return self._config.get('PLATFORM_MAP', {}).get(platform_name, {})

    def get_game_config(self, game_name: str, platform_name: Optional[str] = None) -> Dict[str, Any]:
        """获取指定游戏的配置"""
        platform = self.get_platform(platform_name)
        games = platform.get('games', {})
        return games.get(game_name, {})

    def set_active_platform(self, platform_name: str) -> bool:
        """设置活动平台"""
        if platform_name in self._config.get('PLATFORM_MAP', {}):
            self._config['ACTIVE_PLATFORM'] = platform_name
            self._logger.info(f"设置活动平台: {platform_name}")
            return True
        self._logger.error(f"平台不存在: {platform_name}")
        return False

    def get_platform_config(self) -> list:
        """获取所有平台配置"""
        return self._config.get('PLATFORMS', [])

# 创建配置管理器实例
config_manager = ConfigManager()

def get_config() -> ConfigManager:
    """获取配置管理器实例"""
    return config_manager
