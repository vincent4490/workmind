# -*- coding: utf-8 -*-
from airtest.core.api import connect_device, ST, G, wait, click, snapshot, init_device
from airtest.core.error import NoDeviceError, TargetNotFoundError
import os
import time
import logging
import subprocess
from typing import Optional, Tuple, Union, Any, List
import sys
# 将项目根目录添加到Python路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from apps.ui_test.utils.airtest_config import DEVICE_ID, AIRTEST_CONFIG, EMULATOR_PATH
from airtest.core.api import start_app, G, ST, init_device, wait, click, text, snapshot, touch, Template, sleep, loop_find

# 获取日志器
logger = logging.getLogger('AirtestBase')

class AirtestBase:
    """Airtest基础类，提供Airtest的基本设置和常用功能"""

    def __init__(self, device_id: Optional[str] = None):
        """
        初始化AirtestBase实例
        :param device_id: 设备ID，例如Android设备的adb device ID
        """
        # 如果未提供设备ID，则使用配置文件中的设备ID
        self.device_id = device_id if device_id is not None else DEVICE_ID
        
        # 获取工程师名称，用于创建专属截图目录（必须提供）
        engineer_name = os.environ.get('TEST_ENGINEER')
        if not engineer_name:   
            raise ValueError("未设置环境变量 TEST_ENGINEER，必须提供工程师名称")
        
        # 优先使用环境变量中的截图目录（Web平台传递），实现多工程师隔离
        base_screenshot_dir = os.environ.get('SCREENSHOT_DIR')
        
        if base_screenshot_dir:
            # 如果环境变量已指定完整路径（可能已包含工程师目录），直接使用
            if not os.path.isabs(base_screenshot_dir):
                # 相对路径转换为绝对路径
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
                base_screenshot_dir = os.path.join(project_root, base_screenshot_dir)
            self.screenshots_dir = base_screenshot_dir
        else:
            # 使用配置文件中的截图目录，按工程师创建子目录
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            base_screenshot_dir = os.path.join(project_root, 'screenshots')
            # 按工程师创建专属截图目录
            self.screenshots_dir = os.path.join(base_screenshot_dir, engineer_name)
        
        os.makedirs(self.screenshots_dir, exist_ok=True)
        self.is_connected = False
        logger.info(f"初始化AirtestBase实例，设备ID: {self.device_id}，截图目录: {self.screenshots_dir}")

    def _start_emulator(self) -> bool:
        """
        尝试启动雷电模拟器
        :return: 是否启动成功
        """
        try:
            logger.info("尝试启动雷电模拟器...")
            # 使用配置文件中的模拟器路径
            emulator_path = EMULATOR_PATH
            
            # 检查路径是否存在
            if os.path.exists(emulator_path):
                logger.info(f"使用配置的雷电模拟器路径: {emulator_path}")
            else:
                logger.warning(f"未找到雷电模拟器安装路径: {emulator_path}")
                
                # 尝试通过系统路径查找
                try:
                    # 在Windows上使用where命令查找
                    result = subprocess.run(['where', 'dnplayer.exe'], capture_output=True, text=True, check=True)
                    emulator_path = result.stdout.strip().split('\n')[0]
                    logger.info(f"通过系统路径找到雷电模拟器: {emulator_path}")
                except Exception:
                    logger.error("无法找到雷电模拟器，请确保已安装并添加到系统环境变量或在config.py中配置EMULATOR_PATH")
                    return False

            # 启动模拟器
            process = subprocess.Popen([emulator_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info(f"已启动雷电模拟器: {emulator_path}")
            
            # 等待模拟器启动完成
            logger.info("等待模拟器启动完成...")
            time.sleep(30)  # 等待30秒，根据实际情况调整
            
            # 检查模拟器是否成功启动
            try:
                # 尝试列出设备，检查模拟器是否已启动
                adb_path = os.path.join(os.environ.get('ANDROID_HOME', ''), 'platform-tools', 'adb.exe')
                if not os.path.exists(adb_path):
                    adb_path = 'adb.exe'  # 假设adb在系统路径中
                
                result = subprocess.run([adb_path, 'devices'], capture_output=True, text=True, check=True)
                if self.device_id in result.stdout:
                    logger.info(f"模拟器 {self.device_id} 已成功启动并连接")
                    return True
                else:
                    logger.warning(f"模拟器已启动，但未找到设备 {self.device_id}")
                    return False
            except Exception as e:
                logger.error(f"检查模拟器启动状态时出错: {str(e)}")
                return False
        except Exception as e:
            logger.error(f"启动模拟器时出错: {str(e)}", exc_info=True)
            return False

    def setup_airtest(self) -> bool:
        """
        设置Airtest环境，连接设备
        :return: 是否设置成功
        """
        retry_count = AIRTEST_CONFIG.get('RETRY_COUNT', 3)
        retry_interval = AIRTEST_CONFIG.get('RETRY_INTERVAL', 5)
        timeout = AIRTEST_CONFIG.get('DEVICE_CONNECT_TIMEOUT', 10)
        
        for attempt in range(retry_count):
            try:
                # 确保日志目录存在
                log_dir = os.path.join(os.getcwd(), AIRTEST_CONFIG['LOG_DIR'])
                os.makedirs(log_dir, exist_ok=True)
                logger.info(f"日志目录已创建: {log_dir}")

                if self.device_id:
                    logger.info(f"尝试连接到设备: {self.device_id} (尝试 {attempt+1}/{retry_count})")
                    logger.info(f"准备调用 init_device(platform='Android', uuid='{self.device_id}')...")
                    # 尝试使用init_device连接设备，并设置超时
                    try:
                        import threading
                        import queue
                        
                        # 使用线程和队列来实现超时机制
                        result_queue = queue.Queue()
                        exception_queue = queue.Queue()
                        
                        def call_init_device():
                            try:
                                logger.info(f"线程中开始调用 init_device()...")
                                init_device(platform='Android', uuid=self.device_id)
                                logger.info(f"线程中 init_device() 调用完成")
                                result_queue.put(True)
                            except Exception as e:
                                logger.error(f"线程中 init_device() 调用异常: {type(e).__name__}: {e}", exc_info=True)
                                exception_queue.put(e)
                        
                        thread = threading.Thread(target=call_init_device, daemon=True)
                        thread.start()
                        thread.join(timeout=timeout)
                        
                        if thread.is_alive():
                            logger.error(f"init_device() 调用超时（{timeout}秒），设备可能无法连接")
                            raise TimeoutError(f"设备连接超时: {self.device_id}")
                        
                        if not exception_queue.empty():
                            raise exception_queue.get()
                        
                        if not result_queue.empty():
                            logger.info(f"init_device() 调用完成，已连接到指定设备: {self.device_id}")
                        else:
                            logger.warning(f"init_device() 调用完成，但未收到结果")
                    except Exception as e:
                        logger.error(f"init_device() 调用异常: {type(e).__name__}: {e}", exc_info=True)
                        raise
                else:
                    # 如果未指定设备ID，尝试连接当前唯一的设备
                    logger.info(f"尝试连接到默认设备 (尝试 {attempt+1}/{retry_count})")
                    logger.info(f"准备调用 init_device(platform='Android')...")
                    try:
                        import threading
                        import queue
                        
                        # 使用线程和队列来实现超时机制
                        result_queue = queue.Queue()
                        exception_queue = queue.Queue()
                        
                        def call_init_device():
                            try:
                                logger.info(f"线程中开始调用 init_device()...")
                                init_device(platform='Android')
                                logger.info(f"线程中 init_device() 调用完成")
                                result_queue.put(True)
                            except Exception as e:
                                logger.error(f"线程中 init_device() 调用异常: {type(e).__name__}: {e}", exc_info=True)
                                exception_queue.put(e)
                        
                        thread = threading.Thread(target=call_init_device, daemon=True)
                        thread.start()
                        thread.join(timeout=timeout)
                        
                        if thread.is_alive():
                            logger.error(f"init_device() 调用超时（{timeout}秒），设备可能无法连接")
                            raise TimeoutError(f"设备连接超时: 默认设备")
                        
                        if not exception_queue.empty():
                            raise exception_queue.get()
                        
                        if not result_queue.empty():
                            logger.info("init_device() 调用完成，已连接到默认设备")
                        else:
                            logger.warning("init_device() 调用完成，但未收到结果")
                    except Exception as e:
                        logger.error(f"init_device() 调用异常: {type(e).__name__}: {e}", exc_info=True)
                        raise
                # 设置全局超时时间
                ST.FIND_TIMEOUT = AIRTEST_CONFIG['FIND_TIMEOUT']
                ST.CLICK_DELAY = AIRTEST_CONFIG['CLICK_DELAY']  # type: ignore[attr-defined]
                self.is_connected = True
                logger.info("Airtest环境设置完成，设备已连接")
                return True
            except (IndexError, RuntimeError, Exception) as e:
                # 根据异常类型提供不同的错误信息
                if isinstance(e, IndexError):
                    error_msg = f"无法连接设备: 未找到设备，请检查设备是否已连接并开启USB调试: {str(e)}"
                elif isinstance(e, RuntimeError):
                    error_msg = f"无法连接设备: {str(e)}"
                else:
                    error_msg = f"设置Airtest环境时出错: {str(e)}"
                
                logger.error(error_msg, exc_info=True)
                
                # 统一的模拟器启动逻辑
                should_start_emulator = (
                    attempt == 0 and (
                        isinstance(e, (IndexError, RuntimeError)) or 
                        ('device not ready' in str(e) or 'device not found' in str(e).lower())
                    )
                )
                
                if should_start_emulator and self._start_emulator():
                    logger.info("模拟器启动成功，尝试重新连接...")
                    time.sleep(retry_interval)  # 等待一段时间再重试
                    continue
                elif attempt < retry_count - 1:
                    logger.info(f"{retry_interval}秒后重试连接...")
                    time.sleep(retry_interval)
                    continue
                return False
        return False


    def teardown_airtest(self) -> None:
        """
        清理Airtest环境，断开设备连接
        """
        try:
            # 直接断开设备连接，不再生成报告
            pass
        finally:
            # 无论报告生成是否成功，都尝试断开设备连接
            self._disconnect_device()
            self.is_connected = False





    def _disconnect_device(self) -> None:
        """
        断开与设备的连接
        """
        try:
            if G.DEVICE:
                G.DEVICE.disconnect()
                self.is_connected = False
                logger.info("设备连接已断开")
        except NoDeviceError:
            logger.info("没有设备连接，无需断开")
        except Exception as e:
            logger.error(f"断开设备连接时出错: {str(e)}", exc_info=True)



    def screenshot(self, name: str) -> str:
        """
        截取屏幕并保存
        :param name: 截图名称
        :return: 截图路径
        """
        # 先刷新设备连接状态
        if not self.is_device_connected():
            logger.warning("设备未连接，无法截图")
            return ""

        try:
            screenshot_path = os.path.join(self.screenshots_dir, f'{name}_{time.strftime("%Y%m%d_%H%M%S")}.png')
            snapshot(filename=screenshot_path)
            logger.info(f"截图已保存: {screenshot_path}")
            return screenshot_path
        except Exception as e:
            logger.error(f"截图失败: {str(e)}", exc_info=True)
            return ""




    def is_device_connected(self) -> bool:
        """
        检查设备是否已连接
        :return: 设备连接状态
        """
        # 检查G.DEVICE的实际状态
        device_connected = hasattr(G, 'DEVICE') and G.DEVICE is not None
        # 更新is_connected属性以保持同步
        if device_connected != self.is_connected:
            self.is_connected = device_connected
            if device_connected:
                logger.info("设备连接状态更新: 已连接")
            else:
                logger.info("设备连接状态更新: 已断开")
        return device_connected

    def open_app(self, package_name: str) -> bool:
        """
        启动指定包名的应用，包含智能重试机制
        :param package_name: 应用包名
        :return: 是否启动成功
        """
        retry_count = AIRTEST_CONFIG.get('RETRY_COUNT', 3)
        retry_interval = AIRTEST_CONFIG.get('RETRY_INTERVAL', 5)

        if not self.is_connected:
            if not self.setup_airtest():
                logger.error("设备未连接，无法启动应用")
                return False

        for attempt in range(retry_count):
            try:
                logger.info(f"尝试启动应用: {package_name} (尝试 {attempt+1}/{retry_count})")
                start_app(package_name)
                
                # 验证应用是否真正启动成功
                if self.is_app_running(package_name):
                    logger.info(f"成功启动应用: {package_name}")
                    return True
                else:
                    logger.warning(f"应用 {package_name} 启动后未检测到运行状态")
                    
                if attempt < retry_count - 1:
                    logger.info(f"{retry_interval}秒后重试启动应用...")
                    time.sleep(retry_interval)
            except Exception as e:
                logger.error(f"启动应用失败: {str(e)}", exc_info=True)
                if attempt < retry_count - 1:
                    logger.info(f"{retry_interval}秒后重试启动应用...")
                    time.sleep(retry_interval)

        logger.error(f"经过 {retry_count} 次尝试后，启动应用 {package_name} 失败")
        return False

    def is_app_installed(self, package_name: str) -> bool:
        """
        检查指定包名的应用是否已安装
        :param package_name: 应用包名
        :return: 是否已安装
        """
        if not self.is_connected:
            logger.warning("设备未连接，无法检查应用安装状态")
            return False

        try:
            # 使用adb命令检查应用是否已安装
            result = G.DEVICE.shell(f"pm list packages | grep {package_name}")
            if package_name in result:
                logger.info(f"应用 {package_name} 已安装")
                return True
            else:
                logger.warning(f"应用 {package_name} 未安装")
                return False
        except Exception as e:
            logger.error(f"检查应用安装状态时出错: {str(e)}")
            return False

    def is_app_running(self, package_name: str) -> bool:
        """
        检查指定包名的应用是否正在运行
        :param package_name: 应用包名
        :return: 是否正在运行
        """
        if not self.is_connected:
            logger.warning("设备未连接，无法检查应用运行状态")
            return False

        try:
            # 使用adb命令检查应用是否正在运行
            # 尝试多种方法检查应用运行状态
            methods = [
                f"pidof {package_name}",
                f"ps | grep {package_name}",
                f"dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp' | grep {package_name}"
            ]

            for method in methods:
                try:
                    result = G.DEVICE.shell(method)
                    if result.strip():
                        logger.info(f"使用方法 {method} 检查应用{package_name}运行状态: 正在运行")
                        return True
                except Exception as e_method:
                    logger.warning(f"使用方法 {method} 检查应用运行状态时出错: {str(e_method)}")
                    continue

            # 所有方法都失败或未找到应用
            logger.info(f"应用{package_name}运行状态: 未运行")
            return False
        except Exception as e:
            logger.error(f"检查应用运行状态时出错: {str(e)}", exc_info=True)
            return False

    def close_app(self, package_name: str) -> bool:
        """
        关闭指定包名的应用
        :param package_name: 应用包名
        :return: 是否关闭成功
        """
        if not self.is_connected:
            logger.warning("设备未连接，无需关闭应用")
            return True

        try:
            from airtest.core.api import stop_app
            logger.info(f"尝试关闭应用: {package_name}")
            stop_app(package_name)
            logger.info(f"成功关闭应用: {package_name}")
            return True
        except Exception as e:
            logger.error(f"关闭应用失败: {str(e)}", exc_info=True)
            return False


    

if __name__ == "__main__":
    # 测试代码
    airtest_base = AirtestBase()
    airtest_base.setup_airtest()