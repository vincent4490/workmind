<template>
    <div class="req-structured-root">
        <div class="req-result-toolbar">
            <div class="req-result-toolbar__stats">
                <el-tag
                    v-for="(chip, i) in summaryChips"
                    :key="i"
                    type="info"
                    size="small"
                    effect="plain"
                    class="req-stat-chip"
                >
                    {{ chip }}
                </el-tag>
                <el-tag
                    v-if="confidenceScore != null"
                    :type="confidenceScore >= 0.7 ? 'success' : 'warning'"
                    size="small"
                >
                    置信度 {{ (confidenceScore * 100).toFixed(0) }}%
                </el-tag>
                <el-tag v-if="totalTokens != null && totalTokens > 0" size="small" type="info">
                    Token: {{ totalTokens }}
                </el-tag>
            </div>
            <el-button v-if="showStructuredCollapseToggle" text type="primary" size="small" @click="toggleExpandAll">
                {{ allExpanded ? '收起详情' : '展开详情' }}
            </el-button>
        </div>

        <template v-if="taskType === 'test_requirement_analysis'">
            <el-collapse v-model="activePanels" class="req-struct-collapse">
                <el-collapse-item title="可测性评估" name="testability" v-if="hasList(data.testability_assessment)">
                    <div
                        v-for="(item, idx) in data.testability_assessment"
                        :key="'ta-' + idx"
                        class="req-struct-card"
                    >
                        <div class="req-struct-card__title">条目 {{ idx + 1 }}</div>
                        <KvBlock :record="item" />
                    </div>
                </el-collapse-item>
                <el-collapse-item title="测试策略" name="strategy" v-if="hasTestStrategyContent(data)">
                    <div v-if="hasList(data.test_strategy.test_levels)" class="req-strategy-sub">
                        <div class="req-struct-card__title">测试层级</div>
                        <div
                            v-for="(row, idx) in data.test_strategy.test_levels"
                            :key="'tl-' + idx"
                            class="req-struct-card"
                        >
                            <div class="req-struct-card__title">层级 {{ idx + 1 }}</div>
                            <KvBlock :record="row" />
                        </div>
                    </div>
                    <div v-if="hasList(data.test_strategy.test_environments)" class="req-strategy-sub">
                        <div class="req-struct-card__title">测试环境</div>
                        <ul class="req-bullet-list">
                            <li v-for="(line, idx) in data.test_strategy.test_environments" :key="'env-' + idx">
                                {{ line }}
                            </li>
                        </ul>
                    </div>
                    <div v-if="hasList(data.test_strategy.test_data_requirements)" class="req-strategy-sub">
                        <div class="req-struct-card__title">测试数据需求</div>
                        <ul class="req-bullet-list">
                            <li v-for="(line, idx) in data.test_strategy.test_data_requirements" :key="'td-' + idx">
                                {{ line }}
                            </li>
                        </ul>
                    </div>
                    <pre
                        v-if="!hasList(data.test_strategy.test_levels) && !hasList(data.test_strategy.test_environments) && !hasList(data.test_strategy.test_data_requirements)"
                        class="req-json-block"
                    >{{ formatJson(data.test_strategy) }}</pre>
                </el-collapse-item>
                <el-collapse-item title="风险区域" name="risks" v-if="hasList(data.risk_areas)">
                    <div
                        v-for="(item, idx) in data.risk_areas"
                        :key="'r-' + idx"
                        class="req-struct-card"
                    >
                        <div class="req-struct-card__title">风险 {{ idx + 1 }}</div>
                        <KvBlock :record="item" />
                    </div>
                </el-collapse-item>
                <el-collapse-item title="不可测 / 需补充项" name="untest" v-if="hasList(data.untestable_items)">
                    <div
                        v-for="(item, idx) in data.untestable_items"
                        :key="'u-' + idx"
                        class="req-struct-card"
                    >
                        <div class="req-struct-card__title">项 {{ idx + 1 }}</div>
                        <KvBlock :record="item" />
                    </div>
                </el-collapse-item>
                <el-collapse-item title="待补充需求点" name="missing" v-if="hasList(data.missing_requirements)">
                    <ol class="req-missing-list">
                        <li v-for="(line, idx) in data.missing_requirements" :key="'miss-' + idx">
                            <template v-if="typeof line === 'string'">{{ line }}</template>
                            <pre v-else class="req-inline-json">{{ formatJson(line) }}</pre>
                        </li>
                    </ol>
                </el-collapse-item>
            </el-collapse>
            <el-empty v-if="!hasAnyTestReqSection(data)" description="无可展示的结构化字段" />
        </template>

        <template v-else-if="taskType === 'competitive_analysis'">
            <div v-if="data.markdown_full" class="req-md-wrap">
                <pre class="req-md-pre">{{ data.markdown_full }}</pre>
            </div>
            <el-collapse v-model="activePanels" class="req-struct-collapse">
                <el-collapse-item title="对比矩阵" name="matrix" v-if="hasList(data.comparison_matrix)">
                    <div
                        v-for="(row, idx) in data.comparison_matrix"
                        :key="'m-' + idx"
                        class="req-struct-card"
                    >
                        <KvBlock :record="row" />
                    </div>
                </el-collapse-item>
                <el-collapse-item title="SWOT" name="swot" v-if="data.swot && typeof data.swot === 'object'">
                    <KvBlock :record="data.swot" />
                </el-collapse-item>
                <el-collapse-item v-if="data.ui_analysis" title="界面/体验分析" name="ui">
                    <pre class="req-plain-block">{{ data.ui_analysis }}</pre>
                </el-collapse-item>
                <el-collapse-item
                    title="产品建议"
                    name="rec"
                    v-if="hasList(data.recommendations)"
                >
                    <ul class="req-bullet-list">
                        <li v-for="(line, idx) in data.recommendations" :key="'rec-' + idx">
                            {{ line }}
                        </li>
                    </ul>
                </el-collapse-item>
            </el-collapse>
        </template>

        <template v-else-if="taskType === 'requirement_analysis'">
            <div v-if="data.markdown_full" class="req-md-wrap">
                <pre class="req-md-pre">{{ data.markdown_full }}</pre>
            </div>
            <el-collapse v-model="activePanels" class="req-struct-collapse">
                <el-collapse-item title="功能拆解" name="fd" v-if="hasList(data.functional_decomposition)">
                    <div
                        v-for="(item, idx) in data.functional_decomposition"
                        :key="'fd-' + idx"
                        class="req-struct-card"
                    >
                        <KvBlock :record="item" />
                    </div>
                </el-collapse-item>
                <el-collapse-item title="技术影响" name="ti" v-if="hasList(data.technical_impact)">
                    <div v-for="(item, idx) in data.technical_impact" :key="'ti-' + idx" class="req-struct-card">
                        <KvBlock :record="item" />
                    </div>
                </el-collapse-item>
                <el-collapse-item title="风险" name="risk" v-if="hasList(data.risks)">
                    <div v-for="(item, idx) in data.risks" :key="'rk-' + idx" class="req-struct-card">
                        <KvBlock :record="item" />
                    </div>
                </el-collapse-item>
            </el-collapse>
        </template>

        <template v-else-if="taskType === 'tech_design'">
            <div v-if="data.markdown_full" class="req-md-wrap">
                <pre class="req-md-pre">{{ data.markdown_full }}</pre>
            </div>
            <el-collapse v-model="activePanels" class="req-struct-collapse">
                <el-collapse-item title="架构概览" name="arch" v-if="data.architecture != null">
                    <KvBlock v-if="isPlainObject(data.architecture)" :record="data.architecture" />
                    <pre v-else class="req-json-block">{{ formatJson(data.architecture) }}</pre>
                </el-collapse-item>
                <el-collapse-item title="API 契约" name="api" v-if="hasList(data.api_contracts)">
                    <div v-for="(item, idx) in data.api_contracts" :key="'api-' + idx" class="req-struct-card">
                        <KvBlock :record="item" />
                    </div>
                </el-collapse-item>
                <el-collapse-item v-if="data.mermaid_diagram" title="架构图 (Mermaid)" name="mmd">
                    <pre class="req-plain-block">{{ data.mermaid_diagram }}</pre>
                </el-collapse-item>
                <el-collapse-item title="风险" name="tr" v-if="hasList(data.risks)">
                    <div v-for="(item, idx) in data.risks" :key="'tr-' + idx" class="req-struct-card">
                        <KvBlock :record="item" />
                    </div>
                </el-collapse-item>
            </el-collapse>
        </template>

        <!-- PRD 撰写 / 需求完善：主区 Markdown 版式完全一致（prd_refine 优先 updated_prd.markdown_full，其次根级 markdown_full） -->
        <template v-else-if="taskType === 'prd_draft' || taskType === 'prd_refine'">
            <div v-if="prdMainMarkdown" class="req-md-wrap">
                <pre class="req-md-pre">{{ prdMainMarkdown }}</pre>
            </div>
            <el-collapse
                v-if="taskType === 'prd_refine' && hasPrdRefineSecondary"
                v-model="activePanels"
                class="req-struct-collapse req-struct-collapse--refine"
            >
                <el-collapse-item v-if="data.change_summary" title="变更摘要" name="cs">
                    <pre class="req-plain-block">{{ data.change_summary }}</pre>
                </el-collapse-item>
                <el-collapse-item title="变更条目" name="ch" v-if="hasList(data.changes)">
                    <div v-for="(item, idx) in data.changes" :key="'ch-' + idx" class="req-struct-card">
                        <div class="req-struct-card__title">变更 {{ idx + 1 }}</div>
                        <KvBlock :record="item" />
                    </div>
                </el-collapse-item>
                <el-collapse-item v-if="data.updated_prd" :title="prdRefineJsonPanelTitle" name="up">
                    <pre class="req-json-block">{{ formatJson(data.updated_prd) }}</pre>
                </el-collapse-item>
            </el-collapse>
            <pre v-if="taskType === 'prd_draft' && !prdMainMarkdown" class="req-json-block">{{ formatJson(data) }}</pre>
            <pre
                v-if="taskType === 'prd_refine' && !prdMainMarkdown && !hasPrdRefineSecondary"
                class="req-json-block"
            >{{ formatJson(data) }}</pre>
        </template>

        <template v-else>
            <pre class="req-json-block">{{ formatJson(data) }}</pre>
        </template>
    </div>
