<template>
    <div class="task-management">
        <div class="task-header">
            <h3>任务管理</h3>
            <div class="task-actions">
                <el-button type="primary" :icon="Plus" @click="showAddDialog">新建任务</el-button>
                <el-button type="info" :icon="Refresh" :loading="loading" @click="loadTasks">刷新</el-button>
            </div>
        </div>

        <el-form :inline="true" size="small" style="margin-bottom: 10px;">
            <el-form-item label="任务名称">
                <el-input
                    v-model="searchForm.name"
                    placeholder="请输入任务名称"
                    clearable
                    style="width: 160px;"
                    @keyup.enter="loadTasks"
                />
            </el-form-item>
            <el-form-item label="所属需求">
                <el-select
                    v-model="searchForm.requirement_name"
                    placeholder="请选择所属需求"
                    filterable
                    clearable
                    style="width: 180px;"
                    @change="loadTasks"
                >
                    <el-option
                        v-for="item in requirementOptions"
                        :key="item"
                        :label="item"
                        :value="item"
                    />
                </el-select>
            </el-form-item>
            <el-form-item label="任务负责人">
                <el-select
                    v-model="searchForm.owner"
                    placeholder="请选择负责人"
                    filterable
                    multiple
                    collapse-tags
                    clearable
                    style="width: 180px;"
                    :loading="userListLoading"
                    @change="loadTasks"
                >
                    <el-option
                        v-for="u in userList"
                        :key="u.id"
                        :label="u.name || u.username"
                        :value="u.username"
                    />
                </el-select>
            </el-form-item>
            <el-form-item label="任务状态">
                <el-select
                    v-model="searchForm.status"
                    placeholder="请选择状态"
                    clearable
                    style="width: 120px;"
                    @change="loadTasks"
                >
                    <el-option label="未开始" value="未开始" />
                    <el-option label="进行中" value="进行中" />
                    <el-option label="已完成" value="已完成" />
                </el-select>
            </el-form-item>
            <el-form-item label="创建时间">
                <el-date-picker
                    v-model="searchForm.created_at"
                    type="daterange"
                    range-separator="-"
                    start-placeholder="开始日期"
                    end-placeholder="结束日期"
                    value-format="YYYY-MM-DD"
                    style="width: 240px;"
                    @change="loadTasks"
                />
            </el-form-item>
            <el-form-item label="任务时间">
                <el-date-picker
                    v-model="searchForm.task_time"
                    type="daterange"
                    range-separator="-"
                    start-placeholder="开始日期"
                    end-placeholder="结束日期"
                    value-format="YYYY-MM-DD"
                    style="width: 240px;"
                    @change="loadTasks"
                />
            </el-form-item>
            <el-form-item>
                <el-button type="primary" :icon="Search" @click="loadTasks">查询</el-button>
                <el-button :icon="Refresh" @click="resetSearch">重置</el-button>
            </el-form-item>
        </el-form>

        <el-table
            v-loading="loading"
            :data="taskList"
            :key="'task-table-' + (userList.length || 0)"
            style="width: 100%; margin-top: 10px;"
            :empty-text="emptyText"
            :header-cell-style="{ textAlign: 'center' }"
            :cell-style="{ textAlign: 'center' }"
        >
            <el-table-column type="index" label="序号" width="60" />
            <el-table-column prop="name" label="任务名称" min-width="140" show-overflow-tooltip />
            <el-table-column prop="requirement_name" label="所属需求" width="120" show-overflow-tooltip />
            <el-table-column prop="owner" label="任务负责人" width="100" show-overflow-tooltip>
                <template #default="scope">
                    {{ personFieldToDisplay(scope.row.owner) || '-' }}
                </template>
            </el-table-column>
            <el-table-column prop="status" label="任务状态" width="90">
                <template #default="scope">
                    <el-tag :type="getStatusType(scope.row.status)" size="small">
                        {{ scope.row.status || '-' }}
                    </el-tag>
                </template>
            </el-table-column>
            <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip />
            <el-table-column prop="man_days" label="任务人日" width="90" />
            <el-table-column prop="task_time" label="任务时间" width="180">
                <template #default="scope">
                    {{ formatDisplayDate(scope.row.task_time) }}
                </template>
            </el-table-column>
            <el-table-column prop="created_by_name" label="创建人" width="90" show-overflow-tooltip>
                <template #default="scope">
                    {{ scope.row.created_by_name || scope.row.created_by_username || '-' }}
                </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="160">
                <template #default="scope">
                    {{ formatDate(scope.row.created_at) }}
                </template>
            </el-table-column>
            <el-table-column label="操作" width="140" fixed="right">
                <template #default="scope">
                    <el-button link size="small" @click="editTask(scope.row)">编辑</el-button>
                    <el-button link size="small" style="color: #f56c6c;" @click="deleteTask(scope.row)">删除</el-button>
                </template>
            </el-table-column>
        </el-table>

        <el-pagination
            v-show="total > 0"
            :current-page="currentPage"
            :page-sizes="[10, 20, 50]"
            :page-size="pageSize"
            :total="total"
            layout="total, sizes, prev, pager, next, jumper"
            style="margin-top: 20px; text-align: right;"
            @size-change="handleSizeChange"
            @current-change="handlePageChange"
        />

        <el-dialog :title="dialogTitle" v-model="dialogVisible" width="560px" @close="resetForm">
            <el-form ref="taskForm" :model="taskFormData" :rules="taskRules" label-width="100px">
                <el-form-item label="任务名称" prop="name">
                    <el-input v-model="taskFormData.name" placeholder="请输入任务名称" maxlength="200" show-word-limit />
                </el-form-item>
                <el-form-item label="所属需求" prop="requirement_name">
                    <el-select
                        v-model="taskFormData.requirement_name"
                        filterable
                        clearable
                        placeholder="请选择所属需求"
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
                <el-form-item label="任务负责人" prop="owner">
                    <el-select
                        v-model="taskFormData.owner"
                        multiple
                        filterable
                        collapse-tags
                        placeholder="请选择任务负责人"
                        style="width: 100%;"
                        :loading="userListLoading"
                    >
                        <el-option
                            v-for="u in userList"
                            :key="u.id"
                            :label="u.name || u.username"
                            :value="u.username"
                        />
                    </el-select>
                </el-form-item>
                <el-form-item label="任务状态" prop="status">
                    <el-select v-model="taskFormData.status" placeholder="请选择状态" style="width: 200px;">
                        <el-option label="未开始" value="未开始" />
                        <el-option label="进行中" value="进行中" />
                        <el-option label="已完成" value="已完成" />
                    </el-select>
                </el-form-item>
                <el-form-item label="备注" prop="remark">
                    <el-input v-model="taskFormData.remark" type="textarea" :rows="2" placeholder="请输入备注" />
                </el-form-item>
                <el-form-item label="任务人日" prop="man_days">
                    <el-input v-model="taskFormData.man_days" placeholder="请输入任务人日" />
                </el-form-item>
                <el-form-item label="任务时间" prop="task_time">
                    <el-date-picker
                        v-model="taskFormData.task_time"
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
                <el-button type="primary" :loading="saving" @click="saveTask">保存</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import {
    getTasks,
    createTask,
    updateTask,
    deleteTask as deleteTaskApi,
    getFunctionalRequirements,
    getUserList
} from '@/restful/api'

