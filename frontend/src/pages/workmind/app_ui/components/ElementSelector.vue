<template>
  <el-dialog
    v-model="dialogVisible"
    title="从元素库选择"
    width="900px"
    @close="handleClose"
  >
    <!-- 筛选条件 -->
    <div class="filter-bar" style="margin-bottom: 15px">
      <el-space wrap>
        <el-radio-group v-model="filterType" size="small" @change="loadElements">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="image">图片</el-radio-button>
          <el-radio-button value="pos">坐标</el-radio-button>
          <el-radio-button value="region">区域</el-radio-button>
        </el-radio-group>
        
        <el-input
          v-model="searchKeyword"
          placeholder="搜索名称/标签"
          clearable
          size="small"
          style="width: 200px"
          @change="loadElements"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </el-space>
    </div>

    <!-- 元素列表 -->
    <el-table
      :data="elements"
      border
      v-loading="loading"
      max-height="450"
      highlight-current-row
      @current-change="handleSelectionChange"
    >
      <el-table-column type="index" label="#" width="50" />
      
      <el-table-column prop="name" label="元素名称" width="180">
        <template #default="{ row }">
          <el-tag :type="getTypeTagColor(row.element_type)" size="small" style="margin-right: 5px">
            {{ row.element_type_display }}
          </el-tag>
          {{ row.name }}
        </template>
      </el-table-column>
      
      <el-table-column prop="tags" label="标签" width="150">
        <template #default="{ row }">
          <el-tag
            v-for="tag in row.tags.slice(0, 2)"
            :key="tag"
            size="small"
            style="margin-right: 3px"
          >
            {{ tag }}
          </el-tag>
        </template>
      </el-table-column>
      
      <el-table-column label="预览" width="180">
        <template #default="{ row }">
          <div v-if="row.element_type === 'image'">
            <el-image
              :src="row.preview_url"
              fit="contain"
              style="width: 150px; height: 60px"
              :preview-src-list="[row.preview_url]"
              preview-teleported
            />
          </div>
          <div v-else-if="row.element_type === 'pos'" style="font-size: 12px">
            X: {{ row.config?.x }}, Y: {{ row.config?.y }}
          </div>
          <div v-else-if="row.element_type === 'region'" style="font-size: 12px">
            ({{ row.config?.x1 }},{{ row.config?.y1 }}) ~ ({{ row.config?.x2 }},{{ row.config?.y2 }})
          </div>
        </template>
      </el-table-column>
      
      <el-table-column prop="usage_count" label="使用" width="60" />
    </el-table>

    <!-- 分页 -->
    <el-pagination
      v-model:current-page="currentPage"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[10, 20, 50]"
      layout="total, prev, pager, next, sizes"
      @current-change="loadElements"
      @size-change="loadElements"
      style="margin-top: 15px; justify-content: center"
      small
    />

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" @click="handleConfirm" :disabled="!selectedElement">
        确定选择
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { useGlobalProperties } from '@/composables'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  elementType: {
    type: String,
    default: '' // 限制只显示特定类型的元素
  }
})

const emit = defineEmits(['update:modelValue', 'select'])

const { $api } = useGlobalProperties()

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// 状态
const loading = ref(false)
const elements = ref([])
const selectedElement = ref(null)

// 筛选条件
const filterType = ref('')
const searchKeyword = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

// 加载元素列表
const loadElements = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      size: pageSize.value,
      element_type: filterType.value || props.elementType,
      keyword: searchKeyword.value
    }
    
    const response = await $api.getUiElements(params)
    if (response.code === 0) {
      elements.value = response.data.results || []
      total.value = response.data.count || 0
    }
  } catch (error) {
    ElMessage.error('加载元素列表失败')
  } finally {
    loading.value = false
  }
}

// 选中元素
const handleSelectionChange = (row) => {
  selectedElement.value = row
}

// 确认选择
const handleConfirm = () => {
  if (selectedElement.value) {
    emit('select', selectedElement.value)
    handleClose()
  }
}

// 关闭对话框
const handleClose = () => {
  emit('update:modelValue', false)
  selectedElement.value = null
}

// 获取类型标签颜色
const getTypeTagColor = (type) => {
  const colorMap = {
    'image': 'primary',
    'pos': 'success',
    'region': 'warning'
  }
  return colorMap[type] || ''
}

// 监听对话框打开
watch(() => props.modelValue, (val) => {
  if (val) {
    filterType.value = props.elementType || ''
    loadElements()
  }
})
</script>

<style scoped>
.filter-bar {
  padding: 10px;
  background-color: #f5f7fa;
  border-radius: 4px;
}
</style>