</template>

<script setup>
import { computed, ref, watch, h, defineComponent } from 'vue'
import { ElDescriptions, ElDescriptionsItem } from 'element-plus'

const props = defineProps({
    taskType: { type: String, default: '' },
    data: { type: Object, default: () => ({}) },
    confidenceScore: { type: Number, default: null },
    totalTokens: { type: Number, default: null },
    collapsible: { type: Boolean, default: true },
})

/**
 * PRD 撰写：根级 markdown_full。
 * 需求完善：与 PRD 撰写同一展示源，优先 updated_prd.markdown_full，兼容根级 markdown_full（部分模型/中间层会摊平）。
 */
function getPrdMainMarkdown(data, taskType) {
    const d = data || {}
    if (taskType === 'prd_draft') {
        const m = d.markdown_full
        return typeof m === 'string' && m.trim() ? m : ''
    }
    if (taskType === 'prd_refine') {
        const nested = d.updated_prd?.markdown_full
        if (typeof nested === 'string' && nested.trim()) return nested
        const root = d.markdown_full
        if (typeof root === 'string' && root.trim()) return root
    }
    return ''
}

const prdMainMarkdown = computed(() => getPrdMainMarkdown(props.data, props.taskType))

/** 需求完善除正文外是否还有折叠块（无则与 PRD 撰写同样「仅正文区」） */
const hasPrdRefineSecondary = computed(() => {
    if (props.taskType !== 'prd_refine') return false
    const d = props.data || {}
    const hasSummary = !!(d.change_summary && String(d.change_summary).trim())
    const hasChanges = hasList(d.changes)
    const up = d.updated_prd
    const hasUpdated =
        up != null && typeof up === 'object' && !Array.isArray(up) && Object.keys(up).length > 0
    return hasSummary || hasChanges || hasUpdated
})

