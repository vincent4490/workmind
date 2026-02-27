# -*- coding: utf-8 -*-
"""
conftest.py - pytest 配置文件
关键修复：必须在任何导入之前设置 sys.path，确保 Django 的 apps 模块能正确导入
"""
import os
import sys

# 计算路径：conftest.py 在 backend/apps/ui_test/conftest.py
_conftest_file = os.path.abspath(__file__)
_apps_dir = os.path.dirname(os.path.dirname(os.path.dirname(_conftest_file)))
_backend_dir = os.path.dirname(_apps_dir)

# 查找 backend/backend/settings.py
_backend_settings_file = os.path.join(_backend_dir, 'backend', 'settings.py')
if not os.path.exists(_backend_settings_file):
    # 向上查找最高级
    current = _backend_dir
    for _ in range(3):
        test_path = os.path.join(current, 'backend', 'backend', 'settings.py')
        if os.path.exists(test_path):
            _backend_dir = current
            _backend_settings_file = test_path
            break
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    else:
        raise RuntimeError(
            f"无法找到 backend.settings 模块\n"
            f"  期望路径: {_backend_settings_file}\n"
            f"  计算的 backend_dir: {_backend_dir}\n"
            f"  conftest.py 路径: {_conftest_file}\n"
            f"  当前工作目录: {os.getcwd()}\n"
            f"  请确保 backend/backend/settings.py 存在"
        )

# 调试模式（通过环境变量控制）
_debug_path = os.environ.get('PYTEST_DEBUG_PATH', '0') == '1'

# 调整 sys.path 顺序：确保 apps 目录优先级最高
# 1. apps 目录放在最前面（模块查找优先）
# 2. backend 目录保留在 sys.path 中（Django 需要，但不在最前面）
# 3. 移除已缓存的 backend 模块
if _apps_dir in sys.path:
    sys.path.remove(_apps_dir)
sys.path.insert(0, _apps_dir)

if _backend_dir not in sys.path:
    sys.path.insert(1, _backend_dir)

if 'backend' in sys.modules:
    del sys.modules['backend']

if _debug_path:
    print(f"[conftest.py] 路径信息:")
    print(f"  apps_dir: {_apps_dir}")
    print(f"  backend_dir: {_backend_dir}")
    print(f"  sys.path (前5个): {sys.path[:5]}")

# 导入其他模块
import warnings
from urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.simplefilter('ignore', InsecureRequestWarning)

import pytest


def pytest_configure(config):
    """pytest 配置钩子：初始化 Django"""
    import django
    import logging
    
    logger = logging.getLogger("conftest")
    
    # 确保 backend 目录在 sys.path 中
    if _backend_dir not in sys.path:
        sys.path.insert(0, _backend_dir)
        logger.debug(f"已将 backend 目录添加到 sys.path: {_backend_dir}")
    
    # 验证 backend.settings 可以导入
    try:
        import importlib
        importlib.import_module('backend.settings')
        logger.debug("backend.settings 模块可以正常导入")
    except ImportError as e:
        logger.error(f"无法导入 backend.settings 模块: {e}")
        raise ValueError(f"无法导入 backend.settings 模块: {e}")
    
    # 设置 DJANGO_SETTINGS_MODULE
    if 'DJANGO_SETTINGS_MODULE' not in os.environ:
        os.environ['DJANGO_SETTINGS_MODULE'] = 'backend.settings'
        logger.debug(f"已设置 DJANGO_SETTINGS_MODULE: backend.settings")
    
    # 初始化 Django
    try:
        from django.apps import apps
        if not apps.ready:
            django.setup()
            logger.debug("Django 初始化成功")
    except (ImportError, AttributeError):
        # Django 可能未导入或版本较旧，直接初始化
        try:
            django.setup()
            logger.debug("Django 初始化成功（直接方式）")
        except Exception as e:
            logger.error(f"Django 初始化失败: {e}", exc_info=True)
            raise
    except Exception as e:
        logger.error(f"Django 初始化失败: {e}", exc_info=True)
        raise
import allure
import shutil

from airtest.core.api import *  # type: ignore[reportWildcardImportFromLibrary]
from apps.ui_test.utils.airtest_config import DEVICE_ID, AIRTEST_CONFIG
from apps.ui_test.utils.logger_config import setup_test_logging, get_test_logger
from apps.ui_test.utils.config_manager import config_manager  # 导入配置管理器
# 创建测试日志记录器
logger = get_test_logger("conftest")
from apps.ui_test.utils.airtest_base import AirtestBase


# 全局变量，用于存储设备连接状态
_global_device = None
_global_airtest_base = None

