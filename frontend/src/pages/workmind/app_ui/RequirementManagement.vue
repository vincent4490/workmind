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
                    @change="loadRequirements"
                >
                    <el-option
                        v-for="item in requirementOptions"
                        :key="item"
                        :label="item"
                        :value="item"
                    />
                </el-select>
            </el-form-item>
            <el-form-item label="测试团队">
                <el-select
                    v-model="searchForm.test_team"
                    placeholder="请选择测试团队"
                    clearable
                    filterable
                    style="width: 140px;"
                    @change="loadRequirements"
                >
                    <el-option
                        v-for="item in TEST_TEAM_OPTIONS"
                        :key="item"
                        :label="item"
                        :value="item"
                    />
                </el-select>
            </el-form-item>
            <el-form-item label="测试人员">
                <el-select
                    v-model="searchForm.testers"
                    placeholder="请选择测试人员"
                    filterable
                    clearable
                    style="width: 180px;"
                    @change="loadRequirements"
                >
                    <el-option
                        v-for="u in userList"
                        :key="u.id"
                        :label="u.name || u.username"
                        :value="u.username"
                    />
                </el-select>
            </el-form-item>
            <el-form-item label="状态">
                <el-select
                    v-model="searchForm.status"
                    placeholder="请选择状态"
                    clearable
                    style="width: 120px;"
                    @change="loadRequirements"
                >
                    <el-option
                        v-for="item in STATUS_OPTIONS"
                        :key="item"
                        :label="item"
                        :value="item"
                    />
                </el-select>
            </el-form-item>
            <el-form-item label="标签">
                <el-select
                    v-model="searchForm.tags"
                    placeholder="请选择标签"
                    clearable
                    filterable
                    style="width: 120px;"
                    @change="loadRequirements"
                >
                    <el-option
                        v-for="item in TAG_OPTIONS"
                        :key="item"
                        :label="item"
                        :value="item"
                    />
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
                    @change="loadRequirements"
                />
            </el-form-item>
            <el-form-item>
                <el-button type="primary" :icon="Search" @click="loadRequirements">搜索</el-button>
                <el-button :icon="Refresh" @click="resetSearch">重置</el-button>
            </el-form-item>
        </el-form>

        <el-table
            v-loading="loading"
            :data="requirementList"
            :key="'req-table-' + (userList.length || 0)"
            style="width: 100%; margin-top: 10px;"
            :empty-text="emptyText"
            :header-cell-style="{ textAlign: 'center' }"
            :cell-style="{ textAlign: 'center' }"
        >
            <el-table-column type="index" label="序号" width="60" />
            <el-table-column prop="name" label="需求名称" min-width="160" />
            <el-table-column prop="link" label="需求链接" min-width="240" />
            <el-table-column prop="product_owner" label="产品负责人" width="100" show-overflow-tooltip>
                <template #default="scope">
                    {{ personFieldToDisplay(scope.row.product_owner) || '-' }}
                </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="80">
                <template #default="scope">
                    <el-tag :type="getStatusType(scope.row.status)" size="small">
                        {{ scope.row.status || '-' }}
                    </el-tag>
                </template>
            </el-table-column>
            <el-table-column prop="tags" label="标签" width="80">
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
            <el-table-column prop="remark" label="备注" min-width="200" show-overflow-tooltip />
            <el-table-column prop="developers" label="开发人员" width="80" show-overflow-tooltip>
                <template #default="scope">
                    {{ personFieldToDisplay(scope.row.developers) || '-' }}
                </template>
            </el-table-column>
            <el-table-column prop="dev_man_days" label="开发人日" width="80" />
            <el-table-column prop="dev_time" label="开发时间" min-width="140">
                <template #default="scope">
                    {{ formatDisplayDate(scope.row.dev_time) }}
                </template>
            </el-table-column>
            <el-table-column prop="testers" label="测试人员" width="80" show-overflow-tooltip>
                <template #default="scope">
                    {{ personFieldToDisplay(scope.row.testers) || '-' }}
                </template>
            </el-table-column>
            <el-table-column prop="test_team" label="测试团队" width="80" />
            <el-table-column prop="test_man_days" label="测试人日" width="80" />
            <el-table-column prop="submit_test_time" label="提测时间" width="100">
                <template #default="scope">
                    {{ formatDisplayDate(scope.row.submit_test_time) }}
                </template>
            </el-table-column>
            <el-table-column prop="test_time" label="测试时间" min-width="140">
                <template #default="scope">
                    {{ formatDisplayDate(scope.row.test_time) }}
                </template>
            </el-table-column>
            <el-table-column prop="created_by_name" label="创建人" width="80" show-overflow-tooltip>
                <template #default="scope">
                    {{ scope.row.created_by_name || scope.row.created_by_username || '-' }}
                </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="160">
                <template #default="scope">
                    {{ formatDate(scope.row.created_at) }}
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
            :page-sizes="[10, 20, 50]"
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
                        clearable
                    />
                </el-form-item>
                <el-form-item label="状态" prop="status">
                    <el-select v-model="requirementFormData.status" placeholder="请选择状态" style="width: 200px;">
                        <el-option label="未开始" value="未开始" />
                        <el-option label="已评审" value="已评审" />
                        <el-option label="开发中" value="开发中" />
                        <el-option label="已暂停" value="已暂停" />
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
                        <el-option label="提测延期" value="提测延期" />
                        <el-option label="测试延期" value="测试延期" />
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
                        clearable
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
                    <el-select
                        v-model="requirementFormData.testers"
                        multiple
                        filterable
                        collapse-tags
                        placeholder="请选择测试人员"
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
                <el-form-item label="测试团队" prop="test_team">
                    <el-select
                        v-model="requirementFormData.test_team"
                        placeholder="请选择测试团队"
                        clearable
                        filterable
                        style="width: 100%;"
                    >
                        <el-option
                            v-for="item in TEST_TEAM_OPTIONS"
                            :key="item"
                            :label="item"
                            :value="item"
                        />
                    </el-select>
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
    deleteFunctionalRequirement,
    getUserList
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
const pageSize = ref(20)
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
    testers: [],
    test_team: '',
    test_man_days: '',
    submit_test_time: '',
    test_time: []
})

