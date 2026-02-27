<template>
    <div class="tags-view-container">
        <scroll-pane ref="scrollPaneRef" class="tags-view-wrapper">
            <router-link
                v-for="tag in visitedViews"
                :key="tag.path"
                :to="{ path: tag.path }"
                custom
                v-slot="{ navigate }"
            >
                <span
                    :class="['tags-view-item', isActive(tag) ? 'active' : '']"
                    @click="navigate"
                    @click.middle="!isAffix(tag) ? closeSelectedTag(tag) : ''"
                    @contextmenu.prevent="openMenu(tag, $event)"
                >
                    {{ tag.title }}
                    <el-icon
                        v-if="!isAffix(tag)"
                        class="el-icon-close"
                        @click.prevent.stop="closeSelectedTag(tag)"
                    >
                        <Close />
                    </el-icon>
                </span>
            </router-link>
        </scroll-pane>
        <div class="tags-view-actions">
            <el-dropdown @command="handleCommand">
                <span class="tags-view-more">
                    <el-icon><More /></el-icon>
                </span>
                <template #dropdown>
                    <el-dropdown-menu>
                        <el-dropdown-item command="refresh">
                            <el-icon><Refresh /></el-icon>
                            刷新页面
                        </el-dropdown-item>
                        <el-dropdown-item command="close" :disabled="visitedViews.length === 1">
                            <el-icon><Close /></el-icon>
                            关闭当前
                        </el-dropdown-item>
                        <el-dropdown-item command="closeOthers" :disabled="visitedViews.length === 1">
                            <el-icon><CircleClose /></el-icon>
                            关闭其他
                        </el-dropdown-item>
                        <el-dropdown-item command="closeAll">
                            <el-icon><Delete /></el-icon>
                            关闭所有
                        </el-dropdown-item>
                    </el-dropdown-menu>
                </template>
            </el-dropdown>
        </div>
    </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStore } from 'vuex'
import { Close, Refresh, More, CircleClose, Delete } from '@element-plus/icons-vue'
import ScrollPane from './TagsView/ScrollPane.vue'

const route = useRoute()
const router = useRouter()
const store = useStore()

const scrollPaneRef = ref(null)
const selectedTag = ref({})
const affixTags = ref([])

const visitedViews = computed(() => store.state.visitedViews)

// 判断标签是否激活
const isActive = (tag) => {
    return tag.path === route.path
}

// 判断是否是固定标签
const isAffix = (tag) => {
    return tag.meta && tag.meta.affix
}

// 初始化标签
const initTags = () => {
    const tag = {
        name: route.name,
        path: route.path,
        meta: { ...route.meta }
    }
    addTag(tag)
}

// 添加标签
const addTag = (tag) => {
    if (tag.name) {
        store.dispatch('addView', tag)
    }
}

// 关闭选中的标签
const closeSelectedTag = (view) => {
    store.dispatch('delView', view).then(({ visitedViews }) => {
        if (isActive(view)) {
            toLastView(visitedViews, view)
        }
    })
}

// 跳转到最后一个标签
const toLastView = (visitedViews, view) => {
    const latestView = visitedViews.slice(-1)[0]
    if (latestView) {
        router.push(latestView.path)
    } else {
        // 如果没有标签了，跳转到首页
        if (view.name === 'Dashboard') {
            router.replace({ path: '/workmind/dashboard' })
        } else {
            router.push('/workmind/dashboard')
        }
    }
}

// 右键菜单
const openMenu = (tag, e) => {
    selectedTag.value = tag
}

// 下拉菜单命令处理
const handleCommand = (command) => {
    switch (command) {
        case 'refresh':
            refreshSelectedTag()
            break
        case 'close':
            closeSelectedTag(selectedTag.value || { path: route.path })
            break
        case 'closeOthers':
            closeOthersTags()
            break
        case 'closeAll':
            closeAllTags()
            break
    }
}

// 刷新当前标签
const refreshSelectedTag = () => {
    const view = selectedTag.value.path ? selectedTag.value : { path: route.path, name: route.name }
    store.dispatch('delCachedView', view).then(() => {
        nextTick(() => {
            router.replace({
                path: '/redirect' + view.path
            })
        })
    })
}

// 关闭其他标签
const closeOthersTags = () => {
    const view = selectedTag.value.path ? selectedTag.value : { path: route.path, name: route.name }
    store.dispatch('delOthersViews', view).then(() => {
        if (!isActive(view)) {
            router.push(view.path)
        }
    })
}

// 关闭所有标签
const closeAllTags = () => {
    store.dispatch('delAllViews').then(({ visitedViews }) => {
        toLastView(visitedViews, selectedTag.value)
    })
}

// 监听路由变化
watch(route, () => {
    initTags()
    nextTick(() => {
        scrollPaneRef.value?.moveToTarget(route)
    })
})

// 初始化
initTags()
</script>

<style scoped>
.tags-view-container {
    height: 42px;
    width: 100%;
    background: #1e2a3a;
    border-bottom: 1px solid #2d3e52;
    display: flex;
    align-items: center;
    padding: 0 10px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
}

.tags-view-wrapper {
    flex: 1;
    overflow: hidden;
}

.tags-view-item {
    display: inline-block;
    position: relative;
    cursor: pointer;
    height: 30px;
    line-height: 30px;
    padding: 0 12px;
    font-size: 13px;
    margin-left: 8px;
    background: rgba(255, 255, 255, 0.05);
    color: #8a9fb2;
    border: 1px solid #2d3e52;
    border-radius: 4px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.tags-view-item:first-of-type {
    margin-left: 0;
}

.tags-view-item:hover {
    background: rgba(0, 212, 255, 0.1);
    color: #00d4ff;
    border-color: #00d4ff;
}

.tags-view-item.active {
    background: linear-gradient(90deg, rgba(0, 212, 255, 0.2) 0%, rgba(0, 212, 255, 0.1) 100%);
    color: #00d4ff;
    border-color: #00d4ff;
    box-shadow: 0 0 8px rgba(0, 212, 255, 0.3);
}

.tags-view-item.active::before {
    content: '';
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #00d4ff;
    position: absolute;
    left: 6px;
    top: 50%;
    transform: translateY(-50%);
    box-shadow: 0 0 4px rgba(0, 212, 255, 0.8);
}

.tags-view-item .el-icon-close {
    width: 14px;
    height: 14px;
    margin-left: 6px;
    border-radius: 50%;
    transition: all 0.3s;
    vertical-align: middle;
}

.tags-view-item .el-icon-close:hover {
    background-color: rgba(0, 212, 255, 0.3);
    color: #fff;
}

.tags-view-actions {
    margin-left: 10px;
}

.tags-view-more {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    cursor: pointer;
    color: #8a9fb2;
    border-radius: 4px;
    transition: all 0.3s;
}

.tags-view-more:hover {
    background: rgba(0, 212, 255, 0.1);
    color: #00d4ff;
}

.tags-view-more .el-icon {
    font-size: 18px;
}
</style>
