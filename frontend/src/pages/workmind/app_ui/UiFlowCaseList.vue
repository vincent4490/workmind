<template>
    <div class="ui-flow-case-list">
        <div class="page-header">
            <h3>UI场景用例列表</h3>
            <div class="header-actions">
                <el-button
                    type="primary"
                    size="small"
                    :icon="Refresh"
                    :loading="loading"
                    @click="loadCases"
                >
                    刷新
                </el-button>
            </div>
        </div>

        <el-card class="device-card">
            <el-form :model="form" label-width="100px" size="small">
                <el-row :gutter="16">
                    <el-col :span="8">
                        <el-form-item label="选择设备" required>
                            <el-select
                                v-model="form.deviceId"
                                placeholder="请选择设备"
                                filterable
                                style="width: 100%"
                                :loading="devicesLoading"
                            >
                                <el-option
                                    v-for="device in availableDevices"
                                    :key="device.id"
                                    :label="device.device_id"
                                    :value="device.id"
                                    :disabled="device.status !== 'available'"
                                />
                            </el-select>
                        </el-form-item>
                    </el-col>
                    <el-col :span="8">
                        <el-form-item label="选择应用">
                            <el-select
                                v-model="form.packageId"
                                placeholder="请选择应用（可选）"
                                clearable
                                filterable
                                style="width: 100%"
                            >
                                <el-option
                                    v-for="pkg in appPackages"
                                    :key="pkg.id"
                                    :label="`${pkg.name} (${pkg.package_name})`"
                                    :value="pkg.id"
                                />
                            </el-select>
                        </el-form-item>
                    </el-col>
                </el-row>
            </el-form>
        </el-card>

        <el-table
            v-loading="loading"
            :data="caseList"
            style="width: 100%; margin-top: 16px;"
            empty-text="暂无UI场景用例"
        >
            <el-table-column prop="name" label="用例名称" min-width="200" />
            <el-table-column label="场景描述" min-width="250">
                <template #default="scope">
                    {{ getCaseData(scope.row, 'description') || '-' }}
                </template>
            </el-table-column>
            <el-table-column prop="updated_at" label="更新时间" width="180">
                <template #default="scope">
                    {{ formatDate(scope.row.updated_at) }}
                </template>
            </el-table-column>
            <el-table-column label="操作" width="160">
                <template #default="scope">
                    <el-button link type="primary" size="small" @click="runCase(scope.row)">
                        运行
                    </el-button>
                    <el-button link type="primary" size="small" @click="editCase(scope.row)">
                        编辑
                    </el-button>
                    <el-button link type="danger" size="small" @click="deleteCase(scope.row)">
                        删除
                    </el-button>
                </template>
            </el-table-column>
        </el-table>

        <el-pagination
            v-show="caseTotal > 0"
            :current-page="caseCurrentPage"
            :page-sizes="[10, 20, 50]"
            :page-size="casePageSize"
            :total="caseTotal"
            layout="total, sizes, prev, pager, next, jumper"
            style="margin-top: 16px; text-align: right;"
            @size-change="handleCaseSizeChange"
            @current-change="handleCasePageChange"
        />

        <!-- 测试执行记录 -->
        <el-card class="test-config-card" style="margin-top: 20px">
            <template #header>
                <div class="card-header">
                    <span>测试执行记录</span>
                    <el-button style="float: right; padding: 3px 0" link type="primary" @click="refreshExecutions">刷新</el-button>
                </div>
            </template>
            <el-table
                v-loading="executionsLoading"
                :data="executionData.results"
                style="width: 100%"
            >
                <el-table-column prop="case_name" label="测试用例" width="200" align="center" />
                <el-table-column prop="device_name" label="设备ID" width="150" align="center" />
                <el-table-column prop="user_name" label="测试工程师" width="120" align="center" />
                <el-table-column prop="status" label="状态" width="100" align="center">
                    <template #default="scope">
                        <el-tag
                            :type="getStatusType(scope.row.status)"
                            size="small"
                        >
                            {{ getStatusText(scope.row.status) }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column prop="progress" label="测试进度" width="300" align="center">
                    <template #default="scope">
                        <div style="display: flex; align-items: center; gap: 0; justify-content: center; padding: 4px 8px; background-color: #f5f7fa; border-radius: 4px;">
                            <el-progress
                                :percentage="scope.row.progress || 0"
                                :status="getProgressStatus(scope.row.status)"
                                :stroke-width="8"
                                :show-text="false"
                                style="flex: 1; margin: 0; margin-right: -2px;"
                            />
                            <span style="min-width: 40px; text-align: right; font-size: 12px; color: #606266; margin-left: -2px;">
                                {{ scope.row.progress || 0 }}%
                            </span>
                        </div>
                    </template>
                </el-table-column>
                <el-table-column prop="started_at" label="开始时间" width="180" align="center">
                    <template #default="scope">
                        {{ formatDate(scope.row.started_at) }}
                    </template>
                </el-table-column>
                <el-table-column prop="finished_at" label="结束时间" width="180" align="center">
                    <template #default="scope">
                        {{ scope.row.finished_at ? formatDate(scope.row.finished_at) : '-' }}
                    </template>
                </el-table-column>
                <el-table-column label="操作" width="150" align="center">
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
                        <el-button
                            v-if="scope.row.status === 'running'"
                            link
                            type="danger"
                            size="small"
                            @click="stopTest(scope.row)"
                        >
                            停止
                        </el-button>
                    </template>
                </el-table-column>
            </el-table>

            <!-- 分页 -->
            <el-pagination
                v-show="executionData.count !== 0"
                :current-page="executionCurrentPage"
                :page-sizes="[10, 20, 50]"
                :page-size="executionPageSize"
                :total="executionData.count"
                layout="total, sizes, prev, pager, next, jumper"
                @size-change="handleExecutionSizeChange"
                @current-change="handleExecutionPageChange"
                style="margin-top: 20px; text-align: right;"
            ></el-pagination>
        </el-card>
    </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { useGlobalProperties } from '@/composables'
import { baseUrl } from '@/restful/api'

const router = useRouter()
const { $api } = useGlobalProperties()

// 响应式数据
const loading = ref(false)
const devicesLoading = ref(false)
const executionsLoading = ref(false)
const availableDevices = ref([])

const form = ref({
    deviceId: null,
    packageId: null
})

const appPackages = ref([])

const caseList = ref([])
const caseCurrentPage = ref(1)
const casePageSize = ref(10)
const caseTotal = ref(0)

const executionData = ref({
    count: 0,
    results: []
})
const executionCurrentPage = ref(1)
const executionPageSize = ref(10)

const websockets = ref({})
const lastStatusMessages = ref({})

// 方法
const getCaseData = (row, key) => {
    if (!row || !row.case_data) {
        return ''
    }
    return row.case_data[key] || ''
}

const loadAppPackages = async () => {
    try {
        const response = await $api.getAppPackages()
        if (response.code === 0) {
            appPackages.value = response.data || []
        }
    } catch (error) {
        console.error('获取应用包名列表失败:', error)
    }
}

const loadDevices = async () => {
    devicesLoading.value = true
    try {
        const response = await $api.getDeviceList()
        if (response.code === 0) {
            availableDevices.value = response.data || []
        } else {
            availableDevices.value = []
        }
    } catch (error) {
        console.error('加载设备失败:', error)
        availableDevices.value = []
    } finally {
        devicesLoading.value = false
    }
}

const loadCases = async () => {
    loading.value = true
    try {
        const response = await $api.getUiTestCases({
            params: {
                ui_flow_only: 1,
                page: caseCurrentPage.value,
                size: casePageSize.value
            }
        })
        if (response.code === 0) {
            if (response.data && response.data.results) {
                caseList.value = response.data.results
                caseTotal.value = response.data.count || 0
            } else {
                const allCases = response.data || []
                caseList.value = allCases.filter(item => {
                    return item.test_type === 'ui' && item.case_data && item.case_data.ui_flow
                })
                caseTotal.value = caseList.value.length
            }
        } else {
            caseList.value = []
            caseTotal.value = 0
        }
    } catch (error) {
        console.error('加载UI场景用例失败:', error)
        caseList.value = []
        caseTotal.value = 0
    } finally {
        loading.value = false
    }
}

const handleCaseSizeChange = (size) => {
    casePageSize.value = size
    caseCurrentPage.value = 1
    loadCases()
}

const handleCasePageChange = (page) => {
    caseCurrentPage.value = page
    loadCases()
}

const editCase = (caseRow) => {
    if (!caseRow || !caseRow.id) {
        ElMessage.warning('用例数据不完整')
        return
    }
    router.push({
        name: 'UiTestSceneBuilder',
        query: { case_id: caseRow.id }
    })
}

const deleteCase = async (caseRow) => {
    if (!caseRow || !caseRow.id) {
        ElMessage.warning('用例数据不完整')
        return
    }
    try {
        await ElMessageBox.confirm('确定要删除该用例吗？', '提示', {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
        })
        const response = await $api.deleteUiTestCase(caseRow.id)
        if (response.code === 0 || response.code === undefined) {
            ElMessage.success('删除成功')
            loadCases()
        } else {
            ElMessage.error(response.msg || '删除失败')
        }
    } catch (error) {
        if (error !== 'cancel') {
            console.error('删除用例失败:', error)
        }
    }
}

const runCase = async (caseRow) => {
    if (!caseRow || !caseRow.id) {
        ElMessage.warning('用例数据不完整')
        return
    }
    if (!form.value.deviceId) {
        ElMessage.warning('请先选择设备再运行')
        return
    }
    try {
        const payload = {
            case_id: caseRow.id,
            device_id: form.value.deviceId
        }
        // 如果选择了应用包名，则传递
        if (form.value.packageId) {
            const selectedPackage = appPackages.value.find(pkg => pkg.id === form.value.packageId)
            if (selectedPackage) {
                payload.package_name = selectedPackage.package_name
            }
        }
        const response = await $api.startUiTestExecution(payload)
        if (response.code === 0) {
            ElMessage.success('测试任务已提交')
            const executionId = response.data && response.data.id
            const websocketUrl = response.data && response.data.websocket_url
            
            console.log(`🚀 测试任务已启动: execution_id=${executionId}, websocket_url=${websocketUrl}`)
            
            if (executionId) {
                checkExecutionStatus(executionId)
                
                // 连接 WebSocket 监听进度
                if (websocketUrl) {
                    connectWebSocket(executionId, websocketUrl)
                }
            }
            executionCurrentPage.value = 1
            loadExecutions()
        } else {
            ElMessage.error(response.msg || '启动测试失败')
        }
    } catch (error) {
        console.error('运行UI场景用例失败:', error)
        const errorMsg = (error.response && error.response.data && error.response.data.msg) || error.message
        ElMessage.error(errorMsg || '运行失败')
    }
}

const checkExecutionStatus = async (executionId) => {
    setTimeout(async () => {
        try {
            const response = await $api.getUiTestExecutionDetail(executionId)
            if (response && response.status === 'pending') {
                ElMessage.warning('任务未开始，请确认 Celery worker/Redis 已启动')
            }
        } catch (error) {
            console.error('检查执行状态失败:', error)
        }
    }, 3000)
}

const loadExecutions = async () => {
    executionsLoading.value = true
    try {
        const response = await $api.getUiTestExecutions({
            page: executionCurrentPage.value,
            size: executionPageSize.value,
            ui_flow_only: 1
        })

        if (response.code === 0 && response.data) {
            // 修复：正确处理后端返回的数据结构
            if (response.data.results !== undefined) {
                // 标准分页格式：{code: 0, data: {count: X, results: [...]}}
                executionData.value = response.data
            } else if (Array.isArray(response.data)) {
                // 兼容旧格式：{code: 0, data: [...]}
                executionData.value = {
                    count: response.data.length,
                    results: response.data
                }
            } else {
                executionData.value = {
                    count: 0,
                    results: []
                }
            }

            // 设置进度
            executionData.value.results.forEach(execution => {
                if (execution.progress === undefined) {
                    execution.progress = getProgressFromStatus(execution.status)
                }
            })

            // 连接WebSocket
            executionData.value.results.forEach(execution => {
                if ((execution.status === 'pending' || execution.status === 'running') && execution.id) {
                    if (!websockets.value[execution.id]) {
                        const websocketUrl = `/ws/test-execution/${execution.id}/`
                        connectWebSocket(execution.id, websocketUrl)
                    }
                } else if (execution.status === 'success' || execution.status === 'failed') {
                    if (websockets.value[execution.id]) {
                        closeWebSocket(execution.id)
                    }
                }
            })
        } else {
            executionData.value = {
                count: 0,
                results: []
            }
        }
    } catch (error) {
        console.error('加载执行记录失败:', error)
    } finally {
        executionsLoading.value = false
    }
}

const handleExecutionSizeChange = (size) => {
    executionPageSize.value = size
    executionCurrentPage.value = 1
    loadExecutions()
}

const handleExecutionPageChange = (page) => {
    executionCurrentPage.value = page
    loadExecutions()
}

const refreshExecutions = () => {
    loadExecutions()
}

const connectWebSocket = (executionId, websocketUrl) => {
    if (websockets.value[executionId]) {
        closeWebSocket(executionId)
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'

    // WebSocket 需要直接连接到后端服务器
    let backendHost
    if (baseUrl && baseUrl.trim() !== '') {
        // 生产环境：使用配置的 baseUrl
        const url = new URL(baseUrl)
        backendHost = url.host
    } else {
        // 开发环境：直接使用后端地址（不能通过 Vite proxy）
        backendHost = '127.0.0.1:8009'
    }

    const wsUrl = `${protocol}//${backendHost}${websocketUrl}`
    console.log(`🔌 正在连接 WebSocket: ${wsUrl}`)  // 添加日志

    try {
        const ws = new WebSocket(wsUrl)

        ws.onopen = () => {
            console.log(`✅ WebSocket 已连接: execution_id=${executionId}`)  // 添加日志
            const execution = executionData.value.results.find(e => e.id === executionId)
            if (execution && (execution.status === 'success' || execution.status === 'failed')) {
                closeWebSocket(executionId)
                return
            }
            ws.send(JSON.stringify({ type: 'get_status' }))
            console.log(`📤 已发送状态请求: execution_id=${executionId}`)  // 添加日志
        }

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data)
                console.log(`📨 收到 WebSocket 消息:`, data)  // 添加日志
                
                // 如果收到设备信息，显示详细日志
                if (data.device) {
                    console.log(`   🔧 设备信息: ${data.device.device_name} (${data.device.device_id})`)
                    console.log(`   📌 设备状态: ${data.device.status}`)
                    console.log(`   👤 锁定者: ${data.device.locked_by || '未锁定'}`)
                }
                
                // 如果收到用例信息，显示详细日志
                if (data.case) {
                    console.log(`   📋 测试用例: ${data.case.name} (ID: ${data.case.id})`)
                }

                if (data.type === 'progress_update' || data.type === 'initial_status' || data.type === 'status_response') {
                    if (data.type === 'initial_status') {
                        const msgId = `${data.execution_id || executionId}_${data.status}_${data.finished_at || ''}`
                        if (lastStatusMessages.value[executionId] === msgId) {
                            return
                        }
                        lastStatusMessages.value[executionId] = msgId
                    }

                    updateExecutionStatus(data.execution_id || executionId, {
                        status: data.status,
                        progress: data.progress,
                        message: data.message,
                        finished_at: data.finished_at,
                        report_path: data.report_path
                    })
                }
            } catch (error) {
                console.error('解析 WebSocket 消息失败:', error)
            }
        }

        ws.onerror = (error) => {
            console.error(`❌ WebSocket 错误: execution_id=${executionId}`, error)
        }

        ws.onclose = () => {
            console.log(`🔌 WebSocket 已断开: execution_id=${executionId}`)  // 添加日志
            delete websockets.value[executionId]
        }

        websockets.value[executionId] = ws
    } catch (error) {
        console.error(`❌ 创建 WebSocket 连接失败: execution_id=${executionId}`, error)
    }
}

