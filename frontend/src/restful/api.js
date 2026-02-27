import axios from "axios";
import store from "../store/state";
import router from "../router";
import { ElMessage } from "element-plus";

// Vite 环境变量：开发环境使用相对路径（通过 proxy），生产环境使用完整 URL
export let baseUrl = import.meta.env.VITE_BASE_URL || '';

axios.defaults.withCredentials = true;
axios.defaults.baseURL = baseUrl;

axios.interceptors.request.use(
    function(config) {
        // 完全不需要认证的接口列表（不发送token）
        const noAuthUrls = [
            "/api/user/login"
        ];
        
        // 如果不在完全免认证列表中，添加Authorization头
        if (!noAuthUrls.includes(config.url)) {
            // 在请求拦截中，每次请求，都会加上一个Authorization头
            // JWT token 需要 Bearer 前缀
            if (store.token) {
                config.headers.Authorization = "Bearer " + store.token;
            }
        }
        return config;
    },
    function(error) {
        return Promise.reject(error);
    }
);

axios.interceptors.response.use(
    function(response) {
        return response; // 安全地返回 response
    },
    function(error) {
        if (axios.isCancel(error)) {
            /// 请求被取消
            if (error.message !== "User cancelled the request") {
                ElMessage.error({
                    message: "请求超时，请稍后再试",
                    duration: 2000
                });
            }
        } else {
            // 其他错误
            try {
                let status = error.response ? error.response.status : 0;
                // 对于 /api/user/test_config 接口的401错误，不自动跳转登录
                // 因为这个接口在页面加载时调用，可能token还未准备好
                // 对于登录接口的401错误，也不跳转（避免循环）
                const url = (error.config && error.config.url) || '';
                const isTestConfigApi = url.includes('/api/user/test_config');
                const isLoginApi = url.includes('/api/user/login');
                const isLogoutApi = url.includes('/api/user/logout');
                if (status === 401 && !isTestConfigApi && !isLoginApi && !isLogoutApi) {
                    router.replace({
                        name: "Login"
                    });
                }
                if (status === 500) {
                    ElMessage.error({
                        message: "服务器内部异常，请检查",
                        duration: 2000
                    });
                }
                if (status === 403) {
                    ElMessage.error({
                        message: error.response.data.detail,
                        duration: 2000
                    });
                }
            } catch (e) {
                ElMessage.error({
                    message: "服务器连接超时, 请重试",
                    duration: 2000
                });
            }
        }
        return Promise.reject(error);
    }
);

export const login = params => {
    return axios.post("/api/user/login", params).then(res => res.data);
};

export const logout = () => {
    return axios.post("/api/user/logout").then(res => res.data);
};

export const getPagination = url => {
    return axios.get(url).then(res => res.data);
};

export const getUserList = () => {
    return axios.get("/api/user/list").then(res => res.data);
};

// 用户测试账号配置
export const getUserTestConfig = () => {
    return axios.get("/api/user/test_config").then(res => res.data);
};

export const updateUserTestConfig = params => {
    return axios.put("/api/user/test_config", params).then(res => res.data);
};

// UI组件库
export const getUiComponentDefinitions = params => {
    return axios.get("/api/ui_test/ui-components/", params).then(res => res.data);
};

export const getUiCustomComponentDefinitions = params => {
    return axios.get("/api/ui_test/ui-custom-components/", params).then(res => res.data);
};


export const createUiCustomComponentDefinition = params => {
    return axios.post("/api/ui_test/ui-custom-components/", params).then(res => res.data);
};

export const updateUiCustomComponentDefinition = (id, params) => {
    return axios.patch(`/api/ui_test/ui-custom-components/${id}/`, params).then(res => res.data);
};

export const deleteUiCustomComponentDefinition = id => {
    return axios.delete(`/api/ui_test/ui-custom-components/${id}/`).then(res => res.data);
};

// APP UI 测试相关接口
export const getDeviceList = params => {
    return axios.get("/api/ui_test/devices/", params).then(res => res.data);
};

