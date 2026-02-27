<template>
    <div class="login-container">
        <!-- 背景装饰 -->
        <div class="login-background">
            <div class="bg-shape bg-shape-1"></div>
            <div class="bg-shape bg-shape-2"></div>
            <div class="bg-shape bg-shape-3"></div>
        </div>

        <!-- 登录表单卡片 -->
        <div class="login-card">
            <!-- Logo 区域 -->
            <div class="login-header">
                <img
                    class="login-logo-icon"
                    src="~@/assets/images/logo.png"
                    alt="WorkMind Logo"
                />
                <h1 class="login-title">WorkMind 智能体平台</h1>
                <p class="login-subtitle">欢迎回来,请登录您的账号</p>
            </div>

            <!-- 表单区域 -->
            <el-form
                id="submit-form"
                @keyup.enter="submitForm"
                :model="loginForm"
                class="login-form"
            >
                <div class="form-content">
                    <!-- 用户名输入 -->
                    <div class="form-item">
                        <el-input
                            v-model="loginForm.username"
                            placeholder="请输入账号"
                            size="large"
                            clearable
                            class="login-input"
                        >
                            <template #prefix>
                                <el-icon class="input-icon">
                                    <User />
                                </el-icon>
                            </template>
                        </el-input>
                        <div
                            v-if="usernameInvalid"
                            class="error-message"
                            @mouseover="usernameInvalid = ''"
                        >
                            {{ usernameInvalid }}
                        </div>
                    </div>

                    <!-- 密码输入 -->
                    <div class="form-item">
                        <el-input
                            v-model="loginForm.password"
                            type="password"
                            placeholder="请输入密码"
                            size="large"
                            show-password
                            clearable
                            class="login-input"
                        >
                            <template #prefix>
                                <el-icon class="input-icon">
                                    <Lock />
                                </el-icon>
                            </template>
                        </el-input>
                        <div
                            v-if="passwordInvalid"
                            class="error-message"
                            @mouseover="passwordInvalid = ''"
                        >
                            {{ passwordInvalid }}
                        </div>
                    </div>

                    <!-- 登录按钮 -->
                    <div class="form-submit">
                        <el-button
                            type="primary"
                            size="large"
                            class="login-button"
                            @click="submitForm"
                            :loading="isLoading"
                            :disabled="isLoading"
                        >
                            <span v-if="!isLoading">登录</span>
                            <span v-else>登录中...</span>
                        </el-button>
                    </div>
                </div>
            </el-form>
        </div>
    </div>
</template>

<script setup>
import { ref, reactive, getCurrentInstance } from 'vue'
import { useRouter } from 'vue-router'
import { useStore } from 'vuex'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'

// Router & Store
const router = useRouter()
const store = useStore()

// 获取全局属性
const instance = getCurrentInstance()
const api = instance?.appContext.config.globalProperties.$api
const setLocalValue = instance?.appContext.config.globalProperties.setLocalValue

// 响应式数据
const isLoading = ref(false)
const loginForm = reactive({
    username: '',
    password: ''
})
const usernameInvalid = ref('')
const passwordInvalid = ref('')

// 验证方法
const validateUserName = () => {
    if (loginForm.username.replace(/(^\s*)/g, '') === '') {
        usernameInvalid.value = '用户名不能为空'
        return false
    }
    return true
}

const validatePassword = () => {
    if (loginForm.password.replace(/(^\s*)/g, '') === '') {
        passwordInvalid.value = '密码不能为空'
        return false
    }
    return true
}

// 登录成功处理
const handleLoginSuccess = (resp) => {
    if (resp.success) {
        router.push({ name: 'DeviceManagement' })
        
        // 更新 store
        store.commit('isLogin', resp.token)
        store.commit('setUser', resp.user)
        store.commit('setName', resp.name)
        store.commit('setId', resp.id)
        store.commit('setIsSuperuser', resp.is_superuser)
        store.commit('setRouterName', 'DeviceManagement')

        // 更新 localStorage
        setLocalValue('token', resp.token)
        setLocalValue('user', resp.user)
        setLocalValue('name', resp.name)
        setLocalValue('id', resp.id)
        setLocalValue('is_superuser', resp.is_superuser)
        setLocalValue('routerName', 'DeviceManagement')
    } else {
        ElMessage.error({
            message: resp.msg,
            duration: 2000,
            center: true
        })
    }
}

// 提交表单
const submitForm = () => {
    if (validateUserName() && validatePassword()) {
        isLoading.value = true
        api.login(loginForm).then(resp => {
            handleLoginSuccess(resp)
            isLoading.value = false
        }).catch(() => {
            isLoading.value = false
        })
    }
}
</script>

<style scoped>
.login-container {
    position: relative;
    width: 100vw;
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    overflow: hidden;
}

