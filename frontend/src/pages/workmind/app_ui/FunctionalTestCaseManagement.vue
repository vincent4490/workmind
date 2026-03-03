<template>
    <div class="functional-test-case-management">
        <div class="case-header">
            <h3>功能测试用例管理</h3>
            <div class="case-actions">
                <el-button
                    type="primary"
                    :icon="Plus"
                    @click="showAddDialog"
                >
                    新建用例
                </el-button>
                <el-button type="success" :icon="Upload" @click="showImportManualDialog = true">
                    导入用例
                </el-button>
                <el-button type="warning" @click="showImportAiDialog = true">
                    从 AI 导入
                </el-button>
                <el-dropdown @command="handleExport">
                    <el-button type="warning" :icon="Download">
                        导出用例
                        <el-icon class="el-icon--right"><ArrowDown /></el-icon>
                    </el-button>
                    <template #dropdown>
                        <el-dropdown-menu>
                            <el-dropdown-item command="xlsx">导出为 Excel (.xlsx)</el-dropdown-item>
                            <el-dropdown-item command="xmind">导出为 XMind (.xmind)</el-dropdown-item>
                        </el-dropdown-menu>
                    </template>
                </el-dropdown>
                <el-button
                    type="info"
                    :icon="Refresh"
                    :loading="loading"
                    @click="loadCases"
                >
                    刷新
                </el-button>
            </div>
        </div>

        <!-- 搜索和筛选 -->
        <el-card class="filter-card" style="margin-top: 20px;">
            <el-form :inline="true" size="small">
                <el-form-item label="需求名称">
                    <el-input v-model="searchForm.title" placeholder="需求名称" clearable style="width: 160px;" @keyup.enter="loadCases" />
                </el-form-item>
                <el-form-item label="模块名称">
                    <el-input v-model="searchForm.module_name" placeholder="模块名称" clearable style="width: 140px;" />
                </el-form-item>
                <el-form-item label="功能点">
                    <el-input v-model="searchForm.function_name" placeholder="功能点" clearable style="width: 140px;" />
                </el-form-item>
                <el-form-item label="优先级">
                    <el-select v-model="searchForm.priority" placeholder="优先级" clearable style="width: 100px;" @change="loadCases">
                        <el-option label="P0" value="P0" />
                        <el-option label="P1" value="P1" />
                        <el-option label="P2" value="P2" />
                        <el-option label="P3" value="P3" />
                    </el-select>
                </el-form-item>
                <el-form-item>
                    <el-button type="primary" :icon="Search" @click="loadCases">搜索</el-button>
                    <el-button :icon="Refresh" @click="resetSearch">重置</el-button>
                </el-form-item>
            </el-form>
        </el-card>

        <!-- 用例列表 -->
        <el-table
            v-loading="loading"
            :data="caseList"
            style="width: 100%; margin-top: 20px;"
            :empty-text="emptyText"
        >
            <el-table-column type="index" label="序号" width="60" />
            <el-table-column prop="title" label="需求名称" min-width="140" show-overflow-tooltip />
            <el-table-column prop="module_name" label="模块名称" width="120" show-overflow-tooltip />
            <el-table-column prop="function_name" label="功能点" width="120" show-overflow-tooltip />
            <el-table-column prop="name" label="用例名称" min-width="160" show-overflow-tooltip />
            <el-table-column prop="priority" label="优先级" width="80">
                <template #default="scope">
                    <el-tag :type="getPriorityType(scope.row.priority)" size="small">{{ scope.row.priority }}</el-tag>
                </template>
            </el-table-column>
            <el-table-column prop="precondition" label="前置条件" min-width="160" show-overflow-tooltip />
            <el-table-column prop="steps" label="测试步骤" min-width="200" show-overflow-tooltip />
            <el-table-column prop="expected" label="预期结果" min-width="200" show-overflow-tooltip />
            <el-table-column prop="created_by_name" label="创建人" width="120">
                <template #default="scope">
                    {{ scope.row.created_by_name || scope.row.created_by_username || '-' }}
                </template>
            </el-table-column>
            <el-table-column prop="updated_at" label="更新时间" width="180">
                <template #default="scope">
                    {{ formatDate(scope.row.updated_at) }}
                </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
                <template #default="scope">
                    <el-button
                        link
                        size="small"
                        @click="viewCase(scope.row)"
                    >
                        详情
                    </el-button>
                    <el-button
                        link
                        size="small"
                        @click="editCase(scope.row)"
                    >
                        编辑
                    </el-button>
                    <el-button
                        link
                        size="small"
                        style="color: #f56c6c;"
                        @click="deleteCase(scope.row)"
                    >
                        删除
                    </el-button>
                </template>
            </el-table-column>
        </el-table>

        <!-- 分页 -->
        <el-pagination
            v-show="total > 0"
            :current-page="currentPage"
            :page-sizes="[10, 20, 30, 50]"
            :page-size="pageSize"
            :total="total"
            layout="total, sizes, prev, pager, next, jumper"
            style="margin-top: 20px; text-align: right;"
            @size-change="handleSizeChange"
            @current-change="handlePageChange"
        />

        <!-- 添加/编辑用例对话框 -->
        <el-dialog
            :title="dialogTitle"
            v-model="dialogVisible"
            width="800px"
            @open="loadRequirements"
            @close="resetForm"
        >
            <el-form
                ref="caseForm"
                :model="caseFormData"
                :rules="caseRules"
                label-width="120px"
            >
                <el-form-item label="需求名称" prop="title">
                    <el-select
                        v-model="caseFormData.title"
                        placeholder="请选择需求名称"
                        filterable
                        clearable
                        style="width: 100%;"
                    >
                        <el-option
                            v-for="item in requirementList"
                            :key="item.id"
                            :label="item.name"
                            :value="item.name"
                        />
                    </el-select>
                </el-form-item>
                <el-form-item label="模块名称" prop="module_name">
                    <el-input v-model="caseFormData.module_name" placeholder="模块名称" maxlength="200" />
                </el-form-item>
                <el-form-item label="功能点名称" prop="function_name">
                    <el-input v-model="caseFormData.function_name" placeholder="功能点名称" maxlength="200" />
                </el-form-item>
                <el-form-item label="用例名称" prop="name">
                    <el-input v-model="caseFormData.name" placeholder="用例名称" maxlength="200" show-word-limit />
                </el-form-item>
                <el-form-item label="优先级" prop="priority">
                    <el-select v-model="caseFormData.priority" placeholder="请选择优先级" style="width: 200px;">
                        <el-option label="P0-最高优先级" value="P0" />
                        <el-option label="P1-高优先级" value="P1" />
                        <el-option label="P2-中优先级" value="P2" />
                        <el-option label="P3-低优先级" value="P3" />
                    </el-select>
                </el-form-item>
                <el-form-item label="前置条件" prop="precondition">
                    <el-input v-model="caseFormData.precondition" type="textarea" :rows="2" placeholder="前置条件" />
                </el-form-item>
                <el-form-item label="测试步骤" prop="steps">
                    <el-input v-model="caseFormData.steps" type="textarea" :rows="4" placeholder="1. 步骤一&#10;2. 步骤二" />
                </el-form-item>
                <el-form-item label="预期结果" prop="expected">
                    <el-input v-model="caseFormData.expected" type="textarea" :rows="3" placeholder="预期结果" />
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="dialogVisible = false">取消</el-button>
                <el-button type="primary" :loading="saving" @click="saveCase">保存</el-button>
            </template>
        </el-dialog>

        <!-- 用例详情对话框（布局与编辑一致） -->
        <el-dialog
            title="用例详情"
            v-model="detailDialogVisible"
            width="900px"
            class="detail-dialog"
        >
            <el-form
                :model="detailCase"
                label-width="0px"
            >
                <el-form-item label="">
                    <div class="detail-line">
                        <span class="detail-line-label">需求名称：</span>
                        <span class="detail-line-value">{{ detailCase.title || '-' }}</span>
                    </div>
                </el-form-item>
                <el-form-item label="">
                    <div class="detail-line">
                        <span class="detail-line-label">模块名称：</span>
                        <span class="detail-line-value">{{ detailCase.module_name || '-' }}</span>
                    </div>
                </el-form-item>
                <el-form-item label="">
                    <div class="detail-line">
                        <span class="detail-line-label">功能点：</span>
                        <span class="detail-line-value">{{ detailCase.function_name || '-' }}</span>
                    </div>
                </el-form-item>
                <el-form-item label="">
                    <div class="detail-line">
                        <span class="detail-line-label">用例名称：</span>
                        <span class="detail-line-value">{{ detailCase.name || '-' }}</span>
                    </div>
                </el-form-item>
                <el-form-item label="">
                    <div class="detail-line">
                        <span class="detail-line-label">前置条件：</span>
                        <span class="detail-line-value multiline">{{ detailCase.precondition || '-' }}</span>
                    </div>
                </el-form-item>
                <el-form-item label="">
                    <div class="detail-section-title">测试步骤</div>
                    <span class="detail-line-value multiline">{{ detailCase.steps || '-' }}</span>
                </el-form-item>
                <el-form-item label="">
                    <div class="detail-section-title">预期结果</div>
                    <span class="detail-line-value multiline">{{ detailCase.expected || '-' }}</span>
                </el-form-item>
                <el-form-item label="">
                    <div class="detail-line">
                        <span class="detail-line-label">优先级：</span>
                        <el-tag :type="getPriorityType(detailCase.priority)" size="small">{{ detailCase.priority || '-' }}</el-tag>
                    </div>
                </el-form-item>
                <el-form-item label="">
                    <div class="detail-line">
                        <span class="detail-line-label">来源：</span>
                        <span class="detail-line-value">{{ detailCase.source === 'ai' ? 'AI导入' : '手动' }}</span>
                    </div>
                </el-form-item>
                <el-form-item label="">
                    <div class="detail-line">
                        <span class="detail-line-label">创建人：</span>
                        <span class="detail-line-value">{{ detailCase.created_by_name || detailCase.created_by_username || '-' }}</span>
                    </div>
                </el-form-item>
                <el-form-item label="">
                    <div class="detail-line">
                        <span class="detail-line-label">更新时间：</span>
                        <span class="detail-line-value">{{ formatDate(detailCase.updated_at) }}</span>
                    </div>
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="detailDialogVisible = false">关闭</el-button>
            </template>
        </el-dialog>

        <!-- 手动导入用例 -->
        <el-dialog title="手动导入用例" v-model="showImportManualDialog" width="520px" @open="onImportManualDialogOpen" @close="selectedRequirementIdForManual = null">
            <el-form label-width="100px">
                <el-form-item label="需求名称" required>
                    <el-select
                        v-model="selectedRequirementIdForManual"
                        placeholder="请先选择需求名称"
                        filterable
                        style="width: 100%;"
                    >
                        <el-option
                            v-for="item in requirementList"
                            :key="item.id"
                            :label="item.name"
                            :value="item.id"
                        />
                    </el-select>
                </el-form-item>
                <el-form-item label="选择文件" required>
                    <el-upload
                        :action="uploadAction"
                        :headers="uploadHeaders"
                        :data="manualImportUploadData"
                        :before-upload="beforeManualUpload"
                        :on-success="handleManualImportSuccess"
                        :on-error="handleImportError"
                        :show-file-list="false"
                        accept=".xmind,.xls,.xlsx,.csv"
                    >
                        <el-button type="primary" :icon="Upload">选择 XMind / Excel / CSV 文件</el-button>
                    </el-upload>
                </el-form-item>
            </el-form>
        </el-dialog>

        <!-- 从 AI 导入 -->
        <el-dialog title="从 AI 导入用例" v-model="showImportAiDialog" width="520px" @open="onImportAiDialogOpen" @close="selectedRequirementId = null">
            <el-form label-width="100px">
                <el-form-item label="需求名称" required>
                    <el-select
                        v-model="selectedRequirementId"
                        placeholder="请选择需求名称"
                        filterable
                        style="width: 100%;"
                    >
                        <el-option
                            v-for="item in requirementList"
                            :key="item.id"
                            :label="item.name"
                            :value="item.id"
                        />
                    </el-select>
                </el-form-item>
                <el-form-item label="选择生成记录" required>
                    <el-select
                        v-model="selectedAiGenerationId"
                        placeholder="请选择一条 AI 生成记录"
                        filterable
                        style="width: 100%;"
                    >
                        <el-option
                            v-for="item in aiGenerations"
                            :key="item.id"
                            :label="`#${item.id} ${(item.requirement || '').slice(0, 40)}... (${item.case_count || 0} 条)`"
                            :value="item.id"
                        />
                    </el-select>
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="showImportAiDialog = false">取消</el-button>
                <el-button type="primary" :loading="importAiLoading" @click="confirmImportFromAi">确定导入</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useStore } from 'vuex'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Upload, Download, Refresh, Search, Delete, ArrowDown } from '@element-plus/icons-vue'