const prdRefineJsonPanelTitle = computed(() =>
    prdMainMarkdown.value ? '更新后 PRD（完整 JSON）' : '更新后 PRD（结构化）'
)

/** PRD 撰写无折叠；需求完善无次要块时也不显示「展开/收起」 */
const showStructuredCollapseToggle = computed(() => {
    if (!props.collapsible) return false
    const t = props.taskType
    if (t === 'prd_draft') return false
    if (t === 'prd_refine') return hasPrdRefineSecondary.value
    return true
})

/** 结构化 JSON 字段 key → 中文表头（LLM 常用英文 key） */
const KEY_LABELS = {
    // 测试需求分析 / 可测性
    reason: '原因',
    requirement: '需求',
    improvement_suggestion: '改进建议',
    /** 不可测/需补充项等结构中的「项」描述 */
    item: '条目',
    testability: '可测性',
    test_approach: '测试思路',
    level: '测试层级',
    coverage_focus: '覆盖重点',
    tools: '建议工具',
    test_levels: '测试层级列表',
    test_environments: '测试环境',
    test_data_requirements: '测试数据需求',
    automation_feasibility: '自动化可行性',
    manual_test_hint: '手工测试提示',
    // 风险 / 通用
    area: '范围/模块',
    risk_type: '风险类型',
    risk_level: '风险等级',
    probability: '概率',
    impact: '影响',
    severity: '严重程度',
    likelihood: '可能性',
    mitigation: '缓解措施',
    root_cause: '根因',
    affected_area: '影响范围',
    // 竞品 / 矩阵
    feature: '功能点',
    competitor: '竞品',
    dimension: '维度',
    our_product: '我方产品',
    competitors: '竞品列表',
    gap_analysis: '差距分析',
    opportunity: '差异化机会',
    comparison: '对比结论',
    strengths: '优势',
    weaknesses: '劣势',
    opportunities: '机会',
    threats: '威胁',
    name: '名称',
    status: '支持状态',
    detail: '具体说明',
    // 需求分析
    functional_decomposition: '功能拆解',
    technical_impact: '技术影响',
    dependencies: '依赖',
    assumption: '假设',
    constraint: '约束',
    // 技术方案
    architecture: '架构',
    api_contracts: 'API 契约',
    endpoint: '接口',
    method: '方法',
    request: '请求',
    response: '响应',
    mermaid_diagram: '架构图',
    // 通用
    description: '说明',
    name: '名称',
    title: '标题',
    detail: '详情',
    summary: '摘要',
    status: '状态',
    priority: '优先级',
    category: '分类',
    owner: '负责人',
    notes: '备注',
    comment: '评论',
    evidence: '依据',
    recommendation: '建议',
    gap: '缺口',
    blocker: '阻塞项',
    scenario: '场景',
    precondition: '前置条件',
    postcondition: '后置条件',
    expected_result: '预期结果',
    workaround: '变通方案',
    id: '编号',
    type: '类型',
    value: '值',
    /** 需求完善 changes */
    section: '章节/位置',
    before: '修改前',
    after: '修改后',
    review_checklist: '评审检查项',
}

