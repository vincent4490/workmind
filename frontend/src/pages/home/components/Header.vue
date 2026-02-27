<template>
    <div class="nav-header">
        <div class="logo-and-title">
            <img
                class="side-logo"
                src="~@/assets/images/workmind-icon.png"
                alt="sidebar-logo"
            />
            <span style="color: #D9D9D9; font-size: 23px;">{{ platformTitle }}</span>
        </div>
        <div class="right">
            <div style="float: right; color: #D9D9D9; margin-right: 100px; display: flex; align-items: center; gap: 5px;">
                <el-icon><User /></el-icon>
                <span style="font-size: 15px">{{ username }}</span>

                <a style="padding-left: 10px; cursor: pointer;" @click="handleLogOut">退出</a>
            </div>
        </div>
    </div>
</template>

<script setup>
import { computed, getCurrentInstance, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useStore } from 'vuex'
import { useGlobalProperties } from '@/composables'
import { ElMessage } from 'element-plus'
import { User } from '@element-plus/icons-vue'

const router = useRouter()
const store = useStore()
const { setLocalValue } = useGlobalProperties()

// 获取全局属性
const instance = getCurrentInstance()
const api = instance?.appContext.config.globalProperties.$api

// 计算属性
const platformTitle = computed(() => store.state.WorkMind)

// 获取用户名
const username = computed(() => {
    // 优先从user对象中获取username
    if (store.state.user) {
        // 如果user是字符串，尝试解析为JSON
        if (typeof store.state.user === 'string') {
            try {
                const userObj = JSON.parse(store.state.user)
                return userObj.username || userObj.user || userObj.name || ''
            } catch (e) {
                return store.state.user
            }
        }
        // 如果user是对象，直接获取username
        return store.state.user.username || store.state.user.user || store.state.user.name || ''
    }
    // 如果没有user，尝试从name获取（向后兼容）
    return store.state.name || ''
})

// 退出登录状态
const isLoggingOut = ref(false)

// 退出登录
const handleLogOut = async () => {
    // 防止重复点击
    if (isLoggingOut.value) {
        return
    }
    
    isLoggingOut.value = true
    
    try {
        // 调用退出登录接口（即使失败也继续执行退出逻辑）
        try {
            await api.logout()
        } catch (error) {
            // 静默处理错误，不显示错误提示
            console.log('退出登录接口调用失败（已忽略）:', error)
        }
    } finally {
        // 清除所有本地状态
        store.commit('isLogin', '')
        store.commit('setUser', null)
        store.commit('setName', '')
        store.commit('setId', '')
        store.commit('setIsSuperuser', false)
        store.commit('setRouterName', '')
        
        // 清除localStorage
        setLocalValue('token', '')
        setLocalValue('user', '')
        setLocalValue('name', '')
        setLocalValue('id', '')
        setLocalValue('is_superuser', false)
        setLocalValue('routerName', '')
        
        // 直接使用window.location跳转，确保完全刷新页面
        window.location.href = '/workmind/login'
    }
}
</script>

<style scoped>
.right {
    position: fixed;
    left: 300px;
    right: 0;
    top: 0;
}

.right div a:hover {
    color: darkcyan;
}

.nav-header {
    position: fixed;
    left: 0;
    right: 0;
    z-index: 100;
    background: #242f42;
    margin: 0 auto;
    font-size: 14px;
    width: 100%;
    height: 49px;
    line-height: 49px;
}

.side-logo {
    width: 40px;
    height: 40px;
    padding-left: 10px;
    vertical-align: middle;
    object-fit: contain;
    transition: transform 0.3s ease;
}

.side-logo:hover {
    transform: scale(1.1);
}

.logo-and-title {
    display: flex;
    align-items: center;
}

.a-text {
    margin-right: 10px;
    font-size: 15px;
    color: #d9d9d9;
}
</style>