import {
    getFunctionalCases,
    createFunctionalCase,
    updateFunctionalCase,
    deleteFunctionalCase,
    exportFunctionalCases,
    importFunctionalCasesFromAi,
    getAiTestcaseGenerations,
    getFunctionalRequirements
} from '@/restful/api'

const store = useStore()

// refs
const caseForm = ref(null)

// 响应式数据
const loading = ref(false)
const saving = ref(false)
const caseList = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const emptyText = ref('暂无数据')

const searchForm = ref({
    title: '',
    module_name: '',
    function_name: '',
    priority: '',
    source: ''
})

const dialogVisible = ref(false)
const dialogTitle = ref('新建用例')
const isEdit = ref(false)
const detailDialogVisible = ref(false)
const detailCase = ref({})
const showImportManualDialog = ref(false)
const selectedRequirementIdForManual = ref(null)
const showImportAiDialog = ref(false)
const selectedRequirementId = ref(null)
const selectedAiGenerationId = ref(null)
const requirementList = ref([])
const aiGenerations = ref([])
const importAiLoading = ref(false)

const caseFormData = ref({
    title: '',
    module_name: '',
    function_name: '',
    name: '',
    priority: 'P2',
    precondition: '',
    steps: '',
    expected: ''
})

const caseRules = {
    name: [{ required: true, message: '请输入用例名称', trigger: 'blur' }],
    priority: [{ required: true, message: '请选择优先级', trigger: 'change' }]
}

