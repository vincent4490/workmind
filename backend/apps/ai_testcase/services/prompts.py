# -*- coding: utf-8 -*-
"""
Prompt 模板管理
"""

from apps.ai_testcase.services.mode_policy import render_mode_note_for_direct

# ============ 两种生成模式的提示词 ============

_TESTCASE_DIRECT_JSON_SCHEMA = """{
    "title": "需求名称_测试用例",
    "modules": [
        {
            "name": "模块名称",
            "functions": [
                {
                    "name": "功能点名称",
                    "cases": [
                        {
                            "name": "用例名称",
                            "priority": "P0",
                            "precondition": "前置条件",
                            "steps": "1. 步骤一\\n2. 步骤二",
                            "expected": "预期结果",
                            "scenario_type": "happy|validation|boundary|exception|permission|state|concurrency（可选）",
                            "dedupe_key": "同类场景去重键（可选）"
                        }
                    ]
                }
            ]
        }
    ]
}"""

_TESTCASE_ATTACHMENTS_JSON_SCHEMA = """{
    "title": "需求名称_测试用例",
    "modules": [
        {
            "name": "模块名称",
            "functions": [
                {
                    "name": "功能点名称",
                    "cases": [
                        {
                            "name": "用例名称",
                            "priority": "P0",
                            "precondition": "前置条件",
                            "steps": "1. 步骤一\\n2. 步骤二",
                            "expected": "预期结果"
                        }
                    ]
                }
            ]
        }
    ]
}"""

_TESTCASE_ATTACHMENTS_HEAD = """用户会提供以下信息（可能同时包含多种类型）：
1. 手动输入的需求描述文字
2. 从需求文档 / 技术方案中提取的文字内容
3. UI 设计图 / 原型图（图片）

你需要综合所有信息，生成结构化的测试用例。

特别注意：
- 如果提供了 UI 设计图或原型图，请仔细分析图片中的页面元素、交互控件、布局结构，并据此补充用例
- 标注为未来版本规划的功能（如"v2.0规划"、"后续版本"、"暂不实现"等），不要为其生成用例
- 若文档中引用了外部资料但未包含（如"详见XX文档"），请在对应用例的前置条件中标注"需补充：XX"
- 文档中的表格、列表同样包含重要的业务规则，不要遗漏
"""

_TESTCASE_COMMON_RULES = """要求：
1. priority 只能是 P0/P1/P2/P3
2. P0 是最高优先级（核心功能），P3 是最低（边界/异常）
"""


def _build_testcase_system_prompt(*, head: str, json_schema: str, requirements: str, tail: str) -> str:
    return (
        "你是一个资深专业的测试工程师，擅长编写高质量的测试用例。\n\n"
        + head.strip()
        + "\n\n请严格按照以下 JSON 格式返回，不要包含任何其他文字，只返回纯 JSON：\n\n"
        + json_schema.strip()
        + "\n\n"
        + requirements.strip()
        + "\n\n"
        + tail.strip()
        + "\n"
    )


_TESTCASE_DIRECT_HEAD = "用户会给你一个功能需求描述，你需要生成结构化的测试用例。"


def _with_mode_note(head: str, mode: str) -> str:
    # 将“模式说明块”统一注入 direct/attachments 的 head，保证 direct 与 agent 口径一致。
    return (render_mode_note_for_direct(mode).strip() + "\n\n" + head.strip()).strip()


_REQ_COMPREHENSIVE_DIRECT = (
    _TESTCASE_COMMON_RULES
    + """3. 用例预算按功能复杂度和风险动态分配：简单功能可少量代表性覆盖，复杂/高风险功能可增加用例；预算不是硬性上下限
4. 用例覆盖维度（必须全面覆盖）：
   - 正向流程：主流程 + 各种正常分支场景
   - 异常处理：各类错误输入、异常状态、系统异常
   - 边界值：上下边界、临界值、极限值
   - 业务规则：权限控制、状态流转、数据校验、业务约束
   - 兼容性：不同角色、不同状态、不同环境
   - 性能与安全：大数据量、并发、敏感操作
5. 覆盖优先：关键业务规则和高风险路径不能因为预算被截断；低风险或重复场景可以少写
6. 不能为了凑数量生成低价值重复用例；仅数据不同但测试目的相同的场景应参数化或合并描述
7. steps 字段中多个步骤用 \\n 分隔，每步需包含明确的操作对象和操作动作
8. 尽量为每条用例补充 scenario_type 与 dedupe_key（用于后处理去重/合并）；同类场景不要重复堆叠
9. 只返回 JSON，不要有 ```json 标记或其他文字"""
)

