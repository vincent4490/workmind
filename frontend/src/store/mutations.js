// 用于修改state对象中的数据状态
export default {
    isLogin(state, value) {
        state.token = value;
    },

    setUser(state, value) {
        state.user = value;
    },

    setName(state, value) {
        state.name = value;
    },

    setId(state, value) {
        state.id = value;
    },

    setRouterName(state, value) {
        state.routerName = value;
    },

    setIsSuperuser(state, value) {
        state.is_superuser = value;
    },

    setIsStaff(state, value) {
        state.is_staff = value;
    },

    // 多标签页管理
    ADD_VISITED_VIEW(state, view) {
        // 如果标签已存在，不重复添加
        if (state.visitedViews.some(v => v.path === view.path)) return
        state.visitedViews.push({
            name: view.name,
            path: view.path,
            title: view.meta?.title || view.name,
            meta: { ...view.meta }
        })
    },

    ADD_CACHED_VIEW(state, view) {
        if (state.cachedViews.includes(view.name)) return
        if (view.meta?.noCache) return
        state.cachedViews.push(view.name)
    },

    DEL_VISITED_VIEW(state, view) {
        for (const [i, v] of state.visitedViews.entries()) {
            if (v.path === view.path) {
                state.visitedViews.splice(i, 1)
                break
            }
        }
    },

    DEL_CACHED_VIEW(state, view) {
        const index = state.cachedViews.indexOf(view.name)
        if (index > -1) {
            state.cachedViews.splice(index, 1)
        }
    },

    DEL_OTHERS_VISITED_VIEWS(state, view) {
        state.visitedViews = state.visitedViews.filter(v => {
            return v.meta?.affix || v.path === view.path
        })
    },

    DEL_OTHERS_CACHED_VIEWS(state, view) {
        const index = state.cachedViews.indexOf(view.name)
        if (index > -1) {
            state.cachedViews = state.cachedViews.slice(index, index + 1)
        } else {
            state.cachedViews = []
        }
    },

    DEL_ALL_VISITED_VIEWS(state) {
        // 保留固定标签
        const affixTags = state.visitedViews.filter(tag => tag.meta?.affix)
        state.visitedViews = affixTags
    },

    DEL_ALL_CACHED_VIEWS(state) {
        state.cachedViews = []
    },

    UPDATE_VISITED_VIEW(state, view) {
        for (let v of state.visitedViews) {
            if (v.path === view.path) {
                v = Object.assign(v, view)
                break
            }
        }
    }
};
