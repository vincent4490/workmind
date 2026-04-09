# AI 用例「智能体（Agent）」模式：技术框架与业务说明

本文档仅描述 `backend/apps/ai_testcase` 中 **`generation_mode = agent`** 的路径，不涉及 `direct` 直接生成模式。

---

## 1. 定位与业务价值

**Agent 模式**将「从需求到可导出用例集」拆成多步：需求结构化分析 → 按模块测试策略 → 分模块生成 → 全局合并与量化评审 → 未达标则修订或回退重生成，直至分数达标或达到迭代上限。

与单次 Prompt 直接出全文相比，业务侧差异包括：

- **可解释阶段**：前端可通过 SSE/事件表观察 `analyze_requirement`、`plan_test_strategy`、`generate_module:*`、`merge_and_review`、`refine_cases` 等阶段。
- **质量闭环**：内置评审分数、问题列表、自动修订；多轮仍不达标时可**强制回到分模块重生成**（更强思考/模型策略）。
- **条数与去重策略**：通过 **`case_strategy_mode`（focused / comprehensive）** 与 Prompt 中的模式片段对齐。**合并评审的 LLM 调用仍使用用户所选模式**；仅在 `merge_and_review` **返回之后**，若用户为 focused 且满足低分/高重复等条件，会把状态字段 **`effective_mode` 升为 `comprehensive`**，使下一步 **`refine_cases` 的 Prompt** 按全覆盖口径生成修订指令（分模块重生成仍用原始 `mode`，见代码）。

---

## 2. 技术架构总览

| 层次 | 职责 | 主要代码位置 |
|------|------|----------------|
| **工作流编排** | LangGraph `StateGraph`：节点、条件边、状态聚合 | `workflows/testcase_agent.py` |
| **执行与持久化** | 驱动 `graph.astream`、合并「节点开始」事件、写 DB、产出 XMind | `workflows/executor.py` |
| **节点内事件** | 在调用 LLM 前发出「阶段开始」，与图更新合并为统一流 | `workflows/agent_events.py` |
| **Prompt** | 各节点 system/user 模板与多模态消息构建 | `services/agent_prompts.py` |
| **模式口径** | focused/comprehensive 说明块，供各节点注入 | `services/mode_policy.py` |
| **LLM 路由** | 按阶段选模型（生成/评审/分析/规划/修订）、JSON 解析、成本估算 | `services/model_router.py` |
| **结果归一** | 需求分析 JSON 兼容旧格式、补齐 `rule_id` 等 | `services/agent_result_normalize.py` |
| **HTTP** | SSE 长连接实时推送；异步创建记录后跑执行器 | `views.py`（`agent_generate_stream_view`） |
| **后台任务** | Celery 跑同一套 `TestcaseAgentExecutor`，事件落库供轮询/SSE | `tasks.py`（`run_ai_testcase_agent`） |
| **数据模型** | 记录、评审字段、`agent_state` 快照 | `models.py`（`AiTestcaseGeneration`） |

**运行时依赖**：`langgraph` 的 `StateGraph` + `astream(..., stream_mode='updates')`；异步 OpenAI 兼容客户端（Kimi / DeepSeek，由路由决定）。

---

## 3. 工作流图（LangGraph）

### 3.1 节点顺序（逻辑）

1. **`analyze_requirement`**：输入需求 + 附件文本 + 图片，输出结构化需求分析（模块、规则、风险等）。
2. **`plan_test_strategy`**：基于分析结果，为每个模块输出测试策略与 `dedupe_policy`、用例数量区间等。
3. **`generate_by_module`**：按模块循环调用；每轮只生成一个模块的用例 JSON，追加到 `modules_generated`。
4. **`merge_and_review`**：合并各模块为 `merged_result`，并由模型输出合并后结构、**去重报告**、**评分**、**问题列表** 等。
5. **`refine_cases`**（条件进入）：根据 `issues` 产出**增量变更指令**（非全文重写），由视图层函数应用到 JSON 上。
6. **`finalize`**：标记完成；执行器侧做确定性去重兜底、写 `_meta`、生成 XMind、置 `status=success`。

条件边：

- `generate_by_module` → 若还有模块未生成则回到自身，否则 → `merge_and_review`。
- `merge_and_review` → 若分数 ≥ 阈值或迭代次数 ≥ 上限 → `finalize`；否则 → `refine_cases`。
- `refine_cases` → 回到 `merge_and_review`（再次评审）。