_TAIL_COMPREHENSIVE = """用例设计方法指南（必须遵守）：
- **等价类划分**：识别所有有效和无效等价类，每个等价类至少 1 条用例。对于复杂输入（如表单），不同字段的无效等价类应分别验证（如邮箱格式错误 1 条、手机号格式错误 1 条、必填项为空 1 条）
- **边界值分析**：必须测试所有边界点（最小值、最小值-1、最大值、最大值+1），以及特殊边界（如 0、空字符串、null）
- **场景法**：覆盖主流程 + 所有重要分支路径 + 异常路径。对于多步骤流程，要考虑各步骤的不同状态组合
- **状态转换**：如果功能涉及状态流转，必须覆盖所有合法状态转换 + 非法状态转换
- **组合测试**：当多个条件影响结果时，使用正交表或成对组合法，确保关键组合都被覆盖
- **异常场景**：必须包含网络异常、超时、权限不足、数据不存在、并发冲突等常见异常
- **总原则**：在保证每条用例有独立测试价值的前提下，追求覆盖的全面性。宁可多覆盖，不要遗漏重要场景"""


# 全覆盖模式（复杂需求）- 原有的详细提示词（由积木化块拼接）
TESTCASE_SYSTEM_PROMPT_COMPREHENSIVE = _build_testcase_system_prompt(
    head=_with_mode_note(_TESTCASE_DIRECT_HEAD, "comprehensive"),
    json_schema=_TESTCASE_DIRECT_JSON_SCHEMA,
    requirements=_REQ_COMPREHENSIVE_DIRECT,
    tail=_TAIL_COMPREHENSIVE,
)

_REQ_FOCUSED_DIRECT = (
    _TESTCASE_COMMON_RULES
    + """3. 用例预算按业务价值和风险动态分配：以**核心主流程、核心业务规则、主要异常与关键边界**为主，不追求等价类穷尽与组合枚举
4. 用例覆盖维度（聚焦覆盖）：
   - 正向流程：主流程与对业务有关键影响的分支
   - 异常处理：最高频、对业务影响最大的错误场景
   - 边界值：对业务结果有关键影响的边界点
   - 业务规则：权限、状态流转、数据校验等核心逻辑
5. 不要求单独展开：多环境兼容性枚举、性能/安全/并发专项测试，**除非需求明确写出**
6. 覆盖优先：核心规则必须覆盖；低价值变体可以省略，不能为了凑数量生成低价值重复用例
7. steps 字段中多个步骤用 \\n 分隔，每步需包含明确的操作对象和操作动作
8. 尽量为每条用例补充 scenario_type 与 dedupe_key（用于后处理去重/合并）；同类场景不要重复堆叠
9. 只返回 JSON，不要有 ```json 标记或其他文字"""
)

_TAIL_FOCUSED = """用例设计原则：
- **功能与业务优先**：每条用例对应清晰的业务价值或可识别风险
- **少而精**：同一等价类内避免多条仅参数不同的重复用例
- **效率优先**：适合迭代交付、冒烟与核心回归"""


# 聚焦模式（功能与业务）- 核心路径与业务规则优先，控制条数（由积木化块拼接）
TESTCASE_SYSTEM_PROMPT_FOCUSED = _build_testcase_system_prompt(
    head=_with_mode_note(_TESTCASE_DIRECT_HEAD, "focused"),
    json_schema=_TESTCASE_DIRECT_JSON_SCHEMA,
    requirements=_REQ_FOCUSED_DIRECT,
    tail=_TAIL_FOCUSED,
)

# 默认使用全覆盖模式
TESTCASE_SYSTEM_PROMPT = TESTCASE_SYSTEM_PROMPT_COMPREHENSIVE


# ============ 多模态场景的两种模式提示词 ============

