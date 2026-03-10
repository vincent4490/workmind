<template>
    <div class="ai-req-dashboard">
        <div class="page-header">
            <div class="header-title-row">
                <h2>AI 需求智能体 · 运营看板</h2>
                <el-button text type="primary" @click="loadAll" :loading="loading">
                    <el-icon><Refresh /></el-icon> 刷新
                </el-button>
            </div>
        </div>

        <!-- 成本告警条 -->
        <el-alert v-if="stats.cost_alert" type="warning" :closable="false" show-icon class="cost-alert">
            当日成本已超过告警阈值（${{ stats.cost_alert_threshold_usd }}），当前 ${{ stats.today_cost_usd }}
        </el-alert>

        <!-- 概览卡片 -->
        <el-row :gutter="16" class="stat-cards">
            <el-col :span="4">
                <div class="stat-card">
                    <div class="stat-value">{{ stats.total_tasks }}</div>
                    <div class="stat-label">总任务数</div>
                </div>
            </el-col>
            <el-col :span="4">
                <div class="stat-card success">
                    <div class="stat-value">{{ stats.success_rate }}%</div>
                    <div class="stat-label">成功率</div>
                </div>
            </el-col>
            <el-col :span="4">
                <div class="stat-card">
                    <div class="stat-value">{{ formatTokens(stats.total_tokens) }}</div>
                    <div class="stat-label">总 Token</div>
                </div>
            </el-col>
            <el-col :span="4">
                <div class="stat-card warning">
                    <div class="stat-value">${{ stats.total_cost_usd }}</div>
                    <div class="stat-label">总成本</div>
                </div>
            </el-col>
            <el-col :span="4">
                <div class="stat-card">
                    <div class="stat-value">{{ stats.avg_confidence }}</div>
                    <div class="stat-label">平均置信度</div>
                </div>
            </el-col>
            <el-col :span="4">
                <div class="stat-card" :class="{ success: stats.feedback?.satisfaction_rate >= 80 }">
                    <div class="stat-value">{{ stats.feedback?.satisfaction_rate || 0 }}%</div>
                    <div class="stat-label">满意度 ({{ stats.feedback?.total || 0 }}条)</div>
                </div>
            </el-col>
        </el-row>

        <el-row :gutter="20" style="margin-top: 20px;">
            <!-- 左侧：趋势 + 分布 -->
            <el-col :span="14">
                <!-- 日均趋势 -->
                <el-card shadow="hover" class="chart-card">
                    <template #header>
                        <span class="card-title">最近 14 天趋势</span>
                    </template>
                    <el-table :data="stats.daily_trend || []" stripe size="small" max-height="300">
                        <el-table-column prop="date" label="日期" width="120" />
                        <el-table-column prop="count" label="任务数" width="80" />
                        <el-table-column prop="tokens" label="Token" width="100">
                            <template #default="{ row }">{{ formatTokens(row.tokens) }}</template>
                        </el-table-column>
                        <el-table-column prop="cost" label="成本($)" width="80" />
                        <el-table-column label="Token 柱状" min-width="200">
                            <template #default="{ row }">
                                <div class="bar-cell">
                                    <div class="bar-fill" :style="{ width: barWidth(row.tokens) }"></div>
                                </div>
                            </template>
                        </el-table-column>
                    </el-table>
                </el-card>

                <!-- 按任务类型分布 -->
                <el-card shadow="hover" class="chart-card" style="margin-top: 16px;">
                    <template #header>
                        <span class="card-title">按任务类型分布</span>
                    </template>
                    <el-table :data="stats.by_task_type || []" stripe size="small">
                        <el-table-column prop="task_type" label="任务类型" width="180">
                            <template #default="{ row }">
                                <el-tag size="small">{{ taskLabel(row.task_type) }}</el-tag>
                            </template>
                        </el-table-column>
                        <el-table-column prop="count" label="次数" width="80" />
                        <el-table-column prop="tokens" label="Token" width="100">
                            <template #default="{ row }">{{ formatTokens(row.tokens) }}</template>
                        </el-table-column>
                        <el-table-column prop="cost" label="成本($)" width="80" />
                        <el-table-column prop="avg_conf" label="平均置信度" width="100">
                            <template #default="{ row }">
                                {{ row.avg_conf ? row.avg_conf.toFixed(2) : '-' }}
                            </template>
                        </el-table-column>
                    </el-table>
                </el-card>
            </el-col>

            <!-- 右侧：Prompt 版本管理 -->
            <el-col :span="10">
                <el-card shadow="hover" class="chart-card">
                    <template #header>
                        <div class="card-header">
                            <span class="card-title">Prompt 版本管理</span>
                            <el-button type="primary" size="small" @click="showCreateDialog = true">
                                新建版本
                            </el-button>
                        </div>
                    </template>

                    <div class="prompt-filter">
                        <el-select v-model="promptFilter" placeholder="全部任务类型" clearable size="small"
                            style="width: 180px;" @change="loadPrompts">
                            <el-option label="PRD 撰写" value="prd_draft" />
                            <el-option label="竞品分析" value="competitive_analysis" />
                            <el-option label="需求完善" value="prd_refine" />
                            <el-option label="需求分析" value="requirement_analysis" />
                            <el-option label="技术方案" value="tech_design" />
                            <el-option label="测试需求分析" value="test_requirement_analysis" />
                            <el-option label="功能点梳理" value="feature_breakdown" />
                        </el-select>
                    </div>

                    <div class="prompt-list">
                        <div v-if="promptVersions.length === 0" style="text-align: center; color: #909399; padding: 20px;">
                            暂无 Prompt 版本，请先在代码内置版本基础上创建数据库版本
                        </div>
                        <div
                            v-for="pv in promptVersions"
                            :key="pv.id"
                            class="prompt-item"
                            :class="{ active: pv.is_active, ab: pv.is_ab_candidate }"
                        >
                            <div class="prompt-item-header">
                                <span class="prompt-item-name">
                                    {{ taskLabel(pv.task_type) }} <strong>v{{ pv.version }}</strong>
                                </span>
                                <el-tag v-if="pv.is_active" type="success" size="small" effect="dark">生产</el-tag>
                                <el-tag v-if="pv.is_ab_candidate" type="warning" size="small">
                                    A/B {{ (pv.ab_traffic_ratio * 100).toFixed(0) }}%
                                </el-tag>
                            </div>
                            <div class="prompt-item-meta">
                                <span v-if="pv.accuracy_score != null">准确率: {{ (pv.accuracy_score * 100).toFixed(0) }}%</span>
                                <span v-if="pv.schema_compliance_rate != null">Schema合规: {{ (pv.schema_compliance_rate * 100).toFixed(0) }}%</span>
                                <span>{{ formatDate(pv.created_at) }}</span>
                            </div>
                            <div v-if="pv.change_log" class="prompt-item-changelog">{{ pv.change_log }}</div>
                            <div class="prompt-item-actions">
                                <el-button
                                    v-if="!pv.is_active"
                                    text type="success" size="small"
                                    @click="handleActivate(pv)"
                                >激活</el-button>
                                <el-button
                                    v-if="pv.is_active"
                                    text type="danger" size="small"
                                    @click="handleDeactivate(pv)"
                                >停用</el-button>
                                <el-button
                                    v-if="!pv.is_ab_candidate && !pv.is_active"
                                    text type="warning" size="small"
                                    @click="handleSetAB(pv)"
                                >设为A/B</el-button>
                                <el-button
                                    text type="info" size="small"
                                    @click="handleViewPrompt(pv)"
                                >查看</el-button>
                            </div>
                        </div>
                    </div>
                </el-card>

                <!-- 反馈问题分布 -->
                <el-card shadow="hover" class="chart-card" style="margin-top: 16px;" v-if="stats.feedback?.issues?.length">
                    <template #header>
                        <span class="card-title">负面反馈分布</span>
                    </template>
                    <el-table :data="stats.feedback.issues" size="small" stripe>
                        <el-table-column prop="issue_type" label="问题类型" width="120">
                            <template #default="{ row }">
                                {{ issueLabel(row.issue_type) }}
                            </template>
                        </el-table-column>
                        <el-table-column prop="count" label="次数" width="60" />
                        <el-table-column label="占比" min-width="120">
                            <template #default="{ row }">
                                <el-progress
                                    :percentage="Math.round(row.count / (stats.feedback.negative || 1) * 100)"
                                    :stroke-width="14"
                                    :show-text="true"
                                />
                            </template>
                        </el-table-column>
                    </el-table>
                </el-card>
            </el-col>
        </el-row>

        <!-- 创建 Prompt 版本弹窗 -->
        <el-dialog v-model="showCreateDialog" title="创建 Prompt 版本" width="700px">
            <el-form :model="createForm" label-width="100px">
                <el-form-item label="任务类型" required>
                    <el-select v-model="createForm.task_type" style="width: 100%;">
                        <el-option label="PRD 撰写" value="prd_draft" />
                        <el-option label="竞品分析" value="competitive_analysis" />
                        <el-option label="需求完善" value="prd_refine" />
                        <el-option label="需求分析" value="requirement_analysis" />
                        <el-option label="技术方案" value="tech_design" />
                        <el-option label="测试需求分析" value="test_requirement_analysis" />
                        <el-option label="功能点梳理" value="feature_breakdown" />
                    </el-select>
                </el-form-item>
                <el-form-item label="版本号" required>
                    <el-input v-model="createForm.version" placeholder="如 1.1.0" />
                </el-form-item>
                <el-form-item label="System Prompt" required>
                    <el-input
                        v-model="createForm.system_prompt"
                        type="textarea"
                        :rows="12"
                        placeholder="完整的 System Prompt 文本"
                    />
                </el-form-item>
                <el-form-item label="变更说明">
                    <el-input v-model="createForm.change_log" type="textarea" :rows="2" placeholder="本版本修改了什么" />
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="showCreateDialog = false">取消</el-button>
                <el-button type="primary" @click="handleCreatePrompt" :loading="creating">创建</el-button>
            </template>
        </el-dialog>

        <!-- 查看 Prompt 弹窗 -->
        <el-dialog v-model="showViewDialog" title="Prompt 详情" width="700px">
            <el-input type="textarea" :model-value="viewPromptText" :rows="20" readonly class="json-preview" />
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import {
    getAiRequirementStats,
    getPromptVersions,
    createPromptVersion,
    activatePromptVersion,
} from '@/restful/api'

