# -*- coding: utf-8 -*-
# 初始化工具模块
# 延迟导入，避免启动时依赖问题
# 这些模块包含 airtest 依赖，只在需要时导入

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # 类型检查时导入，满足类型检查器的要求
    from .airtest_base import AirtestBase
    from .base_page import BasePage
else:
    # 运行时使用 __getattr__ 实现延迟导入
    AirtestBase = None  # type: ignore[assignment]
    BasePage = None  # type: ignore[assignment]

__all__ = ['AirtestBase', 'BasePage']

def __getattr__(name: str):
    """延迟导入模块属性"""
    if name == 'AirtestBase':
        from .airtest_base import AirtestBase
        return AirtestBase
    elif name == 'BasePage':
        from .base_page import BasePage
        return BasePage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# 延迟导入函数，保持向后兼容
def get_AirtestBase():
    """延迟导入 AirtestBase"""
    from .airtest_base import AirtestBase
    return AirtestBase

def get_BasePage():
    """延迟导入 BasePage"""
    from .base_page import BasePage
    return BasePage
