<template>
    <div class="dashboard-container">
        <div class="page-header">
            <h2>首页</h2>
            <el-button type="primary" :icon="Refresh" @click="refreshData">刷新</el-button>
        </div>

        <!-- 统计卡片 -->
        <el-row :gutter="16" class="stats-row">
            <el-col :span="6">
                <el-card class="stat-card">
                    <div class="stat-content">
                        <div class="stat-icon" style="background: #ecf5ff; color: #409eff;">
                            <el-icon :size="32"><TrendCharts /></el-icon>
                        </div>
                        <div class="stat-info">
                            <div class="stat-label">今日测试</div>
                            <div class="stat-value">{{ stats.todayTests }} 次</div>
                            <div class="stat-extra">成功率 {{ stats.todaySuccessRate }}%</div>
                        </div>
                    </div>
                </el-card>
            </el-col>
            <el-col :span="6">
                <el-card class="stat-card">
                    <div class="stat-content">
                        <div class="stat-icon" style="background: #f0f9ff; color: #67c23a;">
                            <el-icon :size="32"><DataLine /></el-icon>
                        </div>
                        <div class="stat-info">
                            <div class="stat-label">本周测试</div>
                            <div class="stat-value">{{ stats.weekTests }} 次</div>
                            <div class="stat-extra">成功率 {{ stats.weekSuccessRate }}%</div>
                        </div>
                    </div>
                </el-card>
            </el-col>
            <el-col :span="6">
                <el-card class="stat-card">
                    <div class="stat-content">
                        <div class="stat-icon" style="background: #fef0f0; color: #f56c6c;">
                            <el-icon :size="32"><Document /></el-icon>
                        </div>
                        <div class="stat-info">
                            <div class="stat-label">测试用例</div>
                            <div class="stat-value">{{ stats.totalCases }} 个</div>
                            <div class="stat-extra">UI场景 {{ stats.uiFlowCases }} 个</div>
                        </div>
                    </div>
                </el-card>
            </el-col>
            <el-col :span="6">
                <el-card class="stat-card">
                    <div class="stat-content">
                        <div class="stat-icon" style="background: #f4f4f5; color: #909399;">
                            <el-icon :size="32"><Monitor /></el-icon>
                        </div>
                        <div class="stat-info">
                            <div class="stat-label">在线设备</div>
                            <div class="stat-value">{{ stats.onlineDevices }} 台</div>
                            <div class="stat-extra">总计 {{ stats.totalDevices }} 台</div>
                        </div>
                    </div>
                </el-card>
            </el-col>
        </el-row>

        <!-- 快速操作 -->
        <el-card class="quick-actions-card">
            <template #header>
                <div class="card-header">
                    <span>快速操作</span>
                </div>
            </template>
            <el-space :size="16">
                <el-button type="primary" @click="goToSceneBuilder">
                    <el-icon><Plus /></el-icon>
                    创建场景
                </el-button>
                <el-button type="success" @click="goToCaseList">
                    <el-icon><VideoPlay /></el-icon>
                    运行测试
                </el-button>
                <el-button type="info" @click="goToDeviceManagement">
                    <el-icon><Setting /></el-icon>
                    设备管理
                </el-button>
                <el-button type="warning" @click="goToAppPackageManagement">
                    <el-icon><Box /></el-icon>
                    应用管理
                </el-button>
            </el-space>
        </el-card>

        <!-- 最近测试执行记录 -->
        <el-card class="recent-executions-card">
            <template #header>
                <div class="card-header">
                    <span>最近测试执行记录</span>
                    <el-button link type="primary" @click="goToCaseList">查看全部</el-button>
                </div>
            </template>
            <el-table
                v-loading="loading"
                :data="recentExecutions"
                style="width: 100%"
                empty-text="暂无测试记录"
            >
                <el-table-column label="用例名称" min-width="200">
                    <template #default="scope">
                        <span style="font-weight: 500;">{{ scope.row.case_name }}</span>
                    </template>
                </el-table-column>
                <el-table-column label="状态" width="100" align="center">
                    <template #default="scope">
                        <el-tag v-if="scope.row.status === 'success'" type="success" size="small">成功</el-tag>
                        <el-tag v-else-if="scope.row.status === 'failed'" type="danger" size="small">失败</el-tag>
                        <el-tag v-else-if="scope.row.status === 'running'" type="warning" size="small">执行中</el-tag>
                        <el-tag v-else type="info" size="small">等待中</el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="设备" width="150">
                    <template #default="scope">
                        {{ scope.row.device_name || '-' }}
                    </template>
                </el-table-column>
                <el-table-column label="开始时间" width="180">
                    <template #default="scope">
                        {{ formatDate(scope.row.started_at) }}
                    </template>
                </el-table-column>
                <el-table-column label="耗时" width="100">
                    <template #default="scope">
                        {{ calculateDuration(scope.row) }}
                    </template>
                </el-table-column>
                <el-table-column label="操作" width="100" align="center">
                    <template #default="scope">
                        <el-button
                            v-if="scope.row.report_path"
                            link
                            type="primary"
                            size="small"
                            @click="viewReport(scope.row)"
                        >
                            查看报告
                        </el-button>
                    </template>
                </el-table-column>
            </el-table>
        </el-card>

        <!-- 设备状态概览 -->
        <el-card class="device-status-card">
            <template #header>
                <div class="card-header">
                    <span>设备状态</span>
                    <el-button link type="primary" @click="goToDeviceManagement">查看全部</el-button>
                </div>
            </template>
            <el-row :gutter="16">
                <el-col :span="8" v-for="device in devices" :key="device.id">
                    <div class="device-card" :class="getDeviceStatusClass(device.status)">
                        <div class="device-info">
                            <div class="device-name">{{ device.device_name }}</div>
                            <div class="device-id">{{ device.device_id }}</div>
                        </div>
                        <div class="device-status">
                            <el-tag :type="getDeviceTagType(device.status)" size="small">
                                {{ getDeviceStatusText(device.status) }}
                            </el-tag>
                        </div>
                    </div>
                </el-col>
                <el-col :span="8" v-if="devices.length === 0">
                    <el-empty description="暂无设备" :image-size="80" />
                </el-col>
            </el-row>
        </el-card>
    </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, TrendCharts, DataLine, Document, Monitor, Plus, VideoPlay, Setting, Box } from '@element-plus/icons-vue'
