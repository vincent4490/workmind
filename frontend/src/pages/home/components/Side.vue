<template>
    <el-menu
        class="common-side-bar modern-style"
        :default-active="$store.state.routerName"
        background-color="#1e2a3a"
        text-color="#8a9fb2"
        active-text-color="#00d4ff"
        @select="select"
    >
        <el-menu-item index="Dashboard">
            <el-icon><Odometer /></el-icon>
            <span>首页</span>
        </el-menu-item>

        <el-menu-item
            v-for="item in menuItems"
            :key="item.url"
            :index="item.url"
        >
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.name }}</span>
        </el-menu-item>

        <el-sub-menu
            v-for="item in subMenus"
            :key="item.url"
            :index="item.url"
        >
            <template #title>
                <el-icon><component :is="item.icon" /></el-icon>
                <span>{{ item.name }}</span>
            </template>
            <el-menu-item
                v-for="subItem in item.children"
                :key="subItem.url"
                :index="subItem.url"
            ><span>{{ subItem.name }}</span></el-menu-item>
        </el-sub-menu>
    </el-menu>
</template>

<script setup>
import { ref, computed, markRaw } from 'vue'
import { useRouter } from 'vue-router'
import { useStore } from 'vuex'
import { ElMessage } from 'element-plus'
import { useGlobalProperties } from '@/composables'
import { Odometer, Iphone, List, MagicStick } from '@element-plus/icons-vue'

const router = useRouter()
const store = useStore()
const { setLocalValue } = useGlobalProperties()

// 侧边栏菜单数据
const side_menu = ref([
    {
        name: "APP自动化",
        url: "AppAutomation",
        icon: markRaw(Iphone),
        children: [
            { name: "设备管理", url: "DeviceManagement" },
            { name: "应用包名管理", url: "AppPackageManagement" },
            { name: "元素管理", url: "ElementManagement" },
            { name: "UI场景编排", url: "UiTestSceneBuilder" },
            { name: "UI场景用例列表", url: "UiFlowCaseList" }
        ]
    },
    {
        name: "功能测试",
        url: "FunctionalTest",
        icon: markRaw(List),
        children: [
            { name: "需求管理", url: "RequirementManagement" },
            { name: "用例管理", url: "FunctionalTestCaseManagement" },
            { name: "测试计划", url: "TestPlanManagement" }
        ]
    },
    {
        name: "AI智能体",
        url: "AiAgent",
        icon: markRaw(MagicStick),
        children: [
            { name: "AI用例生成", url: "AiTestcaseGenerator" }
        ]
    }
])

// 计算属性：分离菜单项和子菜单
const menuItems = computed(() => {
    return side_menu.value.filter(item => !item.children)
})

const subMenus = computed(() => {
    return side_menu.value.filter(item => item.children && item.children.length > 0)
})

// 菜单选择处理
const select = (url) => {
    store.commit('setRouterName', url)
    
    if (!router.hasRoute(url)) {
        ElMessage.warning('该页面未配置路由')
        return
    }

    router.push({ name: url }).catch(err => {
        // 忽略NavigationDuplicated错误
        if (err.name !== 'NavigationDuplicated') {
            throw err
        }
    })
    
    setLocalValue('routerName', url)
}

// 生命周期
</script>

<style>
.common-side-bar {
    position: fixed;
    top: 48px;
    border-right: 1px solid #2d3e52;
    height: 100%;
    width: 202px;
    background: linear-gradient(180deg, #1e2a3a 0%, #253447 100%);
    display: inline-block;
}

/* 现代科技风格 - 悬停效果 */
.modern-style :deep(.el-menu-item:hover),
.modern-style :deep(.el-sub-menu__title:hover) {
    background: linear-gradient(90deg, rgba(0, 212, 255, 0.1) 0%, transparent 100%) !important;
    color: #00d4ff !important;
    border-left: 2px solid #00d4ff;
    transition: all 0.3s ease;
}

/* 激活状态 - 带发光效果 */
.modern-style :deep(.el-menu-item.is-active) {
    background: linear-gradient(90deg, rgba(0, 212, 255, 0.2) 0%, rgba(0, 212, 255, 0.05) 100%) !important;
    color: #00d4ff !important;
    border-left: 4px solid #00d4ff;
    box-shadow: inset 0 0 20px rgba(0, 212, 255, 0.1);
    font-weight: 500;
}

/* 子菜单背景 */
.modern-style :deep(.el-menu--inline) {
    background-color: #192533 !important;
}

/* 子菜单项悬停 */
.modern-style :deep(.el-menu--inline .el-menu-item:hover) {
    background: linear-gradient(90deg, rgba(0, 212, 255, 0.08) 0%, transparent 100%) !important;
    padding-left: 52px !important;
    transition: all 0.3s ease;
}

/* 子菜单激活项 */
.modern-style :deep(.el-menu--inline .el-menu-item.is-active) {
    background: linear-gradient(90deg, rgba(0, 212, 255, 0.15) 0%, rgba(0, 212, 255, 0.03) 100%) !important;
    color: #00d4ff !important;
    border-left: 3px solid #00d4ff;
}

/* 子菜单标题展开时 */
.modern-style :deep(.el-sub-menu.is-opened > .el-sub-menu__title) {
    background: rgba(0, 212, 255, 0.05) !important;
    color: #00d4ff !important;
}

/* 菜单项过渡动画 */
.modern-style :deep(.el-menu-item),
.modern-style :deep(.el-sub-menu__title) {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 图标样式 */
.modern-style :deep(.el-menu-item .el-icon),
.modern-style :deep(.el-sub-menu__title .el-icon) {
    margin-right: 10px;
    font-size: 18px;
    transition: color 0.3s ease;
}

/* 菜单项文字样式 */
.modern-style :deep(.el-menu-item span),
.modern-style :deep(.el-sub-menu__title span) {
    font-family: "Microsoft YaHei", sans-serif;
    transition: color 0.3s ease;
    vertical-align: middle;
}

/* 确保菜单项文字颜色正确显示 */
.modern-style :deep(.el-menu-item) {
    color: #8a9fb2 !important;
}

.modern-style :deep(.el-sub-menu__title) {
    color: #8a9fb2 !important;
}

/* 激活项和悬停项文字和图标颜色 */
.modern-style :deep(.el-menu-item.is-active span),
.modern-style :deep(.el-menu-item.is-active .el-icon),
.modern-style :deep(.el-menu-item:hover span),
.modern-style :deep(.el-menu-item:hover .el-icon),
.modern-style :deep(.el-sub-menu__title:hover span),
.modern-style :deep(.el-sub-menu__title:hover .el-icon),
.modern-style :deep(.el-sub-menu.is-opened > .el-sub-menu__title span),
.modern-style :deep(.el-sub-menu.is-opened > .el-sub-menu__title .el-icon) {
    color: #00d4ff !important;
}

/* 子菜单项文字和图标 */
.modern-style :deep(.el-menu--inline .el-menu-item) {
    color: #8a9fb2 !important;
}

.modern-style :deep(.el-menu--inline .el-menu-item.is-active span),
.modern-style :deep(.el-menu--inline .el-menu-item:hover span) {
    color: #00d4ff !important;
}
</style>
