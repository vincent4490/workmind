<template>
  <el-dialog
    v-model="dialogVisible"
    :title="isEdit ? '编辑元素' : '新增元素'"
    width="700px"
    @close="handleClose"
  >
    <el-form :model="formData" ref="formRef" label-width="120px" :rules="rules">
      <el-form-item label="元素名称" prop="name" required>
        <el-input v-model="formData.name" placeholder="如：登录按钮" />
      </el-form-item>
      
      <el-form-item label="元素类型" prop="element_type" required>
        <el-radio-group v-model="formData.element_type" @change="handleTypeChange">
          <el-radio value="image">图片元素</el-radio>
          <el-radio value="pos">坐标元素</el-radio>
          <el-radio value="region">区域元素</el-radio>
        </el-radio-group>
      </el-form-item>
      
      <el-form-item label="标签">
        <el-select
          v-model="formData.tags"
          multiple
          filterable
          allow-create
          placeholder="输入标签后回车"
          style="width: 100%"
        >
          <el-option label="登录" value="登录" />
        </el-select>
        <div style="color: #909399; font-size: 12px; margin-top: 5px;">
          💡 提示：输入标签回车创建
        </div>
      </el-form-item>
      
      <!-- 图片类型配置 -->
      <template v-if="formData.element_type === 'image'">
        <el-divider content-position="left">图片配置</el-divider>
        
        <el-form-item label="图片分类" required>
          <div style="display: flex; gap: 10px;">
            <el-select 
              v-model="formData.config.image_category"
              placeholder="选择分类"
              filterable
              style="flex: 1;"
            >
              <el-option 
                v-for="cat in imageCategories" 
                :key="cat" 
                :label="cat" 
                :value="cat"
              >
                <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
                  <span>{{ cat }}</span>
                  <el-button
                    v-if="cat !== 'common'"
                    type="danger"
                    size="small"
                    link
                    :icon="Delete"
                    @click.stop="handleDeleteCategory(cat)"
                    title="删除分类"
                    style="padding: 0; margin-left: 8px;"
                  />
                </div>
              </el-option>
            </el-select>
            <el-button 
              type="primary" 
              :icon="Plus" 
              @click="showCreateCategoryDialog"
              title="创建新分类"
            />
          </div>
          <div style="color: #909399; font-size: 12px; margin-top: 5px;">
            💡 提示：图片将保存到 Template/<分类>/ 目录下
          </div>
        </el-form-item>
        
        <el-form-item label="元素图片">
          <!-- 编辑模式：显示当前图片和更换选项 -->
          <div v-if="isEdit && formData.config.image_path" class="current-image-section">
            <div style="color: #606266; font-size: 14px; margin-bottom: 10px; font-weight: 500;">
              📷 当前图片
            </div>
            
            <!-- 图片预览 -->
            <div class="image-preview-box">
              <el-image 
                :src="currentImageUrl" 
                style="max-width: 200px; max-height: 150px; border-radius: 4px;"
                fit="contain"
                :preview-src-list="[currentImageUrl]"
              >
                <template #error>
                  <div class="image-error">
                    <el-icon :size="50"><Picture /></el-icon>
                    <div>加载失败</div>
                  </div>
                </template>
              </el-image>
            </div>
            
            <!-- 图片信息 -->
            <div class="image-info-box">
              <div class="info-item">
                <el-icon><Folder /></el-icon>
                <span>{{ formData.config.image_path }}</span>
              </div>
            </div>
            
            <!-- 操作按钮 -->
            <el-space style="margin-top: 10px">
              <el-button 
                v-if="!showUpload" 
                type="primary" 
                size="small"
                :icon="Upload"
                @click="handleChangeImage"
              >
                更换图片
              </el-button>
              <el-button 
                v-if="showUpload"
                size="small"
                @click="cancelUpload"
              >
                取消更换
              </el-button>
            </el-space>
            
            <!-- 隐藏的 upload 组件，仅用于触发文件选择 -->
            <el-upload
              ref="uploadRef"
              :auto-upload="false"
              :on-change="handleImageChange"
              :on-remove="handleRemoveImage"
              :limit="1"
              :show-file-list="false"
              accept="image/png,image/jpg,image/jpeg"
              style="display: none;"
            />
            
            <!-- 新图片预览区域 -->
            <div v-if="showUpload && imagePreview" style="margin-top: 15px">
              <div style="color: #67C23A; font-size: 14px; margin-bottom: 10px; font-weight: 500;">
                <el-icon><SuccessFilled /></el-icon> 新图片
              </div>
              
              <!-- 图片预览 -->
              <div class="image-preview-box" style="border-color: #67C23A;">
                <el-image 
                  :src="imagePreview" 
                  style="max-width: 200px; max-height: 150px; border-radius: 4px;"
                  fit="contain"
                  :preview-src-list="[imagePreview]"
                />
              </div>
              
              <!-- 图片信息 -->
              <div class="image-info-box">
                <div class="info-item">
                  <el-icon><Document /></el-icon>
                  <span>{{ imageFile?.name || '新选择的图片' }}</span>
                </div>
              </div>
              
              <!-- 提示信息 -->
              <div style="color: #67C23A; font-size: 12px; margin-top: 8px;">
                💡 保存后将替换当前图片
              </div>
            </div>
          </div>
          
          <!-- 新建模式：直接显示上传 -->
          <div v-else>
            <el-upload
              ref="uploadRef"
              :auto-upload="false"
              :on-change="handleImageChange"
              :on-exceed="handleExceed"
              :limit="1"
              accept="image/png,image/jpg,image/jpeg"
              list-type="picture"
            >
              <el-button type="primary" size="small" :icon="Upload">
                选择图片
              </el-button>
              <template #tip>
                <div style="color: #909399; font-size: 12px;">
                  支持 PNG、JPG 格式
                </div>
              </template>
            </el-upload>
            
            <div v-if="imagePreview" style="margin-top: 10px">
              <el-image :src="imagePreview" style="max-width: 200px" fit="contain" />
            </div>
          </div>
        </el-form-item>
        
        <el-form-item label="匹配阈值">
          <el-slider
            v-model="formData.config.threshold"
            :min="0.5"
            :max="1.0"
            :step="0.05"
            show-input
            :format-tooltip="val => val.toFixed(2)"
          />
          <div style="color: #909399; font-size: 12px; margin-top: 5px;">
            💡 提示：阈值越高匹配越严格（推荐 0.7-0.8），越低越宽松但可能误匹配
          </div>
        </el-form-item>
        
        <el-form-item label="颜色模式">
          <el-switch
            v-model="formData.config.rgb"
            active-text="RGB彩色"
            inactive-text="灰度"
          />
          <div style="color: #909399; font-size: 12px; margin-top: 5px;">
            💡 提示：RGB彩色适用于彩色界面，灰度适用于单色或对颜色不敏感的场景
          </div>
        </el-form-item>
      </template>
      
      <!-- 坐标类型配置 -->
      <template v-if="formData.element_type === 'pos'">
        <el-divider content-position="left">坐标配置</el-divider>
        
        <el-form-item label="X坐标" required>
          <el-input-number v-model="formData.config.x" :min="0" placeholder="横坐标" style="width: 100%" />
        </el-form-item>
        
        <el-form-item label="Y坐标" required>
          <el-input-number v-model="formData.config.y" :min="0" placeholder="纵坐标" style="width: 100%" />
        </el-form-item>
      </template>
      
      <!-- 区域类型配置 -->
      <template v-if="formData.element_type === 'region'">
        <el-divider content-position="left">区域配置</el-divider>
        
        <el-form-item label="左上角坐标" required>
          <el-space>
            <el-input-number v-model="formData.config.x1" placeholder="X1" style="width: 150px" />
            <el-input-number v-model="formData.config.y1" placeholder="Y1" style="width: 150px" />
          </el-space>
        </el-form-item>
        
        <el-form-item label="右下角坐标" required>
          <el-space>
            <el-input-number v-model="formData.config.x2" placeholder="X2" style="width: 150px" />
            <el-input-number v-model="formData.config.y2" placeholder="Y2" style="width: 150px" />
          </el-space>
        </el-form-item>
      </template>
    </el-form>
    
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
    </template>
  </el-dialog>
  
  <!-- 创建图片分类对话框 -->
  <el-dialog
    v-model="createCategoryVisible"
    title="创建图片分类"
    width="400px"
  >
    <el-form>
      <el-form-item label="分类名称">
        <el-input 
          v-model="newCategoryName" 
          placeholder="如：button, icon, menu"
          @keyup.enter="handleCreateCategory"
        />
        <div style="color: #909399; font-size: 12px; margin-top: 5px;">
          💡 只能包含字母、数字、下划线和中划线
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="createCategoryVisible = false">取消</el-button>
      <el-button type="primary" @click="handleCreateCategory" :loading="creatingCategory">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch, computed, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, Upload, Document, Folder, View, SuccessFilled, Picture } from '@element-plus/icons-vue'
