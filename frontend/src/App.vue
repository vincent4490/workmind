<template>
    <div id="app">
        <router-view />
    </div>
</template>

<script setup>
// App 根组件 - Composition API
// 无需额外逻辑
</script>

<style>
html,
body {
    height: 100%;
    width: 100%;
    margin: 0;
    overflow: auto;
    padding: 0;
    background: #fff;
}

body {
    color: #333;
    font-family: "PingFang SC", "Helvetica Neue", Helvetica, "Hiragino Sans GB",
        STHeitiSC-Light, "Microsoft YaHei", "微软雅黑", Arial, sans-serif;
}
</style>
