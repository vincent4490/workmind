import axios from "axios";
import store from "../store";
import router from "../router";
import { ElMessage } from "element-plus";

// Vite 环境变量：开发环境使用相对路径（通过 proxy），生产环境使用完整 URL
export let baseUrl = import.meta.env.VITE_BASE_URL || '';
// SSE 直连后端地址（可选）：用于绕过代理缓冲；为空则走当前域名（由代理/nginx转发）
// 例：http://172.13.6.230:8009
export const sseBaseUrl = import.meta.env.VITE_SSE_BASE_URL || '';

axios.defaults.withCredentials = true;
axios.defaults.baseURL = baseUrl;

function getAuthToken() {
    // 优先 Vuex store，其次 localStorage（防止 store 尚未初始化导致 token 缺失）
    const t = (store?.state?.token) || (window.localStorage ? localStorage.getItem('token') : '');
    return (t && t !== 'null' && t !== 'undefined') ? t : '';
}

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
            const token = getAuthToken();
            if (token) config.headers.Authorization = "Bearer " + token;
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

/** 需求管理：获取所有测试团队选项（用于筛选/表单下拉） */
export const getFunctionalRequirementTestTeamOptions = () => {
    return axios.get("/api/ui_test/functional-requirements/test-team-options/").then(res => res.data);
};

/** 需求管理：获取所有测试人员选项（用于筛选下拉，可输入搜索） */
export const getFunctionalRequirementTesterOptions = () => {
    return axios.get("/api/ui_test/functional-requirements/tester-options/").then(res => res.data);
};

/** 需求管理：获取所有状态选项（用于筛选下拉） */
export const getFunctionalRequirementStatusOptions = () => {
    return axios.get("/api/ui_test/functional-requirements/status-options/").then(res => res.data);
};

/** 需求管理：获取所有标签选项（用于筛选下拉） */
export const getFunctionalRequirementTagOptions = () => {
    return axios.get("/api/ui_test/functional-requirements/tag-options/").then(res => res.data);
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

// 任务管理
export const getTasks = params => {
    return axios.get("/api/ui_test/tasks/", { params }).then(res => res.data);
};

export const createTask = params => {
    return axios.post("/api/ui_test/tasks/", params).then(res => res.data);
};

export const updateTask = (taskId, params) => {
    return axios.put("/api/ui_test/tasks/" + taskId + "/", params).then(res => res.data);
};

export const deleteTask = taskId => {
    return axios.delete("/api/ui_test/tasks/" + taskId + "/").then(res => res.data);
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

export const importFunctionalCasesFromAi = ({ ai_generation_id, requirement_id }) => {
    return axios.post("/api/ui_test/functional-cases/import-from-ai/", { ai_generation_id, requirement_id }).then(res => res.data);
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

export const batchMarkPlanCaseStatus = (planId, caseIds, status, message = '') => {
    return axios.post(`/api/ui_test/test-plans/${planId}/cases/batch-mark/`, {
        case_ids: caseIds,
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

// P2：启动任务（direct / agent），同步返回 record_id
export const startAiTestcaseGeneration = (data, { agent = false } = {}) => {
    const isFormData = data instanceof FormData;
    const url = agent
        ? '/api/ai_testcase/generations/agent-start/'
        : '/api/ai_testcase/generations/start/';
    return axios
        .post(url, data, {
            headers: isFormData ? { 'Content-Type': 'multipart/form-data' } : undefined,
        })
        .then(res => res.data);
};

// P2：事件流 SSE（从事件表推送，支持 after 游标重连）
export const streamAiTestcaseEvents = async (recordId, { after = 0, onEvent, onError } = {}) => {
    const token = getAuthToken();
    const sseBase = sseBaseUrl || (import.meta.env.DEV ? 'http://127.0.0.1:8009' : '');
    const url = `${sseBase}/api/ai_testcase/generations/${recordId}/events-stream/?after=${after || 0}`;

    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                ...(token ? { 'Authorization': 'Bearer ' + token } : {}),
            },
        });

        if (!response.ok) {
            const text = await response.text();
            if (onError) onError(text || `HTTP ${response.status}`);
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
                if (!line.startsWith('data: ')) continue;
                const raw = line.slice(6);
                if (!raw) continue;
                try {
                    const event = JSON.parse(raw);
                    if (onEvent) onEvent(event);
                } catch (_) {
                    // ignore
                }
            }
        }
    } catch (err) {
        if (onError) onError(err.message || '网络连接失败');
    }
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
    const token = getAuthToken();
    const sseBase = sseBaseUrl || (import.meta.env.DEV ? 'http://127.0.0.1:8009' : '');

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

/** 流式功能点重新生成（SSE） */
export const aiRegenerateFunctionStream = async (data, onChunk, onDone, onError, onStart) => {
    const token = getAuthToken();
    const sseBase = sseBaseUrl || (import.meta.env.DEV ? 'http://127.0.0.1:8009' : '');
    try {
        const response = await fetch(sseBase + '/api/ai_testcase/regenerate-function-stream/', {
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
                        if (event.type === 'start' && onStart) onStart(event);
                        else if (event.type === 'chunk') onChunk(event.content);
                        else if (event.type === 'done') onDone(event);
                        else if (event.type === 'error') onError(event.error);
                    } catch (e) {}
                }
            }
        }
    } catch (err) {
        onError(err.message || '网络连接失败');
    }
};