export const refreshDevices = params => {
    return axios.post("/api/ui_test/devices/refresh/", params).then(res => res.data);
};

export const connectRemoteDevice = params => {
    return axios.post("/api/ui_test/devices/connect/", params).then(res => res.data);
};

export const disconnectDevice = deviceId => {
    return axios.delete("/api/ui_test/devices/" + deviceId + "/disconnect/").then(res => res.data);
};

export const lockDevice = deviceId => {
    return axios.post("/api/ui_test/devices/" + deviceId + "/lock/").then(res => res.data);
};

export const unlockDevice = deviceId => {
    return axios.post("/api/ui_test/devices/" + deviceId + "/unlock/").then(res => res.data);
};

// UI测试相关API
export const getUiTestCases = params => {
    return axios.get("/api/ui_test/cases/", params).then(res => res.data);
};

export const createUiTestCase = params => {
    return axios.post("/api/ui_test/cases/", params).then(res => res.data);
};

export const getUiTestCaseDetail = caseId => {
    return axios.get(`/api/ui_test/cases/${caseId}/`).then(res => res.data);
};

export const updateUiTestCase = (caseId, params) => {
    return axios.put(`/api/ui_test/cases/${caseId}/`, params).then(res => res.data);
};

export const deleteUiTestCase = caseId => {
    return axios.delete(`/api/ui_test/cases/${caseId}/`).then(res => res.data);
};

// UI测试执行记录相关API
export const getUiTestExecutions = params => {
    return axios.get("/api/ui_test/executions/", { params }).then(res => res.data);
};

export const getUiTestExecutionDetail = executionId => {
    return axios.get(`/api/ui_test/executions/${executionId}/`).then(res => res.data);
};

export const startUiTestExecution = params => {
    return axios.post("/api/ui_test/executions/start/", params).then(res => res.data);
};

export const stopUiTestExecution = executionId => {
    return axios.post(`/api/ui_test/executions/${executionId}/stop/`).then(res => res.data);
};


export const uploadUiComponentPackage = formData => {
    return axios.post("/api/ui_test/ui-component-packages/", formData, {
        headers: { "Content-Type": "multipart/form-data" }
    }).then(res => res.data);
};

export const getUiComponentPackages = params => {
    return axios.get("/api/ui_test/ui-component-packages/", params).then(res => res.data);
};

export const exportUiComponentPackage = params => {
    return axios.get("/api/ui_test/ui-component-packages/export/", {
        params,
        responseType: "blob"
    });
};


export const uploadUiFlowTemplate = formData => {
    return axios.post("/api/ui_test/configs/ui-flow-template/", formData, {
        headers: { "Content-Type": "multipart/form-data" }
    }).then(res => res.data);
};

export const getUiFlowTemplates = params => {
    return axios.get("/api/ui_test/configs/ui-flow-templates/", params).then(res => res.data);
};

export const deleteUiFlowTemplate = params => {
    return axios.post("/api/ui_test/configs/ui-flow-template-delete/", params).then(res => res.data);
};

export const getUiFlowScreenshot = params => {
    return axios.get("/api/ui_test/configs/ui-flow-screenshot/", params).then(res => res.data);
};

// 接口用例管理API
export const listApiCases = params => {
    return axios.post("/api/ui_test/api-cases/list_cases/", params).then(res => res.data);
};

export const addApiCase = params => {
    return axios.post("/api/ui_test/api-cases/add_case/", params).then(res => res.data);
};

export const updateApiCase = params => {
    return axios.post("/api/ui_test/api-cases/update_case/", params).then(res => res.data);
};

export const deleteApiCases = params => {
    return axios.post("/api/ui_test/api-cases/delete_cases/", params).then(res => res.data);
};

// ================================================= #
// 功能测试管理 API
// ================================================= #
// 功能测试需求管理
export const getFunctionalRequirements = params => {
    return axios.get("/api/ui_test/functional-requirements/", { params }).then(res => res.data);
};

