<template>
    <div class="requirement-management">
        <div class="requirement-header">
            <h3>需求管理</h3>
            <div class="requirement-actions">
                <el-button
                    type="primary"
                    :icon="Plus"
                    @click="showAddDialog"
                >
                    新建需求
                </el-button>
                <el-button
                    type="info"
                    :icon="Refresh"
                    :loading="loading"
                    @click="loadRequirements"
                >
                    刷新
                </el-button>
            </div>
        </div>

        <el-form :inline="true" size="small" style="margin-bottom: 10px;">
            <el-form-item label="需求名称">
                <el-select
                    v-model="searchForm.name"
                    placeholder="请选择需求名称"
                    filterable
                    clearable
                    style="width: 220px;"
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
                <el-button type="primary" :icon="Search" @click="loadRequirements">搜索</el-button>
                <el-button :icon="Refresh" @click="resetSearch">重置</el-button>
            </el-form-item>
        </el-form>

        <el-table
            v-loading="loading"
            :data="requirementList"
            style="width: 100%; margin-top: 10px;"
            :empty-text="emptyText"
            :header-cell-style="{ textAlign: 'center' }"
            :cell-style="{ textAlign: 'center' }"
        >
            <el-table-column type="index" label="序号" width="60" />
            <el-table-column prop="name" label="需求名称" min-width="160" />
            <el-table-column prop="link" label="需求链接" min-width="240" />
            <el-table-column prop="product_owner" label="产品负责人" width="100" />
            <el-table-column prop="status" label="状态" width="80">
                <template #default="scope">
                    <el-tag :type="getStatusType(scope.row.status)" size="small">
                        {{ scope.row.status || '-' }}
                    </el-tag>
                </template>
            </el-table-column>
            <el-table-column prop="tags" label="标签" width="100">
                <template #default="scope">
                    <span v-if="scope.row.tags">
                        <el-tag
                            v-for="tag in formatTags(scope.row.tags)"
                            :key="tag"
                            :type="getTagType(tag)"
                            size="small"
                            style="margin-right: 4px;"
                        >
                            {{ tag }}
                        </el-tag>
                    </span>
                    <span v-else>-</span>
                </template>
            </el-table-column>
            <el-table-column prop="remark" label="备注" min-width="200" />
            <el-table-column prop="developers" label="开发人员" min-width="100" />
            <el-table-column prop="dev_man_days" label="开发人日" width="90" />
            <el-table-column prop="dev_time" label="开发时间" min-width="180">
                <template #default="scope">
                    {{ formatDisplayDate(scope.row.dev_time) }}
                </template>
            </el-table-column>
            <el-table-column prop="testers" label="测试人员" min-width="100" />
            <el-table-column prop="test_man_days" label="测试人日" width="90" />
            <el-table-column prop="submit_test_time" label="提测时间" width="120">
                <template #default="scope">
                    {{ formatDisplayDate(scope.row.submit_test_time) }}
                </template>
            </el-table-column>
            <el-table-column prop="test_time" label="测试时间" min-width="180">
                <template #default="scope">
                    {{ formatDisplayDate(scope.row.test_time) }}
                </template>
            </el-table-column>
            <el-table-column prop="created_by_username" label="创建人" width="100" />
            <el-table-column prop="updated_at" label="更新时间" width="160">
                <template #default="scope">
                    {{ formatDate(scope.row.updated_at) }}
                </template>
            </el-table-column>
            <el-table-column label="操作" width="180" fixed="right">
                <template #default="scope">
                    <el-button link size="small" @click="editRequirement(scope.row)">
                        编辑
                    </el-button>
                    <el-button
                        link
                        size="small"
                        style="color: #f56c6c;"
                        @click="deleteRequirement(scope.row)"
                    >
                        删除
                    </el-button>
                </template>
            </el-table-column>
        </el-table>

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

        <el-dialog
            :title="dialogTitle"
            v-model="dialogVisible"
            width="600px"
            @close="resetForm"
        >
            <el-form
                ref="requirementForm"
                :model="requirementFormData"
                :rules="requirementRules"
                label-width="100px"
            >
                <el-form-item label="需求名称" prop="name">
                    <el-input
                        v-model="requirementFormData.name"
                        placeholder="请输入需求名称"
                        maxlength="200"
                        show-word-limit
                    />
                </el-form-item>
                <el-form-item label="需求链接" prop="link">
                    <el-input
                        v-model="requirementFormData.link"
                        placeholder="请输入需求链接"
                    />
                </el-form-item>
                <el-form-item label="产品负责人" prop="product_owner">
                    <el-input
                        v-model="requirementFormData.product_owner"
                        placeholder="请输入产品负责人"
                    />
                </el-form-item>
                <el-form-item label="状态" prop="status">
                    <el-select v-model="requirementFormData.status" placeholder="请选择状态" style="width: 200px;">
                        <el-option label="未开始" value="未开始" />
                        <el-option label="已评审" value="已评审" />
                        <el-option label="开发中" value="开发中" />
                        <el-option label="测试中" value="测试中" />
                        <el-option label="验收中" value="验收中" />
                        <el-option label="已上线" value="已上线" />
                    </el-select>
                </el-form-item>
                <el-form-item label="标签" prop="tags">
                    <el-select
                        v-model="requirementFormData.tags"
                        multiple
                        collapse-tags
                        placeholder="请选择标签"
                        style="width: 200px;"
                    >
                        <el-option label="正常" value="正常" />
                        <el-option label="延期" value="延期" />
                        <el-option label="暂停" value="暂停" />
                    </el-select>
                </el-form-item>
                <el-form-item label="备注" prop="remark">
                    <el-input
                        v-model="requirementFormData.remark"
                        type="textarea"
                        :rows="2"
                        placeholder="请输入备注"
                    />
                </el-form-item>
                <el-form-item label="开发人员" prop="developers">
                    <el-input
                        v-model="requirementFormData.developers"
                        placeholder="请输入开发人员"
                    />
                </el-form-item>
                <el-form-item label="开发人日" prop="dev_man_days">
                    <el-input
                        v-model="requirementFormData.dev_man_days"
                        placeholder="请输入开发人日"
                    />
                </el-form-item>
                <el-form-item label="开发时间" prop="dev_time">
                    <el-date-picker
                        v-model="requirementFormData.dev_time"
                        type="daterange"
                        range-separator="-"
                        start-placeholder="开始日期"
                        end-placeholder="结束日期"
                        value-format="YYYY/M/D"
                        style="width: 100%;"
                    />
                </el-form-item>
                <el-form-item label="测试人员" prop="testers">
                    <el-input
                        v-model="requirementFormData.testers"
                        placeholder="请输入测试人员"
                    />
                </el-form-item>
                <el-form-item label="测试人日" prop="test_man_days">
                    <el-input
                        v-model="requirementFormData.test_man_days"
                        placeholder="请输入测试人日"
                    />
                </el-form-item>
                <el-form-item label="提测时间" prop="submit_test_time">
                    <el-date-picker
                        v-model="requirementFormData.submit_test_time"
                        type="date"
                        placeholder="选择日期"
                        value-format="YYYY/M/D"
                        style="width: 200px;"
                    />
                </el-form-item>
                <el-form-item label="测试时间" prop="test_time">
                    <el-date-picker
                        v-model="requirementFormData.test_time"
                        type="daterange"
                        range-separator="-"
                        start-placeholder="开始日期"
                        end-placeholder="结束日期"
                        value-format="YYYY/M/D"
                        style="width: 100%;"
                    />
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="dialogVisible = false">取消</el-button>
                <el-button type="primary" :loading="saving" @click="saveRequirement">保存</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import {
    getFunctionalRequirements,
    createFunctionalRequirement,
    updateFunctionalRequirement,
    deleteFunctionalRequirement
} from '@/restful/api'