**注意**：`route_after_review` 中还存在「第 2 轮及以后仍不达标则清空模块产物、从 `generate_by_module` 重新跑」的质量策略，用于强制「分模块重生成」。

### 3.2 状态 `TestcaseAgentState`（核心字段）

- **输入**：`requirement`、`extracted_texts`、`images`、`mode`（用例策略）、`use_thinking` 等。
- **分析/策略**：`requirement_analysis`、`test_strategy`。
- **分模块生成**：`modules_generated`、`current_module_index`、`module_total`、`generation_errors`。
- **评审循环**：`merged_result`、`review_score`、`review_feedback`、`review_issues`、`iteration_count`。
- **自适应**：`effective_mode`、`mode_switch_reason`、`quality_tier`、`force_strong_generate`（用于第二轮加强生成/思考）。
- **成本**：`total_usage` 与各节点 `node_trace` 中的 `usage` / `cost_usd`。

---

## 4. LLM 调用与多模型路由

### 4.1 统一调用路径 `_run_validated_with_router`

- 使用 `TestcaseModelRouter.select_model(stage)`，`stage` 含：`analyze`、`plan`、`generate`、`review`、`refine`。
- **默认策略**（可通过 Django settings 覆盖）：生成类走 `AI_TESTCASE_MODEL_GENERATE`（默认 `deepseek-chat`）；分析/规划/评审/修订多走 `AI_TESTCASE_MODEL_REVIEW` / `AI_TESTCASE_MODEL_REFINE`（默认 `kimi-k2.5`）。
- 若配置了 DeepSeek 模型但未配置 API Key，**整模型名回退到 Kimi**，避免「客户端与模型不匹配」。
- 调用为 **非流式** `chat.completions.create`，`parse_json` 解析；失败则追加用户消息要求「仅输出 JSON」重试（有限次数）。
- **`use_thinking`**：为 true 时在 `extra_body` 中开启思考预算（与 Kimi 等兼容）；分模块生成在 `force_strong_generate` 时也会打开思考。

### 4.2 超时

- 模块级节点：`TESTCASE_AGENT_MODULE_TIMEOUT`（默认 120s）。
- 评审节点：`TESTCASE_AGENT_REVIEW_TIMEOUT`（默认 180s）。  
超时后评审节点会采用降级策略（如固定分数与文案）并趋向 `finalize`，避免无限挂死。

---

## 5. 业务策略说明

### 5.1 `case_strategy_mode`（与 `generation_mode` 正交）

存储在 `AiTestcaseGeneration.case_strategy_mode`：`focused`（聚焦）或 `comprehensive`（全覆盖）。

`mode_policy.render_mode_guide_for_agent` 生成统一片段，注入各 Agent 节点的 system Prompt，约束：

- 条数与覆盖重心；
- 去重口径（如「同一 rule_id + scenario_type + 预期类别」是否只保留一条代表）。

### 5.2 评审后的「轻量自适应模式」

在 `merge_and_review` 输出后，若用户请求为 **focused**，但分数偏低或去重报告显示重复仍严重，可将 **`effective_mode` 升级为 `comprehensive`**，使后续 **`refine_cases`** 按更广覆盖口径执行，减少漏测与冗余。

### 5.3 质量闭环（迭代与回退）

- **`TESTCASE_AGENT_REVIEW_THRESHOLD`**（默认 0.8）：达标则结束。
- **`TESTCASE_AGENT_MAX_REVISIONS`**（默认 3）：评审轮次上限（与 `iteration_count` 配合）。
- 第一轮低分：提升 `quality_tier`，进入 **refine**（修订阶段可用更强配置）。
- 多轮仍低分：可 **`force_strong_generate`** 并 **清空 `modules_generated` 重新分模块生成**，再进入评审。

### 5.4 合并评审与修订

- **评审**：Prompt 要求输出 `merged_result`、`dedupe_report`、`score`、`issues` 等；用户消息侧对大型结果使用 `review_compact.compact_result_json` 压缩为摘要 + 抽样，控制 token。
- **修订**：模型只输出 `changes` 列表；由 `views._apply_review_changes` 将变更应用到 `merged_result`，再进入下一轮评审。