# 全覆盖模式（复杂需求）- 多模态版本
_REQ_COMPREHENSIVE_ATTACHMENTS = (
    _TESTCASE_COMMON_RULES
    + """3. 用例预算按功能复杂度和风险动态分配：简单功能可少量代表性覆盖，复杂/高风险功能可增加用例；预算不是硬性上下限
4. 用例覆盖维度（必须全面覆盖）：
   - 正向流程：主流程 + 各种正常分支场景
   - 异常处理：各类错误输入、异常状态、系统异常
   - 边界值：上下边界、临界值、极限值
   - 业务规则：权限控制、状态流转、数据校验、业务约束
   - 兼容性：不同角色、不同状态、不同环境
   - 性能与安全：大数据量、并发、敏感操作
5. 覆盖优先：关键业务规则和高风险路径不能因为预算被截断；低风险或重复场景可以少写
6. 不能为了凑数量生成低价值重复用例；仅数据不同但测试目的相同的场景应参数化或合并描述
7. steps 字段中多个步骤用 \\n 分隔，每步需包含明确的操作对象和操作动作
8. 只返回 JSON，不要有 ```json 标记或其他文字"""
)


TESTCASE_SYSTEM_PROMPT_WITH_ATTACHMENTS_COMPREHENSIVE = _build_testcase_system_prompt(
    head=_with_mode_note(_TESTCASE_ATTACHMENTS_HEAD, "comprehensive"),
    json_schema=_TESTCASE_ATTACHMENTS_JSON_SCHEMA,
    requirements=_REQ_COMPREHENSIVE_ATTACHMENTS,
    tail=_TAIL_COMPREHENSIVE,
)

# 聚焦模式（功能与业务）- 多模态版本
_REQ_FOCUSED_ATTACHMENTS = (
    _TESTCASE_COMMON_RULES
    + """3. 用例预算按业务价值和风险动态分配：以**核心主流程、核心业务规则、主要异常与关键边界**为主，不追求等价类穷尽与组合枚举
4. 用例覆盖维度（聚焦覆盖）：
   - 正向流程：主流程与对业务有关键影响的分支
   - 异常处理：最高频、对业务影响最大的错误场景
   - 边界值：对业务结果有关键影响的边界点
   - 业务规则：权限、状态流转、数据校验等核心逻辑
5. 不要求单独展开：多环境兼容性枚举、性能/安全/并发专项测试，**除非需求明确写出**
6. 覆盖优先：核心规则必须覆盖；低价值变体可以省略，不能为了凑数量生成低价值重复用例
7. steps 字段中多个步骤用 \\n 分隔，每步需包含明确的操作对象和操作动作
8. 只返回 JSON，不要有 ```json 标记或其他文字"""
)


TESTCASE_SYSTEM_PROMPT_WITH_ATTACHMENTS_FOCUSED = _build_testcase_system_prompt(
    head=_with_mode_note(_TESTCASE_ATTACHMENTS_HEAD, "focused"),
    json_schema=_TESTCASE_ATTACHMENTS_JSON_SCHEMA,
    requirements=_REQ_FOCUSED_ATTACHMENTS,
    tail=_TAIL_FOCUSED,
)

# 默认使用全覆盖模式
TESTCASE_SYSTEM_PROMPT_WITH_ATTACHMENTS = TESTCASE_SYSTEM_PROMPT_WITH_ATTACHMENTS_COMPREHENSIVE


