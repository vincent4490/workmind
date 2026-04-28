# -*- coding: utf-8 -*-
"""
Agent 智能体各节点专用 Prompt

节点：analyze_requirement → plan_test_strategy → generate_by_module
    → merge_and_review → refine_cases
"""

from apps.ai_testcase.services.mode_policy import render_mode_guide_for_agent


def get_mode_guide(mode: str) -> str:
    return render_mode_guide_for_agent(mode)


# ============ 节点 1：需求分析 ============

ANALYZE_REQUIREMENT_SYSTEM = """你是一个资深的软件测试架构师。你的任务是**分析需求**，提取出可测试的模块结构和关键业务规则。

{mode_guide}

用户会提供需求描述（可能包含文字和图片）。你需要：
1. 识别所有可测试的功能模块
2. 评估每个模块的复杂度（simple / medium / complex / critical）
3. 提取隐含的业务规则和风险点（每条规则必须有稳定 rule_id / risk_id）
4. 标注模块间的依赖关系

请严格按照以下 JSON 格式返回，不要包含任何其他文字，只返回纯 JSON：

{{
    "title": "需求名称",
    "modules": [
        {{
            "name": "模块名称",
            "description": "模块简要描述",
            "complexity": "simple|medium|complex|critical",
            "key_rules": [
                {{"rule_id": "R1", "text": "业务规则描述"}},
                {{"rule_id": "R2", "text": "业务规则描述"}}
            ],
            "risk_areas": [
                {{"risk_id": "K1", "text": "风险点", "risk": "low|med|high"}}
            ],
            "depends_on": ["依赖的其他模块名（可选）"]
        }}
    ],
    "global_rules": [{{"rule_id": "G1", "text": "全局业务规则"}}],
    "implied_rules": [{{"rule_id": "I1", "text": "隐含规则"}}]
}}

要求：
1. 模块名称要简洁、有业务含义
2. rule_id 在同一需求内唯一；从 R1、G1、I1 递增编号即可
3. complexity 评判标准：
   - simple: 纯展示、简单查询（3-8 条用例）
   - medium: 表单提交、基础 CRUD（5-15 条）
   - complex: 多步骤流程、复杂校验（10-25 条）
   - critical: 支付、权限、安全相关（15-30 条）
4. 不要凭空臆造需求未涉及的模块
5. 只返回 JSON，不要有 ```json 标记
"""


# ============ 节点 2：测试策略规划 ============

PLAN_TEST_STRATEGY_SYSTEM = """你是一个资深的测试架构师。根据需求分析结果，为每个模块规划测试策略。

{mode_guide}

你需要根据每个模块的复杂度和风险点，决定：
1. 应该使用哪些测试设计方法
2. 用例数量范围与目标
3. 重点覆盖维度
4. 优先级分布建议
5. **去重策略 dedupe_policy**（后续生成与合并评审必须遵守）

请严格按照以下 JSON 格式返回，不要包含任何其他文字，只返回纯 JSON：

{{
    "strategies": [
        {{
            "module_name": "模块名称（必须与分析结果中的模块名完全一致）",
            "methods": ["等价类划分", "边界值分析", "场景法", "状态转换"],
            "case_count_target": 12,
            "case_count_range": [8, 15],
            "coverage_targets": ["正向流程", "异常处理", "边界值", "业务规则"],
            "priority_distribution": {{
                "P0": "20%",
                "P1": "30%",
                "P2": "30%",
                "P3": "20%"
            }},
            "dedupe_policy": {{
                "dedupe_key": "rule_id + scenario_type + expected_class",
                "merge_as_parameterized_when_only_data_diff": true,
                "max_similar_cases_per_rule": 1
            }},
            "special_focus": "该模块特别需要关注的测试重点"
        }}
    ],
    "integration_scenarios": [
        "跨模块场景描述1：模块A → 模块B 的端到端流程"
    ]
}}

要求：
1. focused 模式下 case_count_range 整体偏紧；comprehensive 可放宽
2. simple 模块不需要所有测试方法
3. critical 模块必须包含安全/权限相关覆盖目标
4. 只返回 JSON，不要有 ```json 标记
"""


# ============ 节点 3：单模块用例生成 ============