/** 编辑单条用例（标题、前置条件、测试步骤、预期结果），写回记录并重建 XMind */
export const aiUpdateCase = (data) => {
    return axios.post('/api/ai_testcase/update-case/', data).then(res => res.data);
};

// 流式用例评审（SSE）
export const aiReviewTestcaseStream = async (data, onChunk, onDone, onError, onStart) => {
    const token = getAuthToken();
    const sseBase = sseBaseUrl || (import.meta.env.DEV ? 'http://127.0.0.1:8009' : '');

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
    const token = getAuthToken();
    const sseBase = sseBaseUrl || (import.meta.env.DEV ? 'http://127.0.0.1:8009' : '');

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

// ============ AI 需求智能体 ============

// SSE 流式生成需求分析（支持 FormData 文件上传 + JSON）
// onCostEstimateRequired: 可选，当服务端返回 cost_estimate_required 时调用（预估成本超阈值，由前端确认后带 cost_confirmed 重发）
export const aiRequirementStream = async (data, onChunk, onDone, onError, onStart, onCostEstimateRequired) => {
    const token = (await import('../store/state')).default.token;
    const sseBase = import.meta.env.DEV ? 'http://127.0.0.1:8009' : '';
    const isFormData = data instanceof FormData;

    try {
        const response = await fetch(sseBase + '/api/ai_requirement/run-stream/', {
            method: 'POST',
            headers: {
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
                        } else if (event.type === 'cost_estimate_required') {
                            if (onCostEstimateRequired) onCostEstimateRequired(event);
                            return;
                        } else if (event.type === 'quota_exceeded') {
                            onError(event.error || '您今日配额已用尽');
                            return;
                        } else if (event.type === 'chunk') {
                            onChunk(event.content);
                            // 等待下一帧再处理下一 chunk，确保浏览器有机会重绘，流式效果可见
                            await new Promise(r => requestAnimationFrame(r));
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

// 获取需求智能体任务历史
export const getAiRequirementTasks = params => {
    return axios.get('/api/ai_requirement/tasks/', { params }).then(res => res.data);
};

// 获取需求智能体任务详情
export const getAiRequirementTask = id => {
    return axios.get(`/api/ai_requirement/tasks/${id}/`).then(res => res.data);
};

/** 下载任务导出文件（Word / XMind）。format: 'word' -> docx, 'xmind' -> xmind。返回 { data: Blob, filename: string } */
export const downloadAiRequirementTaskExport = (taskId, format) => {
    const f = (format || '').toLowerCase()
    const fileFormat = f === 'word' ? 'docx' : 'xmind'
    return axios
        .get(`/api/ai_requirement/tasks/${taskId}/export/`, {
            params: { file_format: fileFormat },
            responseType: 'blob'
        })
        .then(res => {
            const ext = fileFormat === 'docx' ? 'docx' : 'xmind'
            let filename = `requirement_${taskId}.${ext}`
            const disposition = res.headers['content-disposition']
            if (disposition && disposition.includes("filename*=")) {
                const m = disposition.match(/filename\*=UTF-8''([^;]+)/)
                if (m) filename = decodeURIComponent(m[1].trim())
            }
            return { data: res.data, filename }
        })
        .catch(async err => {
            if (err.response?.data instanceof Blob) {
                try {
                    const text = await err.response.data.text();
                    const j = JSON.parse(text);
                    throw new Error(j.error || '导出失败');
                } catch (e) {
                    if (e instanceof SyntaxError) throw err;
                    throw e;
                }
            }
            throw err;
        });
};

// 提交用户反馈
export const submitAiRequirementFeedback = data => {
    return axios.post('/api/ai_requirement/feedback/', data).then(res => res.data);
};

// SSE 多轮对话
export const aiRequirementChatStream = async (data, onChunk, onDone, onError, onStart) => {
    const token = (await import('../store/state')).default.token;
    const sseBase = import.meta.env.DEV ? 'http://127.0.0.1:8009' : '';

    try {
        const response = await fetch(sseBase + '/api/ai_requirement/chat/', {
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
                        } else if (event.type === 'quota_exceeded') {
                            onError(event.error || '您今日配额已用尽');
                            return;
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

// P1-1：澄清并继续（提交澄清答案后流式重新生成）
export const aiRequirementClarifyAndContinue = async (taskId, clarificationAnswers, onChunk, onDone, onError, onStart) => {
    const token = (await import('../store/state')).default.token;
    const sseBase = import.meta.env.DEV ? 'http://127.0.0.1:8009' : '';
    const response = await fetch(sseBase + '/api/ai_requirement/clarify-and-continue/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': 'Bearer ' + token } : {})
        },
        body: JSON.stringify({ task_id: taskId, clarification_answers: clarificationAnswers || [] })
    });
    if (!response.ok) {
        const text = await response.text();
        let err = text;
        try {
            const j = JSON.parse(text);
            err = j.error || text;
        } catch (_) {}
        onError(err || `HTTP ${response.status}`);
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
                    if (event.type === 'start' && onStart) onStart(event);
                    else if (event.type === 'chunk') onChunk(event.content);
                    else if (event.type === 'done') onDone(event);
                    else if (event.type === 'error') onError(event.error);
                } catch (_) {}
            }
        }
    }
};

// 功能点 → 用例智能体桥接
export const bridgeToTestcase = data => {
    return axios.post('/api/ai_requirement/bridge-to-testcase/', data).then(res => res.data);
};

// Jira / Confluence 同步（P2-3）
export const aiRequirementSyncToJira = data => {
    return axios.post('/api/ai_requirement/sync-to-jira/', data).then(res => res.data);
};
export const aiRequirementSyncToConfluence = data => {
    return axios.post('/api/ai_requirement/sync-to-confluence/', data).then(res => res.data);
};

// 成本统计概览
export const getAiRequirementStats = () => {
    return axios.get('/api/ai_requirement/stats/overview/').then(res => res.data);
};

// Prompt 版本管理
export const getPromptVersions = params => {
    return axios.get('/api/ai_requirement/prompts/', { params }).then(res => res.data);
};

export const createPromptVersion = data => {
    return axios.post('/api/ai_requirement/prompts/', data).then(res => res.data);
};

export const updatePromptVersion = (id, data) => {
    return axios.patch(`/api/ai_requirement/prompts/${id}/`, data).then(res => res.data);
};

export const deletePromptVersion = id => {
    return axios.delete(`/api/ai_requirement/prompts/${id}/`).then(res => res.data);
};

export const activatePromptVersion = (id, data) => {
    return axios.post(`/api/ai_requirement/prompts/${id}/activate/`, data).then(res => res.data);
};

// ============ 工作流（深度模式） ============

export const startWorkflowStream = async (data, onEvent, onError) => {
    const token = (await import('../store/state')).default.token;
    const sseBase = import.meta.env.DEV ? 'http://127.0.0.1:8009' : '';

    try {
        const response = await fetch(sseBase + '/api/ai_requirement/workflow/start/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': 'Bearer ' + token } : {}),
            },
            body: JSON.stringify(data),
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
                        onEvent(event);
                    } catch (e) { /* skip */ }
                }
            }
        }
    } catch (err) {
        onError(err.message || '网络连接失败');
    }
};