const route = useRoute()

const taskForm = ref(null)
const loading = ref(false)
const saving = ref(false)
const taskList = ref([])
const requirementOptions = ref([])
const userList = ref([])
const userListLoading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const emptyText = ref('暂无数据')
const dialogVisible = ref(false)
const dialogTitle = ref('新建任务')
const isEdit = ref(false)

const taskFormData = ref({
    id: null,
    name: '',
    requirement_name: '',
    owner: [],
    status: '未开始',
    remark: '',
    man_days: '',
    task_time: []
})

const taskRules = {
    name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
    requirement_name: [{ required: true, message: '请选择所属需求', trigger: 'change' }]
}

const searchForm = ref({
    name: '',
    requirement_name: '',
    owner: [],
    status: '',
    created_at: null,
    task_time: null,
})

const applyRouteQueryToSearchForm = () => {
    const q = route.query || {}
    if (q.name != null && String(q.name).trim() !== '') {
        searchForm.value.name = String(q.name)
    }
    if (q.requirement_name != null && String(q.requirement_name).trim() !== '') {
        searchForm.value.requirement_name = String(q.requirement_name)
    }
    if (q.owner != null && String(q.owner).trim() !== '') {
        // 任务管理 owner 是多选，这里按单值回填
        searchForm.value.owner = [String(q.owner)]
    }
    if (q.status != null && String(q.status).trim() !== '') {
        searchForm.value.status = String(q.status)
    }
    const after = q.task_time_after != null ? String(q.task_time_after).trim() : ''
    const before = q.task_time_before != null ? String(q.task_time_before).trim() : ''
    if (after || before) {
        searchForm.value.task_time = [after || '', before || ''].filter(Boolean)
        if (searchForm.value.task_time.length !== 2) {
            searchForm.value.task_time = null
        }
    }
}