export const createFunctionalRequirement = params => {
    return axios.post("/api/ui_test/functional-requirements/", params).then(res => res.data);
};

export const updateFunctionalRequirement = (requirementId, params) => {
    return axios.put("/api/ui_test/functional-requirements/" + requirementId + "/", params).then(res => res.data);
};

export const deleteFunctionalRequirement = requirementId => {
    return axios.delete("/api/ui_test/functional-requirements/" + requirementId + "/").then(res => res.data);
};

// 功能测试用例管理
export const getFunctionalCases = params => {
    return axios.get("/api/ui_test/functional-cases/", { params }).then(res => res.data);
};

export const createFunctionalCase = params => {
    return axios.post("/api/ui_test/functional-cases/", params).then(res => res.data);
};

export const updateFunctionalCase = (caseId, params) => {
    return axios.put("/api/ui_test/functional-cases/" + caseId + "/", params).then(res => res.data);
};

export const deleteFunctionalCase = caseId => {
    return axios.delete("/api/ui_test/functional-cases/" + caseId + "/").then(res => res.data);
};

export const exportFunctionalCases = params => {
    return axios.get("/api/ui_test/functional-cases/export/", {
        params,
        responseType: 'blob'
    });
};

export const importFunctionalCases = (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return axios.post("/api/ui_test/functional-cases/import/", formData, {
        headers: {
            'Content-Type': 'multipart/form-data'
        }
    }).then(res => res.data);
};

// 测试计划管理
export const getTestPlans = params => {
    return axios.get("/api/ui_test/test-plans/", { params }).then(res => res.data);
};

export const createTestPlan = params => {
    return axios.post("/api/ui_test/test-plans/", params).then(res => res.data);
};

export const updateTestPlan = (planId, params) => {
    return axios.put("/api/ui_test/test-plans/" + planId + "/", params).then(res => res.data);
};

export const deleteTestPlan = planId => {
    return axios.delete("/api/ui_test/test-plans/" + planId + "/").then(res => res.data);
};

export const addCasesToPlan = (planId, caseIds) => {
    return axios.post("/api/ui_test/test-plans/" + planId + "/add-cases/", { case_ids: caseIds }).then(res => res.data);
};

export const removeCaseFromPlan = (planId, caseId) => {
    return axios.delete("/api/ui_test/test-plans/" + planId + "/remove-case/" + caseId + "/").then(res => res.data);
};

export const getPlanCases = planId => {
    return axios.get("/api/ui_test/test-plans/" + planId + "/cases/").then(res => res.data);
};

export const markPlanCaseStatus = (planId, caseId, status, message = '') => {
    return axios.post(`/api/ui_test/test-plans/${planId}/cases/mark/`, {
        case_id: caseId,
        status,
        message
    }).then(res => res.data);
};

export const getPlanCaseLogs = (planId, caseId) => {
    return axios.get(`/api/ui_test/test-plans/${planId}/cases/logs/`, {
        params: caseId ? { case_id: caseId } : {}
    }).then(res => res.data);
};

// ============ 应用包名管理 ============
export const getAppPackages = () => {
    return axios.get('/api/ui_test/app-packages/').then(res => res.data);
};

export const createAppPackage = data => {
    return axios.post('/api/ui_test/app-packages/', data).then(res => res.data);
};

export const updateAppPackage = (id, data) => {
    return axios.put(`/api/ui_test/app-packages/${id}/`, data).then(res => res.data);
};

export const deleteAppPackage = id => {
    return axios.delete(`/api/ui_test/app-packages/${id}/`).then(res => res.data);
};

// ============ Dashboard 统计 ============
export const getDashboardStats = () => {
    return axios.get('/api/ui_test/dashboard/stats/').then(res => res.data);
};

// ============ UI元素管理 ============
// 获取元素列表
export const getUiElements = params => {
    return axios.get('/api/ui_test/elements/', { params }).then(res => res.data);
};