// 计算属性 - 上传配置
const uploadAction = computed(() => {
    const baseUrl = import.meta.env.VITE_BASE_URL || ''
    return baseUrl + '/api/ui_test/functional-cases/import/'
})

const uploadHeaders = computed(() => ({
    'Authorization': 'Bearer ' + store.state.token
}))

const uploadData = computed(() => ({}))

const manualImportUploadData = computed(() => ({
    requirement_id: selectedRequirementIdForManual.value || ''
}))

// 方法
const getDefaultForm = () => ({
    title: '',
    module_name: '',
    function_name: '',
    name: '',
    priority: 'P2',
    precondition: '',
    steps: '',
    expected: ''
})

const onImportManualDialogOpen = () => {
    loadRequirements()
}

const onImportAiDialogOpen = () => {
    loadAiGenerations()
    loadRequirements()
}

const loadRequirements = () => {
    getFunctionalRequirements({ page: 1, page_size: 500 }).then(res => {
        const list = res.results || res.data?.results || res.data || []
        requirementList.value = Array.isArray(list) ? list : []
    }).catch(() => { requirementList.value = [] })
}

const loadAiGenerations = () => {
    getAiTestcaseGenerations({ page_size: 50, status: 'success' }).then(res => {
        const list = res.results || res.data?.results || res.data || []
        aiGenerations.value = Array.isArray(list) ? list : []
        if (!selectedAiGenerationId.value && aiGenerations.value.length) {
            selectedAiGenerationId.value = aiGenerations.value[0].id
        }
    }).catch(() => { aiGenerations.value = [] })
}

