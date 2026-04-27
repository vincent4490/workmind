<template>
    <div class="functional-task-stats">
        <div class="page-header">
            <h3>任务统计</h3>
        </div>

        <el-card class="filters-card" shadow="never">
            <el-form :inline="true" size="small" :model="filters">
                <el-form-item label="时间范围">
                    <el-date-picker
                        v-model="filters.date_range"
                        type="daterange"
                        range-separator="至"
                        start-placeholder="开始日期"
                        end-placeholder="结束日期"
                        value-format="YYYY-MM-DD"
                        style="width: 260px;"
                        clearable
                    />
                </el-form-item>
                <el-form-item label="测试人员">
                    <el-select
                        v-model="filters.tester"
                        placeholder="请选择测试人员"
                        filterable
                        clearable
                        style="width: 180px;"
                    >
                        <el-option
                            v-for="u in userList"
                            :key="u.id"
                            :label="u.name || u.username"
                            :value="u.username"
                        />
                    </el-select>
                </el-form-item>
                <el-form-item>
                    <el-button type="primary" :loading="loadingStats" @click="handleSearch">查询</el-button>
                    <el-button @click="handleReset">重置</el-button>
                </el-form-item>
            </el-form>
        </el-card>

        <div class="kpi-grid">
            <el-card class="kpi-card" shadow="never">
                <div class="kpi-title">需求总数</div>
                <div class="kpi-value">{{ stats?.kpis?.requirements_total ?? '-' }}</div>
            </el-card>
            <el-card class="kpi-card" shadow="never">
                <div class="kpi-title">任务总数</div>
                <div class="kpi-value">{{ stats?.kpis?.tasks_total ?? '-' }}</div>
            </el-card>
            <el-card class="kpi-card" shadow="never">
                <div class="kpi-title">区间需求数</div>
                <div class="kpi-value">{{ stats?.kpis?.requirements_created_recent ?? '-' }}</div>
            </el-card>
            <el-card class="kpi-card" shadow="never">
                <div class="kpi-title">区间任务数</div>
                <div class="kpi-value">{{ stats?.kpis?.tasks_created_recent ?? '-' }}</div>
            </el-card>
        </div>

        <el-card shadow="never" style="margin-top: 16px;">
            <template #header>
                <div class="table-header">
                    <span>需求 / 任务列表</span>
                </div>
            </template>

            <el-tabs v-model="activeTab" @tab-change="handleTabChange">
                <el-tab-pane label="需求统计" name="requirements">
                    <el-table :data="requirementStats" v-loading="loadingReq" style="width: 100%;" max-height="520">
                        <el-table-column prop="tester_display" label="测试人员" min-width="160" show-overflow-tooltip />
                        <el-table-column prop="test_days" label="测试时间(天)" width="120">
                            <template #default="scope">
                                {{ formatDays(scope.row.test_days) }}
                            </template>
                        </el-table-column>
                        <el-table-column label="详情" width="110">
                            <template #default="scope">
                                <el-button link type="primary" @click="goRequirementDetail(scope.row.tester_username)">
                                    详情
                                </el-button>
                            </template>
                        </el-table-column>
                    </el-table>
                    <div class="pager">
                        <el-pagination
                            v-show="reqTotal > 0"
                            :current-page="reqPage"
                            :page-size="reqPageSize"
                            :total="reqTotal"
                            layout="total, prev, pager, next"
                            @current-change="(p) => { reqPage = p; applyRequirementStatsPage(); }"
                        />
                    </div>
                </el-tab-pane>

                <el-tab-pane label="任务统计" name="tasks">
                    <el-table :data="taskStats" v-loading="loadingTask" style="width: 100%;" max-height="520">
                        <el-table-column prop="owner_display" label="任务负责人" min-width="160" show-overflow-tooltip />
                        <el-table-column prop="task_days" label="任务时间(天)" width="120">
                            <template #default="scope">
                                {{ formatDays(scope.row.task_days) }}
                            </template>
                        </el-table-column>
                        <el-table-column label="详情" width="110">
                            <template #default="scope">
                                <el-button link type="primary" @click="goTaskDetail(scope.row.owner_username)">
                                    详情
                                </el-button>
                            </template>
                        </el-table-column>
                    </el-table>
                    <div class="pager">
                        <el-pagination
                            v-show="taskTotal > 0"
                            :current-page="taskPage"
                            :page-size="taskPageSize"
                            :total="taskTotal"
                            layout="total, prev, pager, next"
                            @current-change="(p) => { taskPage = p; applyTaskStatsPage(); }"
                        />
                    </div>
                </el-tab-pane>
            </el-tabs>
        </el-card>
    </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useGlobalProperties } from '@/composables'