const getDefaultForm = () => ({
    id: null,
    name: '',
    requirement_name: '',
    owner: [],
    status: '未开始',
    remark: '',
    man_days: '',
    task_time: []
})

/** 需求名称下拉（与需求管理、用例管理一致：page_size 2000，保证能搜到全部需求） */
const loadRequirementOptions = () => {
    getFunctionalRequirements({ page: 1, page_size: 2000 }).then(res => {
        if (res.code === 0) {
            const list = res.data?.results || res.data || []
            requirementOptions.value = Array.isArray(list) ? list.map(item => item.name).filter(Boolean) : []
        } else {
            requirementOptions.value = []
        }
    }).catch(() => { requirementOptions.value = [] })
}

const loadUserList = () => {
    userListLoading.value = true
    getUserList()
        .then(data => {
            const list = Array.isArray(data) ? data : (data && data.data) ? data.data : []
            userList.value = list.filter(u => u && (u.username || u.id))
        })
        .catch(() => { userList.value = [] })
        .finally(() => { userListLoading.value = false })
}

const loadTasks = () => {
    loading.value = true
    const params = { page: currentPage.value, page_size: pageSize.value }
    if (searchForm.value.name) params.name = searchForm.value.name
    if (searchForm.value.requirement_name) params.requirement_name = searchForm.value.requirement_name
    if (searchForm.value.owner && searchForm.value.owner.length) params.owner = formatPersonField(searchForm.value.owner)
    if (searchForm.value.status) params.status = searchForm.value.status
    if (searchForm.value.created_at && searchForm.value.created_at.length === 2) {
        params.created_at_after = searchForm.value.created_at[0]
        params.created_at_before = searchForm.value.created_at[1]
    }
    if (searchForm.value.task_time && searchForm.value.task_time.length === 2) {
        params.task_time_after = searchForm.value.task_time[0]
        params.task_time_before = searchForm.value.task_time[1]
    }
    getTasks(params).then(res => {
        if (res.code === 0) {
            if (res.data.results) {
                taskList.value = res.data.results
                total.value = res.data.count
            } else {
                taskList.value = res.data || []
                total.value = (res.data || []).length
            }
        } else {
            ElMessage.error(res.msg || '获取任务列表失败')
            taskList.value = []
            total.value = 0
        }
    }).catch(err => {
        ElMessage.error('获取任务列表失败：' + (err.message || '未知错误'))
        taskList.value = []
        total.value = 0
    }).finally(() => { loading.value = false })
}

const resetSearch = () => {
    searchForm.value.name = ''
    searchForm.value.requirement_name = ''
    searchForm.value.owner = []
    searchForm.value.status = ''
    searchForm.value.created_at = null
    searchForm.value.task_time = null
    loadTasks()
}

const handleSizeChange = (size) => {
    pageSize.value = size
    currentPage.value = 1
    loadTasks()
}

const handlePageChange = (page) => {
    currentPage.value = page
    loadTasks()
}

const parsePersonField = (val) => {
    if (!val) return []
    if (Array.isArray(val)) return val
    return String(val).split(',').map(s => s.trim()).filter(Boolean)
}

const formatPersonField = (val) => {
    if (!val || !Array.isArray(val)) return ''
    return val.filter(Boolean).join(',')
}

/** 将存储的用户名字符串转为展示用姓名（与编辑页下拉 label 一致） */
const personFieldToDisplay = (val) => {
    if (!val) return ''
    const usernames = parsePersonField(val)
    if (!usernames.length) return ''
    const list = userList.value || []
    const names = usernames.map(uid => {
        const key = String(uid).trim().toLowerCase()
        const u = list.find(x => String(x.username || x.id || '').toLowerCase() === key)
        return u ? (u.name || u.username || uid) : uid
    })
    return names.join('、')
}

