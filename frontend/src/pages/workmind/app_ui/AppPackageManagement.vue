<template>
    <div class="app-package-management">
        <div class="page-header">
            <h3>应用包名管理</h3>
            <div class="header-actions">
                <el-button type="primary" size="small" @click="showAddDialog">
                    + 添加应用
                </el-button>
                <el-button size="small" :icon="Refresh" @click="loadPackages">
                    刷新
                </el-button>
            </div>
        </div>

        <el-table
            v-loading="loading"
            :data="packageList"
            style="width: 100%; margin-top: 16px;"
            empty-text="暂无应用包名"
        >
            <el-table-column prop="name" label="应用名称" min-width="180" />
            <el-table-column prop="package_name" label="应用包名" min-width="250" />
            <el-table-column prop="created_by_name" label="创建人" width="120" />
            <el-table-column prop="created_at" label="创建时间" width="180">
                <template #default="scope">
                    {{ formatDate(scope.row.created_at) }}
                </template>
            </el-table-column>
            <el-table-column label="操作" width="150" align="center">
                <template #default="scope">
                    <el-button link size="small" @click="editPackage(scope.row)">
                        编辑
                    </el-button>
                    <el-button link size="small" style="color: #f56c6c" @click="deletePackage(scope.row)">
                        删除
                    </el-button>
                </template>
            </el-table-column>
        </el-table>

        <!-- 添加/编辑对话框 -->
        <el-dialog
            v-model="dialogVisible"
            :title="dialogTitle"
            width="500px"
            @close="resetForm"
        >
            <el-form
                ref="formRef"
                :model="form"
                :rules="rules"
                label-width="100px"
            >
                <el-form-item label="应用名称" prop="name">
                    <el-input
                        v-model.trim="form.name"
                        placeholder="如：Android设置"
                        clearable
                    />
                </el-form-item>
                <el-form-item label="应用包名" prop="package_name">
                    <el-input
                        v-model.trim="form.package_name"
                        placeholder="如：com.android.settings"
                        clearable
                    />
                </el-form-item>
            </el-form>
            <template #footer>
                <span class="dialog-footer">
                    <el-button @click="dialogVisible = false">取消</el-button>
                    <el-button type="primary" :loading="submitting" @click="submitForm">
                        确定
                    </el-button>
                </span>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { useGlobalProperties } from '@/composables'

const { $api } = useGlobalProperties()

// 数据
const loading = ref(false)
const packageList = ref([])

// 对话框
const dialogVisible = ref(false)
const dialogTitle = ref('添加应用')
const isEdit = ref(false)
const editingId = ref(null)
const formRef = ref(null)
const submitting = ref(false)

const form = reactive({
    name: '',
    package_name: ''
})

const rules = {
    name: [
        { required: true, message: '请输入应用名称', trigger: 'blur' }
    ],
    package_name: [
        { required: true, message: '请输入应用包名', trigger: 'blur' },
        { 
            pattern: /^[a-zA-Z0-9._]+$/, 
            message: '包名只能包含字母、数字、点和下划线', 
            trigger: 'blur' 
        }
    ]
}

// 方法
const loadPackages = async () => {
    loading.value = true
    try {
        const response = await $api.getAppPackages()
        if (response.code === 0) {
            packageList.value = response.data || []
        } else {
            ElMessage.error(response.msg || '获取应用列表失败')
        }
    } catch (error) {
        console.error('获取应用列表失败:', error)
        ElMessage.error('获取应用列表失败')
    } finally {
        loading.value = false
    }
}

const showAddDialog = () => {
    dialogTitle.value = '添加应用'
    isEdit.value = false
    editingId.value = null
    dialogVisible.value = true
}

const editPackage = (row) => {
    dialogTitle.value = '编辑应用'
    isEdit.value = true
    editingId.value = row.id
    form.name = row.name
    form.package_name = row.package_name
    dialogVisible.value = true
}

const submitForm = async () => {
    if (!formRef.value) return
    
    await formRef.value.validate(async (valid) => {
        if (!valid) return
        
        submitting.value = true
        try {
            let response
            if (isEdit.value) {
                response = await $api.updateAppPackage(editingId.value, form)
            } else {
                response = await $api.createAppPackage(form)
            }
            
            if (response.code === 0) {
                ElMessage.success(isEdit.value ? '更新成功' : '添加成功')
                dialogVisible.value = false
                loadPackages()
            } else {
                ElMessage.error(response.msg || '操作失败')
            }
        } catch (error) {
            console.error('操作失败:', error)
            const errorMsg = (error.response && error.response.data && error.response.data.msg) || error.message
            ElMessage.error(errorMsg || '操作失败')
        } finally {
            submitting.value = false
        }
    })
}

const deletePackage = async (row) => {
    try {
        await ElMessageBox.confirm(
            `确定要删除应用 "${row.name}" 吗？`,
            '提示',
            {
                confirmButtonText: '确定',
                cancelButtonText: '取消',
                type: 'warning'
            }
        )
        
        const response = await $api.deleteAppPackage(row.id)
        if (response.code === 0) {
            ElMessage.success('删除成功')
            loadPackages()
        } else {
            ElMessage.error(response.msg || '删除失败')
        }
    } catch (error) {
        if (error === 'cancel') return
        console.error('删除失败:', error)
        ElMessage.error('删除失败')
    }
}

const resetForm = () => {
    form.name = ''
    form.package_name = ''
    if (formRef.value) {
        formRef.value.clearValidate()
    }
}

const formatDate = (dateStr) => {
    if (!dateStr) return '-'
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    })
}

onMounted(() => {
    loadPackages()
})
</script>

<style scoped>
.app-package-management {
    padding: 20px;
}

.page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}

.page-header h3 {
    margin: 0;
    font-size: 18px;
    font-weight: 500;
}

.header-actions {
    display: flex;
    gap: 8px;
}
</style>