# ============ 模块级重新生成场景 ============
MODULE_REGENERATE_SYSTEM_PROMPT = """你是一个资深专业的测试工程师，擅长编写高质量的测试用例。

现在需要你**重新生成指定模块**的测试用例。用户会提供：
1. 完整的需求文档（文字和/或图片），你需要通读全部内容来理解业务全貌
2. 该模块的补充需求说明（可选）—— 比原始文档更细节的业务规则、功能描述等，作为需求信息的补充
3. 该模块当前已有的测试用例（JSON），供你参考
4. 用户对该模块用例的调整意见（可选）—— 对已有用例质量、覆盖率、粒度等方面的改进要求

你的任务：
- 综合需求文档 + 补充需求 + 调整意见，重新生成该模块的全部用例
- 补充需求是对原始需求文档的信息扩展，要基于这些新信息生成更完整的用例
- 调整意见是对用例质量的改进指令，必须落实到用例中
- 已有用例仅作参考，你可以保留合理的、修改不合理的、补充缺失的
- 不限制用例数量，以质量和覆盖率为目标
- 只需输出该模块的用例，不要输出其他模块

请严格按照以下 JSON 格式返回，不要包含任何其他文字，只返回纯 JSON：

{
    "name": "模块名称（必须与指定的模块名完全一致）",
    "functions": [
        {
            "name": "功能点名称",
            "cases": [
                {
                    "name": "用例名称",
                    "priority": "P0",
                    "precondition": "前置条件",
                    "steps": "1. 步骤一\\n2. 步骤二",
                    "expected": "预期结果"
                }
            ]
        }
    ]
}

要求：
1. priority 只能是 P0/P1/P2/P3
2. P0 是最高优先级（核心功能），P3 是最低（边界/异常）
3. 每个功能点生成 5-20 个用例（简单功能 5-8 条，复杂功能 10-20 条），确保覆盖全面且每条用例有独立测试价值
4. 用例覆盖维度（必须全面覆盖）：
   - 正向流程：主流程 + 各种正常分支场景
   - 异常处理：各类错误输入、异常状态、系统异常
   - 边界值：上下边界、临界值、极限值
   - 业务规则：权限控制、状态流转、数据校验、业务约束
   - 兼容性：不同角色、不同状态、不同环境
   - 性能与安全：大数据量、并发、敏感操作
5. steps 字段中多个步骤用 \\n 分隔，每步需包含明确的操作对象和操作动作
6. name 字段必须与用户指定的模块名完全一致，不得修改
7. 只返回 JSON，不要有 ```json 标记或其他文字

用例设计方法指南：
- **等价类划分**：识别所有有效和无效等价类，每个等价类至少 1 条用例
- **边界值分析**：必须测试所有边界点（最小值、最小值-1、最大值、最大值+1）
- **场景法**：覆盖主流程 + 所有重要分支路径 + 异常路径
- **状态转换**：覆盖所有合法状态转换 + 非法状态转换
- **组合测试**：使用正交表或成对组合法确保关键组合都被覆盖
- **异常场景**：包含网络异常、超时、权限不足、数据不存在、并发冲突等
"""


# ============ 功能点级重新生成场景 ============
FUNCTION_REGENERATE_SYSTEM_PROMPT = """你是一个资深专业的测试工程师，擅长编写高质量的测试用例。

现在需要你**重新生成指定功能点**的测试用例。用户会提供：
1. 完整的需求文档（可选），用于理解业务背景
2. 该功能点当前已有的用例（JSON），供你参考
3. 该功能点的补充需求说明（可选）
4. 用户对该功能点用例的调整意见（可选）

你的任务：
- 综合补充需求 + 调整意见，重新生成该功能点的全部用例
- 只输出这一个功能点的 JSON，不要输出其他功能点或模块
- 已有用例仅作参考，你可以保留合理的、修改不合理的、补充缺失的
- 不限制用例数量，以质量和覆盖率为目标

请严格按照以下 JSON 格式返回，不要包含任何其他文字，只返回纯 JSON：

{
    "name": "功能点名称（必须与指定的功能点名完全一致）",
    "cases": [
        {
            "name": "用例名称",
            "priority": "P0",
            "precondition": "前置条件",
            "steps": "1. 步骤一\\n2. 步骤二",
            "expected": "预期结果"
        }
    ]
}

要求：
1. priority 只能是 P0/P1/P2/P3
2. 每个功能点生成 5-20 条用例，确保覆盖全面且每条用例有独立测试价值
3. steps 字段中多个步骤用 \\n 分隔
4. name 字段必须与用户指定的功能点名完全一致
5. 只返回 JSON，不要有 ```json 标记或其他文字
"""


def get_function_regenerate_prompt(
    module_name: str,
    function_name: str,
    existing_function_json: dict,
    function_requirement: str = '',
    adjustment: str = '',
    requirement: str = ''
) -> list:
    """
    构建功能点级重新生成的消息列表（纯文本）。

    Args:
        module_name: 所属模块名称（上下文）
        function_name: 要重新生成的功能点名称
        existing_function_json: 该功能点当前已有的 JSON（含 name, cases）
        function_requirement: 该功能点的补充需求说明（可选）
        adjustment: 用户的调整意见（可选）
        requirement: 原始需求描述
    """
    import json
    user_parts = []
    user_parts.append(f"请重新生成【{module_name}】模块下【{function_name}】功能点的测试用例。\n")
    if requirement:
        user_parts.append(f"【完整需求文档】\n{requirement}\n")
    if function_requirement:
        user_parts.append(f"【该功能点的补充需求说明】\n{function_requirement}\n")
    user_parts.append(f"【该功能点当前已有的用例（仅供参考）】\n{json.dumps(existing_function_json, ensure_ascii=False, indent=2)}\n")
    if adjustment:
        user_parts.append(f"【调整意见（必须落实）】\n{adjustment}")
    return [
        {"role": "system", "content": FUNCTION_REGENERATE_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_parts)}
    ]