const confirmImportFromAi = () => {
    if (!selectedRequirementId.value) {
        ElMessage.warning('请选择需求名称')
        return
    }
    if (!selectedAiGenerationId.value) {
        ElMessage.warning('请选择一条 AI 生成记录')
        return
    }
    importAiLoading.value = true
    importFunctionalCasesFromAi({
        ai_generation_id: selectedAiGenerationId.value,
        requirement_id: selectedRequirementId.value
    }).then(res => {
        if (res.code === 0) {
            ElMessage.success(res.msg || '导入成功')
            showImportAiDialog.value = false
            loadCases()
        } else {
            ElMessage.error(res.msg || '导入失败')
        }
    }).catch(err => ElMessage.error(err.message || '导入失败')).finally(() => { importAiLoading.value = false })
}

const loadCases = () => {
    loading.value = true
    const params = {
        page: currentPage.value,
        page_size: pageSize.value
    }
    if (searchForm.value.title) params.title = searchForm.value.title
    if (searchForm.value.module_name) params.module_name = searchForm.value.module_name
    if (searchForm.value.function_name) params.function_name = searchForm.value.function_name
    if (searchForm.value.priority) params.priority = searchForm.value.priority
    if (searchForm.value.source) params.source = searchForm.value.source
    getFunctionalCases(params).then(res => {
        if (res.code === 0) {
            if (res.data.results) {
                caseList.value = res.data.results
                total.value = res.data.count
            } else {
                caseList.value = res.data
                total.value = res.data.length
            }
        } else {
            ElMessage.error(res.msg || '获取用例列表失败')
            caseList.value = []
            total.value = 0
        }
    }).catch(err => {
        ElMessage.error('获取用例列表失败：' + (err.message || '未知错误'))
        caseList.value = []
        total.value = 0
    }).finally(() => {
        loading.value = false
    })
}