const TASK_LABELS = {
    competitive_analysis: '竞品分析', prd_draft: 'PRD 撰写', prd_refine: '需求完善',
    requirement_analysis: '需求分析', tech_design: '技术方案',
    test_requirement_analysis: '测试需求分析', feature_breakdown: '功能点梳理',
}
const ISSUE_LABELS = {
    hallucination: '幻觉', missing: '遗漏', format_error: '格式错误',
    irrelevant: '不相关', other: '其他',
}

const taskLabel = (t) => TASK_LABELS[t] || t
const issueLabel = (t) => ISSUE_LABELS[t] || t
const loading = ref(false)

// ---- 统计 ----
const stats = ref({
    total_tasks: 0, success_rate: 0, total_tokens: 0,
    total_cost_usd: '0', today_cost_usd: '0', avg_confidence: 0,
    cost_alert: false, cost_alert_threshold_usd: 0,
    by_role: [], by_task_type: [], daily_trend: [],
    feedback: { total: 0, positive: 0, negative: 0, satisfaction_rate: 0, issues: [] },
})

async function loadStats() {
    try {
        stats.value = await getAiRequirementStats()
    } catch (err) {
        console.error('加载统计失败:', err)
    }
}

function formatTokens(n) {
    if (!n) return '0'
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
    return String(n)
}

