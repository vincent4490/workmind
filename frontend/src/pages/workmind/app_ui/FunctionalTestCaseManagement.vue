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
                <el-upload
                    :action="uploadAction"
                    :headers="uploadHeaders"
                    :data="uploadData"
                    :before-upload="beforeUpload"
                    :on-success="handleImportSuccess"
                    :on-error="handleImportError"
                    :show-file-list="false"
                    accept=".xmind,.xls,.xlsx,.csv"
                    style="display: inline-block; margin-left: 10px;"
                >
                    <el-button
                        type="success"
                        :icon="Upload"
                    >
                        导入用例
                    </el-button>
                </el-upload>
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
                    <el-select
                        v-model="searchForm.requirement_name"
                        placeholder="请选择需求名称"
                        filterable
                        clearable
                        style="width: 200px;"
                        @change="loadCases"
                    >
                        <el-option
                            v-for="item in requirementOptions"
                            :key="item"
                            :label="item"
                            :value="item"
                        />
                    </el-select>
                </el-form-item>
                <el-form-item label="标签">
                    <el-select
                        v-model="searchForm.tag"
                        placeholder="请选择标签"
                        clearable
                        style="width: 150px;"
                        @change="loadCases"
                    >
                        <el-option label="回归" value="回归" />
                        <el-option label="冒烟" value="冒烟" />
                    </el-select>
                </el-form-item>
                <el-form-item label="优先级">
                    <el-select
                        v-model="searchForm.priority"
                        placeholder="请选择优先级"
                        clearable
                        style="width: 150px;"
                        @change="loadCases"
                    >
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
            <el-table-column prop="requirement_name" label="需求名称" min-width="150" />
            <el-table-column prop="feature_name" label="功能模块" min-width="150" />
            <el-table-column prop="name" label="用例名称" min-width="200" />
            <el-table-column prop="tags" label="标签" min-width="150">
                <template #default="scope">
                    <el-tag
                        v-for="tag in scope.row.tags"
                        :key="tag"
                        size="small"
                        style="margin-right: 5px;"
                    >
                        {{ tag }}
                    </el-tag>
                </template>
            </el-table-column>
            <el-table-column prop="priority" label="优先级" width="100">
                <template #default="scope">
                    <el-tag
                        :type="getPriorityType(scope.row.priority)"
                        size="small"
                    >
                        {{ scope.row.priority }}
                    </el-tag>
                </template>
            </el-table-column>
            <el-table-column prop="preconditions" label="前置条件" min-width="200" />
            <el-table-column prop="test_steps" label="操作步骤" min-width="300" show-overflow-tooltip>
                <template #default="scope">
                    <div v-if="scope.row.test_steps && scope.row.test_steps.length > 0">
                        <div
                            v-for="(step, index) in scope.row.test_steps"
                            :key="index"
                            style="margin-bottom: 5px;"
                        >
                            <span style="color: #909399; font-size: 12px;">步骤{{ index + 1 }}：</span>
                            <span>{{ step.step || '-' }}</span>
                        </div>
                    </div>
                    <span v-else>-</span>
                </template>
            </el-table-column>
            <el-table-column prop="expected_results" label="预期结果" min-width="300" show-overflow-tooltip>
                <template #default="scope">
                    <div v-if="scope.row.test_steps && scope.row.test_steps.length > 0">
                        <div
                            v-for="(step, index) in scope.row.test_steps"
                            :key="index"
                            style="margin-bottom: 5px; color: #67c23a;"
                        >
                            <span style="color: #909399; font-size: 12px;">预期结果{{ index + 1 }}：</span>
                            <span>{{ step.expected_result || '-' }}</span>
                        </div>
                    </div>
                    <span v-else>-</span>
                </template>
            </el-table-column>
            <el-table-column prop="created_by_username" label="创建人" width="120" />
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
            @close="resetForm"
        >
            <el-form
                ref="caseForm"
                :model="caseFormData"
                :rules="caseRules"
                label-width="120px"
            >
                <el-form-item label="需求名称" prop="requirement_name">
                    <el-select
                        v-model="caseFormData.requirement_name"
                        placeholder="请选择需求名称"
                        filterable
                        clearable
                        style="width: 100%;"
                    >
                        <el-option
                            v-for="item in requirementOptions"
                            :key="item"
                            :label="item"
                            :value="item"
                        />
                    </el-select>
                </el-form-item>
                <el-form-item label="功能模块" prop="feature_name">
                    <el-input
                        v-model="caseFormData.feature_name"
                        placeholder="请输入功能模块"
                        maxlength="200"
                        show-word-limit
                    />
                </el-form-item>
                <el-form-item label="用例名称" prop="name">
                    <el-input
                        v-model="caseFormData.name"
                        placeholder="请输入用例名称"
                        maxlength="200"
                        show-word-limit
                    />
                </el-form-item>
                <el-form-item label="前置条件" prop="preconditions">
                    <el-input
                        v-model="caseFormData.preconditions"
                        type="textarea"
                        :rows="2"
                        placeholder="请输入前置条件"
                    />
                </el-form-item>
                <el-form-item label="操作步骤" prop="test_steps">
                    <div v-for="(step, index) in caseFormData.test_steps" :key="index" style="margin-bottom: 15px; padding: 10px; border: 1px solid #e4e7ed; border-radius: 4px;">
                        <div style="margin-bottom: 8px; font-weight: bold; color: #606266;">
                            步骤 {{ index + 1 }}
                        </div>
                        <el-form-item :label="'操作步骤' + (index + 1)" style="margin-bottom: 10px;">
                            <el-input
                                v-model="step.step"
                                type="textarea"
                                :rows="2"
                                placeholder="请输入操作步骤"
                            />
                        </el-form-item>
                        <el-form-item :label="'预期结果' + (index + 1)">
                            <el-input
                                v-model="step.expected_result"
                                type="textarea"
                                :rows="2"
                                placeholder="请输入预期结果"
                            />
                        </el-form-item>
                        <el-button
                            v-if="caseFormData.test_steps.length > 1"
                            link
                            :icon="Delete"
                            style="color: #f56c6c;"
                            @click="removeStep(index)"
                        >
                            删除步骤
                        </el-button>
                    </div>
                    <el-button
                        link
                        :icon="Plus"
                        @click="addStep"
                    >
                        添加步骤
                    </el-button>
                </el-form-item>
                <el-form-item label="优先级" prop="priority">
                    <el-select v-model="caseFormData.priority" placeholder="请选择优先级" style="width: 200px;">
                        <el-option label="P0-最高优先级" value="P0" />
                        <el-option label="P1-高优先级" value="P1" />
                        <el-option label="P2-中优先级" value="P2" />
                        <el-option label="P3-低优先级" value="P3" />
                    </el-select>
                </el-form-item>
                <el-form-item label="标签" prop="tags">
                    <el-select
                        v-model="caseFormData.tags"
                        multiple
                        collapse-tags
                        placeholder="请选择标签"
                        style="width: 200px;"
                    >
                        <el-option label="回归" value="回归" />
                        <el-option label="冒烟" value="冒烟" />
                    </el-select>
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
                        <span class="detail-line-value">{{ detailCase.requirement_name || '-' }}</span>
                    </div>
                </el-form-item>
                <el-form-item label="">
                    <div class="detail-line">
                        <span class="detail-line-label">功能模块：</span>
                        <span class="detail-line-value">{{ detailCase.feature_name || '-' }}</span>
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
                        <span class="detail-line-value multiline">{{ detailCase.preconditions || '-' }}</span>
                    </div>
                </el-form-item>
                <el-form-item label="">
                    <div class="detail-section-title">操作步骤</div>
                    <div v-if="detailCase.test_steps && detailCase.test_steps.length">
                        <div v-for="(step, index) in detailCase.test_steps" :key="index" class="detail-step">
                            <div class="detail-step-line">
                                <span class="detail-step-label">步骤{{ index + 1 }}：</span>
                                <span class="detail-step-content">{{ step.step || '-' }}</span>
                            </div>
                            <div class="detail-step-line">
                                <span class="detail-step-label">预期结果{{ index + 1 }}：</span>
                                <span class="detail-step-expected">{{ step.expected_result || '-' }}</span>
                            </div>
                        </div>
                    </div>
                    <span v-else>-</span>
                </el-form-item>
                <el-form-item label="">
                    <div class="detail-line">
                        <span class="detail-line-label">优先级：</span>
                        <el-tag :type="getPriorityType(detailCase.priority)" size="small">
                            {{ detailCase.priority || '-' }}
                        </el-tag>
                    </div>
                </el-form-item>
                <el-form-item label="">
                    <div class="detail-line">
                        <span class="detail-line-label">标签：</span>
                        <span v-if="detailCase.tags && detailCase.tags.length">
                            <el-tag
                                v-for="tag in detailCase.tags"
                                :key="tag"
                                size="small"
                                style="margin-right: 5px;"
                            >
                                {{ tag }}
                            </el-tag>
                        </span>
                        <span v-else>-</span>
                    </div>
                </el-form-item>
                <el-form-item label="">
                    <div class="detail-line">
                        <span class="detail-line-label">创建人：</span>
                        <span class="detail-line-value">{{ detailCase.created_by_username || '-' }}</span>
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

    </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useStore } from 'vuex'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Upload, Download, Refresh, Search, Delete, ArrowDown } from '@element-plus/icons-vue'