import { useGlobalProperties } from '@/composables'
import { baseUrl } from '@/restful/api'

const router = useRouter()
const { $api } = useGlobalProperties()

// 响应式数据
const loading = ref(false)
const stats = ref({
    todayTests: 0,
    todaySuccessRate: 0,
    weekTests: 0,
    weekSuccessRate: 0,
    totalCases: 0,
    uiFlowCases: 0,
    onlineDevices: 0,
    totalDevices: 0
})

const recentExecutions = ref([])
const devices = ref([])

// 方法
const loadDashboardData = async () => {
    loading.value = true
    try {
        await Promise.all([
            loadStats(),
            loadRecentExecutions(),
            loadDevices()
        ])
    } catch (error) {
        console.error('加载仪表板数据失败:', error)
    } finally {
        loading.value = false
    }
}

const loadStats = async () => {
    try {
        const response = await $api.getDashboardStats()
        if (response.code === 0) {
            stats.value = response.data
        }
    } catch (error) {
        // 如果 API 不存在，使用模拟数据
        console.warn('统计 API 未实现，使用模拟数据')
        stats.value = {
            todayTests: 0,
            todaySuccessRate: 0,
            weekTests: 0,
            weekSuccessRate: 0,
            totalCases: 0,
            uiFlowCases: 0,
            onlineDevices: 0,
            totalDevices: 0
        }
    }
}

const loadRecentExecutions = async () => {
    try {
        const response = await $api.getUiTestExecutions({ page: 1, size: 5 })
        if (response.code === 0 && response.data) {
            recentExecutions.value = response.data.results || []
        }
    } catch (error) {
        console.error('加载最近执行记录失败:', error)
        recentExecutions.value = []
    }
}

const loadDevices = async () => {
    try {
        const response = await $api.getDeviceList()
        if (response.code === 0) {
            devices.value = (response.data || []).slice(0, 6) // 只显示前6个设备
        }
    } catch (error) {
        console.error('加载设备列表失败:', error)
        devices.value = []
    }
}