/** 与需求管理「开发时间 / 测试时间」一致 */
const convertToStandardFormat = (dateStr) => {
    if (!dateStr) return null
    let str = dateStr.trim()

    // 兼容后端返回带时间的字符串：YYYY-MM-DD HH:mm:ss
    const dateTimePrefixMatch = str.match(/^(\d{4}-\d{1,2}-\d{1,2})\b/)
    if (dateTimePrefixMatch && dateTimePrefixMatch[1]) {
        str = dateTimePrefixMatch[1]
    }

    if (str.match(/^\d{4}\/\d{1,2}\/\d{1,2}$/)) {
        return str
    }
    const singleDateMatch = str.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/)
    if (singleDateMatch) {
        const [, year, month, day] = singleDateMatch
        return `${year}/${parseInt(month)}/${parseInt(day)}`
    }
    try {
        const date = new Date(str)
        if (!isNaN(date.getTime())) {
            const year = date.getFullYear()
            const month = date.getMonth() + 1
            const day = date.getDate()
            return `${year}/${month}/${day}`
        }
    } catch (e) {}
    return null
}

/**
 * 解析任务时间区间字符串为 [YYYY/M/D, YYYY/M/D]，供 el-date-picker 回显。
 *
 * 注意：不能用 /^(.+?)[\s]*-[\s]*(.+)$/ —— 对 "2024-03-03 - 2024-03-05" 会在第一个「年-月」的横杠处截断，
 * 得到 ("2024", "03-03 - 2024-03-05")，前半段不含日期分隔符，解析失败，编辑页永远不回显。
 */
const parseTimeRange = (value) => {
    if (!value) return []
    if (Array.isArray(value)) {
        if (value.length < 2 || !value[0] || !value[1]) return []
        const startFormatted = convertToStandardFormat(String(value[0]))
        const endFormatted = convertToStandardFormat(String(value[1]))
        return startFormatted && endFormatted ? [startFormatted, endFormatted] : []
    }
    // 归一化：把换行/多空格统一成单空格，避免 split/regex 失效
    const str = String(value).replace(/\s+/g, ' ').trim()

    // 支持 ~ / ～ 分隔（有些接口/人手录入会用波浪线）
    if (str.includes(' ~ ')) {
        const parts = str.split(' ~ ').map(s => s.trim()).filter(Boolean)
        if (parts.length === 2) {
            const a = convertToStandardFormat(parts[0])
            const b = convertToStandardFormat(parts[1])
            if (a && b) return [a, b]
        }
    }
    if (str.includes(' ～ ')) {
        const parts = str.split(' ～ ').map(s => s.trim()).filter(Boolean)
        if (parts.length === 2) {
            const a = convertToStandardFormat(parts[0])
            const b = convertToStandardFormat(parts[1])
            if (a && b) return [a, b]
        }
    }

    // 接口/列表常见：2024-03-03 - 2024-03-05（中间是「空格-空格」）
    if (str.includes(' - ')) {
        const parts = str.split(' - ').map(s => s.trim()).filter(Boolean)
        if (parts.length === 2) {
            const a = convertToStandardFormat(parts[0])
            const b = convertToStandardFormat(parts[1])
            if (a && b) return [a, b]
        }
    }

    // 两段完整 YYYY-MM-DD（中间可有空格）
    const isoPair = str.match(/^(\d{4}-\d{1,2}-\d{1,2})\s*-\s*(\d{4}-\d{1,2}-\d{1,2})$/)
    if (isoPair) {
        const a = convertToStandardFormat(isoPair[1])
        const b = convertToStandardFormat(isoPair[2])
        if (a && b) return [a, b]
    }

    // 需求管理保存格式：2024/1/1-2024/1/5
    const slashPair = str.match(/^(\d{4}\/\d{1,2}\/\d{1,2})-(\d{4}\/\d{1,2}\/\d{1,2})$/)
    if (slashPair) {
        return [slashPair[1], slashPair[2]]
    }

    // 其它「后半段明显是日期」的兜底（避免再误匹配年-月之间的横杠）
    const tail = str.match(/^(.+?)\s+-\s+(.+)$/)
    if (tail) {
        const a = convertToStandardFormat(tail[1].trim())
        const b = convertToStandardFormat(tail[2].trim())
        if (a && b) return [a, b]
    }
    return []
}

const formatTimeRange = (value) => {
    if (!value || value.length !== 2) return ''
    return `${value[0]}-${value[1]}`
}

const showAddDialog = () => {
    dialogTitle.value = '新建任务'
    isEdit.value = false
    dialogVisible.value = true
}

