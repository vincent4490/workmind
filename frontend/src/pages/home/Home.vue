<template>
    <el-container>
        <el-header style="background: #242f42; padding:0; height: 50px">
            <home-header></home-header>
        </el-header>

        <el-container>
            <el-aside style="width: 202px">
                <home-side></home-side>
            </el-aside>
            <el-main class="main-container">
                <!-- 标签栏 -->
                <tags-view />
                <!-- 主内容区 - 使用 keep-alive 缓存页面 -->
                <div class="app-main">
                    <router-view v-slot="{ Component }">
                        <transition name="fade-transform" mode="out-in">
                            <keep-alive :include="cachedViews">
                                <component :is="Component" :key="route.path" />
                            </keep-alive>
                        </transition>
                    </router-view>
                </div>
            </el-main>
        </el-container>
    </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useStore } from 'vuex'
import HomeHeader from "@/pages/home/components/Header.vue"
import HomeSide from "@/pages/home/components/Side.vue"
import TagsView from "@/pages/home/components/TagsView.vue"

const route = useRoute()
const store = useStore()

const cachedViews = computed(() => store.state.cachedViews)
</script>

<style scoped>
.main-container {
    padding: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}

.app-main {
    flex: 1;
    overflow: auto;
    padding: 20px;
    background: #f5f7fa;
}

/* 页面切换动画 */
.fade-transform-leave-active,
.fade-transform-enter-active {
    transition: all 0.3s;
}

.fade-transform-enter-from {
    opacity: 0;
    transform: translateX(-30px);
}

.fade-transform-leave-to {
    opacity: 0;
    transform: translateX(30px);
}
</style>