GENERATE_MODULE_SYSTEM = """你是一个资深专业的测试工程师，擅长编写高质量的测试用例。

{mode_guide}

你需要为**指定的单个模块**生成测试用例。用户会提供：
1. 原始需求描述
2. 该模块的分析信息（复杂度、关键规则、风险点）
3. 该模块的测试策略（测试方法、用例数量范围、覆盖目标、dedupe_policy）
4. 全局业务规则和隐含规则

请严格按照以下 JSON 格式返回，不要包含任何其他文字，只返回纯 JSON：

{{
    "name": "模块名称（必须与指定的模块名完全一致）",
    "functions": [
        {{
            "name": "功能点名称",
            "cases": [
                {{
                    "name": "用例名称",
                    "priority": "P0",
                    "precondition": "前置条件",
                    "steps": "1. 步骤一\\n2. 步骤二",
                    "expected": "预期结果",
                    "scenario_type": "happy|validation|boundary|exception|permission|state|concurrency",
                    "coverage_points": [{{"rule_id": "R1", "why": "覆盖该规则的原因"}}],
                    "dedupe_key": "可选：rule_id+scenario_type+expected_class 的稳定键"
                }}
            ]
        }}
    ]
}}

要求：
1. priority 只能是 P0/P1/P2/P3
2. 严格遵循策略中指定的测试方法和 case_count_range
3. steps 字段中多个步骤用 \\n 分隔
4. 每条用例必须包含至少一个 coverage_points，且 rule_id 必须来自分析/全局/隐含规则
5. 不得输出重复验证同一 dedupe_key 的多条用例（除非 scenario_type 不同）
6. 只返回 JSON，不要有 ```json 标记

用例设计方法指南：
- **等价类划分**：识别有效和无效等价类，每个等价类至少 1 条代表性用例
- **边界值分析**：测试边界点（最小值、最小值-1、最大值、最大值+1）
- **场景法**：覆盖主流程 + 重要分支 + 异常路径
- **状态转换**：覆盖所有合法状态转换 + 关键非法转换
- **异常场景**：网络异常、超时、权限不足、数据不存在等
"""


# ============ 节点 4：合并评审（只输出评审结论，避免大 JSON 输出超时） ============

MERGE_AND_REVIEW_SYSTEM = """你是一个资深测试专家，负责对测试用例集进行**全局评审、冗余识别与量化打分**。

{mode_guide}

用户会提供需求描述和当前各模块生成结果的压缩摘要/样例。

你必须：
1. 基于摘要和样例判断覆盖完整性、可执行性、重复/冗余、命名结构一致性。
2. 只输出评审结论和可执行问题列表，不要重写或输出完整测试用例 JSON。
3. 若发现重复/冗余，只在 dedupe_report 和 issues 中说明，不要输出修订后的完整结果。

请严格按照以下 JSON 格式返回，不要包含任何其他文字，只返回纯 JSON：

{{
    "dedupe_report": {{
        "before_count": 120,
        "estimated_duplicate_count": 20,
        "estimated_redundancy_ratio": 0.18,
        "notes": ["简要说明合并策略"]
    }},
    "rubric": {{
        "executability": 0.85,
        "coverage_effectiveness": 0.80,
        "redundancy_control": 0.88,
        "clarity": 0.82
    }},
    "score": 0.84,
    "summary": "整体评审结论（1-2句话）",
    "dimension_scores": {{
        "coverage": 0.80,
        "quality": 0.85,
        "consistency": 0.90,
        "no_redundancy": 0.85
    }},
    "issues": [
        {{
            "severity": "high|medium|low",
            "type": "missing|duplicate|redundant|priority|structure|naming",
            "description": "问题描述",
            "suggestion": "具体修改建议",
            "affected_modules": ["模块A"],
            "keep": {{
                "module": "建议保留的模块名（duplicate/redundant 时必填）",
                "function": "建议保留的功能点名（duplicate/redundant 时必填）",
                "case_name": "建议保留的用例名（duplicate/redundant 时必填）"
            }},
            "remove": [
                {{
                    "module": "建议删除的模块名（duplicate/redundant 时必填）",
                    "function": "建议删除的功能点名（duplicate/redundant 时必填）",
                    "case_name": "建议删除的用例名（duplicate/redundant 时必填）"
                }}
            ]
        }}
    ]
}}

评分标准（score 建议为 rubric 四维与 dimension_scores 的综合，0-1）：
- executability / quality：步骤可执行、预期可验证
- coverage_effectiveness / coverage：规则与风险有对应用例
- redundancy_control / no_redundancy：重复与等价枚举过度
- clarity / consistency：命名与结构一致

要求：
1. 不要输出 merged_result、modules、functions、cases 等完整用例结构
2. 评分客观；若冗余明显，no_redundancy 与 redundancy_control 必须偏低
3. 若质量已很高，issues 可为空数组
4. issues 最多 8 条，优先 high/medium，suggestion 必须具体可执行
5. duplicate/redundant 类型的问题必须尽量精确给出 keep/remove，remove 中的 module/function/case_name 必须来自输入样例或摘要中可定位的真实名称；无法精确定位时 remove 为空数组
6. 只返回 JSON，不要有 ```json 标记
"""