import { useGlobalProperties } from '@/composables'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  editData: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:modelValue', 'success'])

const { $api } = useGlobalProperties()

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const isEdit = computed(() => !!props.editData)

const formRef = ref(null)
const uploadRef = ref(null)
const submitting = ref(false)
const imageFile = ref(null)
const imagePreview = ref('')
const showUpload = ref(false)  // 是否显示上传区域
const imageCategories = ref([])  // 图片分类列表
const createCategoryVisible = ref(false)  // 创建分类对话框
const newCategoryName = ref('')  // 新分类名称
const creatingCategory = ref(false)  // 创建分类中

// 当前图片 URL（用于编辑模式）
const currentImageUrl = computed(() => {
  if (props.editData?.id && props.editData?.config?.image_path) {
    return `/api/ui_test/elements/${props.editData.id}/preview/`
  }
  return ''
})

const formData = reactive({
  name: '',
  element_type: 'image',
  tags: [],
  config: {
    image_category: 'common',  // 图片分类
    threshold: 0.7,
    rgb: false,  // 默认灰度模式
    x: 0,
    y: 0,
    x1: 0,
    y1: 0,
    x2: 0,
    y2: 0
  }
})

const rules = {
  name: [
    { required: true, message: '请输入元素名称', trigger: 'blur' }
  ],
  element_type: [
    { required: true, message: '请选择元素类型', trigger: 'change' }
  ]
}

