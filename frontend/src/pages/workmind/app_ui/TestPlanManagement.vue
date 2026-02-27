<template>
    <div class="test-plan-management">
        <div class="plan-header">
            <h3>测试计划管理</h3>
            <div class="plan-actions">
                <el-button
                    type="primary"
                    :icon="Plus"
                    @click="showAddDialog"
                >
                    新建计划
                </el-button>
                <el-button
                    type="info"
                    :icon="Refresh"
                    :loading="loading"
                    @click="loadPlans"
                >
                    刷新
                </el-button>
            </div>
        </div>

        <!-- 计划列表 -->
        <el-table
            v-loading="loading"
            :data="planList"
            style="width: 100%; margin-top: 20px;"
            :empty-text="emptyText"
        >
            <el-table-column type="index" label="序号" width="150" />
            <el-table-column prop="name" label="计划名称" width="350" show-overflow-tooltip />
            <el-table-column prop="description" label="描述" width="450" show-overflow-tooltip />
            <el-table-column prop="case_count" label="用例数" width="230" />
            <el-table-column prop="created_by_username" label="创建人" width="250" />
            <el-table-column prop="updated_at" label="更新时间" width="300">
                <template #default="scope">
                    {{ formatDate(scope.row.updated_at) }}
                </template>
            </el-table-column>
            <el-table-column label="操作" width="300" fixed="right">
                <template #default="scope">
                    <el-button
                        link
                        size="small"
                        @click="manageCases(scope.row)"
                    >
                        管理用例
                    </el-button>
                    <el-button
                        link
                        size="small"
                        @click="executePlan(scope.row)"
                    >
                        执行计划
                    </el-button>
                    <el-button
                        link
                        size="small"
                        @click="editPlan(scope.row)"
                    >
                        编辑
                    </el-button>
                    <el-button
                        link
                        size="small"
                        style="color: #f56c6c;"
                        @click="deletePlan(scope.row)"
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

        <!-- 添加/编辑计划对话框 -->
        <el-dialog
            :title="dialogTitle"
            v-model="dialogVisible"
            width="600px"
            @close="resetForm"
        >
            <el-form
                ref="planForm"
                :model="planFormData"
                :rules="planRules"
                label-width="100px"
            >
                <el-form-item label="计划名称" prop="name">
                    <el-input
                        v-model="planFormData.name"
                        placeholder="请输入计划名称"
                        maxlength="200"
                        show-word-limit
                    />
                </el-form-item>
                <el-form-item label="计划描述" prop="description">
                    <el-input
                        v-model="planFormData.description"
                        type="textarea"
                        :rows="4"
                        placeholder="请输入计划描述"
                    />
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="dialogVisible = false">取消</el-button>
                <el-button type="primary" :loading="saving" @click="savePlan">保存</el-button>
            </template>
        </el-dialog>

        <!-- 管理用例对话框 -->
        <el-dialog
            title="管理测试计划用例"
            v-model="caseManageDialogVisible"
            width="1000px"
            @close="closeCaseManage"
        >
            <div style="margin-bottom: 20px;">
                <el-button
                    type="primary"
                    :icon="Plus"
                    @click="showAddCaseDialog"
                >
                    添加用例
                </el-button>
            </div>
            <el-table
                :data="planCaseList"
                style="width: 100%;"
                row-key="id"
            >
                <el-table-column type="index" label="序号" width="60" />
                <el-table-column prop="test_case_detail.requirement_name" label="需求名称" min-width="150" show-overflow-tooltip />
                <el-table-column prop="test_case_detail.feature_name" label="功能模块" min-width="150" show-overflow-tooltip />
                <el-table-column prop="test_case_detail.name" label="用例名称" min-width="200" />
                <el-table-column prop="test_case_detail.priority" label="优先级" width="100">
                    <template #default="scope">
                        <el-tag
                            :type="getPriorityType(scope.row.test_case_detail.priority)"
                            size="small"
                        >
                            {{ scope.row.test_case_detail.priority }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="操作" width="100">
                    <template #default="scope">
                        <el-button
                            link
                            size="small"
                            style="color: #f56c6c;"
                            @click="removeCase(scope.row)"
                        >
                            移除
                        </el-button>
                    </template>
                </el-table-column>
            </el-table>
            <template #footer>
                <el-button @click="caseManageDialogVisible = false">关闭</el-button>
            </template>
        </el-dialog>

        <!-- 添加用例对话框 -->
        <el-dialog
            title="添加用例到测试计划"
            v-model="addCaseDialogVisible"
            width="800px"
        >
            <el-form :inline="true" size="small" style="margin-bottom: 10px;">
                <el-form-item label="需求名称">
                    <el-select
                        v-model="addCaseSearch.requirement_name"
                        placeholder="请选择需求名称"
                        filterable
                        clearable
                        style="width: 200px;"
                    >
                        <el-option
                            v-for="item in requirementOptions"
                            :key="item"
                            :label="item"
                            :value="item"
                        />
                    </el-select>
                </el-form-item>
                <el-form-item>
                    <el-button type="primary" :icon="Search" @click="loadAvailableCases">搜索</el-button>
                    <el-button :icon="Refresh" @click="resetAddCaseSearch">重置</el-button>
                </el-form-item>
            </el-form>
            <el-table
                ref="caseTable"
                :data="availableCases"
                style="width: 100%;"
                @selection-change="handleCaseSelectionChange"
            >
                <el-table-column type="selection" width="55" />
            <el-table-column prop="requirement_name" label="需求名称" min-width="150" show-overflow-tooltip />
            <el-table-column prop="feature_name" label="功能模块" min-width="150" show-overflow-tooltip />
            <el-table-column prop="name" label="用例名称" min-width="200" />
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
            </el-table>
            <template #footer>
                <el-button @click="addCaseDialogVisible = false">取消</el-button>
                <el-button type="primary" :loading="addingCases" @click="confirmAddCases">确定</el-button>
            </template>
        </el-dialog>

    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import {
    getTestPlans,
    createTestPlan,
    updateTestPlan,
    deleteTestPlan,
    getPlanCases,
    addCasesToPlan,
    removeCaseFromPlan,
    getFunctionalCases,
    getFunctionalRequirements
} from '@/restful/api'

const router = useRouter()

// refs
const planForm = ref(null)
const caseTable = ref(null)

// 响应式数据
const loading = ref(false)
const saving = ref(false)
const addingCases = ref(false)
const planList = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const emptyText = ref('暂无数据')
const dialogVisible = ref(false)
const dialogTitle = ref('新建测试计划')
const isEdit = ref(false)

const planFormData = ref({
    name: '',
    description: ''
})

const planRules = {
    name: [
        { required: true, message: '请输入计划名称', trigger: 'blur' }
    ]
}

const caseManageDialogVisible = ref(false)
const currentPlan = ref(null)
const planCaseList = ref([])
const addCaseDialogVisible = ref(false)
const availableCases = ref([])
const selectedCases = ref([])
const requirementOptions = ref([])

const addCaseSearch = ref({
    requirement_name: ''
})

// 方法
const loadRequirementOptions = () => {
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

const loadPlans = () => {
    loading.value = true
    const params = {
        page: currentPage.value,
        page_size: pageSize.value
    }
    getTestPlans(params).then(res => {
        if (res.code === 0) {
            if (res.data.results) {
                planList.value = res.data.results
                total.value = res.data.count
            } else {
                planList.value = res.data
                total.value = res.data.length
            }
        } else {
            ElMessage.error(res.msg || '获取计划列表失败')
            planList.value = []
            total.value = 0
        }
    }).catch(err => {
        ElMessage.error('获取计划列表失败：' + (err.message || '未知错误'))
        planList.value = []
        total.value = 0
    }).finally(() => {
        loading.value = false
    })
}

const showAddDialog = () => {
    dialogTitle.value = '新建测试计划'
    isEdit.value = false
    dialogVisible.value = true
}

const editPlan = (row) => {
    dialogTitle.value = '编辑测试计划'
    isEdit.value = true
    planFormData.value = {
        id: row.id,
        name: row.name,
        description: row.description || ''
    }
    dialogVisible.value = true
}

const deletePlan = (row) => {
    ElMessageBox.confirm('确定要删除该测试计划吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
    }).then(() => {
        deleteTestPlan(row.id).then(res => {
            if (res.code === 0) {
                ElMessage.success('删除成功')
                loadPlans()
            } else {
                ElMessage.error(res.msg || '删除失败')
            }
        }).catch(err => {
            ElMessage.error('删除失败：' + (err.message || '未知错误'))
        })
    }).catch(() => {})
}

const savePlan = () => {
    planForm.value.validate(valid => {
        if (!valid) return
        saving.value = true
        const params = {
            ...planFormData.value
        }
        const promise = isEdit.value
            ? updateTestPlan(planFormData.value.id, params)
            : createTestPlan(params)
        promise.then(res => {
            if (res.code === 0) {
                ElMessage.success(isEdit.value ? '更新成功' : '创建成功')
                dialogVisible.value = false
                loadPlans()
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
    if (planForm.value) {
        planForm.value.resetFields()
    }
    planFormData.value = {
        name: '',
        description: ''
    }
    isEdit.value = false
}

const manageCases = (row) => {
    currentPlan.value = row
    caseManageDialogVisible.value = true
    loadPlanCases()
}

const loadPlanCases = () => {
    if (!currentPlan.value) return
    getPlanCases(currentPlan.value.id).then(res => {
        if (res.code === 0) {
            planCaseList.value = res.data || []
        } else {
            ElMessage.error(res.msg || '获取用例列表失败')
            planCaseList.value = []
        }
    }).catch(err => {
        ElMessage.error('获取用例列表失败：' + (err.message || '未知错误'))
        planCaseList.value = []
    })
}

const closeCaseManage = () => {
    currentPlan.value = null
    planCaseList.value = []
}

const showAddCaseDialog = () => {
    addCaseDialogVisible.value = true
    addCaseSearch.value = { requirement_name: '' }
    loadRequirementOptions()
    loadAvailableCases()
}

const resetAddCaseSearch = () => {
    addCaseSearch.value.requirement_name = ''
    loadAvailableCases()
}

const loadAvailableCases = () => {
    const params = {}
    if (addCaseSearch.value.requirement_name) {
        params.requirement_name = addCaseSearch.value.requirement_name
    }
    getFunctionalCases(params).then(res => {
        if (res.code === 0) {
            const allCases = res.data.results || res.data || []
            const planCaseIds = planCaseList.value.map(pc => pc.test_case_detail.id)
            availableCases.value = allCases.filter(c => !planCaseIds.includes(c.id))
        } else {
            ElMessage.error(res.msg || '获取用例列表失败')
            availableCases.value = []
        }
    }).catch(err => {
        ElMessage.error('获取用例列表失败：' + (err.message || '未知错误'))
        availableCases.value = []
    })
}

const handleCaseSelectionChange = (selection) => {
    selectedCases.value = selection
}

const confirmAddCases = () => {
    if (selectedCases.value.length === 0) {
        ElMessage.warning('请选择要添加的用例')
        return
    }
    addingCases.value = true
    const caseIds = selectedCases.value.map(c => c.id)
    addCasesToPlan(currentPlan.value.id, caseIds).then(res => {
        if (res.code === 0) {
            ElMessage.success(res.msg || '添加成功')
            addCaseDialogVisible.value = false
            selectedCases.value = []
            loadPlanCases()
            loadPlans()
        } else {
            ElMessage.error(res.msg || '添加失败')
        }
    }).catch(err => {
        ElMessage.error('添加失败：' + (err.message || '未知错误'))
    }).finally(() => {
        addingCases.value = false
    })
}

const removeCase = (row) => {
    ElMessageBox.confirm('确定要从计划中移除该用例吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
    }).then(() => {
        removeCaseFromPlan(currentPlan.value.id, row.test_case_detail.id).then(res => {
            if (res.code === 0) {
                ElMessage.success('移除成功')
                loadPlanCases()
                loadPlans()
            } else {
                ElMessage.error(res.msg || '移除失败')
            }
        }).catch(err => {
            ElMessage.error('移除失败：' + (err.message || '未知错误'))
        })
    }).catch(() => {})
}

const executePlan = (row) => {
    if (row.case_count === 0) {
        ElMessage.warning('测试计划中没有用例，无法执行')
        return
    }
    router.push({
        name: 'TestPlanExecute',
        params: {
            planId: row.id
        },
        query: {
            planName: row.name
        }
    })
}

const handleSizeChange = (val) => {
    pageSize.value = val
    currentPage.value = 1
    loadPlans()
}

const handlePageChange = (val) => {
    currentPage.value = val
    loadPlans()
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
    loadPlans()
})
</script>

<style scoped>
.test-plan-management {
    padding: 20px;
}

.plan-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}

.plan-header h3 {
    margin: 0;
}
</style>