function barWidth(tokens) {
    const maxTokens = Math.max(...(stats.value.daily_trend || []).map(d => d.tokens || 0), 1)
    return Math.round((tokens || 0) / maxTokens * 100) + '%'
}

function formatDate(d) {
    if (!d) return ''
    return new Date(d).toLocaleDateString('zh-CN')
}

// ---- Prompt 版本 ----
const promptVersions = ref([])
const promptFilter = ref('')
const showCreateDialog = ref(false)
const showViewDialog = ref(false)
const viewPromptText = ref('')
const creating = ref(false)
const createForm = ref({
    task_type: 'prd_draft', version: '', system_prompt: '', change_log: '',
})

async function loadPrompts() {
    try {
        const params = {}
        if (promptFilter.value) params.task_type = promptFilter.value
        const res = await getPromptVersions(params)
        promptVersions.value = res.results || res
    } catch (err) {
        console.error('加载Prompt版本失败:', err)
    }
}

async function handleCreatePrompt() {
    if (!createForm.value.task_type || !createForm.value.version || !createForm.value.system_prompt) {
        ElMessage.warning('请填写必填项')
        return
    }
    creating.value = true
    try {
        await createPromptVersion(createForm.value)
        ElMessage.success('Prompt 版本创建成功')
        showCreateDialog.value = false
        createForm.value = { task_type: 'prd_draft', version: '', system_prompt: '', change_log: '' }
        loadPrompts()
    } catch (err) {
        ElMessage.error('创建失败：' + (err.response?.data?.version?.[0] || err.message))
    } finally {
        creating.value = false
    }
}

