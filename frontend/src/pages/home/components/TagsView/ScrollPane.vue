<template>
    <div ref="scrollContainer" class="scroll-container" @wheel.prevent="handleScroll">
        <div ref="scrollWrapper" class="scroll-wrapper">
            <slot />
        </div>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

const tagSpacing = 4

const scrollContainer = ref(null)
const scrollWrapper = ref(null)

const handleScroll = (e) => {
    const eventDelta = e.wheelDelta || -e.deltaY * 40
    const $scrollWrapper = scrollWrapper.value
    $scrollWrapper.scrollLeft = $scrollWrapper.scrollLeft + eventDelta / 4
}

const moveToTarget = (currentTag) => {
    const $container = scrollContainer.value
    const $containerWidth = $container.offsetWidth
    const $scrollWrapper = scrollWrapper.value
    const tagList = $scrollWrapper.querySelectorAll('.tags-view-item')

    let firstTag = null
    let lastTag = null

    if (tagList.length > 0) {
        firstTag = tagList[0]
        lastTag = tagList[tagList.length - 1]
    }

    if (firstTag === currentTag) {
        $scrollWrapper.scrollLeft = 0
    } else if (lastTag === currentTag) {
        $scrollWrapper.scrollLeft = $scrollWrapper.scrollWidth - $containerWidth
    } else {
        const currentIndex = tagList.length - 1
        const currentTag = tagList[currentIndex]
        const prevTag = tagList[currentIndex - 1]
        const nextTag = tagList[currentIndex + 1]

        const afterNextTagOffsetLeft = nextTag ? nextTag.offsetLeft + nextTag.offsetWidth + tagSpacing : 0
        const beforePrevTagOffsetLeft = prevTag ? prevTag.offsetLeft - tagSpacing : 0

        if (afterNextTagOffsetLeft > $scrollWrapper.scrollLeft + $containerWidth) {
            $scrollWrapper.scrollLeft = afterNextTagOffsetLeft - $containerWidth
        } else if (beforePrevTagOffsetLeft < $scrollWrapper.scrollLeft) {
            $scrollWrapper.scrollLeft = beforePrevTagOffsetLeft
        }
    }
}

defineExpose({
    moveToTarget
})
</script>

<style scoped>
.scroll-container {
    white-space: nowrap;
    position: relative;
    overflow: hidden;
    width: 100%;
}

.scroll-wrapper {
    display: inline-block;
    overflow-x: auto;
    overflow-y: hidden;
}

.scroll-wrapper::-webkit-scrollbar {
    display: none;
}
</style>