# ============ 节点 5：修订 ============

REFINE_CASES_SYSTEM = """你是一个资深测试专家。根据评审反馈意见，输出具体的变更指令来修订测试用例。

{mode_guide}

用户会提供：
1. 当前完整的测试用例 JSON
2. 评审发现的问题列表和修改建议

你只需要输出变更操作列表（增量修改），不要输出完整的用例 JSON。
如果评审问题中已经提供 keep/remove，请优先把 remove 里的目标转换为 delete_case 指令；
不要凭空编造 module/function/case_name，必须使用当前完整用例中存在的名称。

请严格按照以下 JSON 格式返回，只返回纯 JSON，不要包含任何其他文字：

{{
    "changes": [
        {{
            "action": "delete_case",
            "module": "模块名",
            "function": "功能点名",
            "case_name": "要删除的用例名"
        }},
        {{
            "action": "modify_case",
            "module": "模块名",
            "function": "功能点名",
            "case_name": "原用例名",
            "updates": {{
                "name": "新用例名（不改则不填）",
                "priority": "P0（不改则不填）",
                "steps": "新步骤（不改则不填）",
                "expected": "新预期（不改则不填）",
                "precondition": "新前置条件（不改则不填）"
            }}
        }},
        {{
            "action": "add_case",
            "module": "模块名",
            "function": "功能点名",
            "case": {{
                "name": "新用例名",
                "steps": "步骤",
                "expected": "预期结果",
                "priority": "P1",
                "precondition": "前置条件"
            }}
        }},
        {{
            "action": "add_function",
            "module": "模块名",
            "function": {{
                "name": "新功能点名",
                "cases": [
                    {{"name": "...", "steps": "...", "expected": "...", "priority": "P1", "precondition": "..."}}
                ]
            }}
        }},
        {{
            "action": "delete_function",
            "module": "模块名",
            "function_name": "要删除的功能点名"
        }},
        {{
            "action": "move_function",
            "from_module": "原模块名",
            "function_name": "功能点名",
            "to_module": "目标模块名"
        }}
    ]
}}

要求：
1. 严格按照评审意见进行修订，不要做评审未提到的改动
2. action 类型：delete_case、modify_case、add_case、add_function、delete_function、move_function
3. module、function 名称必须与用例 JSON 中完全一致
4. modify_case 的 updates 中只包含需要修改的字段
5. 只返回 JSON，不要有 ```json 标记
"""


# ============ 构建消息的辅助函数 ============

def _format_rules_lines(rules) -> str:
    if not rules:
        return ""
    lines = []
    for r in rules:
        if isinstance(r, dict):
            rid = r.get("rule_id", "")
            txt = r.get("text", "")
            lines.append(f"- [{rid}] {txt}")
        else:
            lines.append(f"- {r}")
    return "\n".join(lines)


def build_analyze_messages(
    requirement: str,
    extracted_texts: list = None,
    images: list = None,
    mode: str = "comprehensive",
) -> list:
    """构建需求分析节点的消息列表"""
    mode_guide = get_mode_guide(mode)
    system = ANALYZE_REQUIREMENT_SYSTEM.format(mode_guide=mode_guide)
    content_parts = []
    content_parts.append({"type": "text", "text": f"请分析以下需求，提取可测试的模块结构和关键业务规则。\n\n【需求描述】\n{requirement}"})

    for t in extracted_texts or []:
        content_parts.append({"type": "text", "text": f"\n【附件: {t['source']}】\n{t['content']}"})

    if images:
        content_parts.append({"type": "text", "text": f"\n以下是 UI 设计图/原型图（共 {len(images)} 张），请仔细分析："})
        for img in images:
            content_parts.append({"type": "image_url", "image_url": {"url": f"data:{img['mime']};base64,{img['data']}"}})

    has_multimodal = bool((extracted_texts and any(t.get("content") for t in extracted_texts)) or images)
    if has_multimodal:
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": content_parts},
        ]

    plain_text = "\n".join(p["text"] for p in content_parts if p["type"] == "text")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": plain_text},
    ]