const handleTypeChange = () => {
  // 切换类型时重置配置
  formData.config = {
    threshold: 0.7,
    rgb: false,
    x: 0,
    y: 0,
    x1: 0,
    y1: 0,
    x2: 0,
    y2: 0,
    description: ''
  }
  imageFile.value = null
  imagePreview.value = ''
}

const handleImageChange = (file, fileList) => {
  console.log('🔔 handleImageChange 被触发', { file, fileList, showUpload: showUpload.value })
  
  // 防止重复触发
  if (!file || !file.raw) {
    console.warn('⚠️ 文件对象无效:', file)
    return
  }
  
  // 只处理最后一个文件 - 使用 uid 比较而不是引用比较
  if (fileList && fileList.length > 0) {
    const lastFile = fileList[fileList.length - 1]
    // 比较 uid 或 name，而不是对象引用
    if (lastFile.uid !== file.uid) {
      console.log('⏭️ 跳过非最后一个文件', { lastFileUid: lastFile.uid, currentFileUid: file.uid })
      return
    }
  }
  
  console.log('✅ 文件选择成功:', file.name, '大小:', file.size)
  
  // 确保 showUpload 为 true（防止状态不一致）
  if (!showUpload.value) {
    console.log('🔧 修正 showUpload 状态为 true')
    showUpload.value = true
  }
  
  imageFile.value = file.raw
  
  // 创建预览
  const reader = new FileReader()
  reader.onload = (e) => {
    imagePreview.value = e.target.result
    console.log('✅ 图片预览已生成', { previewLength: e.target.result?.length, showUpload: showUpload.value })
  }
  reader.onerror = (error) => {
    console.error('文件读取失败:', error)
    ElMessage.error('文件读取失败')
  }
  
  try {
    reader.readAsDataURL(file.raw)
  } catch (error) {
    console.error('读取文件异常:', error)
    ElMessage.error('读取文件异常')
  }
}

const handleExceed = () => {
  ElMessage.warning('最多只能上传 1 个图片文件')
}

// 更换图片 - 直接打开文件选择对话框
const handleChangeImage = async () => {
  console.log('🔄 开始更换图片')
  
  // 先清理之前的状态
  imagePreview.value = ''
  imageFile.value = null
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
  
  showUpload.value = true
  console.log('✅ showUpload 设置为 true')
  
  // 等待 DOM 更新后，触发文件选择
  await nextTick()
  
  // 触发 el-upload 内部的文件选择
  if (uploadRef.value) {
    // el-upload 内部有一个 input 元素，我们需要找到它并触发点击
    const uploadElement = uploadRef.value.$el
    const inputElement = uploadElement.querySelector('input[type="file"]')
    if (inputElement) {
      // 重置 input 的 value，确保可以选择相同文件
      inputElement.value = ''
      console.log('🖱️ 触发文件选择器')
      inputElement.click()
    } else {
      console.error('❌ 找不到 input[type="file"] 元素')
    }
  } else {
    console.error('❌ uploadRef 不存在')
  }
}

