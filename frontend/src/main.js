/* jshint esversion: 6 */
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import store from './store'
import VueApexCharts from 'vue3-apexcharts'
import VueJsonViewer from 'vue-json-viewer'
import 'vue-json-viewer/style.css'
import VueClipboard from 'vue3-clipboard'
import 'styles/iconfont.css'
import 'styles/swagger.css'
import 'styles/tree.css'
import 'styles/home.css'
import 'styles/reports.css'
import 'styles/iconfont.js'
import * as api from './restful/api'
import { datetimeObj2str, timestamp2time } from '@/util/format'

const app = createApp(App)

// 注册 Element Plus
app.use(ElementPlus, {
    locale: zhCn,
})

// 注册所有 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
}

// 注册其他插件
app.use(router)
app.use(store)
app.use(VueApexCharts)
// 显式注册 ApexCharts 组件（兼容大小写）
app.component('ApexCharts', VueApexCharts)
app.use(VueJsonViewer)
app.use(VueClipboard, {
    autoSetContainer: true,
    appendToBody: true,
})

// 注意：v-jsoneditor 是 Vue 2 的包，已移除
// 如需 JSON 编辑器功能，建议使用：
// 1. vue-json-viewer（已安装，用于查看 JSON）
// 2. vue3-json-editor（Vue 3 兼容的 JSON 编辑器，需要安装：npm install vue3-json-editor）

// 全局属性
app.config.globalProperties.$api = api

// Vue 3 不再支持 filters，改用全局方法
app.config.globalProperties.$filters = {
    datetimeFormat: datetimeObj2str,
    timestampToTime: timestamp2time
}

// LocalStorage 辅助函数
app.config.globalProperties.setLocalValue = function(name, value) {
    if (window.localStorage) {
        localStorage.setItem(name, value)
    } else {
        alert('This browser does not support localStorage')
    }
}

app.config.globalProperties.getLocalValue = function(name) {
    const value = localStorage.getItem(name)
    if (value) {
        // localStorage只能存字符串，布尔类型需要转换
        if (value === 'false' || value === 'true') {
            return eval(value)
        }
        return value
    } else {
        return ''
    }
}

// 初始化 localStorage
const initLocalStorage = () => {
    const defaults = {
        token: '',
        user: '',
        name: '',
        id: '',
        routerName: 'DeviceManagement',
        is_superuser: false
    }
    
    for (const [key, defaultValue] of Object.entries(defaults)) {
        if (localStorage.getItem(key) === null) {
            localStorage.setItem(key, defaultValue)
        }
    }
    
    // 初始化 store
    store.commit('isLogin', localStorage.getItem('token'))
    store.commit('setUser', localStorage.getItem('user'))
    store.commit('setName', localStorage.getItem('name'))
    store.commit('setId', parseInt(localStorage.getItem('id'), 10))
    store.commit('setRouterName', localStorage.getItem('routerName'))
    store.commit('setIsSuperuser', localStorage.getItem('is_superuser'))
    store.dispatch('initStore')
}

// 路由守卫
router.beforeEach((to, from, next) => {
    // 修改页面title
    if (to.meta.title) {
        document.title = to.meta.title
    }

    // 更新侧边栏状态
    if (to.name) {
        store.commit('setRouterName', to.name)
        localStorage.setItem('routerName', to.name)
    }

    // 鉴权
    if (to.meta.requireAuth) {
        if (store.state.token !== '') {
            next()
        } else {
            next({
                name: 'Login'
            })
        }
    } else {
        next()
    }
})

// 初始化并挂载应用
initLocalStorage()
app.mount('#app')
