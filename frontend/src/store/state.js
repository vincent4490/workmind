// 存储应用程序中的数据状态
export default {
    routerName: "",
    token: null,
    user: null,
    is_superuser: false,
    duration: 2000,
    WorkMind: import.meta.env.VITE_WORKMIND_LINK || "WorkMind",
    docsURL: import.meta.env.VITE_DOCS_URL || "https://workmind-docs.fun/docs/guide/introduce.html",
    recordCaseDocsURL: import.meta.env.VITE_RECORD_CASE_DOCS_URL || "https://workmind-docs.fun/docs/guide/test_case.html",
    // 多标签页管理
    visitedViews: [], // 已访问的标签页列表
    cachedViews: []   // 需要缓存的页面名称列表
};