def get_module_regenerate_prompt(
    module_name: str,
    existing_module_json: dict,
    module_requirement: str = '',
    adjustment: str = '',
    requirement: str = ''
) -> list:
    """
    构建模块级重新生成的消息列表（纯文本场景）

    Args:
        module_name: 要重新生成的模块名称
        existing_module_json: 该模块当前已有的用例 JSON
        module_requirement: 该模块的补充需求说明（可选）
        adjustment: 用户的调整意见（可选）
        requirement: 原始需求描述文字
    """
    import json

    user_parts = []
    user_parts.append(f"请重新生成【{module_name}】模块的测试用例。\n")

    if requirement:
        user_parts.append(f"【完整需求文档】\n{requirement}\n")

    if module_requirement:
        user_parts.append(f"【该模块的补充需求说明】\n{module_requirement}\n")

    user_parts.append(f"【该模块当前已有的用例（仅供参考）】\n{json.dumps(existing_module_json, ensure_ascii=False, indent=2)}\n")

    if adjustment:
        user_parts.append(f"【调整意见（必须落实）】\n{adjustment}")

    return [
        {"role": "system", "content": MODULE_REGENERATE_SYSTEM_PROMPT},
        {"role": "user", "content": '\n'.join(user_parts)}
    ]


def get_module_regenerate_prompt_multimodal(
    module_name: str,
    existing_module_json: dict,
    extracted_texts: list,
    images: list,
    module_requirement: str = '',
    adjustment: str = '',
    requirement: str = ''
) -> list:
    """
    构建模块级重新生成的多模态消息列表（文字 + 图片）

    Args:
        module_name: 要重新生成的模块名称
        existing_module_json: 该模块当前已有的用例 JSON
        extracted_texts: [{"source": "文件名", "content": "提取的文字"}]
        images: [{"source": "文件名", "data": "base64", "mime": "image/jpeg"}]
        module_requirement: 该模块的补充需求说明（可选）
        adjustment: 用户的调整意见（可选）
        requirement: 用户手动输入的需求描述
    """
    import json

    content_parts = []

    # 1. 引导语
    content_parts.append({
        "type": "text",
        "text": f"请重新生成【{module_name}】模块的测试用例。你需要通读下面的完整需求文档来理解业务全貌，但只需要输出该模块的用例。\n"
    })

    # 2. 用户手动输入的需求描述
    if requirement:
        content_parts.append({
            "type": "text",
            "text": f"【用户需求描述】\n{requirement}"
        })

    # 3. 文档提取的文字
    for text_item in extracted_texts:
        content_parts.append({
            "type": "text",
            "text": f"\n【附件: {text_item['source']}】\n{text_item['content']}"
        })

    # 4. 图片
    if images:
        content_parts.append({
            "type": "text",
            "text": f"\n以下是需求文档中的 UI 设计图/原型图（共 {len(images)} 张），请仔细分析图片内容："
        })
        for img in images:
            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{img['mime']};base64,{img['data']}"
                }
            })

    # 5. 补充需求（紧跟在需求文档后面，属于"信息输入"）
    if module_requirement:
        content_parts.append({
            "type": "text",
            "text": f"\n【该模块的补充需求说明】\n{module_requirement}"
        })

    # 6. 该模块已有用例
    content_parts.append({
        "type": "text",
        "text": f"\n【该模块当前已有的用例（仅供参考）】\n{json.dumps(existing_module_json, ensure_ascii=False, indent=2)}"
    })

    # 7. 调整意见（放在最后，属于"行为指令"）
    if adjustment:
        content_parts.append({
            "type": "text",
            "text": f"\n【调整意见（必须落实）】\n{adjustment}"
        })

    return [
        {"role": "system", "content": MODULE_REGENERATE_SYSTEM_PROMPT},
        {"role": "user", "content": content_parts}
    ]


# ============ 用例评审场景 ============
# ============ 分维度评审 ============