function formatLabel(key) {
    if (key != null && KEY_LABELS[key] !== undefined) return KEY_LABELS[key]
    return key != null ? String(key) : ''
}

/** 单元格内常见英文枚举 → 中文（可测性、风险等） */
const VALUE_EN_ZH = {
    high: '高',
    low: '低',
    medium: '中',
    critical: '严重',
    major: '主要',
    minor: '次要',
    yes: '是',
    no: '否',
    unknown: '未知',
    pending: '待定',
    /** 需求完善 changes.type */
    clarify: '澄清',
    modify: '修改',
    add: '新增',
    delete: '删除',
    pass: '通过',
    fail: '未通过',
    warning: '警告',
}

function formatValue(val) {
    if (val == null) return '—'
    if (typeof val === 'object') return formatJson(val)
    if (typeof val === 'string') {
        const t = val.trim()
        const lower = t.toLowerCase()
        if (VALUE_EN_ZH[lower] !== undefined) return VALUE_EN_ZH[lower]
    }
    return String(val)
}

function hasList(v) {
    return Array.isArray(v) && v.length > 0
}

/** 与 Prompt 中 test_strategy 结构一致；非空对象即展示 */
function hasTestStrategyContent(d) {
    const s = d?.test_strategy
    if (s == null || typeof s !== 'object' || Array.isArray(s)) return false
    return Object.keys(s).length > 0
}