// refs
const requirementForm = ref(null)

// 响应式数据
const loading = ref(false)
const saving = ref(false)
const requirementList = ref([])
const requirementOptions = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const emptyText = ref('暂无数据')
const dialogVisible = ref(false)
const dialogTitle = ref('新建需求')
const isEdit = ref(false)

const requirementFormData = ref({
    id: null,
    name: '',
    link: '',
    product_owner: '',
    status: '未开始',
    tags: [],
    remark: '',
    developers: '',
    dev_man_days: '',
    dev_time: [],
    testers: '',
    test_man_days: '',
    submit_test_time: '',
    test_time: []
})

const requirementRules = {
    name: [
        { required: true, message: '请输入需求名称', trigger: 'blur' }
    ]
}

const searchForm = ref({
    name: ''
})

// 方法
const getDefaultForm = () => ({
    id: null,
    name: '',
    link: '',
    product_owner: '',
    status: '未开始',
    tags: [],
    remark: '',
    developers: '',
    dev_man_days: '',
    dev_time: [],
    testers: '',
    test_man_days: '',
    submit_test_time: '',
    test_time: []
})

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

const loadRequirements = () => {
    loading.value = true
    const params = {
        page: currentPage.value,
        page_size: pageSize.value
    }
    if (searchForm.value.name) {
        params.name = searchForm.value.name
    }
    getFunctionalRequirements(params).then(res => {
        if (res.code === 0) {
            if (res.data.results) {
                requirementList.value = res.data.results
                total.value = res.data.count
            } else {
                requirementList.value = res.data
                total.value = res.data.length
            }
        } else {
            ElMessage.error(res.msg || '获取需求列表失败')
            requirementList.value = []
            total.value = 0
        }
    }).catch(err => {
        ElMessage.error('获取需求列表失败：' + (err.message || '未知错误'))
        requirementList.value = []
        total.value = 0
    }).finally(() => {
        loading.value = false
    })
}