# 通用的 JSON 输出格式（所有维度共用）
_REVIEW_JSON_FORMAT = """
请严格按照以下 JSON 格式返回，不要包含任何其他文字，只返回纯 JSON：

{
    "items": [
        {
            "id": 1,
            "type": "维度类型",
            "severity": "high|medium|low",
            "title": "问题标题（简短）",
            "description": "问题详细描述",
            "suggestion": "具体的、可操作的修改建议",
            "affected_modules": ["模块A", "模块B"]
        }
    ]
}

要求：
1. 每个问题必须有具体的、可操作的修改建议
2. severity 评判标准：high=影响核心功能/明显问题，medium=中等影响，low=风格等小问题
3. 如果此维度没有发现问题，items 返回空数组
4. 只返回 JSON，不要有 ```json 标记或其他文字
"""

# 评审维度定义（当前保留 4 个高价值维度：重复/冗余/缺失/归属）
REVIEW_DIMENSIONS = [
    {
        "key": "duplicate",
        "label": "重复用例",
        "prompt": """你是一个资深测试专家。你的任务是检查测试用例中的**重复问题**。

请逐一对比每两个模块之间的用例，找出验证相同或高度相似业务逻辑的用例。

判断标准：
- 两条用例的测试目的相同（即使步骤描述、用例名称不同）
- 例如"登录模块"的"密码错误锁定"和"账户安全模块"的"连续输错密码锁定"就是重复
- 同一模块内不同功能点之间也可能重复

请给出具体建议：保留哪条、删除哪条（保留描述更完整的那条）。

每条 item 的 type 固定为 "duplicate"。
""" + _REVIEW_JSON_FORMAT,
    },
    {
        "key": "redundant",
        "label": "用例冗余",
        "prompt": """你是一个资深测试专家。你的任务是检查测试用例中的**等价类枚举冗余**问题。

判断标准：
- 同一功能点下，多条用例验证的是同一个等价类的不同取值（如"邮箱缺少@""邮箱缺少域名""邮箱含特殊字符"都属于"无效邮箱格式"这一个等价类）
- 正确做法是每个等价类只保留 1 条代表性用例
- 边界值只测边界点（刚好、±1），不要在中间罗列多个值

请逐个功能点检查其下的用例，找出可以合并的冗余用例组。建议中要说明：哪几条应该合并为 1 条、保留哪条作为代表。

每条 item 的 type 固定为 "redundant"。
""" + _REVIEW_JSON_FORMAT,
    },
    {
        "key": "structure",
        "label": "模块归属",
        "prompt": """你是一个资深测试专家。你的任务是检查测试用例的**模块归属合理性**。

判断标准：
- 某个功能点或整个子模块放在了不合适的父模块下
- 从业务逻辑角度看，它应该归属到另一个已有模块
- 也检查是否有模块拆分过细（应合并）或过粗（应拆分）

请给出具体建议：应该把什么移到哪里。

每条 item 的 type 固定为 "structure"。
""" + _REVIEW_JSON_FORMAT,
    },
    {
        "key": "missing",
        "label": "缺失场景",
        "prompt": """你是一个资深测试专家。你的任务是结合需求文档检查测试用例的**场景缺失**。

判断标准：
- 需求文档中描述了但用例未覆盖的业务规则
- 缺少跨模块的端到端流程用例（如完整的"注册→登录→使用→退出"流程）
- 缺少重要的集成/交互场景（模块 A 的输出是模块 B 的输入）
- 缺少重要的异常/边界场景

请给出具体建议：应该在哪个模块的哪个功能点下新增什么用例。

每条 item 的 type 固定为 "missing"。
""" + _REVIEW_JSON_FORMAT,
    },
]


def get_dimension_review_prompt(dimension_key: str, result_json: dict, requirement: str = '') -> list:
    """
    构建单维度评审的纯文本消息列表
    """
    import json
    from apps.ai_testcase.services.review_compact import compact_result_json

    dim = None
    for d in REVIEW_DIMENSIONS:
        if d['key'] == dimension_key:
            dim = d
            break
    if not dim:
        raise ValueError(f"未知的评审维度: {dimension_key}")

    user_parts = []
    if requirement:
        user_parts.append(f"【需求文档】\n{requirement}\n")
    compact = compact_result_json(result_json).to_dict()
    user_parts.append(f"【用例摘要（用于快速评审）】\n{json.dumps(compact.get('summary', {}), ensure_ascii=False, indent=2)}\n")
    user_parts.append(f"【用例样例（每功能点最多 3 条）】\n{json.dumps(compact.get('sample', {}), ensure_ascii=False, indent=2)}")

    return [
        {"role": "system", "content": dim['prompt']},
        {"role": "user", "content": '\n'.join(user_parts)}
    ]