const resetSearch = () => {
    searchForm.value = { title: '', module_name: '', function_name: '', priority: '', source: '' }
    currentPage.value = 1
    loadCases()
}

const handleExport = (format) => {
    const params = {
        file_format: format
    }
    
    if (searchForm.value.title) params.title = searchForm.value.title
    if (searchForm.value.module_name) params.module_name = searchForm.value.module_name
    if (searchForm.value.function_name) params.function_name = searchForm.value.function_name
    if (searchForm.value.priority) params.priority = searchForm.value.priority
    if (searchForm.value.source) params.source = searchForm.value.source

    exportFunctionalCases(params).then(response => {
        let mimeType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        let defaultFilename = '功能测试用例.xlsx'
        if (format === 'xmind') {
            mimeType = 'application/x-xmind'
            defaultFilename = '功能测试用例.xmind'
        }
        
        const blob = new Blob([response.data], { type: mimeType })
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        
        const contentDisposition = response.headers['content-disposition']
        let filename = defaultFilename
        if (contentDisposition) {
            const utf8Match = contentDisposition.match(/filename\*\s*=\s*UTF-8''([^;]+)/i)
            if (utf8Match) {
                filename = decodeURIComponent(utf8Match[1])
            } else {
                const filenameMatch = contentDisposition.match(/filename="?([^";]+)"?/)
                if (filenameMatch) {
                    filename = decodeURIComponent(filenameMatch[1])
                }
            }
        }
        
        link.setAttribute('download', filename)
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.URL.revokeObjectURL(url)
        
        ElMessage.success('导出成功')
    }).catch(err => {
        ElMessage.error('导出失败：' + (err.message || '未知错误'))
    })
}

const viewCase = (row) => {
    detailCase.value = { ...row }
    detailDialogVisible.value = true
}

const showAddDialog = () => {
    dialogTitle.value = '新建用例'
    isEdit.value = false
    dialogVisible.value = true
}

const editCase = (row) => {
    dialogTitle.value = '编辑用例'
    isEdit.value = true
    caseFormData.value = {
        id: row.id,
        title: row.title || '',
        module_name: row.module_name || '',
        function_name: row.function_name || '',
        name: row.name,
        priority: row.priority || 'P2',
        precondition: row.precondition || '',
        steps: row.steps || '',
        expected: row.expected || ''
    }
    dialogVisible.value = true
}

const deleteCase = (row) => {
    ElMessageBox.confirm('确定要删除该用例吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
    }).then(() => {
        deleteFunctionalCase(row.id).then(res => {
            if (res.code === 0) {
                ElMessage.success('删除成功')
                loadCases()
            } else {
                ElMessage.error(res.msg || '删除失败')
            }
        }).catch(err => {
            ElMessage.error('删除失败：' + (err.message || '未知错误'))
        })
    }).catch(() => {})
}