export const approveWorkflowStream = async (workflowId, data, onEvent, onError) => {
    const token = (await import('../store/state')).default.token;
    const sseBase = import.meta.env.DEV ? 'http://127.0.0.1:8009' : '';

    try {
        const response = await fetch(sseBase + `/api/ai_requirement/workflow/${workflowId}/approve/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': 'Bearer ' + token } : {}),
            },
            body: JSON.stringify(data),
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
                        onEvent(event);
                    } catch (e) { /* skip */ }
                }
            }
        }
    } catch (err) {
        onError(err.message || '网络连接失败');
    }
};

export const getWorkflowRuns = params => {
    return axios.get('/api/ai_requirement/workflows/', { params }).then(res => res.data);
};

export const getWorkflowRun = id => {
    return axios.get(`/api/ai_requirement/workflows/${id}/`).then(res => res.data);
};

// ============ 多智能体协作工作流 ============

export const startMultiAgentStream = async (data, onEvent, onError) => {
    const token = (await import('../store/state')).default.token;
    const sseBase = import.meta.env.DEV ? 'http://127.0.0.1:8009' : '';

    try {
        const response = await fetch(sseBase + '/api/ai_requirement/multi-agent/start/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': 'Bearer ' + token } : {}),
            },
            body: JSON.stringify(data),
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
                        onEvent(event);
                    } catch (e) { /* skip */ }
                }
            }
        }
    } catch (err) {
        onError(err.message || '网络连接失败');
    }
};

export const approveMultiAgentStream = async (workflowId, data, onEvent, onError) => {
    const token = (await import('../store/state')).default.token;
    const sseBase = import.meta.env.DEV ? 'http://127.0.0.1:8009' : '';

    try {
        const response = await fetch(sseBase + `/api/ai_requirement/multi-agent/${workflowId}/approve/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': 'Bearer ' + token } : {}),
            },
            body: JSON.stringify(data),
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
                        onEvent(event);
                    } catch (e) { /* skip */ }
                }
            }
        }
    } catch (err) {
        onError(err.message || '网络连接失败');
    }
};

