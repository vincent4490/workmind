# -*- coding: utf-8 -*-
"""
测试用例生成配置
可根据项目需求调整用例生成策略
"""

# ============ 用例数量配置 ============
class TestcaseQuantityConfig:
    """用例数量配置"""
    
    # 简单功能（如纯展示页面、简单查询）
    SIMPLE_MIN = 3
    SIMPLE_MAX = 8
    
    # 中等复杂度功能（如表单提交、基础 CRUD）
    MEDIUM_MIN = 5
    MEDIUM_MAX = 15
    
    # 复杂功能（如多步骤流程、复杂业务规则）
    COMPLEX_MIN = 10
    COMPLEX_MAX = 25
    
    # 核心功能（如支付、登录、权限控制）
    CRITICAL_MIN = 15
    CRITICAL_MAX = 30


# ============ 覆盖维度配置 ============
class CoverageDimensionConfig:
    """覆盖维度配置"""
    
    # 必须覆盖的维度（所有功能都要考虑）
    MANDATORY_DIMENSIONS = [
        "正向流程",      # 主流程和正常分支
        "异常处理",      # 错误输入、异常状态
    ]
    
    # 推荐覆盖的维度（根据功能特点选择）
    RECOMMENDED_DIMENSIONS = [
        "边界值",        # 上下边界、临界值
        "业务规则",      # 权限、状态流转、数据校验
        "兼容性",        # 不同角色、状态、环境
    ]
    
    # 可选覆盖的维度（高质量要求时考虑）
    OPTIONAL_DIMENSIONS = [
        "性能",          # 大数据量、响应时间
        "安全",          # 敏感操作、数据保护
        "并发",          # 多用户同时操作
        "容错",          # 网络异常、超时
    ]


# ============ 用例质量配置 ============
class TestcaseQualityConfig:
    """用例质量配置"""
    
    # 用例生成模式
    MODE_BALANCED = "balanced"      # 平衡模式：质量和数量兼顾（默认）
    MODE_QUALITY = "quality"        # 质量优先：精简但深度覆盖
    MODE_COVERAGE = "coverage"      # 覆盖优先：追求全面覆盖
    
    # 当前模式（可在运行时修改）
    CURRENT_MODE = MODE_COVERAGE
    
    # 等价类处理策略
    EQUIVALENCE_CLASS_STRATEGY = {
        MODE_QUALITY: "代表值",      # 每个等价类只取 1 个代表值
        MODE_BALANCED: "关键值",     # 每个等价类取 1-2 个关键值
        MODE_COVERAGE: "多样值",     # 每个等价类取 2-3 个典型值
    }
    
    # 边界值测试策略
    BOUNDARY_VALUE_STRATEGY = {
        MODE_QUALITY: "核心边界",    # 只测最关键的边界点
        MODE_BALANCED: "标准边界",   # 测试上下边界及 ±1
        MODE_COVERAGE: "扩展边界",   # 测试所有边界点及特殊值
    }


# ============ 提示词增强配置 ============
class PromptEnhancementConfig:
    """提示词增强配置"""
    
    # 是否启用详细的测试方法指导
    ENABLE_DETAILED_GUIDANCE = True
    
    # 是否强调覆盖全面性
    EMPHASIZE_COVERAGE = True
    
    # 是否包含示例用例
    INCLUDE_EXAMPLES = False
    
    # 是否启用分层生成（先生成框架，再补充细节）
    ENABLE_LAYERED_GENERATION = False


# ============ 特殊场景配置 ============
class SpecialScenarioConfig:
    """特殊场景配置"""
    
    # 是否自动生成跨模块集成用例
    AUTO_GENERATE_INTEGRATION_CASES = True
    
    # 是否自动生成端到端流程用例
    AUTO_GENERATE_E2E_CASES = True
    
    # 是否自动生成性能测试用例
    AUTO_GENERATE_PERFORMANCE_CASES = False
    
    # 是否自动生成安全测试用例
    AUTO_GENERATE_SECURITY_CASES = True


# ============ 动态调整函数 ============
def get_quantity_range(complexity: str = "medium") -> tuple:
    """
    根据复杂度获取用例数量范围
    
    Args:
        complexity: 复杂度级别 (simple/medium/complex/critical)
    
    Returns:
        (min_count, max_count)
    """
    config = TestcaseQuantityConfig
    
    mapping = {
        "simple": (config.SIMPLE_MIN, config.SIMPLE_MAX),
        "medium": (config.MEDIUM_MIN, config.MEDIUM_MAX),
        "complex": (config.COMPLEX_MIN, config.COMPLEX_MAX),
        "critical": (config.CRITICAL_MIN, config.CRITICAL_MAX),
    }
    
    return mapping.get(complexity, (config.MEDIUM_MIN, config.MEDIUM_MAX))


def get_coverage_dimensions(mode: str = None) -> list:
    """
    根据模式获取应覆盖的维度
    
    Args:
        mode: 生成模式 (quality/balanced/coverage)
    
    Returns:
        维度列表
    """
    if mode is None:
        mode = TestcaseQualityConfig.CURRENT_MODE
    
    config = CoverageDimensionConfig
    
    if mode == TestcaseQualityConfig.MODE_QUALITY:
        return config.MANDATORY_DIMENSIONS
    elif mode == TestcaseQualityConfig.MODE_BALANCED:
        return config.MANDATORY_DIMENSIONS + config.RECOMMENDED_DIMENSIONS
    else:  # coverage
        return (config.MANDATORY_DIMENSIONS + 
                config.RECOMMENDED_DIMENSIONS + 
                config.OPTIONAL_DIMENSIONS)


def build_quantity_instruction(complexity: str = "medium") -> str:
    """
    构建用例数量指导语句
    
    Args:
        complexity: 复杂度级别
    
    Returns:
        指导语句
    """
    min_count, max_count = get_quantity_range(complexity)
    mode = TestcaseQualityConfig.CURRENT_MODE
    
    if mode == TestcaseQualityConfig.MODE_QUALITY:
        return f"每个功能点生成 {min_count}-{min_count+2} 个高质量用例，注重深度而非数量"
    elif mode == TestcaseQualityConfig.MODE_BALANCED:
        return f"每个功能点生成 {min_count}-{max_count} 个用例，平衡质量和覆盖度"
    else:  # coverage
        return f"每个功能点生成 {min_count}-{max_count} 个用例，追求全面覆盖，复杂功能可超过 {max_count} 条"


def build_coverage_instruction(mode: str = None) -> str:
    """
    构建覆盖维度指导语句
    
    Args:
        mode: 生成模式
    
    Returns:
        指导语句
    """
    dimensions = get_coverage_dimensions(mode)
    return "用例必须覆盖以下维度：" + "、".join(dimensions)