import { useRouter } from 'vue-router'

const { $api } = useGlobalProperties()
const router = useRouter()

const activeTab = ref('requirements')

const userList = ref([])

const filters = ref({
    date_range: null,
    tester: '',
})

const getDateRangeParams = () => {
    const dr = filters.value.date_range
    if (!dr || !Array.isArray(dr) || dr.length !== 2) return {}
    const [after, before] = dr
    if (!after && !before) return {}
    return {
        after: after || undefined,
        before: before || undefined,
    }
}

const loadingStats = ref(false)
const stats = ref(null)

// requirements list
const loadingReq = ref(false)
const requirementStatsAll = ref([])
const requirementStats = ref([])
const reqPage = ref(1)
const reqPageSize = ref(10)
const reqTotal = ref(0)

// tasks list
const loadingTask = ref(false)
const taskStatsAll = ref([])
const taskStats = ref([])
const taskPage = ref(1)
const taskPageSize = ref(10)
const taskTotal = ref(0)

const buildStatsParams = () => {
    const { after, before } = getDateRangeParams()
    return {
        // 兼容旧接口字段（没选日期区间时后端仍按 range_days 走）
        range_days: 30,
        test_time_after: after,
        test_time_before: before,
        task_time_after: after,
        task_time_before: before,
        tester: filters.value.tester || undefined,
        // tester 在任务侧同时用于匹配负责人（一期合并输入）
        owner: filters.value.tester || undefined,
    }
}

const loadStats = async () => {
    loadingStats.value = true
    try {
        const res = await $api.getFunctionalTaskStats(buildStatsParams())
        if (res.code === 0) {
            stats.value = res.data || null
        } else {
            ElMessage.error(res.msg || '获取统计失败')
        }
    } catch (e) {
        ElMessage.error(e?.message || '获取统计失败')
    } finally {
        loadingStats.value = false
    }
}

const loadUserList = async () => {
    try {
        const data = await $api.getUserList()
        const list = Array.isArray(data) ? data : (data && data.data) ? data.data : []
        userList.value = (list || []).filter(u => u && (u.username || u.id))
    } catch (e) {
        userList.value = []
    }
}

const loadRequirements = async () => {
    loadingReq.value = true
    try {
        // 需求统计按测试人员聚合，需要一次拉取较多数据（一期先简单处理）
        const params = { page: 1, page_size: 2000 }
        if (filters.value.tester) params.testers = filters.value.tester
        const { after, before } = getDateRangeParams()
        if (after) params.test_time_after = after
        if (before) params.test_time_before = before
        const res = await $api.getFunctionalRequirements(params)
        if (res.code === 0) {
            const data = res.data?.results ? res.data : { results: res.data, count: (res.data || []).length }
            const rows = Array.isArray(data.results) ? data.results : []
            const aggregated = aggregateRequirementsByTester(rows)
            requirementStatsAll.value = aggregated
            reqTotal.value = aggregated.length
            applyRequirementStatsPage()
        } else {
            ElMessage.error(res.msg || '获取需求列表失败')
        }
    } catch (e) {
        ElMessage.error(e?.message || '获取需求列表失败')
    } finally {
        loadingReq.value = false
    }
}

const applyRequirementStatsPage = () => {
    const start = (reqPage.value - 1) * reqPageSize.value
    const end = start + reqPageSize.value
    requirementStats.value = (requirementStatsAll.value || []).slice(start, end)
}

const parsePersonField = (val) => {
    if (!val) return []
    if (Array.isArray(val)) return val
    return String(val)
        .replace(/，/g, ',')
        .split(',')
        .map(s => s.trim())
        .filter(Boolean)
}

const usernameToDisplay = (username) => {
    if (!username) return ''
    const list = userList.value || []
    const u = list.find(x => x && x.username === username)
    return u ? (u.name || u.username || username) : username
}

const parseDays = (val) => {
    if (!val) return 0
    const s = String(val).trim()
    const m = s.match(/(\d+(\.\d+)?)/)
    if (!m) return 0
    const n = Number(m[1])
    return Number.isFinite(n) ? n : 0
}

