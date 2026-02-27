# Vue 3 升级指南

## 已完成的升级

### 1. ✅ 依赖升级
- Vue 2.5.2 → Vue 3.3.11
- Element UI 2.15.3 → Element Plus 2.4.4
- Vue Router 3.x → Vue Router 4.2.5
- Vuex 3.x → Vuex 4.1.0
- Webpack 3.x → Vite 5.x (推荐) / Webpack 5.x (备用)

### 2. ✅ 核心文件更新
- `main.js`: 使用 `createApp()` 替代 `new Vue()`
- `router/index.js`: 使用 `createRouter()` 和 `createWebHistory()`
- `store/index.js`: 使用 `createStore()`
- `index.html`: 添加 `<script type="module">`
- `vite.config.js`: 新增 Vite 配置文件

### 3. ✅ 全局属性迁移
- `Vue.filter()` → `app.config.globalProperties.$filters`
- `Vue.prototype.$api` → `app.config.globalProperties.$api`

## 组件升级指南

### Filters 迁移

**Vue 2:**
```vue
{{ date | datetimeFormat }}
{{ timestamp | timestampToTime }}
```

**Vue 3:**
```vue
{{ $filters.datetimeFormat(date) }}
{{ $filters.timestampToTime(timestamp) }}
```

### 事件监听器

**Vue 2:**
```vue
<el-input @input.native="handleInput" />
```

**Vue 3:**
```vue
<el-input @input="handleInput" />
```
（`.native` 修饰符已移除）

### Element UI → Element Plus 主要变化

1. **图标使用**
```vue
<!-- Vue 2 + Element UI -->
<i class="el-icon-search"></i>

<!-- Vue 3 + Element Plus -->
<el-icon><Search /></el-icon>
<script>
import { Search } from '@element-plus/icons-vue'
export default {
  components: { Search }
}
</script>
```

2. **组件名变化（大部分保持不变）**
- `el-table` → `el-table` ✅ 保持
- `el-form` → `el-form` ✅ 保持
- `el-dialog` → `el-dialog` ✅ 保持
- `el-button` → `el-button` ✅ 保持

3. **API 变化**
- `this.$message()` → 直接使用（已全局注册）
- `this.$confirm()` → `ElMessageBox.confirm()`

### v-model 语法

**Vue 2:**
```vue
<custom-component v-model="value" />
<!-- 等价于 -->
<custom-component :value="value" @input="value = $event" />
```

**Vue 3:**
```vue
<custom-component v-model="value" />
<!-- 等价于 -->
<custom-component :modelValue="value" @update:modelValue="value = $event" />
```

### $attrs 和 $listeners

**Vue 2:**
```vue
v-bind="$attrs" v-on="$listeners"
```

**Vue 3:**
```vue
v-bind="$attrs"
```
（`$listeners` 已合并到 `$attrs`）

### 生命周期钩子（Options API保持不变）

✅ 继续使用 Options API，无需修改：
- `beforeCreate`, `created`
- `beforeMount`, `mounted`
- `beforeUpdate`, `updated`
- `beforeDestroy` → `beforeUnmount`
- `destroyed` → `unmounted`

## 运行命令

### 开发环境
```bash
# 安装依赖
npm install

# 或使用 yarn
yarn install

# 启动开发服务器 (Vite)
npm run dev

# 启动开发服务器 (Webpack, 备用)
npm run dev:webpack
```

### 生产构建
```bash
# Vite 构建 (推荐)
npm run build

# Webpack 构建 (备用)
npm run build:webpack
```

## 兼容性说明

- ✅ 保留 Options API：所有组件继续使用 Options API，无需重写
- ✅ 渐进升级：可逐步迁移到 Composition API
- ⚠️ 不兼容 IE 11：Vue 3 不再支持 IE 11
- ✅ 构建工具：优先使用 Vite（更快），Webpack 5 作为备用

## 下一步

1. 运行 `npm install` 安装新依赖
2. 运行 `npm run dev` 启动开发服务器
3. 测试所有功能模块
4. 修复可能出现的兼容性问题
