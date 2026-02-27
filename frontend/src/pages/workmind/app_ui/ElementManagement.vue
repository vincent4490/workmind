<template>
  <div class="element-management">
    <el-card>
      <!-- 顶部操作栏 -->
      <template #header>
        <div class="header-actions">
          <el-space wrap>
            <!-- 类型切换 -->
            <el-radio-group v-model="filterType" @change="loadElements">
              <el-radio-button value="">全部</el-radio-button>
              <el-radio-button value="image">图片</el-radio-button>
              <el-radio-button value="pos">坐标</el-radio-button>
              <el-radio-button value="region">区域</el-radio-button>
            </el-radio-group>
            
            <!-- 搜索 -->
            <el-input
              v-model="searchKeyword"
              placeholder="搜索元素名称/标签"
              style="width: 250px"
              clearable
              @change="loadElements"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </el-space>
          
          <!-- 操作按钮 -->
          <el-space>
            <el-button type="success" @click="openCaptureDialog">
              <el-icon><Camera /></el-icon>
              从设备创建
            </el-button>
            <el-button type="primary" @click="openManualDialog">
              <el-icon><Plus /></el-icon>
              手动创建
            </el-button>
          </el-space>
        </div>
      </template>

      <!-- 元素列表 -->
      <el-table
        :data="elements"
        border
        v-loading="loading"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        
        <el-table-column prop="name" label="元素名称" width="200" fixed="left">
          <template #default="{ row }">
            <el-link type="primary" @click="handleView(row)">
              {{ row.name }}
            </el-link>
          </template>
        </el-table-column>
        
        <el-table-column prop="element_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getTypeTagColor(row.element_type)">
              {{ row.element_type_display }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column label="图片分类" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.element_type === 'image' && row.config?.image_category" type="info" size="small">
              {{ row.config.image_category }}
            </el-tag>
            <span v-else style="color: #909399;">-</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="tags" label="标签" width="200">
          <template #default="{ row }">
            <el-tag
              v-for="tag in row.tags"
              :key="tag"
              size="small"
              style="margin-right: 5px"
            >
              {{ tag }}
            </el-tag>
          </template>
        </el-table-column>
        
        <!-- 预览 -->
        <el-table-column label="预览" width="200" align="center">
          <template #default="{ row }">
            <!-- 图片类型 -->
            <div v-if="row.element_type === 'image'" class="preview-image">
              <el-image
                :src="getImageUrl(row)"
                fit="contain"
                style="width: 150px; height: 80px; cursor: pointer"
                :preview-src-list="[getImageUrl(row)]"
                preview-teleported
              />
            </div>
            
            <!-- 坐标类型 -->
            <div v-else-if="row.element_type === 'pos'" class="preview-pos">
              <el-space :size="4">
                <el-tag type="primary" size="small">X: {{ row.config?.x }}</el-tag>
                <el-tag type="primary" size="small">Y: {{ row.config?.y }}</el-tag>
              </el-space>
            </div>
            
            <!-- 区域类型 -->
            <div v-else-if="row.element_type === 'region'" class="preview-region">
              <el-space direction="vertical" :size="4">
                <el-space :size="4">
                  <el-tag type="success" size="small">X1: {{ row.config?.x1 }}</el-tag>
                  <el-tag type="success" size="small">Y1: {{ row.config?.y1 }}</el-tag>
                </el-space>
                <el-space :size="4">
                  <el-tag type="warning" size="small">X2: {{ row.config?.x2 }}</el-tag>
                  <el-tag type="warning" size="small">Y2: {{ row.config?.y2 }}</el-tag>
                </el-space>
              </el-space>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="usage_count" label="使用次数" width="100" sortable />
        
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="handleEdit(row)">
              编辑
            </el-button>
            <el-button size="small" @click="handleDuplicate(row)">
              复制
            </el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 批量操作栏 -->
      <div v-if="selectedElements.length > 0" class="batch-actions">
        <el-space>
          <span>已选择 {{ selectedElements.length }} 项</span>
          <el-button type="danger" size="small" @click="handleBatchDelete">
            批量删除
          </el-button>
        </el-space>
      </div>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="loadElements"
        @size-change="loadElements"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>

    <!-- 从设备截图创建对话框 -->
    <CaptureElementDialog
      v-model="captureDialogVisible"
      @success="handleCreateSuccess"
    />

    <!-- 手动创建/编辑对话框 -->
    <ManualElementDialog
      v-model="manualDialogVisible"
      :edit-data="editingElement"
      @success="handleCreateSuccess"
    />

    <!-- 查看详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      title="元素详情"
      width="800px"
    >
      <el-descriptions :column="2" border v-if="viewingElement">
        <el-descriptions-item label="元素名称">{{ viewingElement.name }}</el-descriptions-item>
        <el-descriptions-item label="元素类型">{{ viewingElement.element_type_display }}</el-descriptions-item>
        <el-descriptions-item label="标签" :span="2">
          <el-tag v-for="tag in viewingElement.tags" :key="tag" size="small" style="margin-right: 5px">
            {{ tag }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="配置信息" :span="2">
          <pre>{{ JSON.stringify(viewingElement.config, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="使用次数">{{ viewingElement.usage_count }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDate(viewingElement.created_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, Camera } from '@element-plus/icons-vue'
import { useGlobalProperties } from '@/composables'
import CaptureElementDialog from './components/CaptureElementDialog.vue'
import ManualElementDialog from './components/ManualElementDialog.vue'

const { $api } = useGlobalProperties()

// 状态
const loading = ref(false)
const elements = ref([])
const selectedElements = ref([])
const refreshTimestamp = ref(Date.now()) // 用于刷新图片缓存

// 筛选条件
const filterType = ref('')
const searchKeyword = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 对话框
const captureDialogVisible = ref(false)
const manualDialogVisible = ref(false)
const detailDialogVisible = ref(false)
const editingElement = ref(null)
const viewingElement = ref(null)

// 方法
const loadElements = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      size: pageSize.value,
      element_type: filterType.value,
      keyword: searchKeyword.value
    }
    
    const response = await $api.getUiElements(params)
    if (response.code === 0) {
      elements.value = response.data.results || []
      total.value = response.data.count || 0
      // 更新刷新时间戳，强制刷新所有图片
      refreshTimestamp.value = Date.now()
    }
  } catch (error) {
    ElMessage.error('加载元素列表失败')
  } finally {
    loading.value = false
  }
}

const handleSelectionChange = (selection) => {
  selectedElements.value = selection
}

const openCaptureDialog = () => {
  captureDialogVisible.value = true
}

const openManualDialog = () => {
  editingElement.value = null
  manualDialogVisible.value = true
}

const handleView = (row) => {
  viewingElement.value = row
  detailDialogVisible.value = true
}

const handleEdit = (row) => {
  editingElement.value = { ...row }
  manualDialogVisible.value = true
}

const handleDuplicate = async (row) => {
  try {
    const response = await $api.duplicateElement(row.id)
    if (response.code === 0) {
      ElMessage.success('复制成功')
      loadElements()
    }
  } catch (error) {
    ElMessage.error('复制失败')
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要删除元素"${row.name}"吗？`, '确认删除', {
      type: 'warning'
    })
    
    const response = await $api.deleteUiElement(row.id)
    if (response.code === 0) {
      ElMessage.success('删除成功')
      loadElements()
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleBatchDelete = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedElements.value.length} 个元素吗？`,
      '批量删除',
      { type: 'warning' }
    )
    
    const ids = selectedElements.value.map(el => el.id)
    const response = await $api.batchDeleteElements({ ids })
    
    if (response.code === 0) {
      ElMessage.success(response.msg)
      selectedElements.value = []
      loadElements()
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('批量删除失败')
    }
  }
}

const handleCreateSuccess = () => {
  loadElements()
}

// 获取图片 URL（添加时间戳防止缓存）
const getImageUrl = (row) => {
  if (!row.preview_url) return ''
  // 使用全局刷新时间戳，确保每次列表刷新时图片都会重新加载
  const separator = row.preview_url.includes('?') ? '&' : '?'
  return `${row.preview_url}${separator}_t=${refreshTimestamp.value}`
}

const getTypeTagColor = (type) => {
  const colorMap = {
    'image': 'primary',
    'pos': 'success',
    'region': 'warning'
  }
  return colorMap[type] || ''
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

// 初始化
onMounted(() => {
  loadElements()
})
</script>

<style scoped>
.element-management {
  padding: 20px;
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.preview-image {
  display: flex;
  justify-content: center;
  align-items: center;
}

.preview-pos, .preview-region {
  font-size: 13px;
}

.batch-actions {
  margin-top: 15px;
  padding: 10px;
  background-color: #f5f7fa;
  border-radius: 4px;
  display: flex;
  align-items: center;
}
</style>