// 取消更换图片
const cancelUpload = () => {
  console.log('❌ 取消更换图片')
  showUpload.value = false
  imagePreview.value = ''
  imageFile.value = null
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
  console.log('✅ 状态已清理', { showUpload: showUpload.value, hasPreview: !!imagePreview.value })
}

// 移除图片
const handleRemoveImage = () => {
  imageFile.value = null
  imagePreview.value = ''
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    
    console.log('📝 开始提交表单')
    console.log('- 编辑模式:', isEdit.value)
    console.log('- 元素类型:', formData.element_type)
    console.log('- 是否选择了新文件:', imageFile.value !== null)
    console.log('- 当前 image_path:', formData.config.image_path)
    
    submitting.value = true
    
    // 图片类型需要先上传图片
    if (formData.element_type === 'image') {
      if (!isEdit.value && !imageFile.value) {
        ElMessage.warning('请选择图片文件')
        submitting.value = false
        return
      }
      
      // 上传图片（如果有新图片）
      if (imageFile.value) {
        // 使用 image_category
        const imageCategory = formData.config.image_category || 'common'
        // 编辑模式下传递元素ID，避免检测到自身
        const elementId = props.editData?.id || null
        
        const uploadResponse = await $api.uploadElementImage(imageFile.value, imageCategory, elementId)
        console.log('上传响应:', uploadResponse)
        
        if (uploadResponse.code === 0) {
          formData.config.image_path = uploadResponse.data.image_path
          formData.config.file_hash = uploadResponse.data.file_hash
          console.log('图片上传成功, image_path:', formData.config.image_path)
        } else {
          // 显示详细的错误信息
          let errorMessage = uploadResponse.msg || '上传图片失败'
          
          // 如果有详细说明和建议，添加到消息中
          if (uploadResponse.detail) {
            errorMessage += `\n\n${uploadResponse.detail}`
          }
          if (uploadResponse.suggestion) {
            errorMessage += `\n\n💡 建议：${uploadResponse.suggestion}`
          }
          
          // 如果有已存在的元素信息
          if (uploadResponse.data?.existing_element) {
            const existing = uploadResponse.data.existing_element
            errorMessage += `\n\n已存在元素：${existing.name} (ID: ${existing.id})`
            if (existing.image_path) {
              errorMessage += `\n文件路径：${existing.image_path}`
            }
          }
          
          ElMessage.error({
            message: errorMessage,
            duration: 8000,
            showClose: true,
            dangerouslyUseHTMLString: false
          })
          submitting.value = false
          return
        }
      } else if (isEdit.value && !formData.config.image_path) {
        // 编辑模式下，如果没有上传新图片，且原有 image_path 为空，给出提示
        console.warn('警告：编辑模式下没有图片路径')
      }
    }
    
    // 准备提交数据，根据类型清理不需要的字段
    const submitData = {
      name: formData.name,
      element_type: formData.element_type,
      tags: formData.tags,
      config: {}
    }
    
    // 根据元素类型只包含必要的配置字段
    if (formData.element_type === 'image') {
      submitData.config = {
        image_category: formData.config.image_category || 'common',
        threshold: formData.config.threshold,
        rgb: formData.config.rgb,
        image_path: formData.config.image_path || '',
        file_hash: formData.config.file_hash || ''
      }
      
      console.log('最终提交的 config:', submitData.config)
    } else if (formData.element_type === 'pos') {
      submitData.config = {
        x: formData.config.x,
        y: formData.config.y
      }
    } else if (formData.element_type === 'region') {
      submitData.config = {
        x1: formData.config.x1,
        y1: formData.config.y1,
        x2: formData.config.x2,
        y2: formData.config.y2
      }
    }
    
    // 创建或更新元素
    let response
    if (isEdit.value) {
      response = await $api.updateUiElement(props.editData.id, submitData)
    } else {
      response = await $api.createUiElement(submitData)
    }
    
    if (response.code === 0) {
      ElMessage.success(isEdit.value ? '更新成功' : '创建成功')
      emit('success')
      handleClose()
    } else {
      ElMessage.error(response.msg || '操作失败')
    }
  } catch (error) {
    console.error('提交失败:', error)
    if (error !== 'validation failed') {
      ElMessage.error('操作失败')
    }
  } finally {
    submitting.value = false
  }
}