// 流式生成测试用例（SSE）
// 直连后端 8009 端口，绕过 Vite 代理（代理会缓冲 SSE 流）
// 支持 FormData（带文件上传）和普通 JSON 两种格式
export const aiGenerateTestcaseStream = async (data, onChunk, onDone, onError, onStart) => {
    const token = getAuthToken();
    // 优先使用 VITE_SSE_BASE_URL；否则开发环境默认直连 127.0.0.1:8009；生产环境走相对路径（由 nginx 转发）
    const sseBase = sseBaseUrl || (import.meta.env.DEV ? 'http://127.0.0.1:8009' : '');

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

// Agent 智能体流式生成测试用例（SSE）
// 后端 /api/ai_testcase/agent-generate-stream/
// 事件类型：agent_start, agent_node_done, agent_review, agent_refining, agent_done, error, warnings
export const aiAgentGenerateTestcaseStream = async (data, callbacks) => {
    const token = getAuthToken();
    const sseBase = sseBaseUrl || (import.meta.env.DEV ? 'http://127.0.0.1:8009' : '');
    const isFormData = data instanceof FormData;

    const { onStart, onNodeDone, onReview, onRefining, onDone, onError, onWarnings } = callbacks;

    try {
        const response = await fetch(sseBase + '/api/ai_testcase/agent-generate-stream/', {
            method: 'POST',
            headers: {
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
                        switch (event.type) {
                            case 'agent_start':
                                if (onStart) onStart(event);
                                break;
                            case 'agent_node_done':
                                if (onNodeDone) onNodeDone(event);
                                break;
                            case 'agent_review':
                                if (onReview) onReview(event);
                                break;
                            case 'agent_refining':
                                if (onRefining) onRefining(event);
                                break;
                            case 'agent_done':
                                if (onDone) onDone(event);
                                break;
                            case 'warnings':
                                if (onWarnings) onWarnings(event.warnings);
                                break;
                            case 'error':
                                onError(event.error);
                                break;
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