const userList = ref([])
const userListLoading = ref(false)

const requirementRules = {
    name: [
        { required: true, message: '请输入需求名称', trigger: 'blur' }
    ],
    test_team: [
        { required: true, message: '请选择测试团队', trigger: 'change' }
    ]
}

const searchForm = ref({
    name: '',
    test_team: '',
    testers: '',
    status: '',
    tags: '',
    created_at: null
})

// 状态、标签、测试团队与「新增需求」表单一致，固定枚举（不随数据计划）
const STATUS_OPTIONS = ['未开始', '已评审', '开发中', '已暂停', '测试中', '验收中', '已上线']
const TAG_OPTIONS = ['正常', '提测延期', '测试延期']
const TEST_TEAM_OPTIONS = ['slots', '国际棋牌', '大厅', '捕鱼', '本地棋牌']

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
    testers: [],
    test_team: '',
    test_man_days: '',
    submit_test_time: '',
    test_time: []
})

const loadRequirementOptions = () => {
    const params = {
        page: 1,
        page_size: 2000
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
    if (searchForm.value.test_team) {
        params.test_team = searchForm.value.test_team
    }
    if (searchForm.value.testers) {
        params.testers = searchForm.value.testers
    }
    if (searchForm.value.status) {
        params.status = searchForm.value.status
    }
    if (searchForm.value.tags) {
        params.tags = searchForm.value.tags
    }
    if (searchForm.value.created_at && searchForm.value.created_at.length === 2) {
        params.created_at_after = searchForm.value.created_at[0]
        params.created_at_before = searchForm.value.created_at[1]
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
    searchForm.value.test_team = ''
    searchForm.value.testers = ''
    searchForm.value.status = ''
    searchForm.value.tags = ''
    searchForm.value.created_at = null
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

const parsePersonField = (val) => {
    if (!val) return []
    if (Array.isArray(val)) return val
    return String(val).split(',').map(s => s.trim()).filter(Boolean)
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

const formatPersonField = (val) => {
    if (!val || !Array.isArray(val)) return ''
    return val.filter(Boolean).join(',')
}

const editRequirement = (row) => {
    dialogTitle.value = '编辑需求'
    isEdit.value = true
    requirementFormData.value = {
        id: row.id,
        name: row.name,
        link: row.link || '',
        product_owner: String(row.product_owner || '').trim(),
        status: row.status || '未开始',
        tags: parseTags(row.tags),
        remark: row.remark || '',
        developers: String(row.developers || '').trim(),
        dev_man_days: row.dev_man_days || '',
        dev_time: parseTimeRange(row.dev_time),
        testers: parsePersonField(row.testers),
        test_team: row.test_team || '',
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
            product_owner: (requirementFormData.value.product_owner || '').trim(),
            status: requirementFormData.value.status || '未开始',
            tags: formatTagsValue(requirementFormData.value.tags),
            remark: requirementFormData.value.remark || '',
            developers: (requirementFormData.value.developers || '').trim(),
            dev_man_days: requirementFormData.value.dev_man_days || '',
            dev_time: formatTimeRange(requirementFormData.value.dev_time),
            testers: formatPersonField(requirementFormData.value.testers),
            test_team: requirementFormData.value.test_team || '',
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
        '已暂停': 'info',
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
        '提测延期': 'warning',
        '测试延期': 'warning'
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

// 显示用：统一为 YYYY/M/D（如 2026/2/27）
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

const loadUserList = () => {
    userListLoading.value = true
    getUserList()
        .then(data => {
            const list = Array.isArray(data) ? data : (data && data.data) ? data.data : []
            userList.value = list.filter(u => u && (u.username || u.id))
        })
        .catch(() => {
            userList.value = []
        })
        .finally(() => {
            userListLoading.value = false
        })
}

// 生命周期
onMounted(() => {
    loadUserList()
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