const editTask = (row) => {
    dialogTitle.value = '编辑任务'
    isEdit.value = true
    taskFormData.value = {
        id: row.id,
        name: row.name,
        requirement_name: row.requirement_name || '',
        owner: parsePersonField(row.owner),
        status: row.status || '未开始',
        remark: row.remark || '',
        man_days: row.man_days || '',
        task_time: parseTimeRange(row.task_time)
    }
    dialogVisible.value = true
}

const deleteTask = (row) => {
    ElMessageBox.confirm('确定要删除该任务吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
    }).then(() => {
        deleteTaskApi(row.id).then(res => {
            if (res.code === 0) {
                ElMessage.success('删除成功')
                loadRequirementOptions()
                loadTasks()
            } else {
                ElMessage.error(res.msg || '删除失败')
            }
        }).catch(err => ElMessage.error('删除失败：' + (err.message || '未知错误')))
    }).catch(() => {})
}

const saveTask = () => {
    taskForm.value.validate(valid => {
        if (!valid) return
        saving.value = true
        const params = {
            name: taskFormData.value.name,
            requirement_name: taskFormData.value.requirement_name || '',
            owner: formatPersonField(taskFormData.value.owner),
            status: taskFormData.value.status || '未开始',
            remark: taskFormData.value.remark || '',
            man_days: taskFormData.value.man_days || '',
            task_time: formatTimeRange(taskFormData.value.task_time)
        }
        const request = isEdit.value
            ? updateTask(taskFormData.value.id, params)
            : createTask(params)
        request.then(res => {
            if (res.code === 0) {
                ElMessage.success(isEdit.value ? '更新成功' : '创建成功')
                dialogVisible.value = false
                loadRequirementOptions()
                loadTasks()
            } else {
                ElMessage.error(res.msg || (isEdit.value ? '更新失败' : '创建失败'))
            }
        }).catch(err => {
            ElMessage.error((isEdit.value ? '更新失败：' : '创建失败：') + (err.message || '未知错误'))
        }).finally(() => { saving.value = false })
    })
}

const resetForm = () => {
    if (taskForm.value) taskForm.value.resetFields()
    taskFormData.value = getDefaultForm()
}

const getStatusType = (status) => {
    const map = { '未开始': 'info', '进行中': 'primary', '已完成': 'success' }
    return map[status] || 'info'
}

const formatDate = (date) => {
    if (!date) return '-'
    return new Date(date).toLocaleString('zh-CN')
}

const formatSingleDate = (dateStr) => {
    if (!dateStr) return '-'
    const str = String(dateStr).trim()
    if (str.includes('/')) {
        const parts = str.split('/').map(item => item.trim())
        if (parts.length === 3) {
            const [y, m, d] = parts
            return `${y}/${Number(m)}/${Number(d)}`
        }
    }
    if (str.match(/^\d{4}-\d{1,2}-\d{1,2}$/)) {
        const [year, month, day] = str.split('-')
        return `${year}/${Number(month)}/${Number(day)}`
    }
    try {
        const date = new Date(str)
        if (!isNaN(date.getTime())) {
            const year = date.getFullYear()
            const month = date.getMonth() + 1
            const day = date.getDate()
            return `${year}/${month}/${day}`
        }
    } catch (e) {}
    return str
}

const formatDisplayDate = (dateStr) => {
    if (!dateStr) return '-'
    const str = String(dateStr).trim()
    const rangeMatch = str.match(/^(.+?)[\s]*-[\s]*(.+)$/)
    if (rangeMatch) {
        const [, start, end] = rangeMatch
        if ((start.includes('/') || start.includes('-')) &&
            (end.includes('/') || end.includes('-'))) {
            const formattedStart = formatSingleDate(start.trim())
            const formattedEnd = formatSingleDate(end.trim())
            return `${formattedStart} ~ ${formattedEnd}`
        }
    }
    return formatSingleDate(str)
}

onMounted(() => {
    loadUserList()
    loadRequirementOptions()
    applyRouteQueryToSearchForm()
    loadTasks()
})

watch(
    () => route.query,
    () => {
        applyRouteQueryToSearchForm()
        loadTasks()
    }
)
</script>

<style scoped>
.task-management { padding: 20px; }
.task-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.task-header h3 { margin: 0; }
.task-management .el-table .cell { white-space: normal; word-break: break-all; }
</style>