const handleClose = () => {
  // 先重置表单
  if (formRef.value) {
    formRef.value.resetFields()
  }
  
  // 清理状态
  imageFile.value = null
  imagePreview.value = ''
  showUpload.value = false
  
  // 重置表单数据到初始状态
  Object.assign(formData, {
    name: '',
    element_type: 'image',
    tags: [],
    config: {
      image_category: 'common',
      threshold: 0.7,
      rgb: false,  // 默认灰度模式
      x: 0,
      y: 0,
      x1: 0,
      y1: 0,
      x2: 0,
      y2: 0
    }
  })
  
  // 最后关闭对话框
  emit('update:modelValue', false)
}

// 监听编辑数据
watch(() => props.editData, (data) => {
  if (data) {
    // 重置表单字段
    formData.name = data.name || ''
    formData.element_type = data.element_type || 'image'
    formData.tags = data.tags ? [...data.tags] : []
    
    // 深拷贝配置，避免响应式循环
    if (data.config) {
      formData.config = {
        image_category: data.config.image_category || 'common',
        threshold: data.config.threshold || 0.7,
        rgb: data.config.rgb !== undefined ? data.config.rgb : false,  // 默认灰度模式
        x: data.config.x || 0,
        y: data.config.y || 0,
        x1: data.config.x1 || 0,
        y1: data.config.y1 || 0,
        x2: data.config.x2 || 0,
        y2: data.config.y2 || 0,
        // 保留图片相关字段
        image_path: data.config.image_path || '',
        file_hash: data.config.file_hash || ''
      }
    }
    
    // 如果是图片类型，清空预览和上传状态
    if (data.element_type === 'image') {
      // 编辑模式下，清空新图片预览和文件选择
      imagePreview.value = ''
      imageFile.value = null
      showUpload.value = false
    } else {
      imagePreview.value = ''
      imageFile.value = null
      showUpload.value = false
    }
  }
}, { immediate: true, deep: false })

// 加载可用的分类列表
// 加载图片分类列表
const loadImageCategories = async () => {
  try {
    const response = await $api.getImageCategories()
    if (response.code === 0 && Array.isArray(response.data)) {
      imageCategories.value = response.data
    }
  } catch (error) {
    console.error('加载图片分类失败:', error)
    imageCategories.value = ['common']
  }
}

// 显示创建分类对话框
const showCreateCategoryDialog = () => {
  newCategoryName.value = ''
  createCategoryVisible.value = true
}

// 创建新分类
const handleCreateCategory = async () => {
  if (!newCategoryName.value.trim()) {
    ElMessage.warning('请输入分类名称')
    return
  }
  
  try {
    creatingCategory.value = true
    const response = await $api.createImageCategory(newCategoryName.value.trim())
    
    if (response.code === 0) {
      ElMessage.success('创建成功')
      // 刷新分类列表
      await loadImageCategories()
      // 自动选中新创建的分类
      formData.config.image_category = response.data.name
      // 关闭对话框
      createCategoryVisible.value = false
    } else {
      ElMessage.error(response.msg || '创建失败')
    }
  } catch (error) {
    console.error('创建分类失败:', error)
    ElMessage.error('创建失败')
  } finally {
    creatingCategory.value = false
  }
}

// 删除分类
const handleDeleteCategory = async (categoryName) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除分类 "${categoryName}" 吗？只能删除空目录。`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    const response = await $api.deleteImageCategory(categoryName)
    
    if (response.code === 0) {
      ElMessage.success('删除成功')
      // 刷新分类列表
      await loadImageCategories()
      // 如果当前选中的分类被删除，切换到 common
      if (formData.config.image_category === categoryName) {
        formData.config.image_category = 'common'
      }
    } else {
      ElMessage.error(response.msg || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除分类失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

// 组件挂载时加载分类
onMounted(() => {
  loadImageCategories()
})
</script>

<style scoped>
.el-divider {
  margin: 10px 0;
}

/* 当前图片区域 */
.current-image-section {
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
}

/* 图片预览框 */
.image-preview-box {
  display: inline-block;
  padding: 10px;
  background: white;
  border-radius: 4px;
  border: 1px solid #dcdfe6;
}

/* 图片加载错误 */
.image-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 30px;
  color: #909399;
  font-size: 12px;
}

/* 图片信息框 */
.image-info-box {
  margin-top: 10px;
  font-size: 12px;
  color: #606266;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 0;
}

.info-item .el-icon {
  color: #909399;
}
</style>