async function handleActivate(pv) {
    try {
        await ElMessageBox.confirm(`确定激活 ${pv.task_type} v${pv.version} 为生产版本？其他版本将被停用。`, '确认')
        await activatePromptVersion(pv.id, { action: 'activate' })
        ElMessage.success('已激活')
        loadPrompts()
    } catch (err) {
        if (err !== 'cancel') ElMessage.error('操作失败')
    }
}

async function handleDeactivate(pv) {
    try {
        await activatePromptVersion(pv.id, { action: 'deactivate' })
        ElMessage.success('已停用，将降级到代码内置版本')
        loadPrompts()
    } catch (err) {
        ElMessage.error('操作失败')
    }
}

async function handleSetAB(pv) {
    try {
        await ElMessageBox.confirm(`将 v${pv.version} 设为 A/B 测试候选（10% 流量）？`, '确认')
        await activatePromptVersion(pv.id, { action: 'set_ab', ab_traffic_ratio: 0.1 })
        ElMessage.success('已设为 A/B 候选')
        loadPrompts()
    } catch (err) {
        if (err !== 'cancel') ElMessage.error('操作失败')
    }
}

function handleViewPrompt(pv) {
    viewPromptText.value = pv.system_prompt
    showViewDialog.value = true
}

// ---- 生命周期 ----
async function loadAll() {
    loading.value = true
    await Promise.all([loadStats(), loadPrompts()])
    loading.value = false
}

onMounted(() => { loadAll() })
</script>

<style scoped>
.ai-req-dashboard {
    padding: 20px;
}

.page-header {
    margin-bottom: 16px;
}

.cost-alert {
    margin-bottom: 16px;
}

.header-title-row {
    display: flex;
    align-items: center;
    gap: 12px;
}

.header-title-row h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: #303133;
}

/* 概览卡片 */
.stat-cards {
    margin-bottom: 4px;
}

.stat-card {
    background: #fff;
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    padding: 16px;
    text-align: center;
    transition: all 0.2s;
}

.stat-card:hover {
    border-color: #409eff;
    box-shadow: 0 2px 12px rgba(64, 158, 255, 0.1);
}

.stat-card.success {
    border-left: 3px solid #67c23a;
}

.stat-card.warning {
    border-left: 3px solid #e6a23c;
}

.stat-value {
    font-size: 24px;
    font-weight: 700;
    color: #303133;
    line-height: 1.2;
}

.stat-label {
    font-size: 12px;
    color: #909399;
    margin-top: 4px;
}

/* 图表卡片 */
.chart-card {
    margin-bottom: 0;
}

.card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.card-title {
    font-size: 15px;
    font-weight: 600;
    color: #303133;
}

/* Token 柱状条 */
.bar-cell {
    height: 14px;
    background: #f0f0f0;
    border-radius: 7px;
    overflow: hidden;
}

.bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #409eff, #67c23a);
    border-radius: 7px;
    transition: width 0.3s ease;
}

/* Prompt 列表 */
.prompt-filter {
    margin-bottom: 12px;
}

.prompt-list {
    max-height: 400px;
    overflow-y: auto;
}

.prompt-item {
    padding: 10px 14px;
    border: 1px solid #e4e7ed;
    border-radius: 6px;
    margin-bottom: 8px;
    background: #fafafa;
    transition: all 0.2s;
}

.prompt-item.active {
    border-color: #67c23a;
    background: #f0f9eb;
}

.prompt-item.ab {
    border-color: #e6a23c;
    background: #fdf6ec;
}

.prompt-item-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
}

.prompt-item-name {
    font-size: 14px;
    color: #303133;
}

.prompt-item-meta {
    font-size: 12px;
    color: #909399;
    display: flex;
    gap: 12px;
    margin-bottom: 4px;
}

.prompt-item-changelog {
    font-size: 12px;
    color: #606266;
    margin-bottom: 4px;
}

.prompt-item-actions {
    display: flex;
    gap: 4px;
}

.prompt-list::-webkit-scrollbar { width: 4px; }
.prompt-list::-webkit-scrollbar-thumb { background: #dcdfe6; border-radius: 2px; }

/* JSON 预览 */
.json-preview :deep(.el-textarea__inner) {
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 13px;
    line-height: 1.6;
}
</style>