const closeWebSocket = (executionId) => {
    if (websockets.value[executionId]) {
        websockets.value[executionId].close()
        delete websockets.value[executionId]
    }
}

const closeAllWebSockets = () => {
    Object.keys(websockets.value).forEach(executionId => {
        closeWebSocket(executionId)
    })
}

const updateExecutionStatus = (executionId, updates) => {
    const execution = executionData.value.results.find(e => e.id === executionId)
    if (execution) {
        if (updates.status !== undefined && updates.status !== null) {
            execution.status = updates.status
        }
        if (updates.progress !== undefined) {
            execution.progress = updates.progress
        }
        if (updates.finished_at) {
            execution.finished_at = updates.finished_at
        }
        if (updates.report_path !== undefined) {
            execution.report_path = updates.report_path
        }

        const finalStatus = updates.status || execution.status
        if ((finalStatus === 'success' || finalStatus === 'failed') && execution.report_path) {
            closeWebSocket(executionId)
            delete lastStatusMessages.value[executionId]
        }
    } else {
        if (!executionsLoading.value) {
            loadExecutions()
        }
    }
}

const stopTest = async (execution) => {
    try {
        const response = await $api.stopUiTestExecution(execution.id)
        if (response.code === 0) {
            ElMessage.success('测试已停止')
            loadExecutions()
        }
    } catch (error) {
        console.error('停止测试失败:', error)
        ElMessage.error('停止测试失败')
    }
}

