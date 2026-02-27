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
                v-loading="loading"
                :data="caseList"
                style="width: 100%;"
            >
                <el-table-column type="index" label="序号" width="60" />
                <el-table-column prop="test_case_detail.requirement_name" label="需求名称" min-width="150" />
                <el-table-column prop="test_case_detail.feature_name" label="功能模块" min-width="150" />
                <el-table-column prop="test_case_detail.name" label="用例名称" min-width="200" />
                <el-table-column prop="test_case_detail.priority" label="优先级" width="100">
                    <template #default="scope">
                        <el-tag
                            :type="getPriorityType(scope.row.test_case_detail?.priority)"
                            size="small"
                        >
                            {{ scope.row.test_case_detail?.priority || '-' }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="执行状态" width="120">
                    <template #default="scope">
                        <el-tag
                            :type="getStatusType(scope.row.status)"
                            size="small"
                        >
                            {{ getStatusText(scope.row.status) }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="操作" width="150">
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
                            @click="viewCase(scope.row)"
                        >
                            查看详情
                        </el-button>
                    </template>
                </el-table-column>
            </el-table>
        </el-card>

        <!-- 用例详情对话框 -->
        <el-dialog
            v-model="detailDialogVisible"
            title="用例详情"
            width="800px"
        >
            <div v-if="currentCase">
                <el-descriptions :column="2" border>
                    <el-descriptions-item label="需求名称">
                        {{ currentCase.test_case_detail?.requirement_name || '-' }}
                    </el-descriptions-item>
                    <el-descriptions-item label="功能模块">
                        {{ currentCase.test_case_detail?.feature_name || '-' }}
                    </el-descriptions-item>
                    <el-descriptions-item label="用例名称" :span="2">
                        {{ currentCase.test_case_detail?.name || '-' }}
                    </el-descriptions-item>
                    <el-descriptions-item label="优先级">
                        <el-tag
                            :type="getPriorityType(currentCase.test_case_detail?.priority)"
                            size="small"
                        >
                            {{ currentCase.test_case_detail?.priority || '-' }}
                        </el-tag>
                    </el-descriptions-item>
                    <el-descriptions-item label="标签">
                        <el-tag
                            v-for="tag in currentCase.test_case_detail?.tags"
                            :key="tag"
                            size="small"
                            style="margin-right: 5px;"
                        >
                            {{ tag }}
                        </el-tag>
                    </el-descriptions-item>
                    <el-descriptions-item label="前置条件" :span="2">
                        {{ currentCase.test_case_detail?.preconditions || '-' }}
                    </el-descriptions-item>
                </el-descriptions>

                <el-divider />

                <h4>测试步骤</h4>
                <el-table
                    :data="currentCase.test_case_detail?.test_steps"
                    style="width: 100%;"
                >
                    <el-table-column type="index" label="步骤" width="60" />
                    <el-table-column prop="step" label="操作步骤" min-width="200" />
                    <el-table-column prop="expected_result" label="预期结果" min-width="200" />
                </el-table>
            </div>
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
const detailDialogVisible = ref(false)
const currentCase = ref(null)

const goBack = () => {
    router.back()
}

const loadCases = async () => {
    loading.value = true
    try {
        const response = await $api.getPlanCases(planId.value)
        if (response.code === 0) {
            caseList.value = response.data.map(item => ({
                ...item,
                status: 'pending' // pending, running, success, failed
            }))
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
    ElMessage.info('用例执行功能开发中...')
    // TODO: 实现用例执行逻辑
}

const executeAll = () => {
    ElMessageBox.confirm('确定要批量执行所有用例吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
    }).then(() => {
        ElMessage.info('批量执行功能开发中...')
        // TODO: 实现批量执行逻辑
    }).catch(() => {})
}

const viewCase = (row) => {
    currentCase.value = row
    detailDialogVisible.value = true
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
        'running': 'warning',
        'success': 'success',
        'failed': 'danger'
    }
    return typeMap[status] || 'info'
}

const getStatusText = (status) => {
    const textMap = {
        'pending': '待执行',
        'running': '执行中',
        'success': '成功',
        'failed': '失败'
    }
    return textMap[status] || '未知'
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
