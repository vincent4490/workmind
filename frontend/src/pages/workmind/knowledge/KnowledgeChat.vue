<template>
    <div class="knowledge-chat-page">
        <!-- 左侧会话列表 -->
        <div class="conversation-panel">
            <div class="panel-header">
                <span>历史对话</span>
                <el-button size="small" :icon="Plus" type="primary" @click="newConversation">新对话</el-button>
            </div>
            <div class="conv-list">
                <div
                    v-for="conv in conversations"
                    :key="conv.id"
                    class="conv-item"
                    :class="{ active: currentConvId === conv.id }"
                    @click="loadConversation(conv)"
                >
                    <div class="conv-title">{{ conv.title || '新对话' }}</div>
                    <div v-if="conv.last_message" class="conv-preview">
                        {{ conv.last_message.content }}
                    </div>
                    <div class="conv-time">{{ formatDate(conv.updated_at) }}</div>
                    <el-button
                        class="conv-delete"
                        size="small"
                        type="danger"
                        link
                        :icon="Delete"
                        @click.stop="deleteConversation(conv)"
                    />
                </div>
                <el-empty v-if="conversations.length === 0" description="暂无对话记录" :image-size="60" />
            </div>
        </div>

        <!-- 主聊天区域 -->
        <div class="chat-main">
            <!-- 顶部 -->
            <div class="chat-header">
                <div class="chat-title">
                    <el-icon><ChatDotRound /></el-icon>
                    <span>{{ currentConvTitle || '知识库问答' }}</span>
                </div>
                <!-- 知识库范围选择器 -->
                <div class="scope-selector">
                    <el-popover
                        v-model:visible="scopePopoverVisible"
                        trigger="click"
                        width="320"
                        placement="bottom-end"
                    >
                        <template #reference>
                            <el-button size="small" :icon="Filter">
                                知识范围
                                <span v-if="selectedDocIds.length" style="color:#409eff;margin-left:4px">
                                    ({{ selectedDocIds.length }})
                                </span>
                            </el-button>
                        </template>
                        <div class="scope-panel">
                            <div class="scope-title">选择检索范围（不选则全库检索）</div>
                            <el-select
                                v-model="selectedCategories"
                                multiple
                                placeholder="按分类筛选"
                                style="width:100%;margin-bottom:10px"
                            >
                                <el-option label="需求文档" value="requirement" />
                                <el-option label="技术方案" value="tech_design" />
                                <el-option label="测试用例" value="test_case" />
                                <el-option label="业务知识" value="business" />
                                <el-option label="AI生成用例" value="generated" />
                                <el-option label="其他" value="other" />
                            </el-select>
                            <el-checkbox-group v-model="selectedDocIds" style="max-height:200px;overflow-y:auto">
                                <div v-for="doc in readyDocs" :key="doc.id" style="padding:4px 0">
                                    <el-checkbox :label="doc.id">
                                        <span style="font-size:13px">{{ doc.title }}</span>
                                        <el-tag size="small" style="margin-left:6px" type="info">{{ getCategoryLabel(doc.category) }}</el-tag>
                                    </el-checkbox>
                                </div>
                                <el-empty v-if="readyDocs.length === 0" description="暂无可用文档" :image-size="40" />
                            </el-checkbox-group>
                            <div style="text-align:right;margin-top:10px">
                                <el-button size="small" @click="selectedDocIds = []; selectedCategories = []">清空</el-button>
                                <el-button size="small" type="primary" @click="scopePopoverVisible = false">确定</el-button>
                            </div>
                        </div>
                    </el-popover>
                    <el-button v-if="messages.length" size="small" :icon="Delete" @click="clearMessages">清空消息</el-button>
                </div>
            </div>

            <!-- 消息区 -->
            <div class="messages-area" ref="messagesAreaRef">
                <!-- 欢迎语 -->
                <div v-if="messages.length === 0" class="welcome-area">
                    <el-icon size="48" style="color:#c0c4cc"><ChatDotRound /></el-icon>
                    <p class="welcome-title">知识库智能问答</p>
                    <p class="welcome-desc">基于你上传的文档进行智能检索和回答，支持多轮对话</p>
                    <div class="quick-questions">
                        <div
                            v-for="q in quickQuestions"
                            :key="q"
                            class="quick-btn"
                            @click="sendQuestion(q)"
                        >{{ q }}</div>
                    </div>
                </div>

                <!-- 消息列表 -->
                <div v-for="(msg, idx) in messages" :key="idx" class="message-item" :class="msg.role">
                    <div class="avatar">
                        <el-icon v-if="msg.role === 'assistant'" size="18"><Cpu /></el-icon>
                        <el-icon v-else size="18"><User /></el-icon>
                    </div>
                    <div class="message-content">
                        <div class="bubble" v-html="renderMarkdown(msg.content)"></div>

                        <!-- 引用来源 -->
                        <div v-if="msg.sources && msg.sources.length" class="sources-panel">
                            <div class="sources-title">
                                <el-icon><Link /></el-icon>
                                引用来源（{{ msg.sources.length }}）
                            </div>
                            <div class="source-items">
                                <div
                                    v-for="(src, si) in msg.sources"
                                    :key="si"
                                    class="source-item"
                                >
                                    <el-icon size="14"><Document /></el-icon>
                                    <span class="source-name">{{ src.doc_title }}</span>
                                    <span v-if="src.page_num" class="source-page">第{{ src.page_num }}页</span>
                                    <el-tag size="small" type="info">{{ (src.score * 100).toFixed(0) }}%</el-tag>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 流式回复中的骨架 -->
                <div v-if="streaming" class="message-item assistant">
                    <div class="avatar"><el-icon size="18"><Cpu /></el-icon></div>
                    <div class="message-content">
                        <div class="bubble streaming-bubble" v-html="renderMarkdown(streamingContent || '...')"></div>
                    </div>
                </div>
            </div>

            <!-- 输入区 -->
            <div class="input-area">
                <el-input
                    v-model="inputText"
                    type="textarea"
                    :rows="3"
                    placeholder="输入问题，按 Enter 发送，Shift+Enter 换行..."
                    resize="none"
                    :disabled="streaming"
                    @keydown.enter="handleEnterKey"
                />
                <div class="input-actions">
                    <span class="input-tip">Enter 发送 · Shift+Enter 换行</span>
                    <el-button
                        type="primary"
                        :loading="streaming"
                        :disabled="!inputText.trim()"
                        @click="handleSend"
                    >
                        {{ streaming ? '回答中...' : '发送' }}
                    </el-button>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, Filter, ChatDotRound, Cpu, User, Link, Document } from '@element-plus/icons-vue'
