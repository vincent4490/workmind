# -*- coding: utf-8 -*-
"""
UI场景动态测试
从数据库读取场景数据并执行
"""
import os
import logging
import pytest
import allure

logger = logging.getLogger(__name__)


def test_ui_flow_execution(global_device, global_airtest_base, package_name):
    """
    动态UI场景测试
    
    通过环境变量 UI_FLOW_EXECUTION_ID 获取执行ID，
    从数据库读取场景数据并执行
    
    Args:
        global_device: 全局设备连接
        global_airtest_base: Airtest基础环境
        package_name: 应用包名（用户在前端输入，可选）
    """
    # 1. 获取执行ID
    execution_id = os.environ.get('UI_FLOW_EXECUTION_ID')
    if not execution_id:
        pytest.fail("未设置环境变量 UI_FLOW_EXECUTION_ID，无法执行测试")
    
    logger.info(f"开始执行UI场景测试: execution_id={execution_id}")
    
    # 2. 从数据库加载场景数据
    from apps.ui_test.models import UiTestExecution
    from apps.ui_test.utils.ui_flow_runner import UiFlowRunner
    
    try:
        execution = UiTestExecution.objects.get(id=execution_id)
        case = execution.case
        case_data = case.case_data
        
        logger.info(f"加载用例: {case.name}")
        if package_name:
            logger.info(f"应用包名: {package_name}")
        allure.dynamic.title(f"UI场景: {case.name}")
        allure.dynamic.description(case_data.get('description', ''))
        
        # 3. 准备场景数据
        ui_flow = case_data.get('ui_flow', [])
        variables = case_data.get('variables', [])
        runtime = case_data.get('runtime', {})
        custom_component_defs = case_data.get('custom_component_defs', {})
        
        if not ui_flow:
            pytest.fail("场景数据为空，无法执行")
        
        logger.info(f"场景包含 {len(ui_flow)} 个步骤")
        
        # 4. 获取图片资源目录
        # 默认使用 common 目录（当步骤中 image_scope="game" 或留空时使用）
        from pathlib import Path
        image_base_dir = Path(__file__).resolve().parents[1] / "Template" / "common"
        
        # 5. 创建并执行场景
        runner = UiFlowRunner(image_base_dir=str(image_base_dir))
        runner.run(
            ui_flow=ui_flow,
            custom_component_defs=custom_component_defs,
            variables=variables,
            runtime=runtime
        )
        
        logger.info(f"✅ UI场景执行成功: {case.name}")
        
    except UiTestExecution.DoesNotExist:
        error_msg = f"执行记录不存在: execution_id={execution_id}"
        logger.error(error_msg)
        pytest.fail(error_msg)
    except Exception as e:
        error_msg = f"UI场景执行失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        pytest.fail(error_msg)
