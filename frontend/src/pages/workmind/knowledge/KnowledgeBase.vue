<template>
    <div class="knowledge-base-page">
        <!-- 顶部操作栏 -->
        <div class="page-header">
            <div class="header-left">
                <h2 class="page-title">知识库</h2>
                <el-tag type="info" size="small">{{ stats.total || 0 }} 个文档</el-tag>
            </div>
            <el-button type="primary" :icon="Plus" @click="uploadDialogVisible = true">
                上传文档
            </el-button>
        </div>

        <div class="main-layout">
            <!-- 左侧分类导航 -->
            <div class="category-sidebar">
                <div class="category-title">文档分类</div>
                <div
                    v-for="cat in categories"
                    :key="cat.value"
                    class="category-item"
                    :class="{ active: selectedCategory === cat.value }"
                    @click="selectCategory(cat.value)"
                >
                    <el-icon><component :is="cat.icon" /></el-icon>
                    <span>{{ cat.label }}</span>
                    <el-badge
                        v-if="getCategoryCount(cat.value)"
                        :value="getCategoryCount(cat.value)"
                        class="cat-badge"
                    />
                </div>
            </div>

            <!-- 右侧文档列表 -->
            <div class="doc-content">
                <!-- 搜索栏 -->
                <div class="search-bar">
                    <el-input
                        v-model="searchKeyword"
                        placeholder="搜索文档标题..."
                        :prefix-icon="Search"
                        clearable
                        @input="handleSearch"
                        style="width: 300px"
                    />
                    <el-select v-model="statusFilter" placeholder="全部状态" clearable style="width: 130px; margin-left: 12px">
                        <el-option label="全部状态" value="" />
                        <el-option label="可用" value="ready" />
                        <el-option label="解析中" value="processing" />
                        <el-option label="待处理" value="pending" />
                        <el-option label="失败" value="failed" />
                    </el-select>
                </div>

                <!-- 文档列表 -->
                <div v-loading="loading" class="doc-list">
                    <el-empty v-if="!loading && documents.length === 0" description="暂无文档，点击上传按钮添加" />

                    <div
                        v-for="doc in documents"
                        :key="doc.id"
                        class="doc-card"
                    >
                        <div class="doc-icon">
                            <el-icon size="28"><component :is="getFileIcon(doc.file_type)" /></el-icon>
                        </div>
                        <div class="doc-info">
                            <div class="doc-title">{{ doc.title }}</div>
                            <div class="doc-meta">
                                <el-tag size="small" :type="getCategoryType(doc.category)">
                                    {{ getCategoryLabel(doc.category) }}
                                </el-tag>
                                <span class="meta-item">{{ formatSize(doc.file_size) }}</span>
                                <span class="meta-item">{{ doc.chunk_count }} 块</span>
                                <span class="meta-item">{{ formatDate(doc.created_at) }}</span>
                            </div>
                            <div v-if="doc.summary" class="doc-summary">{{ doc.summary }}</div>
                            <div v-if="doc.tags && doc.tags.length" class="doc-tags">
                                <el-tag
                                    v-for="tag in doc.tags"
                                    :key="tag"
                                    size="small"
                                    type="info"
                                    style="margin-right: 4px"
                                >{{ tag }}</el-tag>
                            </div>
                        </div>
                        <div class="doc-status">
                            <el-tag :type="getStatusType(doc.status)" size="small">
                                <el-icon v-if="doc.status === 'processing'" class="is-loading"><Loading /></el-icon>
                                {{ getStatusLabel(doc.status) }}
                            </el-tag>
                            <div v-if="doc.status === 'failed'" class="error-tip">
                                <el-tooltip :content="doc.error_message" placement="top">
                                    <el-icon style="color: #f56c6c; cursor: pointer"><Warning /></el-icon>
                                </el-tooltip>
                            </div>
                        </div>
                        <div class="doc-actions">
                            <el-button
                                v-if="doc.status === 'failed'"
                                size="small"
                                type="warning"
                                @click="reprocessDoc(doc)"
                            >重新处理</el-button>
                            <el-button
                                size="small"
                                type="danger"
                                @click="deleteDoc(doc)"
                            >删除</el-button>
                        </div>
                    </div>
                </div>

                <!-- 分页 -->
                <div class="pagination-wrapper" v-if="total > pageSize">
                    <el-pagination
                        v-model:current-page="currentPage"
                        :page-size="pageSize"
                        :total="total"
                        layout="prev, pager, next, total"
                        @current-change="fetchDocuments"
                    />
                </div>
            </div>
        </div>

        <!-- 上传对话框 -->
        <el-dialog
            v-model="uploadDialogVisible"
            title="上传文档"
            width="500px"
            :close-on-click-modal="false"
        >
            <el-form :model="uploadForm" label-width="80px">
                <el-form-item label="文档标题" required>
                    <el-input v-model="uploadForm.title" placeholder="请输入文档标题" />
                </el-form-item>
                <el-form-item label="文档分类" required>
                    <el-select v-model="uploadForm.category" style="width: 100%">
                        <el-option
                            v-for="cat in categories.filter(c => c.value !== 'all')"
                            :key="cat.value"
                            :label="cat.label"
                            :value="cat.value"
                        />
                    </el-select>
                </el-form-item>
                <el-form-item label="选择文件" required>
                    <el-upload
                        ref="uploadRef"
                        :auto-upload="false"
                        :limit="1"
                        :on-change="handleFileChange"
                        :on-exceed="() => ElMessage.warning('只能上传一个文件')"
                        accept=".pdf,.docx,.doc,.xlsx,.xls,.md,.txt,.jpg,.jpeg,.png"
                        drag
                    >
                        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                        <div class="el-upload__text">
                            拖拽文件到此处，或 <em>点击上传</em>
                        </div>
                        <template #tip>
                            <div class="el-upload__tip">
                                支持 PDF / Word / Excel / Markdown / 图片，单文件不超过 100MB
                            </div>
                        </template>
                    </el-upload>
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="uploadDialogVisible = false">取消</el-button>
                <el-button type="primary" :loading="uploading" @click="submitUpload">上传</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
    Plus, Search, Loading, Warning, UploadFilled,
    Document, Picture, Grid, Memo, Collection, Files
} from '@element-plus/icons-vue'
import {
    knowledgeDocumentList,
    knowledgeDocumentCreate,
    knowledgeDocumentDelete,
    knowledgeDocumentReprocess,
    knowledgeDocumentStats,
} from '@/restful/api'