const aggregateRequirementsByTester = (rows) => {
    const map = new Map()
    for (const r of rows || []) {
        const testers = parsePersonField(r.testers)
        const team = (r.test_team || '').trim()
        const days = parseDays(r.test_man_days)
        if (testers.length === 0) {
            // 无测试人员也不计入统计
            continue
        }
        for (const t of testers) {
            if (!map.has(t)) {
                map.set(t, { tester: t, testTeams: new Set(), test_days: 0 })
            }
            const item = map.get(t)
            if (team) item.testTeams.add(team)
            item.test_days += days
        }
    }
    const out = []
    for (const v of map.values()) {
        out.push({
            tester_username: v.tester,
            tester_display: usernameToDisplay(v.tester),
            test_team: Array.from(v.testTeams).join('、') || '-',
            test_days: Math.round(v.test_days * 10) / 10,
        })
    }
    out.sort((a, b) => (b.test_days || 0) - (a.test_days || 0))
    return out
}

const formatDays = (n) => {
    const num = Number(n)
    if (!Number.isFinite(num)) return '-'
    if (num === 0) return '0'
    return String(num)
}

const goRequirementDetail = (testerUsername) => {
    if (!testerUsername) return
    const { after, before } = getDateRangeParams()
    router.push({
        name: 'RequirementManagement',
        query: {
            testers: testerUsername,
            test_time_after: after || undefined,
            test_time_before: before || undefined,
        }
    })
}

const loadTasks = async () => {
    loadingTask.value = true
    try {
        // 任务统计按负责人聚合，需要一次拉取较多数据（一期先简单处理）
        const params = { page: 1, page_size: 2000 }
        // tester 在任务侧同时用于匹配负责人（一期合并输入）
        if (filters.value.tester) params.owner = filters.value.tester
        const { after, before } = getDateRangeParams()
        if (after) params.task_time_after = after
        if (before) params.task_time_before = before
        const res = await $api.getTasks(params)
        if (res.code === 0) {
            const data = res.data?.results ? res.data : { results: res.data, count: (res.data || []).length }
            const rows = Array.isArray(data.results) ? data.results : []
            const aggregated = aggregateTasksByOwner(rows)
            taskStatsAll.value = aggregated
            taskTotal.value = aggregated.length
            applyTaskStatsPage()
        } else {
            ElMessage.error(res.msg || '获取任务列表失败')
        }
    } catch (e) {
        ElMessage.error(e?.message || '获取任务列表失败')
    } finally {
        loadingTask.value = false
    }
}

const applyTaskStatsPage = () => {
    const start = (taskPage.value - 1) * taskPageSize.value
    const end = start + taskPageSize.value
    taskStats.value = (taskStatsAll.value || []).slice(start, end)
}

const aggregateTasksByOwner = (rows) => {
    const map = new Map()
    for (const r of rows || []) {
        const owners = parsePersonField(r.owner)
        const days = parseDays(r.man_days)
        if (!owners.length) continue
        for (const o of owners) {
            if (!map.has(o)) {
                map.set(o, { owner: o, task_days: 0 })
            }
            const item = map.get(o)
            item.task_days += days
        }
    }
    const out = []
    for (const v of map.values()) {
        out.push({
            owner_username: v.owner,
            owner_display: usernameToDisplay(v.owner),
            task_days: Math.round(v.task_days * 10) / 10,
        })
    }
    out.sort((a, b) => (b.task_days || 0) - (a.task_days || 0))
    return out
}

const goTaskDetail = (ownerUsername) => {
    if (!ownerUsername) return
    const { after, before } = getDateRangeParams()
    router.push({
        name: 'TaskManagement',
        query: {
            owner: ownerUsername,
            task_time_after: after || undefined,
            task_time_before: before || undefined,
        }
    })
}

const handleSearch = async () => {
    reqPage.value = 1
    taskPage.value = 1
    await Promise.all([
        loadStats(),
        activeTab.value === 'requirements' ? loadRequirements() : loadTasks(),
    ])
}

const handleReset = async () => {
    filters.value = {
        date_range: null,
        tester: '',
    }
    await handleSearch()
}

const handleTabChange = async () => {
    if (activeTab.value === 'requirements') {
        reqPage.value = 1
        await loadRequirements()
    } else {
        taskPage.value = 1
        await loadTasks()
    }
}

onMounted(async () => {
    await loadUserList()
    await loadStats()
    await loadRequirements()
})
</script>

<style scoped>
.functional-task-stats {
    padding: 20px;
}

.page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.page-header h3 {
    margin: 0;
}

.filters-card {
    margin-top: 12px;
}

.kpi-grid {
    margin-top: 12px;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
}

.kpi-card {
    min-height: 92px;
}

.kpi-title {
    color: var(--el-text-color-secondary);
    font-size: 12px;
}

.kpi-value {
    margin-top: 8px;
    font-size: 28px;
    font-weight: 600;
    color: var(--el-text-color-primary);
}

.table-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.pager {
    margin-top: 12px;
    display: flex;
    justify-content: flex-end;
}
</style>