// 创建元素
export const createUiElement = data => {
    return axios.post('/api/ui_test/elements/', data).then(res => res.data);
};

// 更新元素
export const updateUiElement = (id, data) => {
    return axios.put(`/api/ui_test/elements/${id}/`, data).then(res => res.data);
};

// 删除元素
export const deleteUiElement = id => {
    return axios.delete(`/api/ui_test/elements/${id}/`).then(res => res.data);
};

// 上传图片
export const uploadElementImage = (file, imageCategory = 'common', elementId = null) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('image_category', imageCategory);
    if (elementId) {
        formData.append('element_id', elementId);
    }
    
    return axios.post('/api/ui_test/elements/upload_image/', formData, {
        headers: {
            'Content-Type': 'multipart/form-data'
        }
    }).then(res => res.data);
};

// 获取图片分类列表
export const getImageCategories = () => {
    return axios.get('/api/ui_test/elements/image_categories/').then(res => res.data);
};

// 创建图片分类
export const createImageCategory = (name) => {
    return axios.post('/api/ui_test/elements/create_image_category/', { name }).then(res => res.data);
};

// 删除图片分类
export const deleteImageCategory = (name) => {
    return axios.post('/api/ui_test/elements/delete_image_category/', { name }).then(res => res.data);
};

// 获取标签列表
export const getElementTags = () => {
    return axios.get('/api/ui_test/elements/tags/').then(res => res.data);
};

// 复制元素
export const duplicateElement = id => {
    return axios.post(`/api/ui_test/elements/${id}/duplicate/`).then(res => res.data);
};

// 批量删除元素
export const batchDeleteElements = data => {
    return axios.post('/api/ui_test/elements/batch_delete/', data).then(res => res.data);
};

// 记录元素使用
export const recordElementUsage = id => {
    return axios.post(`/api/ui_test/elements/${id}/record_usage/`).then(res => res.data);
};

// ============ AI 用例智能体 ============
// 生成测试用例
export const aiGenerateTestcase = data => {
    return axios.post('/api/ai_testcase/generations/generate/', data).then(res => res.data);
};

// 获取生成记录列表
export const getAiTestcaseGenerations = params => {
    return axios.get('/api/ai_testcase/generations/', { params }).then(res => res.data);
};

// 获取生成记录详情
export const getAiTestcaseGeneration = id => {
    return axios.get(`/api/ai_testcase/generations/${id}/`).then(res => res.data);
};

// 删除生成记录
export const deleteAiTestcaseGeneration = id => {
    return axios.delete(`/api/ai_testcase/generations/${id}/`).then(res => res.data);
};

// 预览用例数据
export const previewAiTestcase = id => {
    return axios.get(`/api/ai_testcase/generations/${id}/preview/`).then(res => res.data);
};

// 下载 XMind 文件
export const downloadAiTestcaseXmind = id => {
    return axios.get(`/api/ai_testcase/generations/${id}/download/`, {
        responseType: 'blob'
    }).then(res => res);
};

// 检查 AI 配置状态
export const getAiTestcaseConfigStatus = () => {
    return axios.get('/api/ai_testcase/generations/config-status/').then(res => res.data);
};

// 模块级重新生成测试用例（SSE 流式）
export const aiRegenerateModuleStream = async (data, onChunk, onDone, onError, onStart) => {
    const token = (await import('../store/state')).default.token;
    const sseBase = import.meta.env.DEV ? 'http://127.0.0.1:8000' : '';

    try {
        const response = await fetch(sseBase + '/api/ai_testcase/regenerate-module-stream/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': 'Bearer ' + token } : {})
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            const text = await response.text();
            onError(text || `HTTP ${response.status}`);
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const event = JSON.parse(line.slice(6));
                        if (event.type === 'start') {
                            if (onStart) onStart(event);
                        } else if (event.type === 'chunk') {
                            onChunk(event.content);
                        } else if (event.type === 'done') {
                            onDone(event);
                        } else if (event.type === 'error') {
                            onError(event.error);
                        } else if (event.type === 'warning') {
                            if (onStart) onStart(event);
                        }
                    } catch (e) {
                        // 忽略解析失败的行
                    }
                }
            }
        }
    } catch (err) {
        onError(err.message || '网络连接失败');
    }
};