const resetSearch = () => {
    searchForm.value.name = ''
    loadRequirements()
}

const handleSizeChange = (size) => {
    pageSize.value = size
    currentPage.value = 1
    loadRequirements()
}

const handlePageChange = (page) => {
    currentPage.value = page
    loadRequirements()
}

const showAddDialog = () => {
    dialogTitle.value = '新建需求'
    isEdit.value = false
    dialogVisible.value = true
}

const editRequirement = (row) => {
    dialogTitle.value = '编辑需求'
    isEdit.value = true
    requirementFormData.value = {
        id: row.id,
        name: row.name,
        link: row.link || '',
        product_owner: row.product_owner || '',
        status: row.status || '未开始',
        tags: parseTags(row.tags),
        remark: row.remark || '',
        developers: row.developers || '',
        dev_man_days: row.dev_man_days || '',
        dev_time: parseTimeRange(row.dev_time),
        testers: row.testers || '',
        test_man_days: row.test_man_days || '',
        submit_test_time: parseSingleDate(row.submit_test_time),
        test_time: parseTimeRange(row.test_time)
    }
    dialogVisible.value = true
}

const deleteRequirement = (row) => {
    ElMessageBox.confirm('确定要删除该需求吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
    }).then(() => {
        deleteFunctionalRequirement(row.id).then(res => {
            if (res.code === 0) {
                ElMessage.success('删除成功')
                loadRequirementOptions()
                loadRequirements()
            } else {
                ElMessage.error(res.msg || '删除失败')
            }
        }).catch(err => {
            ElMessage.error('删除失败：' + (err.message || '未知错误'))
        })
    }).catch(() => {})
}