def get_dimension_review_prompt_multimodal(
    dimension_key: str,
    result_json: dict,
    extracted_texts: list,
    images: list,
    requirement: str = ''
) -> list:
    """
    构建单维度评审的多模态消息列表
    """
    import json
    from apps.ai_testcase.services.review_compact import compact_result_json

    dim = None
    for d in REVIEW_DIMENSIONS:
        if d['key'] == dimension_key:
            dim = d
            break
    if not dim:
        raise ValueError(f"未知的评审维度: {dimension_key}")

    content_parts = []

    if requirement:
        content_parts.append({
            "type": "text",
            "text": f"【需求描述】\n{requirement}"
        })

    for text_item in extracted_texts:
        content_parts.append({
            "type": "text",
            "text": f"\n【附件: {text_item['source']}】\n{text_item['content']}"
        })

    if images:
        content_parts.append({
            "type": "text",
            "text": f"\n以下是需求文档中的图片（共 {len(images)} 张）："
        })
        for img in images:
            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{img['mime']};base64,{img['data']}"
                }
            })

    compact = compact_result_json(result_json).to_dict()
    content_parts.append({
        "type": "text",
        "text": f"\n【用例摘要（用于快速评审）】\n{json.dumps(compact.get('summary', {}), ensure_ascii=False, indent=2)}"
    })
    content_parts.append({
        "type": "text",
        "text": f"\n【用例样例（每功能点最多 3 条）】\n{json.dumps(compact.get('sample', {}), ensure_ascii=False, indent=2)}"
    })

    return [
        {"role": "system", "content": dim['prompt']},
        {"role": "user", "content": content_parts}
    ]


APPLY_REVIEW_SYSTEM_PROMPT = """你是一个资深测试专家，需要根据用户选定的评审意见，输出具体的变更指令。

用户会提供：
1. 当前完整的测试用例 JSON（包含所有模块）
2. 用户选定要采纳的评审意见列表

你只需要输出变更操作列表（增量修改），不要输出完整的用例 JSON。

请严格按照以下 JSON 格式返回，只返回纯 JSON，不要包含任何其他文字：

{
    "changes": [
        {
            "action": "delete_case",
            "module": "模块名",
            "function": "功能点名",
            "case_name": "要删除的用例名"
        },
        {
            "action": "modify_case",
            "module": "模块名",
            "function": "功能点名",
            "case_name": "原用例名",
            "updates": {
                "name": "新用例名（不改则不填）",
                "priority": "P0（不改则不填）",
                "steps": "新步骤（不改则不填）",
                "expected": "新预期（不改则不填）",
                "precondition": "新前置条件（不改则不填）"
            }
        },
        {
            "action": "add_case",
            "module": "模块名",
            "function": "功能点名（已有的功能点）",
            "case": {
                "name": "新用例名",
                "steps": "步骤",
                "expected": "预期结果",
                "priority": "P0",
                "precondition": "前置条件"
            }
        },
        {
            "action": "add_function",
            "module": "模块名",
            "function": {
                "name": "新功能点名",
                "cases": [
                    {"name": "...", "steps": "...", "expected": "...", "priority": "P1", "precondition": "..."}
                ]
            }
        },
        {
            "action": "move_function",
            "from_module": "原模块名",
            "function_name": "要移动的功能点名",
            "to_module": "目标模块名"
        },
        {
            "action": "delete_function",
            "module": "模块名",
            "function_name": "要删除的功能点名（整个功能点及其所有用例）"
        },
        {
            "action": "delete_module",
            "module": "要删除的模块名（整个模块及其所有功能点和用例）"
        }
    ]
}

要求：
1. 只输出需要变更的操作，不要输出未涉及的内容
2. action 允许七种：delete_case、modify_case、add_case、add_function、move_function、delete_function、delete_module
3. modify_case 的 updates 中只包含需要修改的字段，不改的字段不要写
4. module 和 function 名称必须与用例 JSON 中完全一致（精确匹配）
5. 只返回 JSON，不要有 ```json 标记或其他文字
"""

