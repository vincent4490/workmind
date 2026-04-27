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
            append-to-body
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
                <el-form-item v-if="!isBatchMark" label="图片">
                    <div class="upload-row">
                        <div v-if="markFileList.length" class="upload-preview-grid">
                            <div v-for="f in markFileList" :key="f.uid" class="upload-preview-item">
                                <el-image
                                    :src="getUploadPreviewUrl(f)"
                                    :preview-src-list="markFileList.map(x => getUploadPreviewUrl(x))"
                                    :preview-teleported="true"
                                    :z-index="4000"
                                    fit="cover"
                                    class="upload-preview-img"
                                />
                                <el-button
                                    class="upload-preview-remove"
                                    circle
                                    size="small"
                                    @click="removeUploadFile(f)"
                                >
                                    <el-icon><Close /></el-icon>
                                </el-button>
                            </div>
                        </div>

                        <el-upload
                            v-if="markFileList.length < 9"
                            v-model:file-list="markFileList"
                            list-type="picture"
                            drag
                            :auto-upload="false"
                            :show-file-list="false"
                            :limit="9"
                            accept="image/*"
                            :on-exceed="handleUploadExceed"
                            :before-upload="beforeUpload"
                        >
                            <div class="upload-plus-wrap">
                                <el-icon><Plus /></el-icon>
                                <div class="upload-plus-caption">支持上传 / 拖拽 / 复制粘贴</div>
                            </div>
                        </el-upload>
                    </div>
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
            append-to-body
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
                <el-table-column label="图片" width="120">
                    <template #default="scope">
                        <div v-if="scope.row.attachments && scope.row.attachments.length" class="log-attachments">
                            <el-image
                                v-for="att in scope.row.attachments"
                                :key="att.id"
                                :src="att.url"
                                :preview-src-list="scope.row.attachments.map(a => a.url)"
                                :preview-teleported="true"
                                :z-index="4000"
                                :initial-index="0"
                                fit="cover"
                                style="width: 32px; height: 32px; margin-right: 6px; border-radius: 4px;"
                            />
                        </div>
                        <span v-else>-</span>
                    </template>
                </el-table-column>
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
import { ref, onMounted, watch, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useGlobalProperties } from '@/composables'
import { Plus, Close } from '@element-plus/icons-vue'

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
const markFileList = ref([])
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
    // revoke blob urls to avoid memory leak
    try {
        ;(markFileList.value || []).forEach((f) => {
            if (f?.url && String(f.url).startsWith('blob:')) {
                URL.revokeObjectURL(f.url)
            }
        })
    } catch (e) {}
    markForm.value = { status: 'passed', message: '' }
    currentMarkRow.value = null
    isBatchMark.value = false
    markFileList.value = []
}

const handleUploadExceed = () => {
    ElMessage.warning('最多上传 9 张图片')
}

const beforeUpload = (file) => {
    if (!file) return false
    if (!String(file.type || '').startsWith('image/')) {
        ElMessage.error('仅支持图片文件')
        return false
    }
    return true
}

const getUploadPreviewUrl = (file) => {
    return file?.url || ''
}

const removeUploadFile = (file) => {
    const uid = file?.uid
    if (!uid) return
    const idx = (markFileList.value || []).findIndex(x => x.uid === uid)
    if (idx >= 0) {
        const f = markFileList.value[idx]
        if (f?.url && String(f.url).startsWith('blob:')) {
            try { URL.revokeObjectURL(f.url) } catch (e) {}
        }
        markFileList.value.splice(idx, 1)
    }
}

const addFilesToUploadList = (files) => {
    const list = markFileList.value || []
    const remain = Math.max(0, 9 - list.length)
    if (remain <= 0) {
        ElMessage.warning('最多上传 9 张图片')
        return
    }
    const toAdd = Array.from(files || []).slice(0, remain)
    let added = 0
    toAdd.forEach((raw) => {
        if (!raw) return
        if (!String(raw.type || '').startsWith('image/')) return
        const url = URL.createObjectURL(raw)
        list.push({
            name: raw.name || `paste_${Date.now()}.png`,
            url,
            raw,
            uid: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
            status: 'ready',
        })
        added += 1
    })
    markFileList.value = list
    if (added > 0) {
        ElMessage.success(`已添加 ${added} 张图片`)
    }
}

const handlePaste = (event) => {
    if (!markDialogVisible.value || isBatchMark.value) return
    const items = event?.clipboardData?.items
    if (!items || items.length === 0) return

    const files = []
    for (const item of items) {
        if (item?.kind === 'file' && String(item.type || '').startsWith('image/')) {
            const f = item.getAsFile?.()
            if (f) files.push(f)
        }
    }
    if (files.length) {
        // If clipboard also includes text, don't block normal paste into inputs/textarea.
        const types = Array.from(event?.clipboardData?.types || [])
        const hasText = types.includes('text/plain') || types.includes('text/html')
        if (!hasText) {
            event.preventDefault()
        }
        addFilesToUploadList(files)
    }
}

watch(markDialogVisible, async (visible) => {
    if (visible) {
        window.addEventListener('paste', handlePaste)
        await nextTick()
    } else {
        window.removeEventListener('paste', handlePaste)
    }
})

onUnmounted(() => {
    window.removeEventListener('paste', handlePaste)
})

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
            const files = (markFileList.value || []).map(i => i.raw).filter(Boolean)
            const res = await $api.markPlanCaseStatusWithFiles(planId.value, caseId, status, message || '', files)
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

.log-attachments {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
}

.upload-tip {
    color: var(--el-text-color-secondary);
    font-size: 12px;
    line-height: 16px;
    margin-top: 6px;
}

/* 拖拽框在弹窗里更紧凑些 */
:deep(.el-upload) {
    display: inline-block;
}

:deep(.el-upload-dragger) {
    width: 112px;
    height: 112px;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
}

:deep(.el-upload-dragger .el-icon) {
    font-size: 22px;
    margin: 0;
}

.upload-plus-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
}

.upload-plus-caption {
    font-size: 12px;
    line-height: 16px;
    color: var(--el-text-color-secondary);
    user-select: none;
}

.upload-row {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    flex-wrap: wrap;
}

.upload-preview-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.upload-preview-item {
    position: relative;
    width: 112px;
    height: 112px;
}

.upload-preview-img {
    width: 112px;
    height: 112px;
    border-radius: 6px;
    overflow: hidden;
    border: 1px solid var(--el-border-color-lighter);
}

.upload-preview-remove {
    position: absolute;
    top: -10px;
    right: -10px;
    padding: 0;
    width: 22px;
    height: 22px;
}
</style>