import {
    knowledgeDocumentList,
    knowledgeConversationList,
    knowledgeConversationDetail,
    knowledgeConversationCreate,
    knowledgeConversationDelete,
    knowledgeConversationClearMessages,
    knowledgeChatStream,
} from '@/restful/api'

const conversations = ref([])
const messages = ref([])
const currentConvId = ref(null)
const currentConvTitle = ref('')
const inputText = ref('')
const streaming = ref(false)
const streamingContent = ref('')
const messagesAreaRef = ref(null)
const scopePopoverVisible = ref(false)
const selectedDocIds = ref([])
const selectedCategories = ref([])
const readyDocs = ref([])

const quickQuestions = [
    '这个系统有哪些核心功能？',
    '登录功能需要测试哪些场景？',
    '支付流程的异常情况有哪些？',
    '系统的技术架构是什么？',
]

const getCategoryLabel = (value) => {
    const map = { requirement: '需求', tech_design: '技术', test_case: '用例', business: '业务', generated: 'AI生成', other: '其他' }
    return map[value] || value
}

const formatDate = (dt) => {
    if (!dt) return ''
    const d = new Date(dt)
    const now = new Date()
    const diff = now - d
    if (diff < 60000) return '刚刚'
    if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前'
    if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前'
    return d.toLocaleDateString('zh-CN')
}

const renderMarkdown = (text) => {
    if (!text) return ''
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/^#{1,3}\s(.+)$/gm, (_, h) => `<strong style="display:block;margin:8px 0 4px;font-size:15px">${h}</strong>`)
        .replace(/^[-*]\s(.+)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/gs, '<ul style="padding-left:16px;margin:4px 0">$1</ul>')
        .replace(/\n\n/g, '<br/><br/>')
        .replace(/\n/g, '<br/>')
}