const refreshData = () => {
    ElMessage.success('正在刷新数据...')
    loadDashboardData()
}

const formatDate = (dateStr) => {
    if (!dateStr) return '-'
    const date = new Date(dateStr)
    const now = new Date()
    const diff = Math.floor((now - date) / 1000)

    if (diff < 60) return '刚刚'
    if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
    if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`

    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    return `${year}-${month}-${day} ${hours}:${minutes}`
}

const calculateDuration = (execution) => {
    if (!execution.started_at) return '-'
    
    const start = new Date(execution.started_at)
    const end = execution.finished_at ? new Date(execution.finished_at) : new Date()
    const duration = Math.floor((end - start) / 1000)

    if (duration < 60) return `${duration}秒`
    const minutes = Math.floor(duration / 60)
    const seconds = duration % 60
    return `${minutes}分${seconds}秒`
}

const viewReport = (execution) => {
    if (!execution.report_path) {
        ElMessage.info('报告路径不存在')
        return
    }

    const reportUrl = `${baseUrl}/api/ui_test/executions/${execution.id}/report/`
    window.open(reportUrl, '_blank')
}

const getDeviceStatusClass = (status) => {
    if (status === 'online' || status === 'available' || status === 'locked') return 'device-online'
    if (status === 'offline') return 'device-offline'
    return 'device-unknown'
}

const getDeviceTagType = (status) => {
    if (status === 'online' || status === 'available') return 'success'
    if (status === 'locked') return 'warning'
    if (status === 'offline') return 'danger'
    return 'info'
}

const getDeviceStatusText = (status) => {
    if (status === 'online') return '在线'
    if (status === 'available') return '可用'
    if (status === 'locked') return '已锁定'
    if (status === 'offline') return '离线'
    return status || '未知'
}

// 导航方法
const goToSceneBuilder = () => {
    router.push({ name: 'UiTestSceneBuilder' })
}

const goToCaseList = () => {
    router.push({ name: 'UiFlowCaseList' })
}

const goToDeviceManagement = () => {
    router.push({ name: 'DeviceManagement' })
}

const goToAppPackageManagement = () => {
    router.push({ name: 'AppPackageManagement' })
}

// 生命周期
onMounted(() => {
    loadDashboardData()
})
</script>

<style scoped>
.dashboard-container {
    padding: 20px;
}

.page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}

.page-header h2 {
    margin: 0;
    font-size: 24px;
    font-weight: 600;
    color: #303133;
}

/* 统计卡片 */
.stats-row {
    margin-bottom: 20px;
}

.stat-card {
    height: 120px;
    cursor: pointer;
    transition: all 0.3s;
}

.stat-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.stat-content {
    display: flex;
    align-items: center;
    height: 100%;
}

.stat-icon {
    width: 64px;
    height: 64px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-right: 16px;
}

.stat-info {
    flex: 1;
}

.stat-label {
    font-size: 14px;
    color: #909399;
    margin-bottom: 8px;
}

.stat-value {
    font-size: 28px;
    font-weight: 600;
    color: #303133;
    margin-bottom: 4px;
}

.stat-extra {
    font-size: 12px;
    color: #67c23a;
}

/* 快速操作 */
.quick-actions-card {
    margin-bottom: 20px;
}

/* 最近执行记录 */
.recent-executions-card {
    margin-bottom: 20px;
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
}

/* 设备状态 */
.device-status-card {
    margin-bottom: 20px;
}

.device-card {
    padding: 16px;
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    transition: all 0.3s;
}

.device-card:hover {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.device-card.device-online {
    border-left: 4px solid #67c23a;
}

.device-card.device-offline {
    border-left: 4px solid #f56c6c;
}

.device-card.device-unknown {
    border-left: 4px solid #909399;
}

.device-info {
    flex: 1;
}

.device-name {
    font-size: 14px;
    font-weight: 500;
    color: #303133;
    margin-bottom: 4px;
}

.device-id {
    font-size: 12px;
    color: #909399;
}

.device-status {
    margin-left: 12px;
}
</style>