const saveCase = () => {
    caseForm.value.validate(valid => {
        if (!valid) return
        saving.value = true
        const { id, ...rest } = caseFormData.value
        const params = {
            title: rest.title || '',
            module_name: rest.module_name || '',
            function_name: rest.function_name || '',
            name: rest.name,
            priority: rest.priority || 'P2',
            precondition: rest.precondition || '',
            steps: rest.steps || '',
            expected: rest.expected || '',
            source: 'manual'
        }
        const promise = isEdit.value
            ? updateFunctionalCase(id, params)
            : createFunctionalCase(params)
        promise.then(res => {
            if (res.code === 0) {
                ElMessage.success(isEdit.value ? '更新成功' : '创建成功')
                dialogVisible.value = false
                loadCases()
            } else {
                ElMessage.error(res.msg || '保存失败')
            }
        }).catch(err => {
            ElMessage.error('保存失败：' + (err.message || '未知错误'))
        }).finally(() => {
            saving.value = false
        })
    })
}

const resetForm = () => {
    if (caseForm.value) {
        caseForm.value.resetFields()
    }
    caseFormData.value = getDefaultForm()
    isEdit.value = false
}

const beforeUpload = (file) => {
    const isValidType = ['xmind', 'xls', 'xlsx', 'csv'].some(ext => file.name.toLowerCase().endsWith('.' + ext))
    if (!isValidType) {
        ElMessage.error('只能上传 XMind、Excel 或 CSV 文件！')
        return false
    }
    const isLt10M = file.size / 1024 / 1024 < 10
    if (!isLt10M) {
        ElMessage.error('文件大小不能超过 10MB！')
        return false
    }
    return true
}

const beforeManualUpload = (file) => {
    if (!selectedRequirementIdForManual.value) {
        ElMessage.warning('请先选择需求名称')
        return false
    }
    return beforeUpload(file)
}

const handleManualImportSuccess = (res) => {
    handleImportSuccess(res)
    showImportManualDialog.value = false
}

const handleImportSuccess = (res) => {
    if (res.code === 0) {
        ElMessage.success(res.msg || '导入成功')
        if (res.data) {
            const msg = `成功导入 ${res.data.created_count} 条用例`
            if (res.data.failed_count > 0) {
                ElMessage.warning(`${msg}，失败 ${res.data.failed_count} 条`)
            }
        }
        loadCases()
    } else {
        ElMessage.error(res.msg || '导入失败')
    }
}

const handleImportError = (err) => {
    ElMessage.error('导入失败：' + (err.message || '未知错误'))
}

const handleSizeChange = (val) => {
    pageSize.value = val
    currentPage.value = 1
    loadCases()
}

const handlePageChange = (val) => {
    currentPage.value = val
    loadCases()
}

const getPriorityType = (priority) => {
    const typeMap = {
        'P0': 'danger',
        'P1': 'warning',
        'P2': 'primary',
        'P3': 'info'
    }
    return typeMap[priority] || 'info'
}

const formatDate = (date) => {
    if (!date) return '-'
    return new Date(date).toLocaleString('zh-CN')
}

// 生命周期
onMounted(() => {
    loadCases()
})
</script>

<style scoped>
.functional-test-case-management {
    padding: 20px;
}

.functional-test-case-management :deep(.el-table__body-wrapper .cell) {
    white-space: normal;
    word-break: break-all;
    line-height: 20px;
}

.case-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}

.case-actions {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}

.case-header h3 {
    margin: 0;
}

.filter-card {
    margin-bottom: 20px;
}

.detail-step {
    margin-bottom: 12px;
    padding: 10px 12px;
    border: 1px solid #e4e7ed;
    border-radius: 4px;
    background: #fafafa;
}

.detail-step-line {
    display: flex;
    gap: 6px;
    align-items: flex-start;
    margin-bottom: 6px;
}

.detail-step-label {
    color: #909399;
    font-size: 12px;
    white-space: nowrap;
}

.detail-step-content {
    color: #303133;
    white-space: pre-wrap;
}

.detail-step-expected {
    color: #67c23a;
    white-space: pre-wrap;
}

.detail-line {
    display: flex;
    align-items: center;
    gap: 6px;
    min-height: 32px;
    padding: 10px 12px;
    border: 1px solid #e4e7ed;
    border-radius: 4px;
    background: #fafafa;
}

.detail-line-label {
    color: #909399;
    font-size: 12px;
    white-space: nowrap;
}

.detail-line-value {
    color: #303133;
    white-space: pre-wrap;
}

.detail-line-value.multiline {
    white-space: pre-wrap;
}

.detail-section-title {
    font-weight: bold;
    color: #606266;
    margin-bottom: 8px;
}
</style>