/* 背景装饰 */
.login-background {
    position: absolute;
    width: 100%;
    height: 100%;
    top: 0;
    left: 0;
    z-index: 0;
}

.bg-shape {
    position: absolute;
    border-radius: 50%;
    opacity: 0.1;
    animation: float 20s infinite ease-in-out;
}

.bg-shape-1 {
    width: 400px;
    height: 400px;
    background: #fff;
    top: -100px;
    left: -100px;
    animation-delay: 0s;
}

.bg-shape-2 {
    width: 300px;
    height: 300px;
    background: #fff;
    bottom: -50px;
    right: -50px;
    animation-delay: 5s;
}

.bg-shape-3 {
    width: 200px;
    height: 200px;
    background: #fff;
    top: 50%;
    right: 10%;
    animation-delay: 10s;
}

@keyframes float {
    0%, 100% {
        transform: translate(0, 0) rotate(0deg);
    }
    33% {
        transform: translate(30px, -30px) rotate(120deg);
    }
    66% {
        transform: translate(-20px, 20px) rotate(240deg);
    }
}

/* 登录卡片 */
.login-card {
    position: relative;
    z-index: 1;
    width: 100%;
    max-width: 420px;
    padding: 48px 40px;
    background: rgba(255, 255, 255, 0.98);
    border-radius: 20px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    backdrop-filter: blur(10px);
    animation: slideUp 0.6s ease-out;
}

@keyframes slideUp {
    from {
        opacity: 0;
        transform: translateY(30px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

/* Logo 区域 */
.login-header {
    text-align: center;
    margin-bottom: 40px;
}

.login-logo-icon {
    width: 80px;
    height: 80px;
    margin: 0 auto 20px;
    display: block;
    object-fit: contain;
    transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
    filter: drop-shadow(0 4px 12px rgba(0, 0, 0, 0.1));
}

.login-logo-icon:hover {
    transform: scale(1.1) rotate(5deg);
}

.login-logo {
    width: 200px;
    height: auto;
    margin-bottom: 20px;
    transition: transform 0.3s ease;
}

.login-logo:hover {
    transform: scale(1.05);
}

.login-title {
    margin: 0 0 8px 0;
    font-size: 28px;
    font-weight: 700;
    background: linear-gradient(135deg, #4c1d95 0%, #7c3aed 50%, #a78bfa 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: 0.5px;
    text-align: center;
}

.login-subtitle {
    margin: 0 0 32px 0;
    font-size: 15px;
    color: #6b7280;
    font-weight: 400;
    text-align: center;
    letter-spacing: 0.3px;
}

/* 表单区域 */
.login-form {
    width: 100%;
}

.form-content {
    display: flex;
    flex-direction: column;
    gap: 24px;
}

.form-item {
    position: relative;
}

.login-input {
    width: 100%;
    height: 48px;
}

.login-input :deep(.el-input__wrapper) {
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    transition: all 0.3s ease;
    padding: 0 16px;
}

.login-input :deep(.el-input__wrapper:hover) {
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
}

.login-input :deep(.el-input__wrapper.is-focus) {
    box-shadow: 0 4px 16px rgba(102, 126, 234, 0.3);
    border-color: #667eea;
}

.input-icon {
    font-size: 18px;
    color: #8c8c8c;
}

.error-message {
    position: absolute;
    left: 0;
    top: 100%;
    margin-top: 6px;
    font-size: 12px;
    color: #f56c6c;
    animation: shake 0.3s ease;
}

@keyframes shake {
    0%, 100% {
        transform: translateX(0);
    }
    25% {
        transform: translateX(-5px);
    }
    75% {
        transform: translateX(5px);
    }
}

/* 登录按钮 */
.form-submit {
    margin-top: 8px;
}

.login-button {
    width: 100%;
    height: 48px;
    font-size: 16px;
    font-weight: 600;
    border-radius: 12px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border: none;
    transition: all 0.3s ease;
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.login-button:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
}

.login-button:active:not(:disabled) {
    transform: translateY(0);
}

.login-button:disabled {
    opacity: 0.7;
    cursor: not-allowed;
}

/* 响应式设计 */
@media (max-width: 768px) {
    .login-card {
        max-width: 90%;
        padding: 36px 28px;
        margin: 20px;
    }

    .login-title {
        font-size: 24px;
    }

    .login-logo-icon {
        width: 64px;
        height: 64px;
    }

    .login-logo {
        width: 160px;
    }
}

@media (max-width: 480px) {
    .login-card {
        padding: 32px 24px;
    }

    .login-title {
        font-size: 22px;
    }

    .login-logo-icon {
        width: 56px;
        height: 56px;
    }

    .login-subtitle {
        font-size: 13px;
    }
}
</style>