// 流式用例评审（SSE）
export const aiReviewTestcaseStream = async (data, onChunk, onDone, onError, onStart) => {
    const token = (await import('../store/state')).default.token;
    const sseBase = import.meta.env.DEV ? 'http://127.0.0.1:8000' : '';

    try {
        const response = await fetch(sseBase + '/api/ai_testcase/review-stream/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': 'Bearer ' + token } : {})
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            const text = await response.text();
            onError(text || `HTTP ${response.status}`);
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const event = JSON.parse(line.slice(6));
                        if (event.type === 'start' || event.type === 'dimension_start' || event.type === 'dimension_done') {
                            if (onStart) onStart(event);
                        } else if (event.type === 'chunk') {
                            onChunk(event.content);
                        } else if (event.type === 'done') {
                            onDone(event);
                        } else if (event.type === 'error') {
                            onError(event.error);
                        }
                    } catch (e) {
                        // 忽略解析失败的行
                    }
                }
            }
        }
    } catch (err) {
        onError(err.message || '网络连接失败');
    }
};

// 流式采纳评审意见（SSE）
export const aiApplyReviewStream = async (data, onChunk, onDone, onError, onStart) => {
    const token = (await import('../store/state')).default.token;
    const sseBase = import.meta.env.DEV ? 'http://127.0.0.1:8000' : '';

    try {
        const response = await fetch(sseBase + '/api/ai_testcase/apply-review-stream/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': 'Bearer ' + token } : {})
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            const text = await response.text();
            onError(text || `HTTP ${response.status}`);
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const event = JSON.parse(line.slice(6));
                        if (event.type === 'start') {
                            if (onStart) onStart(event);
                        } else if (event.type === 'chunk') {
                            onChunk(event.content);
                        } else if (event.type === 'done') {
                            onDone(event);
                        } else if (event.type === 'error') {
                            onError(event.error);
                        }
                    } catch (e) {
                        // 忽略解析失败的行
                    }
                }
            }
        }
    } catch (err) {
        onError(err.message || '网络连接失败');
    }
};

// 流式生成测试用例（SSE）
// 直连后端 8000 端口，绕过 Vite 代理（代理会缓冲 SSE 流）
// 支持 FormData（带文件上传）和普通 JSON 两种格式
export const aiGenerateTestcaseStream = async (data, onChunk, onDone, onError, onStart) => {
    const token = (await import('../store/state')).default.token;
    // 开发环境直连后端，生产环境用相对路径
    const sseBase = import.meta.env.DEV ? 'http://127.0.0.1:8000' : '';

    // 判断是 FormData 还是普通对象
    const isFormData = data instanceof FormData;

    try {
        const response = await fetch(sseBase + '/api/ai_testcase/generate-stream/', {
            method: 'POST',
            headers: {
                // FormData 不设 Content-Type，浏览器自动加 multipart boundary
                ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
                ...(token ? { 'Authorization': 'Bearer ' + token } : {})
            },
            body: isFormData ? data : JSON.stringify(data)
        });

        if (!response.ok) {
            const text = await response.text();
            onError(text || `HTTP ${response.status}`);
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const event = JSON.parse(line.slice(6));
                        if (event.type === 'start') {
                            if (onStart) onStart(event);
                        } else if (event.type === 'chunk') {
                            onChunk(event.content);
                        } else if (event.type === 'done') {
                            onDone(event);
                        } else if (event.type === 'error') {
                            onError(event.error);
                        }
                    } catch (e) {
                        // 忽略解析失败的行
                    }
                }
            }
        }
    } catch (err) {
        onError(err.message || '网络连接失败');
    }
};