import {
    getFunctionalCases,
    getFunctionalRequirements,
    createFunctionalCase,
    updateFunctionalCase,
    deleteFunctionalCase,
    importFunctionalCases,
    exportFunctionalCases
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
    requirement_name: '',
    tag: '',
    priority: ''
})

const dialogVisible = ref(false)
const dialogTitle = ref('新建用例')
const isEdit = ref(false)
const detailDialogVisible = ref(false)
const detailCase = ref({})
const requirementOptions = ref([])

const caseFormData = ref({
    requirement_name: '',
    feature_name: '',
    name: '',
    preconditions: '',
    test_steps: [{ step: '', expected_result: '' }],
    priority: 'P2',
    tags: []
})

const caseRules = {
    requirement_name: [
        { required: true, message: '请输入需求名称', trigger: 'blur' }
    ],
    feature_name: [
        { required: true, message: '请输入功能模块', trigger: 'blur' }
    ],
    name: [
        { required: true, message: '请输入用例名称', trigger: 'blur' }
    ],
    priority: [
        { required: true, message: '请选择优先级', trigger: 'change' }
    ]
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

// 方法
const getDefaultForm = () => ({
    requirement_name: '',
    feature_name: '',
    name: '',
    preconditions: '',
    test_steps: [{ step: '', expected_result: '' }],
    priority: 'P2',
    tags: []
})

const loadRequirements = () => {
    const params = {
        page: 1,
        page_size: 1000
    }
    getFunctionalRequirements(params).then(res => {
        if (res.code === 0) {
            const list = res.data.results || res.data || []
            requirementOptions.value = list.map(item => item.name).filter(Boolean)
        } else {
            requirementOptions.value = []
        }
    }).catch(() => {
        requirementOptions.value = []
    })
}

const loadCases = () => {
    loading.value = true
    const params = {
        page: currentPage.value,
        page_size: pageSize.value
    }
    if (searchForm.value.requirement_name) {
        params.requirement_name = searchForm.value.requirement_name
    }
    if (searchForm.value.tag) {
        params.tag = searchForm.value.tag
    }
    if (searchForm.value.priority) {
        params.priority = searchForm.value.priority
    }
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
    searchForm.value = {
        requirement_name: '',
        tag: '',
        priority: ''
    }
    currentPage.value = 1
    loadCases()
}

const handleExport = (format) => {
    const params = {
        file_format: format
    }
    
    if (searchForm.value.requirement_name) {
        params.requirement_name = searchForm.value.requirement_name
    }
    if (searchForm.value.tag) {
        params.tag = searchForm.value.tag
    }
    if (searchForm.value.priority) {
        params.priority = searchForm.value.priority
    }
    
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
    loadRequirements()
}

const editCase = (row) => {
    dialogTitle.value = '编辑用例'
    isEdit.value = true
    let testSteps = row.test_steps && row.test_steps.length > 0 ? row.test_steps : [{ step: '', expected_result: '' }]
    testSteps = testSteps.map(step => ({
        step: step.step || '',
        expected_result: step.expected_result || step.expected || ''
    }))
    caseFormData.value = {
        id: row.id,
        requirement_name: row.requirement_name || '',
        feature_name: row.feature_name || '',
        name: row.name,
        preconditions: row.preconditions || '',
        test_steps: testSteps,
        priority: row.priority || 'P2',
        tags: row.tags || []
    }
    dialogVisible.value = true
    loadRequirements()
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
        const params = {
            ...caseFormData.value
        }
        const promise = isEdit.value
            ? updateFunctionalCase(caseFormData.value.id, params)
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

const addStep = () => {
    caseFormData.value.test_steps.push({ step: '', expected_result: '' })
}

const removeStep = (index) => {
    caseFormData.value.test_steps.splice(index, 1)
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
    loadRequirements()
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

