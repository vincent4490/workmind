# -*- coding: utf-8 -*-
from __future__ import annotations

# 添加项目根目录到Python路径
import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


from apps.ui_test.utils.airtest_base import AirtestBase
from airtest.core.api import keyevent, swipe, touch, Template, loop_find, wait, click, text, snapshot, exists, G
from typing import Optional, Tuple, Any, List, Union
from airtest.core.error import TargetNotFoundError, NoDeviceError
import os
import time
import logging
from apps.ui_test.utils.airtest_config import AIRTEST_CONFIG
from apps.ui_test.utils.logger_config import get_test_logger
from functools import wraps

from apps.ui_test.utils.config_manager import config_manager  # 导入配置管理器

class BasePage(AirtestBase):
    """
    页面基础类，所有页面类都继承自此类
    
    提供页面操作的基础功能，如等待页面加载、返回、主页、滚动等
    """
    
    template_dir: str  # 模板目录路径，由子类设置

    #def __init__(self, device_id: Optional[str] = None):
    def __init__(self, device_id: Optional[str] = None, platform_name: Optional[str] = None, game_name: Optional[str] = None):
        """
        初始化页面
        
        Args:
            device_id (Optional[str]): 设备ID，如果为None则使用配置文件中的设备ID
            platform_name (Optional[str]): 平台名称，如果为None则使用配置文件中的活动平台
            game_name (Optional[str]): 游戏名称，如果为None则使用配置文件中的活动游戏
        """
        super().__init__(device_id)
        # 初始化日志
        self.logger = get_test_logger(__name__)
        # 获取平台信息
        self.platform = config_manager.get_platform(platform_name)
        self.platform_name = self.platform.get('platform_name', 'Royal_Dream')
        
        # 获取 game_test 目录的绝对路径（相对于当前文件）
        _current_file_dir = os.path.dirname(os.path.abspath(__file__))
        _game_test_dir = os.path.dirname(_current_file_dir)
        self._template_base_dir = os.path.join(_game_test_dir, "Template")
        
        # # 游戏图片路径 - 根据页面类型设置不同的路径
        # if game_name is not None:
        #     # 游戏页面：Template/platform_name/game_page/game_collection/game_name
        #     self.template_dir = os.path.join(os.getcwd(), 'Template', self.platform_name, 'game_page', 'game_collection', game_name)
        # else:
        #     # 其他页面（如登录页面、大厅页面）：使用通用路径
        #     self.template_dir = os.path.join(os.getcwd(), 'Template', self.platform_name)

    def wait_for_page_loaded(self, img, timeout: float = 600, retry_interval: float = 2) -> bool:
        """
        等待页面加载完成

        Args:
            img (str): 要查找的模板图片名称，用于判断页面是否加载完成
            timeout (float): 等待页面加载完成的最大超时时间，默认600秒
            retry_interval (float): 每次尝试查找图片之间的时间间隔，默认2秒

        Returns:
            bool: 页面是否加载完成
                - True: 成功找到页面元素，页面加载完成
                - False: 超时或发生异常，页面加载失败
        """
        start_time = time.time()
        try:
            while time.time() - start_time < timeout:
                print(f"现在时间-----------------------------: {time.time()}")
                print(f"现在时间-----------------------------: {time.time()}")
                print(f"开始时间-----------------------------: {start_time}")
                print(f"超时时间-----------------------------: {timeout}")
                print(f"重试时间-----------------------------: {retry_interval}")
                if self._check_loaded_once(
                    img,
                    record_pos=(0.5, 0.5),
                    resolution=(1920, 1080),
                    threshold=0.9,
                ):
                    self.logger.info(f"已查看到页面{img}")
                    # 增加额外检查，确保图片真正出现
                    return True
                else:
                    self.logger.info(f"未找到图片: {img}")
                    # 关闭弹窗与重试逻辑在 _check_loaded_once 的装饰器中处理
                time.sleep(retry_interval)
            self.logger.error(f"等待页面加载超时: {img}")
            return False
        except Exception as e:
            self.logger.error(f"等待页面加载时发生异常: {img}, 错误信息: {str(e)}")
            return False

    def go_back(self) -> 'BasePage':
        """
        返回上一页
        
        Returns:
            BasePage: 返回自身，支持链式调用
        """
        keyevent('BACK')
        return self

    def home(self) -> 'BasePage':
        """
        返回主页
        
        Returns:
            BasePage: 返回自身，支持链式调用
        """
        keyevent('HOME')
        return self

    def get_current_activity(self) -> Optional[str]:
        """
        获取当前Activity
        
        Returns:
            Optional[str]: 当前Activity名称，如果获取失败则返回None
        """
        return self._safe_get_device_attribute('current_activity', None)

    def is_activity(self, activity_name: str) -> bool:
        """
        判断当前是否为指定Activity
        
        Args:
            activity_name (str): Activity名称
            
        Returns:
            bool: 是否为指定Activity
        """
        if not activity_name:
            return False
        current_activity = self.get_current_activity()
        return bool(current_activity and activity_name in current_activity)

    def scroll_up(self, duration: float = 1.0) -> 'BasePage':
        """
        向上滑动屏幕
        
        Args:
            duration (float): 滑动持续时间，默认1.0秒
            
        Returns:
            BasePage: 返回自身，支持链式调用
        """
        if not self.is_device_connected():
            self.logger.warning("设备未连接，尝试连接...")
            # 尝试连接设备
            if self.setup_airtest():
                self.logger.info("设备连接成功")
            else:
                self.logger.error("设备连接失败，无法滑动")
                return self
        
        width, height = self._get_device_resolution()
        if width and height:
            swipe((495, 864), (495, 182), duration=duration)
            self.logger.info(f"向上滑动屏幕，持续时间: {duration}秒")
        return self

    def scroll_down(self, duration: float = 1.0) -> 'BasePage':
        """
        向下滑动屏幕
        
        Args:
            duration (float): 滑动持续时间，默认1.0秒
            
        Returns:
            BasePage: 返回自身，支持链式调用
        """
        # 调试日志：输出设备连接状态的详细信息
        is_connected_flag = self.is_connected
        has_device_attr = hasattr(G, 'DEVICE')
        device_is_not_none = G.DEVICE is not None if has_device_attr else False
        self.logger.debug(f"设备连接状态检查: is_connected={is_connected_flag}, has_device_attr={has_device_attr}, device_is_not_none={device_is_not_none}")

        if not self.is_device_connected():
            self.logger.warning("设备未连接，尝试重新连接")
            # 尝试重新连接设备
            if not self.setup_airtest():
                self.logger.error("重新连接设备失败")
                return self
            self.logger.info("重新连接设备成功")
        # 连接成功后继续执行滑动
        
        width, height = self._get_device_resolution()
        if width and height:
            swipe((width/2, height/4), (width/2, height*3/4), duration=duration)
            self.logger.info(f"向下滑动屏幕，持续时间: {duration}秒")
        return self

    def scroll_left(self, duration: float = 1.0) -> 'BasePage':
        """
        向左滑动屏幕
        
        Args:
            duration (float): 滑动持续时间，默认1.0秒
            
        Returns:
            BasePage: 返回自身，支持链式调用
        """
        if not self.is_device_connected():
            self.logger.warning("设备未连接，无法滑动")
            return self
        
        width, height = self._get_device_resolution()
        if width and height:
            # 整屏滑动：从最右侧滑动到最左侧
            swipe((width*0.86, height/2), (width*0.1, height/2), duration=duration)
            self.logger.info(f"向左滑动屏幕，持续时间: {duration}秒")
        return self

    def scroll_right(self, duration: float = 1.0) -> 'BasePage':
        """
        向右滑动屏幕
        
        Args:
            duration (float): 滑动持续时间，默认1.0秒
            
        Returns:
            BasePage: 返回自身，支持链式调用
        """
        if not self.is_device_connected():
            self.logger.warning("设备未连接，无法滑动")
            return self
        
        width, height = self._get_device_resolution()
        if width and height:
            swipe((width/4, height/2), (width*3/4, height/2), duration=duration)
            self.logger.info(f"向右滑动屏幕，持续时间: {duration}秒")
        return self
        
    def _safe_get_device_attribute(self, attribute: str, default_value: Any = None) -> Any:
        """
        安全获取设备属性
        
        Args:
            attribute (str): 要获取的属性名
            default_value (Any): 默认值
            
        Returns:
            Any: 属性值或默认值
        """
        if not self.is_device_connected():
            self.logger.warning(f"设备未连接，无法获取属性: {attribute}")
            return default_value
        
        device = self._get_device()
        if hasattr(device, attribute):
            return getattr(device, attribute)() if callable(getattr(device, attribute)) else getattr(device, attribute)
        self.logger.warning(f"设备没有属性: {attribute}")
        return default_value
        
    def _get_device_resolution(self) -> Tuple[int, int]:
        """
        获取设备分辨率
        
        Returns:
            Tuple[int, int]: 分辨率(width, height)
        """
        return self._safe_get_device_attribute('get_current_resolution', (0, 0))
        
    def _get_device(self) -> Optional[Any]:
        """
        获取设备实例
        
        Returns:
            Optional[Any]: 设备实例或None
        """
        from airtest.core.api import G
        return G.DEVICE if hasattr(G, 'DEVICE') and G.DEVICE else None

    # 通用装饰器：当目标方法返回False时，尝试关闭弹窗后重试一次
    # 用法：@BasePage.close_popup_on_false(["a.png", "b.png"]) 或 from utils.base_page import close_popup_on_false
    @staticmethod
    def close_popup_on_false(
        image_names: List[str],
        close_btn_record_pos: Optional[Tuple[float, float]] = None,
        resolution: Optional[Tuple[int, int]] = None,
        retries: int = 1,
    ):
        def decorator(func):
            @wraps(func)
            def wrapper(self, *args, **kwargs):
                result = func(self, *args, **kwargs)
                if result:
                    return result
                # 按参数化的重试策略进行：关弹窗 -> 等待 -> 重试检测
                attempt = 0
                while attempt < max(0, retries):
                    attempt += 1
                    try:
                        if image_names:
                            self.logger.info(f"页面检查未通过，尝试第{attempt}/{retries}次关闭弹窗后重试")
                            self.close_popup(
                                image_names=image_names,
                                close_btn_record_pos=close_btn_record_pos,
                                resolution=resolution,
                            )
                    except Exception as e:
                        self.logger.warning(f"第{attempt}次关闭弹窗出现异常: {str(e)}")
                    # 固定等待 0.5 秒
                    time.sleep(0.5)

                    result = func(self, *args, **kwargs)
                    if result:
                        return result
                return False
            return wrapper
        return decorator

    def close_popup(self, image_names: List[str], close_btn_record_pos: Optional[Tuple[float, float]] = None, resolution: Optional[Tuple[float, float]] = None) -> bool:
        """
        关闭弹窗操作，包括查找弹窗、点击关闭按钮和验证关闭结果
        
        Args:
            image_names (List[str]): 弹窗图片名称列表，用于识别弹窗
            close_btn_record_pos (Optional[Tuple[float, float]]): 关闭按钮的记录位置坐标，默认为None时使用配置文件中的值
            resolution (Optional[Tuple[int, int]]): 分辨率，默认为None时使用配置文件中的值
            
        Returns:
            bool: 若找到任意一个弹窗并关闭成功则立即返回True；若均未成功则返回False
        """
        try:
            self.logger.info(f"开始处理弹窗列表(找到一个即返回): {image_names}")
            # 遍历所有图片名称，任意一个关闭成功即返回True
            for index, image_name in enumerate(image_names):
                self.logger.info(f"尝试关闭第{index+1}/{len(image_names)}个弹窗: {image_name}")
                # 构建包含平台名称的路径: Template/Royal_Dream/common/image_name
                close_btn_path = os.path.join(self._template_base_dir, self.platform_name, "common", image_name)
                self.logger.info(f"弹窗图片路径: {close_btn_path}")
                try:
                    template = Template(
                        close_btn_path,
                        record_pos=close_btn_record_pos if close_btn_record_pos is not None else AIRTEST_CONFIG['RECORD_POS'],
                        resolution=resolution if resolution is not None else AIRTEST_CONFIG['RESOLUTION']
                    )
                    pos = exists(template)
                    if pos:
                        click(pos)
                        self.logger.info(f"检测到并点击{image_name}弹窗关闭按钮成功")
                        time.sleep(1.5)
                        self.logger.info(f"{image_name}弹窗关闭完成，立即返回True")
                        return True
                    else:
                        self.logger.info(f"未检测到弹窗关闭按钮: {image_name}")
                except Exception as e_check:
                    self.logger.warning(f"处理{image_name}弹窗时出现异常: {str(e_check)}，尝试下一个")
                    continue

            self.logger.info("未发现可关闭的弹窗或全部尝试失败，返回False")
            return False
        except Exception as e:
            self.logger.error(f"关闭弹窗失败: {str(e)}")
            return False

    @staticmethod
    def _common_popup_images() -> List[str]:
        return [
            "paket_close.png",
            "vip1_close.png",
            "vip2_close.png",
            "general_close.png"
        ]

    @close_popup_on_false(image_names=_common_popup_images.__func__())
    def _check_loaded_once(
        self,
        img: str,
        record_pos: Optional[Tuple[float, float]] = None,
        resolution: Optional[Tuple[int, int]] = None,
        threshold: Optional[float] = None,
    ) -> bool:
        """
        执行一次页面元素检测；失败时由装饰器尝试关闭常见弹窗并重试一次
        """
        pos = self.is_template_exists(
            img,
            template_dir=self.template_dir,
            record_pos=record_pos,
            resolution=resolution,
            threshold=threshold,
        )
        return True if pos else False

    def touch_template(self, image_name: str, template_dir: str, record_pos: Optional[Tuple[float, float]] = None, resolution: Optional[Tuple[int, int]] = None, duration: float = 0, threshold: Optional[float] = None) -> bool:
        """
        封装touch操作，点击指定模板图片，支持长按功能
        
        Args:
            image_name (str): 图片文件名
            template_dir (str): 模板图片所在的目录
            record_pos (Optional[Tuple[float, float]]): 记录位置坐标，默认为None时使用配置文件中的值
            resolution (Optional[Tuple[int, int]]): 分辨率，默认为None时使用配置文件中的值
            duration (float): 点击时间（秒），默认为0表示普通点击
            threshold (Optional[float]): 图片匹配阈值，默认为None时使用Airtest默认阈值
            
        Returns:
            bool: 操作是否成功
            
        Raises:
            FileNotFoundError: 当模板图片不存在时
            Exception: 当点击操作失败时
        """
        try:
            if not template_dir:
                self.logger.warning("template_dir参数不能为None或空")
                return False
            # template_dir 可能是绝对路径或相对路径，如果是相对路径则基于 Template 基础目录
            if os.path.isabs(template_dir):
                full_template_path = os.path.join(template_dir, image_name)
            else:
                # 相对路径：基于 Template 基础目录
                full_template_path = os.path.join(self._template_base_dir, template_dir, image_name)
            if not os.path.exists(full_template_path):
                self.logger.warning(f"模板图片不存在: {full_template_path}")
                return False

            template_kwargs = {
                'record_pos': record_pos if record_pos is not None else AIRTEST_CONFIG["RECORD_POS"],
                'resolution': resolution if resolution is not None else AIRTEST_CONFIG["RESOLUTION"]
            }

            if threshold is not None:
                template_kwargs['threshold'] = threshold

            template = Template(
                full_template_path,
                **template_kwargs
            )

            if duration > 0:
                touch(template, duration=duration)
                self.logger.info(f"长按模板图片成功: {image_name}，长按时间: {duration}秒")
            else:
                touch(template)
                self.logger.info(f"点击模板图片成功: {image_name}")

            return True
        except Exception as e:
            self.logger.error(f"点击模板图片失败: {str(e)}")
            return False

    def find_template_position(self, image_name: str, template_dir: str, record_pos: Optional[Tuple[float, float]] = None, resolution: Optional[Tuple[int, int]] = None, timeout: int = 3, threshold: Optional[float] = None) -> Optional[Tuple[int, int]]:
        """
        查找模板图片的位置并返回坐标
        
        Args:
            image_name (str): 图片文件名
            template_dir (str): 模板图片所在的目录
            record_pos (Optional[Tuple[float, float]]): 记录位置坐标，默认为None时使用配置文件中的值
            resolution (Optional[Tuple[int, int]]): 分辨率，默认为None时使用配置文件中的值
            timeout (int): 查找超时时间，默认为20秒
            threshold (Optional[float]): 图片匹配阈值，默认为None时使用Airtest默认阈值
            
        Returns:
            Optional[Tuple[int, int]]: 图片的坐标位置，如果查找失败则返回None
            
        Raises:
            FileNotFoundError: 当模板图片不存在时
            TargetNotFoundError: 当超时未找到图片时
            Exception: 当查找图片位置失败时
        """
        try:
            if not template_dir:
                raise ValueError("template_dir参数不能为None或空")
            
            # template_dir 可能是绝对路径或相对路径，如果是相对路径则基于 Template 基础目录
            if os.path.isabs(template_dir):
                full_template_path = os.path.join(template_dir, image_name)
            else:
                # 相对路径：基于 Template 基础目录
                full_template_path = os.path.join(self._template_base_dir, template_dir, image_name)
            if not os.path.exists(full_template_path):
                raise FileNotFoundError(f"模板图片不存在: {full_template_path}")
            
            template_kwargs = {
                'record_pos': record_pos if record_pos is not None else AIRTEST_CONFIG["RECORD_POS"],
                'resolution': resolution if resolution is not None else AIRTEST_CONFIG["RESOLUTION"]
            }

            if threshold is not None:
                template_kwargs['threshold'] = threshold
            
            pos = loop_find(
                Template(
                    full_template_path,
                    **template_kwargs
                ),
                timeout=timeout
            )
            self.logger.info(f"找到模板图片位置: {image_name}, 坐标: {pos}")
            return pos if pos else None
        except Exception as e:
            self.logger.error(f"查找模板图片位置失败: {str(e)}")
            return None

   
    def _validate_element_path(self, element_path: str) -> bool:
        """
        验证元素路径是否有效
        
        Args:
            element_path (str): 元素路径
            
        Returns:
            bool: 路径是否有效
        """
        if not element_path or not isinstance(element_path, str):
            self.logger.warning("元素路径无效")
            return False
        return True
    
    def find_element(self, element_path: str, timeout: int = 20) -> Optional[Tuple[int, int]]:
        """
        查找元素位置
        
        Args:
            element_path (str): 元素模板图片完整路径
            timeout (int): 超时时间，默认为20秒
            
        Returns:
            Optional[Tuple[int, int]]: 元素位置坐标，如果未找到则返回None
        """
        if not self._validate_element_path(element_path):
            return None
        
        if not self.is_device_connected():
            self.logger.warning("设备未连接，无法查找元素")
            return None
        
        try:
            # 假设 element_path 是图片文件名，template_dir 是目录
            if not hasattr(self, 'template_dir') or not self.template_dir:
                self.logger.warning("template_dir未设置，无法查找元素")
                return None
            
            pos = self.find_template_position(
                image_name=os.path.basename(element_path),
                template_dir=self.template_dir,
                timeout=timeout
            )
            return pos
        except Exception as e:
            self.logger.error(f"查找元素时出错: {str(e)}")
            return None
    
    def input_text(self, element_path: str, input_text: str, timeout: int = 20) -> bool:
        """
        输入文本
        
        Args:
            element_path (str): 输入框模板图片完整路径
            input_text (str): 要输入的文本
            timeout (int): 超时时间，默认为20秒
            
        Returns:
            bool: 是否输入成功
        """
        if not self._validate_element_path(element_path):
            return False

        if not self.is_device_connected():
            self.logger.warning("设备未连接，无法输入文本")
            return False

        try:
            pos = self.find_element(element_path, timeout)
            if pos:
                click(pos)
                text(input_text)  # 使用重命名后的参数名
                self.logger.info(f"输入文本成功: {input_text}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"输入文本时出错: {str(e)}")
            return False

    

    def is_template_exists(self, image_name: str, template_dir: str, record_pos: Optional[Tuple[float, float]] = None, resolution: Optional[Tuple[int, int]] = None, threshold: Optional[float] = None) -> Union[Tuple[float, float], bool]:
        """
        检查模板图片是否存在于屏幕上
        
        Args:
            image_name (str): 图片文件名
            template_dir (str): 模板图片所在的目录
            record_pos (Optional[Tuple[float, float]]): 记录位置坐标，默认为None时使用配置文件中的值
            resolution (Optional[Tuple[int, int]]): 分辨率，默认为None时使用配置文件中的值
            threshold (Optional[float]): 图片匹配阈值，默认为None时使用Airtest默认阈值
            
        Returns:
            Union[Tuple[float, float], bool]: 图片存在返回坐标，不存在返回False
            
        Raises:
            FileNotFoundError: 当模板图片不存在时
            Exception: 当检查图片存在性失败时
        """
        try:
            if not template_dir:
                self.logger.warning("template_dir参数不能为None或空")
                return False

            # template_dir 可能是绝对路径或相对路径，如果是相对路径则基于 Template 基础目录
            if os.path.isabs(template_dir):
                full_template_path = os.path.join(template_dir, image_name)
            else:
                # 相对路径：基于 Template 基础目录
                full_template_path = os.path.join(self._template_base_dir, template_dir, image_name)
            if not os.path.exists(full_template_path):
                self.logger.warning(f"模板图片不存在: {full_template_path}")
                return False

            template_kwargs = {
                'record_pos': record_pos if record_pos is not None else AIRTEST_CONFIG["RECORD_POS"],
                'resolution': resolution if resolution is not None else AIRTEST_CONFIG["RESOLUTION"]
            }

            if threshold is not None:
                template_kwargs['threshold'] = threshold

            pos = exists(
                Template(
                    full_template_path,
                    **template_kwargs
                )
            )
            self.logger.info(f"检查模板图片存在性: {image_name}, 结果: {pos is not False}")
            return pos
        except Exception as e:
            self.logger.error(f"检查模板图片存在性失败: {str(e)}")
            return False
            
if __name__ == "__main__":
    base_page = BasePage()