@pytest.fixture(scope='session', autouse=True)
def setup_test_session(request):
    """设置测试会话"""
    # 获取工程师名称，用于日志区分
    engineer_name = os.environ.get('TEST_ENGINEER')
    if engineer_name:
        setup_test_logging(engineer_name)
        logger.info(f"当前工程师: {engineer_name}")
    else:
        setup_test_logging()
    # 设置日志配置 - 必须在最前面执行，确保后续的 logger.info 能正常输出
    logger.info("=== UI测试会话开始 ===")
    
    # 清除旧的测试报告和截图
    clear_old_reports()
    
    # 初始化 Airtest 环境
    init_airtest_env()
    
    yield
    # 测试会话结束后清理
    logger.info("UI测试会话结束，清理环境完成...")

@pytest.fixture(scope='session')
def global_device(device_id):
    """全局设备连接 fixture，整个测试会话只连接一次"""
    global _global_device, _global_airtest_base
    
    logger.info("=" * 60)
    logger.info("========== global_device fixture 开始执行 ==========")
    logger.info(f"参数: device_id={device_id}")
    logger.info(f"当前 _global_device 状态: {_global_device}")
    logger.info("=" * 60)
    
    if _global_device is None:
        # 优先级：命令行参数 > 环境变量 > 配置文件默认值
        actual_device_id = device_id
        if not actual_device_id:
            # 尝试从环境变量获取
            actual_device_id = os.environ.get('DEVICE_ID')
        if not actual_device_id:
            # 使用配置文件中的默认值
            actual_device_id = DEVICE_ID or "emulator-5554"
        
        logger.info(f"使用的设备 ID: {actual_device_id} (来源: {'命令行' if device_id else '环境变量' if os.environ.get('DEVICE_ID') else '配置文件'})")
        
        # 创建 AirtestBase 实例
        logger.info(f"正在创建 AirtestBase 实例，设备 ID: {actual_device_id}")
        _global_airtest_base = AirtestBase(device_id=actual_device_id)
        logger.info(f"AirtestBase 实例创建完成")
        
        # 连接设备
        logger.info(f"开始连接设备: {actual_device_id}")
        logger.info(f"准备调用 setup_airtest()...")
        try:
            connection_result = _global_airtest_base.setup_airtest()
            logger.info(f"setup_airtest() 返回结果: {connection_result}")
            if connection_result:
                # 在 Airtest 中，设备连接后通过 G.DEVICE 访问
                logger.info("准备获取 G.DEVICE...")
                from airtest.core.api import G
                _global_device = G.DEVICE
                logger.info(f"全局设备连接成功: {actual_device_id}, 设备对象: {type(_global_device)}")
            else:
                logger.error(f"全局设备连接失败: {actual_device_id}")
                pytest.fail(f"全局设备连接失败: {actual_device_id}")
        except Exception as e:
            logger.error(f"连接设备时发生异常 {type(e).__name__}: {e}", exc_info=True)
            pytest.fail(f"连接设备时发生异常 {type(e).__name__}: {e}")
    
    yield _global_device
    
    # 测试会话结束时，设备会在 cleanup_global_device 中清理

@pytest.fixture(scope='session')
def global_airtest_base():
    """全局 AirtestBase 实例 fixture"""
    global _global_airtest_base
    
    if _global_airtest_base is None:
        pytest.fail("全局设备未连接，请先使用 global_device fixture")
    
    return _global_airtest_base

# global_app fixture 已删除：开源版本不需要自动启动应用

def cleanup_global_device():
    """清理全局设备连接"""
    global _global_device, _global_airtest_base
    
    if _global_airtest_base:
        try:
            _global_airtest_base.teardown_airtest()
            logger.info("全局设备连接已清理")
        except Exception as e:
            logger.warning(f"清理全局设备连接时出错: {e}")
        finally:
            _global_device = None
            _global_airtest_base = None

# cleanup_global_app 已删除：开源版本不需要自动管理应用

def _get_screenshot_dir():
    """获取截图目录（按工程师隔离）"""
    # 获取工程师名称，用于创建专属截图目录（必须提供）
    engineer_name = os.environ.get('TEST_ENGINEER')
    if not engineer_name:
        raise ValueError("未设置环境变量 TEST_ENGINEER，必须提供工程师名称")
    
    # 优先使用环境变量中的截图目录（Web 平台传递），实现多工程师隔离
    base_screenshot_dir = os.environ.get('SCREENSHOT_DIR')
    
    if base_screenshot_dir:
        # 如果环境变量已指定完整路径（可能已包含工程师目录），直接使用
        if not os.path.isabs(base_screenshot_dir):
            # 相对路径转换为绝对路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            ui_test_dir = os.path.dirname(current_dir)
            base_screenshot_dir = os.path.join(ui_test_dir, base_screenshot_dir)
        return base_screenshot_dir
    else:
        # 使用配置文件中的截图目录，按工程师创建子目录
        # 获取 ui_test 目录的绝对路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # current_dir 为 backend/apps/ui_test，直接在此目录下创建 screenshots
        base_screenshot_dir = os.path.join(current_dir, 'screenshots')
        # 按工程师创建专属截图目录
        return os.path.join(base_screenshot_dir, engineer_name)