const saveRequirement = () => {
    requirementForm.value.validate(valid => {
        if (!valid) return
        saving.value = true
        const params = {
            name: requirementFormData.value.name,
            link: requirementFormData.value.link || '',
            product_owner: requirementFormData.value.product_owner || '',
            status: requirementFormData.value.status || '未开始',
            tags: formatTagsValue(requirementFormData.value.tags),
            remark: requirementFormData.value.remark || '',
            developers: requirementFormData.value.developers || '',
            dev_man_days: requirementFormData.value.dev_man_days || '',
            dev_time: formatTimeRange(requirementFormData.value.dev_time),
            testers: requirementFormData.value.testers || '',
            test_man_days: requirementFormData.value.test_man_days || '',
            submit_test_time: formatSingleDateToString(requirementFormData.value.submit_test_time),
            test_time: formatTimeRange(requirementFormData.value.test_time)
        }
        const request = isEdit.value
            ? updateFunctionalRequirement(requirementFormData.value.id, params)
            : createFunctionalRequirement(params)
        request.then(res => {
            if (res.code === 0) {
                ElMessage.success(isEdit.value ? '更新成功' : '创建成功')
                dialogVisible.value = false
                loadRequirementOptions()
                loadRequirements()
            } else {
                ElMessage.error(res.msg || (isEdit.value ? '更新失败' : '创建失败'))
            }
        }).catch(err => {
            ElMessage.error((isEdit.value ? '更新失败：' : '创建失败：') + (err.message || '未知错误'))
        }).finally(() => {
            saving.value = false
        })
    })
}

const resetForm = () => {
    if (requirementForm.value) {
        requirementForm.value.resetFields()
    }
    requirementFormData.value = getDefaultForm()
}

const parseTags = (tags) => {
    if (!tags) return []
    if (Array.isArray(tags)) return tags
    return String(tags)
        .replace(/，/g, ',')
        .split(',')
        .map(item => item.trim())
        .filter(Boolean)
}

const formatTagsValue = (tags) => {
    if (!tags || !tags.length) return ''
    return tags.join(',')
}

const parseTimeRange = (value) => {
    if (!value) return []
    if (Array.isArray(value)) return value
    
    const str = String(value).trim()
    

    const rangeMatch = str.match(/^(.+?)[\s]*-[\s]*(.+)$/)
    
    if (rangeMatch && rangeMatch.length === 3) {
        const [, start, end] = rangeMatch
        const startTrimmed = start.trim()
        const endTrimmed = end.trim()
        

        if ((startTrimmed.includes('/') || startTrimmed.includes('-')) &&
            (endTrimmed.includes('/') || endTrimmed.includes('-'))) {
            

            const startFormatted = convertToStandardFormat(startTrimmed)
            const endFormatted = convertToStandardFormat(endTrimmed)
            
            if (startFormatted && endFormatted) {
                return [startFormatted, endFormatted]
            }
        }
    }
    
    return []
}

const convertToStandardFormat = (dateStr) => {
    if (!dateStr) return null
    
    const str = dateStr.trim()
    

    if (str.match(/^\d{4}\/\d{1,2}\/\d{1,2}$/)) {
        return str
    }

    const singleDateMatch = str.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/)
    if (singleDateMatch) {
        const [, year, month, day] = singleDateMatch
        return `${year}/${parseInt(month)}/${parseInt(day)}`
    }
    
    // 尝试使用 Date 对象解析
    try {
        const date = new Date(str)
        if (!isNaN(date.getTime())) {
            const year = date.getFullYear()
            const month = date.getMonth() + 1
            const day = date.getDate()
            return `${year}/${month}/${day}`
        }
    } catch (e) {
        // 解析失败
    }
    
    return null
}