function hasAnyTestReqSection(d) {
    return (
        hasList(d.testability_assessment) ||
        hasList(d.risk_areas) ||
        hasList(d.untestable_items) ||
        hasTestStrategyContent(d) ||
        hasList(d.missing_requirements)
    )
}

function formatJson(v) {
    try {
        return JSON.stringify(v, null, 2)
    } catch {
        return String(v)
    }
}

function isPlainObject(v) {
    return v != null && typeof v === 'object' && !Array.isArray(v)
}

const KvBlock = defineComponent({
    name: 'KvBlock',
    props: {
        record: { type: [Object, Array], default: () => ({}) },
    },
    setup(p) {
        return () => {
            const raw = p.record
            const o =
                raw != null && typeof raw === 'object' && !Array.isArray(raw)
                    ? raw
                    : {}
            const entries = Object.entries(o)
            if (!entries.length) {
                return h('span', { class: 'req-empty' }, typeof raw === 'string' ? raw : '—')
            }
            // Vue 3：组件子内容必须通过 slots 对象传入，否则 el-descriptions-item 的单元格为空
            return h(
                ElDescriptions,
                { column: 1, border: true, size: 'small', class: 'req-desc' },
                {
                    default: () =>
                        entries.map(([key, val]) =>
                            h(
                                ElDescriptionsItem,
                                { key: String(key), label: formatLabel(key) },
                                {
                                    default: () =>
                                        h('span', { class: 'req-desc-val' }, formatValue(val)),
                                }
                            )
                        ),
                }
            )
        }
    },
})

const activePanels = ref([])
const allExpanded = ref(true)

function defaultPanelNames() {
    const t = props.taskType
    const d = props.data || {}
    if (t === 'test_requirement_analysis') {
        const names = []
        if (hasList(d.testability_assessment)) names.push('testability')
        if (hasTestStrategyContent(d)) names.push('strategy')
        if (hasList(d.risk_areas)) names.push('risks')
        if (hasList(d.untestable_items)) names.push('untest')
        if (hasList(d.missing_requirements)) names.push('missing')
        return names
    }
    if (t === 'competitive_analysis') {
        const names = []
        if (hasList(d.comparison_matrix)) names.push('matrix')
        if (d.swot && typeof d.swot === 'object') names.push('swot')
        if (d.ui_analysis) names.push('ui')
        if (hasList(d.recommendations)) names.push('rec')
        return names
    }
    if (t === 'requirement_analysis') {
        const names = []
        if (hasList(d.functional_decomposition)) names.push('fd')
        if (hasList(d.technical_impact)) names.push('ti')
        if (hasList(d.risks)) names.push('risk')
        return names
    }
    if (t === 'tech_design') {
        const names = []
        if (d.architecture != null) names.push('arch')
        if (hasList(d.api_contracts)) names.push('api')
        if (d.mermaid_diagram) names.push('mmd')
        if (hasList(d.risks)) names.push('tr')
        return names
    }
    if (t === 'prd_refine') {
        const names = []
        if (d.change_summary) names.push('cs')
        if (hasList(d.changes)) names.push('ch')
        const hasMd = getPrdMainMarkdown(d, 'prd_refine')
        if (d.updated_prd && !hasMd) names.push('up')
        return names
    }
    return []
}