const loading = ref(false)
const uploading = ref(false)
const documents = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchKeyword = ref('')
const statusFilter = ref('')
const selectedCategory = ref('all')
const uploadDialogVisible = ref(false)
const uploadRef = ref(null)
const stats = ref({ total: 0, ready: 0, by_category: [] })

const uploadForm = ref({
    title: '',
    category: 'requirement',
    file: null,
})

const categories = [
    { value: 'all', label: '全部文档', icon: 'Collection' },
    { value: 'requirement', label: '需求文档', icon: 'Memo' },
    { value: 'tech_design', label: '技术方案', icon: 'Grid' },
    { value: 'test_case', label: '测试用例', icon: 'Document' },
    { value: 'business', label: '业务知识', icon: 'Files' },
    { value: 'generated', label: 'AI生成用例', icon: 'Picture' },
    { value: 'other', label: '其他', icon: 'Document' },
]

const getCategoryCount = (catValue) => {
    if (catValue === 'all') return stats.value.total || 0
    const found = (stats.value.by_category || []).find(c => c.category === catValue)
    return found ? found.count : 0
}

const getCategoryLabel = (value) => {
    const cat = categories.find(c => c.value === value)
    return cat ? cat.label : value
}

const getCategoryType = (value) => {
    const map = { requirement: 'primary', tech_design: 'success', test_case: 'warning', business: 'info', generated: 'danger', other: '' }
    return map[value] || ''
}

const getStatusType = (s) => {
    const map = { ready: 'success', processing: 'warning', pending: 'info', failed: 'danger' }
    return map[s] || ''
}

const getStatusLabel = (s) => {
    const map = { ready: '可用', processing: '解析中', pending: '待处理', failed: '失败' }
    return map[s] || s
}

const getFileIcon = (fileType) => {
    const map = { pdf: 'Document', docx: 'Memo', xlsx: 'Grid', image: 'Picture', md: 'Document', txt: 'Document' }
    return map[fileType] || 'Document'
}