### 5.5 确定性去重兜底

`finalize` 前对 `merged_result` 调用 `dedupe.dedupe_result_json`（按 `case_strategy_mode`），防止 LLM 合并仍不彻底导致用例爆炸。

---

## 6. 执行器 `TestcaseAgentExecutor` 与事件

### 6.1 事件流合并

- LangGraph `astream` 放入队列；节点内 `emit_node_start` 放入 `('node_start', node_name)`。
- 消费队列：`agent_node_started` 先于该步的图更新到达，实现「先显示阶段开始，再显示阶段完成」。

### 6.2 对外事件类型（概念）

- `agent_start`：携带 `nodes` 顺序列表（含 `generate_by_module`、`refine_cases`、`finalize` 等展示用名）。
- `agent_node_started` / `agent_node_done`：进度与结构化 `data`（分析摘要、策略、当前模块进度、合并统计等）。
- `agent_review`：分数、反馈、issues、迭代信息、模型与用量等。
- `agent_refining`：修订轮次与变更条数提示。
- `agent_done`：最终 `result_json`、统计、token 用量等。
- `error` / `cancelled`：失败或用户取消。

### 6.3 持久化

- 节点级更新：`result_json`、`review_score`、`review_feedback`、`iteration_count`、token 字段、`agent_state`（含 `node_trace`、`dedupe_report`、`review_rubric` 等）。
- 结束：`XMindBuilder` 写文件路径到 `xmind_file`，`status='success'`。

---

## 7. API 与异步执行

| 入口 | 说明 |
|------|------|
| **`POST .../agent-generate-stream/`** | **SSE**：创建 `AiTestcaseGeneration`（`generation_mode=agent`），随后 `TestcaseAgentExecutor.run` 流式返回事件。支持幂等复用（同键近期成功记录直接 `agent_done` + `reused`）。 |
| **`POST .../generations/agent-start/`** | **同步返回 `record_id`**，由 **Celery `run_ai_testcase_agent`** 执行；若上传文件在请求中处理，否则任务内从 `source_files` 再解析。事件写入 P2 事件表供前端轮询/推送。 |

两者共享同一套工作流与执行器，差异在于：**连接形态**（长连接 SSE vs 后台任务 + 事件持久化）及**文件处理时机**。

---

## 8. 配置项（摘录）

| 配置项 | 作用 |
|--------|------|
| `KIMI_API_KEY` / `KIMI_BASE_URL` | Kimi 客户端（必选之一路径） |
| `DEEPSEEK_API_KEY` | 可选；缺失时生成阶段若指向 DeepSeek 会回退 Kimi |
| `AI_TESTCASE_MODEL_GENERATE` | 分模块生成等阶段默认模型 |
| `AI_TESTCASE_MODEL_REVIEW` | 分析、规划、评审默认模型 |
| `AI_TESTCASE_MODEL_REFINE` | 修订阶段模型 |
| `AI_TESTCASE_PROMPT_VERSION` | 写入记录与 `agent_state`，便于追溯 |
| `AI_TESTCASE_IDEMPOTENCY_REUSE_WINDOW_SECONDS` | 幂等复用时间窗 |
| `TESTCASE_AGENT_MAX_REVISIONS` | 最大修订/评审轮次（代码内 `getattr`，未在 settings 中时可依赖代码默认值 3） |
| `TESTCASE_AGENT_REVIEW_THRESHOLD` | 评审达标阈值（默认 0.8） |
| `TESTCASE_AGENT_MODULE_TIMEOUT` / `TESTCASE_AGENT_REVIEW_TIMEOUT` | 各节点超时秒数 |

---

## 9. 关键文件索引

```
backend/apps/ai_testcase/
├── workflows/
│   ├── testcase_agent.py    # LangGraph 定义与节点实现
│   ├── executor.py          # TestcaseAgentExecutor、DB 同步、finalize
│   └── agent_events.py      # emit_node_start
├── services/
│   ├── agent_prompts.py     # 各节点 Prompt 与消息构建
│   ├── agent_result_normalize.py
│   ├── mode_policy.py
│   └── model_router.py
├── tasks.py                   # run_ai_testcase_agent
├── views.py                   # agent_generate_stream_view、agent_start
└── models.py                  # AiTestcaseGeneration
```

---