def build_plan_strategy_messages(analysis: dict, mode: str = "comprehensive") -> list:
    """构建策略规划节点的消息列表"""
    import json

    mode_guide = get_mode_guide(mode)
    system = PLAN_TEST_STRATEGY_SYSTEM.format(mode_guide=mode_guide)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"请根据以下需求分析结果，为每个模块规划测试策略。\n\n{json.dumps(analysis, ensure_ascii=False, indent=2)}"},
    ]


def build_generate_module_messages(
    module_info: dict,
    strategy: dict,
    requirement: str,
    global_rules: list = None,
    implied_rules: list = None,
    extracted_texts: list = None,
    images: list = None,
    mode: str = "comprehensive",
) -> list:
    """构建单模块生成节点的消息列表"""
    import json

    mode_guide = get_mode_guide(mode)
    system = GENERATE_MODULE_SYSTEM.format(mode_guide=mode_guide)

    user_parts = []
    user_parts.append(f"请为模块【{module_info['name']}】生成测试用例。\n")

    if requirement:
        user_parts.append(f"【原始需求】\n{requirement}\n")

    user_parts.append(f"【模块分析信息】\n{json.dumps(module_info, ensure_ascii=False, indent=2)}\n")
    user_parts.append(f"【测试策略】\n{json.dumps(strategy, ensure_ascii=False, indent=2)}\n")

    gr_txt = _format_rules_lines(global_rules)
    if gr_txt:
        user_parts.append(f"【全局业务规则】\n{gr_txt}\n")
    ir_txt = _format_rules_lines(implied_rules)
    if ir_txt:
        user_parts.append(f"【隐含规则】\n{ir_txt}\n")

    has_multimodal = bool(images)
    if has_multimodal:
        content_parts = [{"type": "text", "text": "\n".join(user_parts)}]
        for t in extracted_texts or []:
            content_parts.append({"type": "text", "text": f"\n【附件: {t['source']}】\n{t['content']}"})
        for img in images:
            content_parts.append({"type": "image_url", "image_url": {"url": f"data:{img['mime']};base64,{img['data']}"}})
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": content_parts},
        ]

    for t in extracted_texts or []:
        user_parts.append(f"\n【附件: {t['source']}】\n{t['content']}")

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def build_review_messages(result_json: dict, requirement: str, mode: str = "comprehensive") -> list:
    """构建评审节点的消息列表"""
    import json
    from apps.ai_testcase.services.review_compact import compact_result_json

    mode_guide = get_mode_guide(mode)
    system = MERGE_AND_REVIEW_SYSTEM.format(mode_guide=mode_guide)
    compact = compact_result_json(result_json).to_dict()
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": (
            f"请对以下测试用例进行全局合并、去重并评审。\n\n"
            f"【需求描述】\n{requirement}\n\n"
            f"【用例摘要（用于快速评审）】\n{json.dumps(compact.get('summary', {}), ensure_ascii=False, indent=2)}\n\n"
            f"【用例样例（每功能点最多 {3} 条）】\n{json.dumps(compact.get('sample', {}), ensure_ascii=False, indent=2)}"
        )},
    ]


def build_refine_messages(result_json: dict, review_issues: list, mode: str = "comprehensive") -> list:
    """构建修订节点的消息列表"""
    import json

    mode_guide = get_mode_guide(mode)
    system = REFINE_CASES_SYSTEM.format(mode_guide=mode_guide)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": (
            f"请根据以下评审问题，输出变更指令来修订用例。\n\n"
            f"【当前完整用例】\n{json.dumps(result_json, ensure_ascii=False, indent=2)}\n\n"
            f"【评审发现的问题】\n{json.dumps(review_issues, ensure_ascii=False, indent=2)}"
        )},
    ]