const parseDateString = (dateStr) => {
    if (!dateStr) return null
    
    // 处理 yyyy/M/d 格式
    if (dateStr.includes('/')) {
        const parts = dateStr.split('/').map(p => p.trim())
        if (parts.length === 3) {
            const [year, month, day] = parts
            return new Date(parseInt(year), parseInt(month) - 1, parseInt(day))
        }
    }
    
    // 处理 yyyy-MM-dd 格式
    if (dateStr.includes('-')) {
        const parts = dateStr.split('-').map(p => p.trim())
        if (parts.length === 3) {
            const [year, month, day] = parts
            return new Date(parseInt(year), parseInt(month) - 1, parseInt(day))
        }
    }
    
    // 尝试直接解析
    try {
        const date = new Date(dateStr)
        if (!isNaN(date.getTime())) {
            return date
        }
    } catch (e) {
        // 解析失败
    }
    
    return null
}

const parseSingleDate = (value) => {
    if (!value) return ''
    

    return convertToStandardFormat(value) || ''
}

const formatTimeRange = (value) => {
    if (!value || value.length !== 2) return ''

    return `${value[0]}-${value[1]}`
}

const formatDateToString = (date) => {
    if (!date || !(date instanceof Date)) return ''
    const year = date.getFullYear()
    const month = date.getMonth() + 1
    const day = date.getDate()
    return `${year}/${month}/${day}`
}

const formatSingleDateToString = (value) => {
    if (!value) return ''
    

    return String(value)
}

const getStatusType = (status) => {
    const typeMap = {
        '未开始': 'info',
        '已评审': 'warning',
        '开发中': 'primary',
        '测试中': 'success',
        '验收中': 'warning',
        '已上线': 'danger'
    }
    return typeMap[status] || 'info'
}

const formatTags = (tags) => {
    return String(tags)
        .replace(/，/g, ',')
        .split(',')
        .map(item => item.trim())
        .filter(Boolean)
}

const getTagType = (tag) => {
    const typeMap = {
        '正常': 'success',
        '延期': 'warning',
        '暂停': 'danger'
    }
    return typeMap[tag] || 'info'
}

const formatDate = (date) => {
    if (!date) return '-'
    return new Date(date).toLocaleString('zh-CN')
}

const formatDisplayDate = (dateStr) => {
    if (!dateStr) return '-'
    
    const str = String(dateStr).trim()
    

    const rangeMatch = str.match(/^(.+?)[\s]*-[\s]*(.+)$/)
    
    if (rangeMatch) {
        const [, start, end] = rangeMatch
        // 验证是否真的是日期范围（两部分都包含日期分隔符）
        if ((start.includes('/') || start.includes('-')) && 
            (end.includes('/') || end.includes('-'))) {
            const formattedStart = formatSingleDate(start.trim())
            const formattedEnd = formatSingleDate(end.trim())
            return `${formattedStart} ~ ${formattedEnd}`
        }
    }
    
    // 处理单个日期
    return formatSingleDate(str)
}

const formatSingleDate = (dateStr) => {
    if (!dateStr) return '-'
    
    const str = String(dateStr).trim()
    

    if (str.includes('/')) {
        const parts = str.split('/').map(item => item.trim())
        if (parts.length === 3) {
            const [year, month, day] = parts
            return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
        }
    }

    if (str.match(/^\d{4}-\d{1,2}-\d{1,2}$/)) {
        const parts = str.split('-')
        const [year, month, day] = parts
        return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    }
    
    // 尝试使用 Date 对象解析
    try {
        const date = new Date(str)
        if (!isNaN(date.getTime())) {
            const year = date.getFullYear()
            const month = String(date.getMonth() + 1).padStart(2, '0')
            const day = String(date.getDate()).padStart(2, '0')
            return `${year}-${month}-${day}`
        }
    } catch (e) {
        // 解析失败，返回原始字符串
    }
    
    return str
}

// 生命周期
onMounted(() => {
    loadRequirementOptions()
    loadRequirements()
})
</script>

<style scoped>
.requirement-management {
    padding: 20px;
}

.requirement-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}

.requirement-header h3 {
    margin: 0;
}

.requirement-management .el-table .cell {
    white-space: normal;
    word-break: break-all;
}
</style>