const scrollToBottom = async () => {
    await nextTick()
    if (messagesAreaRef.value) {
        messagesAreaRef.value.scrollTop = messagesAreaRef.value.scrollHeight
    }
}

const fetchConversations = async () => {
    try {
        const res = await knowledgeConversationList()
        conversations.value = res.data.results || res.data || []
    } catch (e) {
        // ignore
    }
}

const fetchReadyDocs = async () => {
    try {
        const res = await knowledgeDocumentList({ status: 'ready', page_size: 100 })
        readyDocs.value = res.data.results || res.data || []
    } catch (e) {
        // ignore
    }
}

const newConversation = () => {
    currentConvId.value = null
    currentConvTitle.value = ''
    messages.value = []
    streamingContent.value = ''
}

const loadConversation = async (conv) => {
    currentConvId.value = conv.id
    currentConvTitle.value = conv.title || '对话'
    messages.value = []
    try {
        const res = await knowledgeConversationDetail(conv.id)
        const detail = res.data
        messages.value = (detail.messages || []).map(m => ({
            role: m.role,
            content: m.content,
            sources: m.sources || [],
        }))
    } catch (e) {
        ElMessage.error('加载历史消息失败')
    }
    scrollToBottom()
}

const deleteConversation = async (conv) => {
    try {
        await ElMessageBox.confirm(`确定删除对话「${conv.title || '新对话'}」？`, '提示', { type: 'warning' })
        await knowledgeConversationDelete(conv.id)
        if (currentConvId.value === conv.id) {
            newConversation()
        }
        fetchConversations()
    } catch (e) {
        if (e !== 'cancel') ElMessage.error('删除失败')
    }
}

const clearMessages = async () => {
    if (!currentConvId.value) {
        messages.value = []
        return
    }
    try {
        await ElMessageBox.confirm('确定清空本次对话消息？', '提示', { type: 'warning' })
        await knowledgeConversationClearMessages(currentConvId.value)
        messages.value = []
        ElMessage.success('消息已清空')
    } catch (e) {
        if (e !== 'cancel') ElMessage.error('操作失败')
    }
}

const sendQuestion = (q) => {
    inputText.value = q
    handleSend()
}

const handleEnterKey = (e) => {
    if (e.shiftKey) return
    e.preventDefault()
    handleSend()
}

const handleSend = async () => {
    const question = inputText.value.trim()
    if (!question || streaming.value) return

    inputText.value = ''
    messages.value.push({ role: 'user', content: question, sources: [] })
    scrollToBottom()

    streaming.value = true
    streamingContent.value = ''
    let tempSources = []

    try {
        await knowledgeChatStream(
            {
                question,
                conversation_id: currentConvId.value || undefined,
                doc_ids: selectedDocIds.value,
                category_filter: selectedCategories.value,
            },
            {
                onConversationId: (id) => {
                    currentConvId.value = id
                    if (!currentConvTitle.value) {
                        currentConvTitle.value = question.slice(0, 30)
                    }
                },
                onChunk: (content) => {
                    streamingContent.value += content
                    scrollToBottom()
                },
                onSources: (sources) => {
                    tempSources = sources
                },
                onDone: () => {
                    messages.value.push({
                        role: 'assistant',
                        content: streamingContent.value,
                        sources: tempSources,
                    })
                    streamingContent.value = ''
                    streaming.value = false
                    scrollToBottom()
                    fetchConversations()
                },
                onError: (err) => {
                    ElMessage.error('回答失败：' + (err || '网络错误'))
                    streaming.value = false
                    streamingContent.value = ''
                },
            }
        )
    } catch (e) {
        ElMessage.error('请求失败')
        streaming.value = false
        streamingContent.value = ''
    }
}

onMounted(() => {
    fetchConversations()
    fetchReadyDocs()
})
</script>

<style scoped>
.knowledge-chat-page {
    display: flex;
    height: 100%;
    background: #f5f7fa;
    overflow: hidden;
}