def get_apply_review_prompt(result_json: dict, selected_items: list) -> list:
    """
    构建采纳评审意见的消息列表
    优化：只传入评审意见涉及的模块数据，而非全部用例，大幅减少输入 token
    """
    import json

    # 提取评审意见涉及的模块名称
    affected_modules = set()
    for item in selected_items:
        for mod_name in item.get('affected_modules', []):
            affected_modules.add(mod_name)

    # 如果评审意见没标注 affected_modules，退回传全部
    modules = result_json.get('modules', [])
    if affected_modules:
        relevant_modules = [m for m in modules if m['name'] in affected_modules]
    else:
        relevant_modules = modules

    partial_json = {"modules": relevant_modules}

    user_parts = []
    user_parts.append("请根据以下选定的评审意见，输出变更指令。\n")
    user_parts.append(f"【涉及的模块用例（共 {len(relevant_modules)} 个模块）】\n{json.dumps(partial_json, ensure_ascii=False, indent=2)}\n")
    user_parts.append(f"【选定要采纳的评审意见】\n{json.dumps(selected_items, ensure_ascii=False, indent=2)}")

    return [
        {"role": "system", "content": APPLY_REVIEW_SYSTEM_PROMPT},
        {"role": "user", "content": '\n'.join(user_parts)}
    ]


def get_testcase_prompt(requirement: str, mode: str = 'comprehensive') -> list:
    """
    构建用例生成的消息列表（纯文本场景）
    
    Args:
        requirement: 需求描述
        mode: 生成模式 ('comprehensive', 'focused')
    """
    mode_prompts = {
        'comprehensive': TESTCASE_SYSTEM_PROMPT_COMPREHENSIVE,
        'focused': TESTCASE_SYSTEM_PROMPT_FOCUSED,
    }

    system_prompt = mode_prompts.get(mode, TESTCASE_SYSTEM_PROMPT_COMPREHENSIVE)
    
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"请基于以下需求生成测试用例。要求：①严格围绕需求描述的功能范围；②挖掘需求中隐含但合理的业务规则或业务场景及影响范围；③不要凭空臆造需求未涉及的功能模块。\n\n{requirement}"}
    ]


def get_testcase_prompt_multimodal(
    requirement: str,
    extracted_texts: list,
    images: list,
    mode: str = 'comprehensive'
) -> list:
    """
    构建多模态用例生成的消息列表（文字 + 图片）

    Args:
        requirement: 用户手动输入的需求描述
        extracted_texts: [{"source": "文件名", "content": "提取的文字"}]
        images: [{"source": "文件名", "data": "base64", "mime": "image/jpeg"}]
        mode: 生成模式 ('comprehensive', 'focused')

    Returns:
        OpenAI 格式的 messages 列表
    """
    mode_prompts = {
        'comprehensive': TESTCASE_SYSTEM_PROMPT_WITH_ATTACHMENTS_COMPREHENSIVE,
        'focused': TESTCASE_SYSTEM_PROMPT_WITH_ATTACHMENTS_FOCUSED,
    }

    system_prompt = mode_prompts.get(mode, TESTCASE_SYSTEM_PROMPT_WITH_ATTACHMENTS_COMPREHENSIVE)
    
    # 构建 user content 数组（多模态格式）
    content_parts = []

    # 1. 引导语
    intro = "请基于以下需求信息生成测试用例。要求：①严格围绕需求描述的功能范围；②挖掘需求中隐含但合理的业务规则或业务场景及影响范围；③不要凭空臆造需求未涉及的功能模块。\n"
    content_parts.append({"type": "text", "text": intro})

    # 2. 用户手动输入的文字
    if requirement:
        content_parts.append({
            "type": "text",
            "text": f"【用户需求描述】\n{requirement}"
        })

    # 3. 文档提取的文字
    for text_item in extracted_texts:
        content_parts.append({
            "type": "text",
            "text": f"\n【附件: {text_item['source']}】\n{text_item['content']}"
        })

    # 4. 图片
    if images:
        content_parts.append({
            "type": "text",
            "text": f"\n以下是上传的 UI 设计图/原型图/文档中的嵌入图片（共 {len(images)} 张），请仔细分析图片内容："
        })
        for img in images:
            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{img['mime']};base64,{img['data']}"
                }
            })

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content_parts}
    ]