const viewReport = (execution) => {
    if (!execution.report_path) {
        ElMessage.info('报告路径不存在')
        return
    }
    const reportUrl = `/api/ui_test/executions/${execution.id}/report/`
    window.open(reportUrl, '_blank')
}

const formatDate = (dateStr) => {
    if (!dateStr) {
        return '-'
    }
    const date = new Date(dateStr)
    return date.toLocaleString()
}

const getStatusType = (status) => {
    const statusMap = {
        'pending': 'info',
        'running': 'warning',
        'success': 'success',
        'failed': 'danger'
    }
    return statusMap[status] || 'info'
}

const getStatusText = (status) => {
    const statusMap = {
        'pending': '等待中',
        'running': '执行中',
        'success': '成功',
        'failed': '失败'
    }
    return statusMap[status] || status
}

const getProgressFromStatus = (status) => {
    const statusProgressMap = {
        'pending': 0,
        'running': 50,
        'success': 100,
        'failed': 100
    }
    return statusProgressMap[status] || 0
}

const getProgressStatus = (status) => {
    if (status === 'success') {
        return 'success'
    } else if (status === 'failed') {
        return 'exception'
    }
    return null
}

// 生命周期
onMounted(() => {
    loadAppPackages()
    loadDevices()
    loadCases()
    loadExecutions()
})

onBeforeUnmount(() => {
    closeAllWebSockets()
})
</script>

<style scoped>
.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.ui-flow-case-list {
    padding: 16px;
}

.page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.header-actions {
    display: flex;
    gap: 8px;
}

.device-card {
    margin-top: 12px;
}

.test-config-card {
    margin-top: 20px;
}
</style>