.conversation-panel {
    width: 220px;
    flex-shrink: 0;
    background: #fff;
    border-right: 1px solid #ebeef5;
    display: flex;
    flex-direction: column;
}

.panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 12px;
    border-bottom: 1px solid #ebeef5;
    font-weight: 600;
    font-size: 14px;
    color: #1a2332;
}

.conv-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px 0;
}

.conv-item {
    padding: 10px 12px;
    cursor: pointer;
    position: relative;
    border-radius: 6px;
    margin: 2px 6px;
    transition: background 0.2s;
}

.conv-item:hover {
    background: #f5f7fa;
}

.conv-item.active {
    background: #ecf5ff;
}

.conv-title {
    font-size: 13px;
    font-weight: 500;
    color: #1a2332;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    padding-right: 24px;
}

.conv-preview {
    font-size: 11px;
    color: #8a9fb2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-top: 2px;
}

.conv-time {
    font-size: 11px;
    color: #b0bec5;
    margin-top: 2px;
}

.conv-delete {
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    opacity: 0;
    transition: opacity 0.2s;
}

.conv-item:hover .conv-delete {
    opacity: 1;
}

.chat-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    height: 100%;
}

.chat-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 20px;
    background: #fff;
    border-bottom: 1px solid #ebeef5;
    flex-shrink: 0;
}

.chat-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 16px;
    font-weight: 600;
    color: #1a2332;
}

.scope-selector {
    display: flex;
    gap: 8px;
    align-items: center;
}

.scope-panel {
    padding: 4px;
}

.scope-title {
    font-size: 13px;
    color: #606266;
    margin-bottom: 8px;
    font-weight: 500;
}

.messages-area {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.welcome-area {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex: 1;
    text-align: center;
    gap: 8px;
    color: #909399;
}

.welcome-title {
    font-size: 18px;
    font-weight: 600;
    color: #4a5568;
    margin: 0;
}

.welcome-desc {
    font-size: 13px;
    color: #909399;
    margin: 0;
}

.quick-questions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: center;
    margin-top: 16px;
    max-width: 600px;
}

.quick-btn {
    padding: 8px 14px;
    border: 1px solid #dcdfe6;
    border-radius: 20px;
    cursor: pointer;
    font-size: 13px;
    color: #606266;
    transition: all 0.2s;
    background: #fff;
}

.quick-btn:hover {
    border-color: #409eff;
    color: #409eff;
    background: #ecf5ff;
}

.message-item {
    display: flex;
    gap: 12px;
    max-width: 85%;
}

.message-item.user {
    flex-direction: row-reverse;
    align-self: flex-end;
}

.message-item.assistant {
    align-self: flex-start;
}

.avatar {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    font-size: 14px;
}

.message-item.user .avatar {
    background: #409eff;
    color: #fff;
}

.message-item.assistant .avatar {
    background: #f0f4ff;
    color: #409eff;
}

.message-content {
    flex: 1;
}

.bubble {
    padding: 12px 16px;
    border-radius: 12px;
    font-size: 14px;
    line-height: 1.6;
    word-break: break-word;
}

.message-item.user .bubble {
    background: #409eff;
    color: #fff;
    border-bottom-right-radius: 4px;
}

.message-item.assistant .bubble {
    background: #fff;
    color: #1a2332;
    border-bottom-left-radius: 4px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

.streaming-bubble {
    position: relative;
}

.streaming-bubble::after {
    content: '▋';
    animation: blink 1s infinite;
    color: #409eff;
}

@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
}

.sources-panel {
    margin-top: 8px;
    border-radius: 8px;
    border: 1px solid #ebeef5;
    overflow: hidden;
    background: #fafbfc;
}

.sources-title {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    font-size: 12px;
    color: #8a9fb2;
    background: #f5f7fa;
    border-bottom: 1px solid #ebeef5;
}

.source-items {
    padding: 8px 12px;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.source-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: #606266;
}

.source-name {
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.source-page {
    color: #8a9fb2;
}

.input-area {
    padding: 16px 20px;
    background: #fff;
    border-top: 1px solid #ebeef5;
    flex-shrink: 0;
}

.input-actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 8px;
}

.input-tip {
    font-size: 12px;
    color: #c0c4cc;
}
</style>