def clear_old_reports():
    """清除旧的测试报告和截图"""
    # 不清除 allure 报告目录，保留历史数据用于独立报告生成
    # if os.path.exists('allure-results'):
    #     shutil.rmtree('allure-results')
    
    # 获取工程师专属截图目录（_get_screenshot_dir 会检查并抛出错误）
    engineer_name = os.environ.get('TEST_ENGINEER')
    if not engineer_name:
        raise ValueError("未设置环境变量 TEST_ENGINEER，必须提供工程师名称")
    screenshot_dir = _get_screenshot_dir()
    
    # 清除截图目录（每次测试重新截图，只清理当前工程师的目录）
    if os.path.exists(screenshot_dir):
        shutil.rmtree(screenshot_dir)
    
    # 重新创建必要的目录
    os.makedirs(screenshot_dir, exist_ok=True)
    logger.info(f"已清理截图目录（工程师: {engineer_name}）: {screenshot_dir}")
    
    # 注意：不需要在这里创建 allure-results 目录
    # 测试执行器会通过 --alluredir 参数指定正确的路径（backend/apps/ui_test/allure-results/allure-results-{test_id}）
    # pytest 会在需要时自动创建该目录

def init_airtest_env():
    """初始化 Airtest 环境"""
    # 获取工程师专属截图目录（_get_screenshot_dir 会检查并抛出错误）
    engineer_name = os.environ.get('TEST_ENGINEER')
    if not engineer_name:
        raise ValueError("未设置环境变量 TEST_ENGINEER，必须提供工程师名称")
    screenshot_dir = _get_screenshot_dir()
    
    # 设置 Airtest 截图目录
    ST.LOG_DIR = screenshot_dir  # type: ignore[attr-defined]
    os.makedirs(screenshot_dir, exist_ok=True)
    
    # 设置其他 Airtest 配置
    ST.FIND_TIMEOUT = AIRTEST_CONFIG['FIND_TIMEOUT']
    ST.CLICK_DELAY = AIRTEST_CONFIG['CLICK_DELAY']  # type: ignore[attr-defined]
    logger.info(f"Airtest 环境初始化完成，截图目录（工程师: {engineer_name}）: {ST.LOG_DIR}")

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """捕获测试结果并添加到 Allure 报告"""
    outcome = yield
    report = outcome.get_result()
    if report.when == 'call' and report.failed:
        # 如果测试失败，尝试截图
        try:
            # 获取测试用例中的页面对象
            page = item.funcargs.get('login_page') or item.funcargs.get('game_page') or item.funcargs.get('game_hall_page')
            if page:
                screenshot_path = page.screenshot(f"{item.name}_failed")
                allure.attach.file(screenshot_path, name=f"{item.name}失败截图", attachment_type=allure.attachment_type.PNG)
        except Exception as e:
            logger.error(f"测试失败截图失败: {e}")

def pytest_addoption(parser):
    """添加命令行参数"""
    parser.addoption("--device-id", action="store", default=None, help="设备ID")
    parser.addoption("--package-name", action="store", default=None, help="应用包名")
    parser.addoption("--user-id", action="store", default=None, help="用户ID")
    parser.addoption("--password", action="store", default=None, help="用户密码")

@pytest.fixture(scope='session')
def device_id(request):
    """获取设备ID"""
    return request.config.getoption("--device-id")

@pytest.fixture(scope='session')
def package_name(request):
    """获取应用包名（用户在前端输入）"""
    return request.config.getoption("--package-name")

@pytest.fixture(scope='session')
def user_id(request):
    """获取用户ID"""
    return request.config.getoption("--user-id")

@pytest.fixture(scope='session')
def password(request):
    """获取用户密码"""
    return request.config.getoption("--password")


@pytest.fixture(scope="session",autouse=True)
def clean_logs_dir():
    # 日志目录已移至 ui_test/logs，由 logger_config.py 管理
    # 清理旧日志文件的功能已移至 utils/logger_config.py
    # 这里不再需要手动清理
    pass