watch(
    () => [props.taskType, props.data],
    () => {
        activePanels.value = defaultPanelNames()
        allExpanded.value = true
    },
    { immediate: true, deep: true }
)

function toggleExpandAll() {
    allExpanded.value = !allExpanded.value
    activePanels.value = allExpanded.value ? defaultPanelNames() : []
}

const summaryChips = computed(() => {
    const d = props.data || {}
    const chips = []
    if (props.taskType === 'test_requirement_analysis') {
        if (hasList(d.testability_assessment)) chips.push(`${d.testability_assessment.length} 条可测性评估`)
        if (hasTestStrategyContent(d)) chips.push('含测试策略')
        if (hasList(d.risk_areas)) chips.push(`${d.risk_areas.length} 个风险区域`)
        if (hasList(d.untestable_items)) chips.push(`${d.untestable_items.length} 项需补充`)
        if (hasList(d.missing_requirements)) chips.push(`${d.missing_requirements.length} 条待补充需求`)
    } else if (props.taskType === 'competitive_analysis') {
        if (hasList(d.comparison_matrix)) chips.push(`${d.comparison_matrix.length} 行对比`)
        if (hasList(d.recommendations)) chips.push(`${d.recommendations.length} 条产品建议`)
    } else if (props.taskType === 'requirement_analysis') {
        if (hasList(d.functional_decomposition)) chips.push(`${d.functional_decomposition.length} 项功能拆解`)
        if (hasList(d.technical_impact)) chips.push(`${d.technical_impact.length} 条技术影响`)
        if (hasList(d.risks)) chips.push(`${d.risks.length} 条风险`)
    } else if (props.taskType === 'tech_design') {
        if (hasList(d.api_contracts)) chips.push(`${d.api_contracts.length} 条 API 契约`)
    } else if (props.taskType === 'prd_draft' || props.taskType === 'prd_refine') {
        const md = getPrdMainMarkdown(d, props.taskType)
        if (md) chips.push(`PRD 正文 ${Math.round(md.length / 1000)}k 字`)
        if (props.taskType === 'prd_refine' && hasList(d.changes)) {
            chips.push(`${d.changes.length} 条变更`)
        }
    }
    return chips
})
</script>

<style scoped>
.req-structured-root {
    margin-top: 12px;
}

.req-result-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 12px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--el-border-color-lighter);
}

.req-result-toolbar__stats {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
}

.req-stat-chip {
    font-weight: 500;
}

.req-struct-collapse {
    border: none;
}

.req-struct-collapse :deep(.el-collapse-item__header) {
    font-weight: 600;
    font-size: 14px;
}

.req-struct-card {
    margin-bottom: 12px;
}

.req-struct-card:last-child {
    margin-bottom: 0;
}

.req-struct-card__title {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    margin-bottom: 6px;
}

.req-plain-block,
.req-json-block,
.req-md-pre {
    margin: 0;
    padding: 12px;
    background: var(--el-fill-color-light);
    border-radius: 6px;
    font-size: 13px;
    line-height: 1.55;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
}

.req-md-wrap {
    max-height: 70vh;
    overflow: auto;
}

.req-struct-collapse--refine {
    margin-top: 12px;
}

.req-desc-val {
    white-space: pre-wrap;
    word-break: break-word;
}

.req-empty {
    color: var(--el-text-color-placeholder);
}

.req-strategy-sub {
    margin-bottom: 16px;
}

.req-strategy-sub:last-child {
    margin-bottom: 0;
}

.req-bullet-list,
.req-missing-list {
    margin: 0;
    padding-left: 1.25em;
    font-size: 13px;
    line-height: 1.65;
    color: var(--el-text-color-primary);
}

.req-missing-list {
    list-style: decimal;
}

.req-inline-json {
    margin: 0;
    font-size: 12px;
    white-space: pre-wrap;
    word-break: break-word;
}
</style>
