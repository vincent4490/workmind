<template>
    <div class="test-plan-execute">
        <el-page-header @back="goBack" :title="planName">
            <template #content>
                <span class="text-large font-600 mr-3">执行测试计划</span>
            </template>
        </el-page-header>

        <el-card style="margin-top: 20px;">
            <template #header>
                <div class="card-header">
                    <span>测试用例列表</span>
                    <el-button type="primary" @click="executeAll">
                        批量执行
                    </el-button>
                </div>
            </template>

            <el-table
                ref="tableRef"
                v-loading="loading"
                :data="caseList"
                style="width: 100%;"
                @selection-change="handleSelectionChange"
            >
                <el-table-column type="selection" width="55" />
                <el-table-column type="index" label="序号" width="60" />
                <el-table-column prop="test_case_detail.title" label="需求名称" min-width="140" show-overflow-tooltip />
                <el-table-column prop="test_case_detail.module_name" label="模块名称" width="120" show-overflow-tooltip />
                <el-table-column prop="test_case_detail.function_name" label="功能点" width="120" show-overflow-tooltip />
                <el-table-column prop="test_case_detail.name" label="用例名称" min-width="160" show-overflow-tooltip />
                <el-table-column prop="test_case_detail.priority" label="优先级" width="80">
                    <template #default="scope">
                        <el-tag
                            :type="getPriorityType(scope.row.test_case_detail?.priority)"
                            size="small"
                        >
                            {{ scope.row.test_case_detail?.priority || '-' }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column prop="test_case_detail.precondition" label="前置条件" min-width="160" show-overflow-tooltip />
                <el-table-column prop="test_case_detail.steps" label="测试步骤" min-width="200" show-overflow-tooltip />
                <el-table-column prop="test_case_detail.expected" label="预期结果" min-width="200" show-overflow-tooltip />
                <el-table-column label="执行状态" width="100">
                    <template #default="scope">
                        <el-tag
                            :type="getStatusType(scope.row.status)"
                            size="small"
                        >
                            {{ getStatusText(scope.row.status) }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="操作" width="180">
                    <template #default="scope">
                        <el-button
                            link
                            type="primary"
                            size="small"
                            @click="executeCase(scope.row)"
                        >
                            执行
                        </el-button>
                        <el-button
                            link
                            type="info"
                            size="small"
                            @click="showLogs(scope.row)"
                        >
                            查看记录
                        </el-button>
                    </template>
                </el-table-column>
            </el-table>
        </el-card>

        <!-- 标记执行结果弹窗 -->
        <el-dialog
            v-model="markDialogVisible"
            :title="isBatchMark ? '批量标记执行结果' : '标记执行结果'"
            width="440px"
            @close="resetMarkForm"
        >
            <el-form :model="markForm" label-width="90px">
                <el-form-item label="执行结果" required>
                    <el-radio-group v-model="markForm.status">
                        <el-radio label="passed">通过</el-radio>
                        <el-radio label="failed">失败</el-radio>
                        <el-radio label="skipped">跳过</el-radio>
                    </el-radio-group>
                </el-form-item>
                <el-form-item label="执行备注" :required="markForm.status === 'failed' || markForm.status === 'skipped'">
                    <el-input
                        v-model="markForm.message"
                        type="textarea"
                        :rows="3"
                        placeholder="失败或跳过时必填"
                    />
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="markDialogVisible = false">取消</el-button>
                <el-button type="primary" :loading="markLoading" @click="confirmMark">确定</el-button>
            </template>
        </el-dialog>

        <!-- 查看执行记录弹窗 -->
        <el-dialog
            v-model="logDialogVisible"
            title="执行记录"
            width="560px"
        >
            <el-table :data="logList" style="width: 100%;" max-height="400">
                <el-table-column prop="operator_username" label="操作人" width="100" />
                <el-table-column prop="status" label="结果" width="80">
                    <template #default="scope">
                        <el-tag :type="getStatusType(scope.row.status)" size="small">
                            {{ getStatusText(scope.row.status) }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column prop="message" label="备注" min-width="160" show-overflow-tooltip />
                <el-table-column prop="created_at" label="时间" width="160">
                    <template #default="scope">
                        {{ formatLogTime(scope.row.created_at) }}
                    </template>
                </el-table-column>
            </el-table>
            <template #footer>
                <el-button @click="logDialogVisible = false">关闭</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useGlobalProperties } from '@/composables'

const route = useRoute()
const router = useRouter()
const { $api } = useGlobalProperties()

const planId = ref(route.params.planId)
const planName = ref(route.query.planName || '未命名计划')
const loading = ref(false)
const caseList = ref([])
const tableRef = ref(null)
const selectedRows = ref([])
const markDialogVisible = ref(false)
const markForm = ref({ status: 'passed', message: '' })
const markLoading = ref(false)
const isBatchMark = ref(false)
const currentMarkRow = ref(null)
const logDialogVisible = ref(false)
const logList = ref([])
const currentLogCase = ref(null)

const goBack = () => {
    router.back()
}

const handleSelectionChange = (rows) => {
    selectedRows.value = rows || []
}

const loadCases = async () => {
    loading.value = true
    try {
        const response = await $api.getPlanCases(planId.value)
        if (response.code === 0) {
            caseList.value = response.data || []
        } else {
            ElMessage.error(response.msg || '加载用例失败')
        }
    } catch (error) {
        console.error('加载测试计划用例失败:', error)
        ElMessage.error('加载用例失败')
    } finally {
        loading.value = false
    }
}

const executeCase = (row) => {
    currentMarkRow.value = row
    isBatchMark.value = false
    markForm.value = { status: 'passed', message: '' }
    markDialogVisible.value = true
}

const executeAll = () => {
    if (!selectedRows.value || selectedRows.value.length === 0) {
        ElMessage.warning('请先勾选要标记的用例')
        return
    }
    currentMarkRow.value = null
    isBatchMark.value = true
    markForm.value = { status: 'passed', message: '' }
    markDialogVisible.value = true
}

const resetMarkForm = () => {
    markForm.value = { status: 'passed', message: '' }
    currentMarkRow.value = null
    isBatchMark.value = false
}

const confirmMark = async () => {
    const { status, message } = markForm.value
    if ((status === 'failed' || status === 'skipped') && !String(message || '').trim()) {
        ElMessage.warning('失败或跳过必须填写备注')
        return
    }
    markLoading.value = true
    try {
        if (isBatchMark.value) {
            const caseIds = selectedRows.value.map(r => r.test_case_detail?.id).filter(Boolean)
            const res = await $api.batchMarkPlanCaseStatus(planId.value, caseIds, status, message || '')
            if (res.code === 0) {
                ElMessage.success(res.msg || '批量标记成功')
                markDialogVisible.value = false
                tableRef.value?.clearSelection()
                loadCases()
            } else {
                ElMessage.error(res.msg || '批量标记失败')
            }
        } else {
            const caseId = currentMarkRow.value?.test_case_detail?.id
            if (!caseId) {
                ElMessage.error('用例信息异常')
                return
            }
            const res = await $api.markPlanCaseStatus(planId.value, caseId, status, message || '')
            if (res.code === 0) {
                ElMessage.success('标记成功')
                markDialogVisible.value = false
                loadCases()
            } else {
                ElMessage.error(res.msg || '标记失败')
            }
        }
    } catch (e) {
        ElMessage.error(e?.message || '操作失败')
    } finally {
        markLoading.value = false
    }
}

const showLogs = async (row) => {
    currentLogCase.value = row
    logList.value = []
    logDialogVisible.value = true
    try {
        const res = await $api.getPlanCaseLogs(planId.value, row.test_case_detail?.id)
        if (res.code === 0 && res.data) {
            logList.value = res.data
        }
    } catch (e) {
        ElMessage.error('加载执行记录失败')
    }
}

const formatLogTime = (val) => {
    if (!val) return '-'
    const d = new Date(val)
    if (isNaN(d.getTime())) return val
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const h = String(d.getHours()).padStart(2, '0')
    const min = String(d.getMinutes()).padStart(2, '0')
    const s = String(d.getSeconds()).padStart(2, '0')
    return `${y}/${m}/${day} ${h}:${min}:${s}`
}

const getPriorityType = (priority) => {
    const typeMap = {
        'P0': 'danger',
        'P1': 'warning',
        'P2': '',
        'P3': 'info'
    }
    return typeMap[priority] || 'info'
}

const getStatusType = (status) => {
    const typeMap = {
        'pending': 'info',
        'passed': 'success',
        'failed': 'danger',
        'skipped': 'warning'
    }
    return typeMap[status] || 'info'
}

const getStatusText = (status) => {
    const textMap = {
        'pending': '未执行',
        'passed': '通过',
        'failed': '失败',
        'skipped': '跳过'
    }
    return textMap[status] || (status || '未执行')
}

onMounted(() => {
    loadCases()
})
</script>

<style scoped>
.test-plan-execute {
    padding: 20px;
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

</style>