const formatSize = (bytes) => {
    if (!bytes) return '-'
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

const formatDate = (dt) => {
    if (!dt) return ''
    return new Date(dt).toLocaleDateString('zh-CN')
}

let searchTimer = null
const handleSearch = () => {
    clearTimeout(searchTimer)
    searchTimer = setTimeout(() => fetchDocuments(), 400)
}

const selectCategory = (value) => {
    selectedCategory.value = value
    currentPage.value = 1
    fetchDocuments()
}

const fetchDocuments = async () => {
    loading.value = true
    try {
        const params = {
            page: currentPage.value,
            page_size: pageSize.value,
        }
        if (searchKeyword.value) params.search = searchKeyword.value
        if (statusFilter.value) params.status = statusFilter.value
        if (selectedCategory.value !== 'all') params.category = selectedCategory.value

        const res = await knowledgeDocumentList(params)
        documents.value = res.data.results || res.data || []
        total.value = res.data.count || documents.value.length
    } catch (e) {
        ElMessage.error('加载文档列表失败')
    } finally {
        loading.value = false
    }
}

const fetchStats = async () => {
    try {
        const res = await knowledgeDocumentStats()
        stats.value = res.data
    } catch (e) {
        // ignore
    }
}

const handleFileChange = (file) => {
    uploadForm.value.file = file.raw
    if (!uploadForm.value.title) {
        uploadForm.value.title = file.name.replace(/\.[^.]+$/, '')
    }
}

const submitUpload = async () => {
    if (!uploadForm.value.title.trim()) {
        ElMessage.warning('请输入文档标题')
        return
    }
    if (!uploadForm.value.file) {
        ElMessage.warning('请选择文件')
        return
    }

    uploading.value = true
    try {
        const formData = new FormData()
        formData.append('title', uploadForm.value.title)
        formData.append('category', uploadForm.value.category)
        formData.append('file', uploadForm.value.file)

        await knowledgeDocumentCreate(formData)
        ElMessage.success('上传成功，后台正在解析文档...')
        uploadDialogVisible.value = false
        uploadForm.value = { title: '', category: 'requirement', file: null }
        uploadRef.value?.clearFiles()
        fetchDocuments()
        fetchStats()
    } catch (e) {
        ElMessage.error(e?.response?.data?.detail || '上传失败')
    } finally {
        uploading.value = false
    }
}

const reprocessDoc = async (doc) => {
    try {
        await knowledgeDocumentReprocess(doc.id)
        ElMessage.success('已重新提交处理')
        fetchDocuments()
    } catch (e) {
        ElMessage.error('操作失败')
    }
}

const deleteDoc = async (doc) => {
    try {
        await ElMessageBox.confirm(`确定删除文档「${doc.title}」？删除后向量数据也会一并清除。`, '提示', {
            type: 'warning',
        })
        await knowledgeDocumentDelete(doc.id)
        ElMessage.success('删除成功')
        fetchDocuments()
        fetchStats()
    } catch (e) {
        if (e !== 'cancel') ElMessage.error('删除失败')
    }
}

// 轮询处理中的文档
let pollTimer = null
const startPolling = () => {
    pollTimer = setInterval(() => {
        const hasProcessing = documents.value.some(d => ['processing', 'pending'].includes(d.status))
        if (hasProcessing) {
            fetchDocuments()
            fetchStats()
        }
    }, 3000)
}

onMounted(() => {
    fetchDocuments()
    fetchStats()
    startPolling()
})
</script>

<style scoped>
.knowledge-base-page {
    padding: 20px;
    height: 100%;
    display: flex;
    flex-direction: column;
    background: #f5f7fa;
}

.page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}

.header-left {
    display: flex;
    align-items: center;
    gap: 12px;
}

.page-title {
    margin: 0;
    font-size: 20px;
    font-weight: 600;
    color: #1a2332;
}

.main-layout {
    display: flex;
    gap: 16px;
    flex: 1;
    min-height: 0;
}

.category-sidebar {
    width: 160px;
    background: #fff;
    border-radius: 8px;
    padding: 12px 0;
    flex-shrink: 0;
    height: fit-content;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

.category-title {
    font-size: 12px;
    color: #8a9fb2;
    padding: 0 16px 8px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.category-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    cursor: pointer;
    font-size: 13px;
    color: #4a5568;
    transition: all 0.2s;
    position: relative;
}

.category-item:hover {
    background: #f0f4ff;
    color: #409eff;
}

.category-item.active {
    background: #ecf5ff;
    color: #409eff;
    font-weight: 500;
}

.cat-badge {
    margin-left: auto;
}

.doc-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
}

.search-bar {
    display: flex;
    align-items: center;
    margin-bottom: 16px;
}

.doc-list {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.doc-card {
    background: #fff;
    border-radius: 8px;
    padding: 16px;
    display: flex;
    align-items: flex-start;
    gap: 14px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    transition: box-shadow 0.2s;
}

.doc-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.doc-icon {
    width: 44px;
    height: 44px;
    border-radius: 8px;
    background: #ecf5ff;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #409eff;
    flex-shrink: 0;
}

.doc-info {
    flex: 1;
    min-width: 0;
}

.doc-title {
    font-size: 15px;
    font-weight: 500;
    color: #1a2332;
    margin-bottom: 6px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.doc-meta {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
    flex-wrap: wrap;
}

.meta-item {
    font-size: 12px;
    color: #8a9fb2;
}

.doc-summary {
    font-size: 12px;
    color: #6b7785;
    margin-top: 4px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.doc-tags {
    margin-top: 6px;
}

.doc-status {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 6px;
    flex-shrink: 0;
}

.doc-actions {
    display: flex;
    flex-direction: column;
    gap: 6px;
    flex-shrink: 0;
}

.error-tip {
    cursor: pointer;
}

.pagination-wrapper {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
}
</style>
