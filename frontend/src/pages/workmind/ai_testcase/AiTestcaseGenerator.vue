<template>
    <div class="ai-testcase-container">
        <!-- 页面头部 -->
        <div class="page-header">
            <div class="header-title-row">
                <h2>AI 用例智能体</h2>
                <span v-if="configStatus.configured" class="status-badge status-connected">
                    <span class="status-dot"></span>
                    {{ configStatus.model }} 已连接
                </span>
                <span v-else class="status-badge status-disconnected">
                    <span class="status-dot"></span>
                    未配置 API Key
                </span>
            </div>
            <span class="header-desc">使用 Kimi K2.5 大模型，智能生成结构化测试用例并导出 XMind</span>
        </div>

        <el-row :gutter="20">
            <!-- 左侧：生成区 -->
            <el-col :span="14">
                <!-- 输入卡片 -->
                <el-card class="input-card" shadow="hover">
                    <template #header>
                        <div class="card-header">
                            <span class="card-title">
                                <el-icon><Edit /></el-icon>
                                需求描述
                            </span>
                            <el-switch
                                v-model="useThinking"
                                active-text="思考模式"
                                inactive-text=""
                                style="margin-left: auto;"
                            />
                        </div>
                    </template>

                    <el-input
                        v-model="requirement"
                        type="textarea"
                        :rows="4"
                        placeholder="请输入功能需求描述（可选），也可以直接上传需求文档 / UI 设计图"
                        resize="vertical"
                        maxlength="5000"
                        show-word-limit
                    />

                    <!-- 文件上传区 -->
                    <div class="upload-section">
                        <div class="upload-label">
                            <el-icon><Paperclip /></el-icon>
                            <span>上传附件</span>
                            <span class="upload-label-tip">支持需求文档、UI 设计图、技术方案</span>
                        </div>
                        <el-upload
                            ref="uploadRef"
                            v-model:file-list="fileList"
                            :auto-upload="false"
                            :limit="10"
                            :on-exceed="handleFileExceed"
                            :before-upload="beforeFileUpload"
                            multiple
                            drag
                            class="upload-dragger"
                            accept=".docx,.pdf,.txt,.md,.png,.jpg,.jpeg,.webp"
                        >
                            <div class="upload-drag-content">
                                <el-icon class="upload-icon"><UploadFilled /></el-icon>
                                <div class="upload-drag-text">
                                    拖拽文件到此处，或 <em>点击上传</em>
                                </div>
                                <div class="upload-drag-tip">
                                    .docx / .pdf / .txt / .md / .png / .jpg / .webp，单文件最大 10MB，最多 10 个
                                </div>
                            </div>
                        </el-upload>
                    </div>

                    <!-- 附件提示 -->
                    <div v-if="fileWarnings.length > 0" class="file-warnings">
                        <el-alert
                            v-for="(warn, idx) in fileWarnings"
                            :key="idx"
                            :title="warn"
                            type="warning"
                            show-icon
                            :closable="true"
                            class="file-warning-item"
                        />
                    </div>

                    <div class="input-actions">
                        <el-button
                            type="primary"
                            size="large"
                            :loading="generating"
                            :disabled="(!requirement.trim() && fileList.length === 0) || !configStatus.configured"
                            @click="handleGenerate"
                        >
                            <el-icon v-if="!generating"><MagicStick /></el-icon>
                            {{ generating ? '正在生成中...' : '智能生成用例' }}
                        </el-button>
                        <el-button size="large" @click="handleClear" :disabled="generating">
                            清空
                        </el-button>
                        <span v-if="generating" class="generating-timer">
                            已耗时 {{ elapsedTime }}s
                        </span>
                    </div>
                </el-card>

                <!-- 流式输出面板 -->
                <el-card v-if="streamContent || generating" class="stream-card" shadow="hover">
                    <template #header>
                        <div class="card-header">
                            <span class="card-title">
                                <el-icon><Document /></el-icon>
                                {{ generating ? 'AI 正在生成...' : '生成结果' }}
                            </span>
                            <span v-if="generating" class="stream-indicator">
                                <span class="typing-dot"></span>
                                <span class="typing-dot"></span>
                                <span class="typing-dot"></span>
                            </span>
                            <div v-if="currentResult" class="result-stats">
                                <el-tag type="info" size="small">{{ currentResult.module_count }} 个模块</el-tag>
                                <el-tag type="success" size="small">{{ currentResult.case_count }} 条用例</el-tag>
                                <el-tag size="small">Token: {{ currentResult.usage?.total_tokens || 0 }}</el-tag>
                            </div>
                        </div>
                    </template>

                    <!-- 流式文本输出（生成中） -->
                    <div v-if="generating || !currentResult" class="stream-output" ref="streamOutputRef">
                        <pre class="stream-text">{{ streamContent }}</pre>
                    </div>

                    <!-- 树形预览（生成完成后） -->
                    <div v-if="currentResult" class="result-preview">
                        <el-tree
                            :data="treeData"
                            :props="treeProps"
                            default-expand-all
                            :expand-on-click-node="false"
                        >
                            <template #default="{ node, data }">
                                <span class="tree-node">
                                    <el-tag
                                        v-if="data.nodeType === 'module'"
                                        type="primary" size="small" effect="dark"
                                    >模块</el-tag>
                                    <el-tag
                                        v-else-if="data.nodeType === 'function'"
                                        type="warning" size="small" effect="dark"
                                    >功能</el-tag>
                                    <el-tag
                                        v-else-if="data.nodeType === 'case'"
                                        :type="getPriorityType(data.priority)" size="small"
                                    >{{ data.priority }}</el-tag>
                                    <span class="tree-label">{{ data.label }}</span>
                                    <el-button
                                        v-if="data.nodeType === 'module' && !regenerating"
                                        class="module-adjust-btn"
                                        text type="warning" size="small"
                                        @click.stop="openRegenerateDialog(data.label)"
                                    >
                                        <el-icon><EditPen /></el-icon>
                                        调整
                                    </el-button>
                                </span>
                            </template>
                        </el-tree>
                    </div>

                    <div v-if="currentResult" class="result-actions">
                        <el-button type="success" @click="handleDownload">
                            <el-icon><Download /></el-icon>
                            下载 XMind
                        </el-button>
                        <el-button @click="showJsonDialog = true">
                            <el-icon><View /></el-icon>
                            查看 JSON
                        </el-button>
                        <el-button type="warning" @click="openReviewDialog" :disabled="reviewing || applyingReview">
                            <el-icon><Search /></el-icon>
                            评审用例
                        </el-button>
                    </div>
                </el-card>

                <!-- 旧的结果卡片（从历史记录查看时） -->
                <el-card v-if="!streamContent && currentResult" class="result-card" shadow="hover">
                    <template #header>
                        <div class="card-header">
                            <span class="card-title">
                                <el-icon><Document /></el-icon>
                                生成结果
                            </span>
                            <div class="result-stats">
                                <el-tag type="info" size="small">{{ currentResult.module_count }} 个模块</el-tag>
                                <el-tag type="success" size="small">{{ currentResult.case_count }} 条用例</el-tag>
                                <el-tag size="small">
                                    Token: {{ currentResult.usage?.total_tokens || 0 }}
                                </el-tag>
                            </div>
                        </div>
                    </template>

                    <!-- 用例树状预览 -->
                    <div class="result-preview">
                        <el-tree
                            :data="treeData"
                            :props="treeProps"
                            default-expand-all
                            :expand-on-click-node="false"
                        >
                            <template #default="{ node, data }">
                                <span class="tree-node">
                                    <el-tag
                                        v-if="data.nodeType === 'module'"
                                        type="primary"
                                        size="small"
                                        effect="dark"
                                    >模块</el-tag>
                                    <el-tag
                                        v-else-if="data.nodeType === 'function'"
                                        type="warning"
                                        size="small"
                                        effect="dark"
                                    >功能</el-tag>
                                    <el-tag
                                        v-else-if="data.nodeType === 'case'"
                                        :type="getPriorityType(data.priority)"
                                        size="small"
                                    >{{ data.priority }}</el-tag>
                                    <span class="tree-label">{{ data.label }}</span>
                                    <el-button
                                        v-if="data.nodeType === 'module' && !regenerating"
                                        class="module-adjust-btn"
                                        text type="warning" size="small"
                                        @click.stop="openRegenerateDialog(data.label)"
                                    >
                                        <el-icon><EditPen /></el-icon>
                                        调整
                                    </el-button>
                                </span>
                            </template>
                        </el-tree>
                    </div>

                    <div class="result-actions">
                        <el-button type="success" @click="handleDownload">
                            <el-icon><Download /></el-icon>
                            下载 XMind
                        </el-button>
                        <el-button @click="showJsonDialog = true">
                            <el-icon><View /></el-icon>
                            查看 JSON
                        </el-button>
                        <el-button type="warning" @click="openReviewDialog" :disabled="reviewing || applyingReview">
                            <el-icon><Search /></el-icon>
                            评审用例
                        </el-button>
                    </div>
                </el-card>
            </el-col>

            <!-- 右侧：历史记录 -->
            <el-col :span="10">
                <el-card class="history-card" shadow="hover">
                    <template #header>
                        <div class="card-header">
                            <span class="card-title">
                                <el-icon><Clock /></el-icon>
                                生成历史
                            </span>
                            <el-button text type="primary" @click="loadHistory">
                                <el-icon><Refresh /></el-icon>
                                刷新
                            </el-button>
                        </div>
                    </template>

                    <div v-if="historyList.length === 0" class="empty-history">
                        <el-empty description="暂无历史记录" :image-size="80" />
                    </div>

                    <div v-else class="history-list">
                        <div
                            v-for="item in historyList"
                            :key="item.id"
                            class="history-item"
                            :class="{ active: currentResult && currentResult.id === item.id }"
                        >
                            <div class="history-header">
                                <el-tag
                                    :type="getStatusType(item.status)"
                                    size="small"
                                    effect="dark"
                                >{{ getStatusText(item.status) }}</el-tag>
                                <span class="history-time">{{ formatTime(item.created_at) }}</span>
                            </div>
                            <div class="history-requirement">{{ item.requirement }}</div>
                            <div class="history-meta">
                                <span v-if="item.module_count">
                                    <el-icon><Folder /></el-icon>
                                    {{ item.module_count }} 模块
                                </span>
                                <span v-if="item.case_count">
                                    <el-icon><Document /></el-icon>
                                    {{ item.case_count }} 用例
                                </span>
                                <span v-if="item.total_tokens">
                                    Token: {{ item.total_tokens }}
                                </span>
                            </div>
                            <div class="history-actions">
                                <el-button
                                    v-if="item.status === 'success'"
                                    text type="primary" size="small"
                                    @click="handlePreview(item)"
                                >
                                    <el-icon><View /></el-icon>
                                    查看/调整
                                </el-button>
                                <el-button
                                    v-if="item.status === 'success'"
                                    text type="success" size="small"
                                    @click="handleHistoryDownload(item)"
                                >
                                    <el-icon><Download /></el-icon>
                                    下载
                                </el-button>
                                <el-button
                                    text type="danger" size="small"
                                    @click="handleDelete(item)"
                                >
                                    <el-icon><Delete /></el-icon>
                                    删除
                                </el-button>
                            </div>
                        </div>
                    </div>

                    <!-- 分页 -->
                    <div v-if="historyTotal > 10" class="history-pagination">
                        <el-pagination
                            v-model:current-page="historyPage"
                            :page-size="10"
                            :total="historyTotal"
                            layout="prev, pager, next"
                            size="small"
                            @current-change="loadHistory"
                        />
                    </div>
                </el-card>
            </el-col>
        </el-row>

        <!-- JSON 预览弹窗 -->
        <el-dialog
            v-model="showJsonDialog"
            title="用例 JSON 数据"
            width="70%"
            top="5vh"
        >
            <el-input
                type="textarea"
                :model-value="jsonPreview"
                :rows="25"
                readonly
                class="json-preview"
            />
        </el-dialog>

        <!-- 模块调整弹窗 -->
        <el-dialog
            v-model="showRegenerateDialog"
            :title="`调整模块用例 —「${regenerateModuleName}」`"
            width="800px"
            :close-on-click-modal="!regenerating"
            :close-on-press-escape="!regenerating"
            @close="handleRegenerateDialogClose"
        >
            <!-- 输入表单 -->
            <div v-if="!regenerating && !regenerateStreamContent" class="regenerate-form">
                <p class="regenerate-hint">
                    AI 将根据以下信息重新生成该模块的用例，其他模块不受影响。两项至少填写一项。
                </p>

                <!-- 补充需求 -->
                <div class="regenerate-field">
                    <div class="regenerate-field-label">
                        <span>补充模块需求</span>
                        <el-tag size="small" type="info">可选</el-tag>
                    </div>
                    <el-input
                        v-model="regenerateModuleRequirement"
                        type="textarea"
                        :rows="10"
                        placeholder="补充该模块更细节的业务规则、功能描述等，如：密码必须包含大小写+数字+特殊字符，连续错误5次锁定30分钟..."
                        maxlength="20000"
                        show-word-limit
                    />
                </div>

                <!-- 调整意见 -->
                <div class="regenerate-field">
                    <div class="regenerate-field-label">
                        <span>调整意见</span>
                        <el-tag size="small" type="info">可选</el-tag>
                    </div>
                    <el-input
                        v-model="regenerateAdjustment"
                        type="textarea"
                        :rows="4"
                        placeholder="对已有用例的改进要求，如：补充更多异常场景和边界值用例、步骤要更详细、增加兼容性测试用例..."
                        maxlength="2000"
                        show-word-limit
                    />
                </div>

                <div class="regenerate-options">
                    <el-switch
                        v-model="regenerateUseThinking"
                        active-text="思考模式"
                        inactive-text=""
                    />
                </div>
            </div>

            <!-- 流式输出（重新生成中） -->
            <div v-if="regenerating || regenerateStreamContent" class="regenerate-stream">
                <div class="regenerate-stream-header">
                    <span v-if="regenerating" class="regenerate-status">
                        <span class="typing-dot"></span>
                        <span class="typing-dot"></span>
                        <span class="typing-dot"></span>
                        <span style="margin-left: 8px;">AI 正在重新生成「{{ regenerateModuleName }}」模块...</span>
                        <span class="generating-timer">{{ regenerateElapsedTime }}s</span>
                    </span>
                    <span v-else class="regenerate-status regenerate-done">
                        <el-icon><CircleCheck /></el-icon>
                        模块「{{ regenerateModuleName }}」已更新
                    </span>
                </div>
                <div class="stream-output regenerate-output" ref="regenerateStreamRef">
                    <pre class="stream-text">{{ regenerateStreamContent }}</pre>
                </div>
            </div>

            <template #footer>
                <div class="regenerate-footer">
                    <el-button @click="showRegenerateDialog = false" :disabled="regenerating">
                        {{ regenerateStreamContent && !regenerating ? '关闭' : '取消' }}
                    </el-button>
                    <el-button
                        v-if="!regenerateStreamContent || regenerating"
                        type="primary"
                        :loading="regenerating"
                        :disabled="!canSubmitRegenerate"
                        @click="handleRegenerateModule"
                    >
                        {{ regenerating ? '正在重新生成...' : '开始重新生成' }}
                    </el-button>
                </div>
            </template>
        </el-dialog>

        <!-- 用例评审弹窗 -->
        <el-dialog
            v-model="showReviewDialog"
            title="用例全局评审"
            width="900px"
            top="3vh"
            :close-on-click-modal="!reviewing && !applyingReview"
            :close-on-press-escape="!reviewing && !applyingReview"
            @close="handleReviewDialogClose"
        >
            <!-- 阶段1: 评审中 / 评审结果 -->
            <div v-if="!applyingReview && !applyReviewStreamContent">

                <!-- 评审前提示 -->
                <div v-if="!reviewing && !reviewStreamContent && !reviewResult" class="review-intro">
                    <el-alert
                        type="info"
                        show-icon
                        :closable="false"
                    >
                        <template #title>
                            AI 将分 6 个维度逐一深入扫描所有用例：重复、冗余、归属、优先级、缺失场景、命名覆盖，确保不遗漏问题。
                        </template>
                    </el-alert>
                </div>

                <!-- 评审进行中：维度进度 -->
                <div v-if="reviewing" class="review-progress">
                    <div class="review-progress-header">
                        <span class="regenerate-status">
                            <span class="typing-dot"></span>
                            <span class="typing-dot"></span>
                            <span class="typing-dot"></span>
                            <span style="margin-left: 8px;">
                                正在扫描：{{ reviewCurrentDim?.dimension_label || '准备中' }}
                                （{{ reviewCurrentDim?.index || 0 }}/{{ reviewCurrentDim?.total || 6 }}）
                            </span>
                            <span class="generating-timer">{{ reviewElapsedTime }}s</span>
                        </span>
                    </div>

                    <!-- 维度进度条 -->
                    <div class="review-dim-list">
                        <div
                            v-for="dim in reviewDimResults"
                            :key="dim.key"
                            class="review-dim-item"
                            :class="{ done: true }"
                        >
                            <el-icon color="#67c23a"><CircleCheck /></el-icon>
                            <span class="review-dim-label">{{ dim.label }}</span>
                            <el-tag v-if="dim.items_count > 0" type="danger" size="small">
                                {{ dim.items_count }} 个问题
                            </el-tag>
                            <el-tag v-else type="success" size="small">无问题</el-tag>
                            <el-tag v-if="dim.warning" type="warning" size="small">{{ dim.warning }}</el-tag>
                        </div>
                        <div
                            v-if="reviewCurrentDim"
                            class="review-dim-item current"
                        >
                            <span class="typing-dot" style="width: 14px; height: 14px;"></span>
                            <span class="review-dim-label">{{ reviewCurrentDim.dimension_label }}</span>
                            <span class="review-dim-scanning">扫描中...</span>
                        </div>
                    </div>

                    <!-- 当前维度流式输出 -->
                    <div class="stream-output review-stream-output" ref="reviewStreamRef">
                        <pre class="stream-text">{{ reviewStreamContent }}</pre>
                    </div>
                </div>

                <!-- 评审报告 -->
                <div v-if="reviewResult" class="review-report">
                    <div class="review-summary">
                        <el-icon><Warning /></el-icon>
                        <span>{{ reviewResult.summary }}</span>
                        <el-tag type="danger" size="small" v-if="reviewResult.total_issues > 0" style="margin-left: 8px;">
                            {{ reviewResult.total_issues }} 个问题
                        </el-tag>
                        <el-tag type="success" size="small" v-else style="margin-left: 8px;">
                            无问题
                        </el-tag>
                    </div>

                    <div v-if="reviewResult.items && reviewResult.items.length > 0" class="review-items">
                        <div class="review-select-all">
                            <el-checkbox
                                :model-value="isAllReviewSelected"
                                :indeterminate="isReviewIndeterminate"
                                @change="handleSelectAllReview"
                            >全选</el-checkbox>
                            <span class="review-select-count">
                                已选 {{ reviewSelectedIds.length }} / {{ reviewResult.items.length }} 项
                            </span>
                        </div>

                        <div
                            v-for="item in reviewResult.items"
                            :key="item.id"
                            class="review-item"
                            :class="{ selected: reviewSelectedIds.includes(item.id) }"
                        >
                            <div class="review-item-header">
                                <el-checkbox
                                    :model-value="reviewSelectedIds.includes(item.id)"
                                    @change="(val) => toggleReviewItem(item.id, val)"
                                />
                                <el-tag
                                    :type="getReviewSeverityType(item.severity)"
                                    size="small"
                                    effect="dark"
                                >{{ getReviewSeverityText(item.severity) }}</el-tag>
                                <el-tag size="small" type="info">{{ getReviewTypeText(item.type) }}</el-tag>
                                <span class="review-item-title">{{ item.title }}</span>
                            </div>
                            <div class="review-item-body">
                                <div class="review-item-desc">
                                    <strong>问题：</strong>{{ item.description }}
                                </div>
                                <div class="review-item-suggestion">
                                    <strong>建议：</strong>{{ item.suggestion }}
                                </div>
                                <div v-if="item.affected_modules && item.affected_modules.length" class="review-item-modules">
                                    <strong>涉及模块：</strong>
                                    <el-tag
                                        v-for="m in item.affected_modules"
                                        :key="m"
                                        size="small"
                                        type="primary"
                                        style="margin-right: 4px;"
                                    >{{ m }}</el-tag>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div v-else class="review-no-issues">
                        <el-result icon="success" title="用例质量良好" sub-title="未发现需要调整的问题" />
                    </div>
                </div>
            </div>

            <!-- 阶段2: 采纳执行中 -->
            <div v-if="applyingReview || applyReviewStreamContent">
                <div class="regenerate-stream-header">
                    <span v-if="applyingReview" class="regenerate-status">
                        <span class="typing-dot"></span>
                        <span class="typing-dot"></span>
                        <span class="typing-dot"></span>
                        <span style="margin-left: 8px;">AI 正在应用 {{ reviewSelectedIds.length }} 项评审意见...</span>
                        <span class="generating-timer">{{ applyReviewElapsedTime }}s</span>
                    </span>
                    <span v-else class="regenerate-status regenerate-done">
                        <el-icon><CircleCheck /></el-icon>
                        评审意见已应用，用例已更新
                    </span>
                </div>
                <div class="stream-output review-stream-output" ref="applyReviewStreamRef">
                    <pre class="stream-text">{{ applyReviewStreamContent }}</pre>
                </div>
            </div>

            <template #footer>
                <div class="regenerate-footer">
                    <el-button @click="showReviewDialog = false" :disabled="reviewing || applyingReview">
                        {{ (reviewResult && !applyingReview) || applyReviewStreamContent ? '关闭' : '取消' }}
                    </el-button>
                    <!-- 开始评审按钮 -->
                    <el-button
                        v-if="!reviewResult && !reviewing && !applyingReview && !applyReviewStreamContent"
                        type="warning"
                        @click="handleStartReview"
                    >
                        <el-icon><Search /></el-icon>
                        开始评审
                    </el-button>
                    <!-- 重新评审按钮 -->
                    <el-button
                        v-if="reviewResult && !applyingReview && !applyReviewStreamContent"
                        @click="handleReReview"
                    >
                        <el-icon><Refresh /></el-icon>
                        重新评审
                    </el-button>
                    <!-- 采纳选中项按钮 -->
                    <el-button
                        v-if="reviewResult && reviewResult.items && reviewResult.items.length > 0 && !applyingReview && !applyReviewStreamContent"
                        type="primary"
                        :disabled="reviewSelectedIds.length === 0"
                        @click="handleApplyReview"
                    >
                        <el-icon><Select /></el-icon>
                        采纳选中项（{{ reviewSelectedIds.length }}）
                    </el-button>
                </div>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
    Edit, MagicStick, Document, Download, View,
    Clock, Refresh, Delete, Folder, UploadFilled, Paperclip,
    EditPen, CircleCheck, Search, Select, Warning
} from '@element-plus/icons-vue'
import {
    aiGenerateTestcaseStream,
    aiRegenerateModuleStream,
    aiReviewTestcaseStream,
    aiApplyReviewStream,
    getAiTestcaseGenerations,
    deleteAiTestcaseGeneration,
    previewAiTestcase,
    downloadAiTestcaseXmind,
    getAiTestcaseConfigStatus
} from '@/restful/api'

// 状态
const requirement = ref('')
const useThinking = ref(false)
const generating = ref(false)
const currentResult = ref(null)
const configStatus = ref({ configured: false, model: '', base_url: '', api_key_prefix: '' })

// 文件上传
const uploadRef = ref(null)
const fileList = ref([])
const fileWarnings = ref([])

// 流式输出
const streamContent = ref('')
const streamOutputRef = ref(null)

// 计时器
const elapsedTime = ref(0)
let timerInterval = null

// 历史记录
const historyList = ref([])
const historyPage = ref(1)
const historyTotal = ref(0)

// 弹窗
const showJsonDialog = ref(false)

// 模块调整
const showRegenerateDialog = ref(false)
const regenerateModuleName = ref('')
const regenerateModuleRequirement = ref('')
const regenerateAdjustment = ref('')
const regenerateUseThinking = ref(false)
const regenerating = ref(false)
const regenerateStreamContent = ref('')
const regenerateStreamRef = ref(null)
const regenerateElapsedTime = ref(0)
let regenerateTimerInterval = null

// 用例评审
const showReviewDialog = ref(false)
const reviewing = ref(false)
const reviewStreamContent = ref('')
const reviewStreamRef = ref(null)
const reviewElapsedTime = ref(0)
let reviewTimerInterval = null
const reviewResult = ref(null)       // { summary, total_issues, items: [...] }
const reviewSelectedIds = ref([])    // 勾选的评审项 id 数组
const applyingReview = ref(false)
const applyReviewStreamContent = ref('')
const applyReviewStreamRef = ref(null)
const applyReviewElapsedTime = ref(0)
let applyReviewTimerInterval = null
const reviewUseThinking = ref(true)

// 维度进度
const reviewDimensions = ref([])     // [{key, label}]
const reviewCurrentDim = ref(null)   // 当前维度 {key, label, index, total}
const reviewDimResults = ref([])     // 每个维度的结果 [{key, label, items_count, items, warning?}]

// 树形配置
const treeProps = { label: 'label', children: 'children' }

// 计算属性
const treeData = computed(() => {
    if (!currentResult.value?.data) return []
    return buildTreeData(currentResult.value.data)
})

const jsonPreview = computed(() => {
    if (!currentResult.value?.data) return ''
    return JSON.stringify(currentResult.value.data, null, 2)
})

// 构建树形数据
function buildTreeData(data) {
    const modules = data.modules || []
    return modules.map(mod => ({
        label: mod.name,
        nodeType: 'module',
        children: (mod.functions || []).map(func => ({
            label: func.name,
            nodeType: 'function',
            children: (func.cases || []).map(c => ({
                label: c.name,
                nodeType: 'case',
                priority: c.priority,
                precondition: c.precondition,
                steps: c.steps,
                expected: c.expected
            }))
        }))
    }))
}

// 文件上传校验
function beforeFileUpload(file) {
    const maxSize = 10 * 1024 * 1024
    if (file.size > maxSize) {
        ElMessage.warning(`文件 ${file.name} 超过 10MB 限制`)
        return false
    }
    const allowedExts = ['.docx', '.pdf', '.txt', '.md', '.png', '.jpg', '.jpeg', '.webp']
    const ext = '.' + file.name.split('.').pop().toLowerCase()
    if (!allowedExts.includes(ext)) {
        ElMessage.warning(`不支持的文件格式: ${ext}`)
        return false
    }
    return true
}

function handleFileExceed() {
    ElMessage.warning('最多上传 10 个文件')
}

function handleClear() {
    requirement.value = ''
    fileList.value = []
    fileWarnings.value = []
}

// 生成用例（流式）
async function handleGenerate() {
    const hasText = requirement.value.trim()
    const hasFiles = fileList.value.length > 0

    if (!hasText && !hasFiles) {
        ElMessage.warning('请输入需求描述或上传文件')
        return
    }

    // 重置状态
    generating.value = true
    currentResult.value = null
    streamContent.value = ''
    fileWarnings.value = []
    elapsedTime.value = 0

    // 启动计时器
    timerInterval = setInterval(() => {
        elapsedTime.value++
    }, 1000)

    // 构建 FormData
    const formData = new FormData()
    formData.append('requirement', requirement.value.trim())
    formData.append('use_thinking', useThinking.value)

    // 添加文件
    for (const file of fileList.value) {
        formData.append('files', file.raw)
    }

    await aiGenerateTestcaseStream(
        formData,
        // onChunk — 每收到一个片段
        (content) => {
            streamContent.value += content
            // 自动滚动到底部
            nextTick(() => {
                if (streamOutputRef.value) {
                    streamOutputRef.value.scrollTop = streamOutputRef.value.scrollHeight
                }
            })
        },
        // onDone — 生成完成
        (result) => {
            stopTimer()
            generating.value = false
            // 后端 SSE 返回 record_id，统一映射为 id
            currentResult.value = { ...result, id: result.record_id }
            ElMessage.success(`生成成功！共 ${result.module_count} 个模块，${result.case_count} 条用例`)
            loadHistory()
        },
        // onError — 出错
        (error) => {
            stopTimer()
            generating.value = false
            ElMessage.error(`生成失败：${error}`)
            loadHistory()
        },
        // onStart — 接收 start 事件（含文件处理警告）
        (startData) => {
            if (startData.warnings && startData.warnings.length > 0) {
                fileWarnings.value = startData.warnings
            }
            if (startData.attachment_info) {
                const info = startData.attachment_info
                ElMessage.info(`已解析附件：${info.text_count} 个文档，${info.image_count} 张图片`)
            }
        }
    )
}

function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval)
        timerInterval = null
    }
}

// 下载 XMind
async function handleDownload() {
    if (!currentResult.value?.id) return
    await doDownload(currentResult.value.id, currentResult.value.title)
}

async function handleHistoryDownload(item) {
    const title = item.result_json?.title || `testcase_${item.id}`
    await doDownload(item.id, title)
}

async function doDownload(id, title) {
    try {
        const res = await downloadAiTestcaseXmind(id)
        const blob = new Blob([res.data], { type: 'application/octet-stream' })
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `${title}.xmind`
        link.click()
        window.URL.revokeObjectURL(url)
        ElMessage.success('下载成功')
    } catch (err) {
        ElMessage.error('下载失败：' + err.message)
    }
}

// 预览历史记录
async function handlePreview(item) {
    try {
        const res = await previewAiTestcase(item.id)
        streamContent.value = ''  // 清掉流式内容，使用旧的结果卡片
        currentResult.value = {
            id: item.id,
            title: res.title,
            module_count: res.module_count,
            case_count: res.case_count,
            data: res.data,
            usage: { total_tokens: item.total_tokens }
        }
    } catch (err) {
        ElMessage.error('加载失败')
    }
}

// 删除记录
async function handleDelete(item) {
    try {
        await ElMessageBox.confirm('确定删除该生成记录？', '确认', {
            type: 'warning'
        })
        await deleteAiTestcaseGeneration(item.id)
        ElMessage.success('已删除')
        if (currentResult.value?.id === item.id) {
            currentResult.value = null
        }
        loadHistory()
    } catch (err) {
        if (err !== 'cancel') {
            ElMessage.error('删除失败')
        }
    }
}

// ============ 模块调整 ============

function openRegenerateDialog(moduleName) {
    if (!currentResult.value?.id) {
        ElMessage.warning('请先查看一条用例记录')
        return
    }
    regenerateModuleName.value = moduleName
    regenerateModuleRequirement.value = ''
    regenerateAdjustment.value = ''
    regenerateStreamContent.value = ''
    regenerateElapsedTime.value = 0
    showRegenerateDialog.value = true
}

function handleRegenerateDialogClose() {
    if (regenerating.value) return  // 生成中不允许关闭
    regenerateStreamContent.value = ''
    regenerateModuleRequirement.value = ''
    regenerateAdjustment.value = ''
}

// 计算属性：两者至少填一项才能提交
const canSubmitRegenerate = computed(() => {
    return regenerateModuleRequirement.value.trim() || regenerateAdjustment.value.trim()
})

async function handleRegenerateModule() {
    if (!canSubmitRegenerate.value) {
        ElMessage.warning('请至少填写「补充需求」或「调整意见」中的一项')
        return
    }

    regenerating.value = true
    regenerateStreamContent.value = ''
    regenerateElapsedTime.value = 0

    // 启动计时器
    regenerateTimerInterval = setInterval(() => {
        regenerateElapsedTime.value++
    }, 1000)

    await aiRegenerateModuleStream(
        {
            record_id: currentResult.value.id,
            module_name: regenerateModuleName.value,
            module_requirement: regenerateModuleRequirement.value.trim(),
            adjustment: regenerateAdjustment.value.trim(),
            use_thinking: regenerateUseThinking.value
        },
        // onChunk
        (content) => {
            regenerateStreamContent.value += content
            nextTick(() => {
                if (regenerateStreamRef.value) {
                    regenerateStreamRef.value.scrollTop = regenerateStreamRef.value.scrollHeight
                }
            })
        },
        // onDone
        (result) => {
            stopRegenerateTimer()
            regenerating.value = false
            // 用合并后的完整数据更新 currentResult
            currentResult.value = {
                ...currentResult.value,
                data: result.data,
                module_count: result.module_count,
                case_count: result.case_count,
                usage: {
                    ...currentResult.value.usage,
                    total_tokens: (currentResult.value.usage?.total_tokens || 0) + (result.usage?.total_tokens || 0)
                }
            }
            ElMessage.success(`模块「${regenerateModuleName.value}」已重新生成，共 ${result.case_count} 条用例`)
            loadHistory()
        },
        // onError
        (error) => {
            stopRegenerateTimer()
            regenerating.value = false
            ElMessage.error(`模块调整失败：${error}`)
        },
        // onStart
        (startData) => {
            if (startData.warnings && startData.warnings.length > 0) {
                ElMessage.warning(startData.warnings.join('；'))
            }
        }
    )
}

function stopRegenerateTimer() {
    if (regenerateTimerInterval) {
        clearInterval(regenerateTimerInterval)
        regenerateTimerInterval = null
    }
}

// ============ 用例评审 ============

function openReviewDialog() {
    if (!currentResult.value?.id) {
        ElMessage.warning('请先查看一条用例记录')
        return
    }
    // 重置状态
    reviewStreamContent.value = ''
    reviewResult.value = null
    reviewSelectedIds.value = []
    reviewElapsedTime.value = 0
    applyReviewStreamContent.value = ''
    applyReviewElapsedTime.value = 0
    reviewDimResults.value = []
    reviewCurrentDim.value = null
    showReviewDialog.value = true
}

function handleReviewDialogClose() {
    if (reviewing.value || applyingReview.value) return
    reviewStreamContent.value = ''
    reviewResult.value = null
    reviewSelectedIds.value = []
    applyReviewStreamContent.value = ''
    reviewDimResults.value = []
    reviewCurrentDim.value = null
}

async function handleStartReview() {
    reviewing.value = true
    reviewStreamContent.value = ''
    reviewResult.value = null
    reviewSelectedIds.value = []
    reviewElapsedTime.value = 0
    reviewDimResults.value = []
    reviewCurrentDim.value = null

    reviewTimerInterval = setInterval(() => {
        reviewElapsedTime.value++
    }, 1000)

    await aiReviewTestcaseStream(
        {
            record_id: currentResult.value.id
        },
        // onChunk
        (content) => {
            reviewStreamContent.value += content
            nextTick(() => {
                if (reviewStreamRef.value) {
                    reviewStreamRef.value.scrollTop = reviewStreamRef.value.scrollHeight
                }
            })
        },
        // onDone
        (result) => {
            stopReviewTimer()
            reviewing.value = false
            reviewCurrentDim.value = null
            if (result.data) {
                reviewResult.value = result.data
                // 默认全选
                if (result.data.items && result.data.items.length > 0) {
                    reviewSelectedIds.value = result.data.items.map(it => it.id)
                }
            }
            reviewStreamContent.value = ''
        },
        // onError
        (error) => {
            stopReviewTimer()
            reviewing.value = false
            reviewCurrentDim.value = null
            ElMessage.error(`评审失败：${error}`)
        },
        // onStart
        (event) => {
            if (event.type === 'start') {
                reviewDimensions.value = event.dimensions || []
            } else if (event.type === 'dimension_start') {
                // 新维度开始，清空流内容
                reviewStreamContent.value = ''
                reviewCurrentDim.value = event
            } else if (event.type === 'dimension_done') {
                // 维度完成，记录结果
                reviewDimResults.value.push({
                    key: event.dimension_key,
                    label: event.dimension_label,
                    items_count: event.items_count,
                    items: event.items,
                    warning: event.warning || null
                })
                reviewCurrentDim.value = null
                reviewStreamContent.value = ''
            }
        }
    )
}

function handleReReview() {
    reviewResult.value = null
    reviewSelectedIds.value = []
    reviewStreamContent.value = ''
    applyReviewStreamContent.value = ''
    reviewDimResults.value = []
    reviewCurrentDim.value = null
    handleStartReview()
}

// 勾选/取消勾选评审项
function toggleReviewItem(id, checked) {
    if (checked) {
        if (!reviewSelectedIds.value.includes(id)) {
            reviewSelectedIds.value.push(id)
        }
    } else {
        reviewSelectedIds.value = reviewSelectedIds.value.filter(i => i !== id)
    }
}

// 全选计算属性
const isAllReviewSelected = computed(() => {
    if (!reviewResult.value?.items?.length) return false
    return reviewSelectedIds.value.length === reviewResult.value.items.length
})
const isReviewIndeterminate = computed(() => {
    const total = reviewResult.value?.items?.length || 0
    const selected = reviewSelectedIds.value.length
    return selected > 0 && selected < total
})
function handleSelectAllReview(val) {
    if (val) {
        reviewSelectedIds.value = reviewResult.value.items.map(it => it.id)
    } else {
        reviewSelectedIds.value = []
    }
}

// 采纳选中项
async function handleApplyReview() {
    if (reviewSelectedIds.value.length === 0) {
        ElMessage.warning('请至少选择一项要采纳的评审意见')
        return
    }

    const selectedItems = reviewResult.value.items.filter(
        it => reviewSelectedIds.value.includes(it.id)
    )

    applyingReview.value = true
    applyReviewStreamContent.value = ''
    applyReviewElapsedTime.value = 0

    applyReviewTimerInterval = setInterval(() => {
        applyReviewElapsedTime.value++
    }, 1000)

    await aiApplyReviewStream(
        {
            record_id: currentResult.value.id,
            selected_items: selectedItems,
            use_thinking: reviewUseThinking.value
        },
        // onChunk
        (content) => {
            applyReviewStreamContent.value += content
            nextTick(() => {
                if (applyReviewStreamRef.value) {
                    applyReviewStreamRef.value.scrollTop = applyReviewStreamRef.value.scrollHeight
                }
            })
        },
        // onDone
        (result) => {
            stopApplyReviewTimer()
            applyingReview.value = false
            if (result.data) {
                currentResult.value = {
                    ...currentResult.value,
                    data: result.data,
                    module_count: result.module_count,
                    case_count: result.case_count,
                    usage: {
                        ...currentResult.value.usage,
                        total_tokens: (currentResult.value.usage?.total_tokens || 0) + (result.usage?.total_tokens || 0)
                    }
                }
            }
            const summary = result.apply_summary || `${selectedItems.length} 项`
            ElMessage.success(`评审意见已应用：${summary}`)
            loadHistory()
        },
        // onError
        (error) => {
            stopApplyReviewTimer()
            applyingReview.value = false
            ElMessage.error(`采纳失败：${error}`)
        },
        // onStart
        null
    )
}

function stopReviewTimer() {
    if (reviewTimerInterval) {
        clearInterval(reviewTimerInterval)
        reviewTimerInterval = null
    }
}

function stopApplyReviewTimer() {
    if (applyReviewTimerInterval) {
        clearInterval(applyReviewTimerInterval)
        applyReviewTimerInterval = null
    }
}

// 评审辅助函数
function getReviewSeverityType(severity) {
    const map = { high: 'danger', medium: 'warning', low: 'info' }
    return map[severity] || 'info'
}
function getReviewSeverityText(severity) {
    const map = { high: '高', medium: '中', low: '低' }
    return map[severity] || severity
}
function getReviewTypeText(type) {
    const map = {
        duplicate: '重复',
        priority: '优先级',
        missing: '缺失',
        naming: '命名',
        coverage: '覆盖',
        structure: '归属',
        redundant: '冗余',
        other: '其他'
    }
    return map[type] || type
}

// 加载历史记录
async function loadHistory() {
    try {
        const res = await getAiTestcaseGenerations({
            page: historyPage.value,
            page_size: 10,
            ordering: '-created_at'
        })
        historyList.value = res.results || res
        historyTotal.value = res.count || historyList.value.length
    } catch (err) {
        console.error('加载历史记录失败:', err)
    }
}

// 加载配置状态
async function loadConfigStatus() {
    try {
        configStatus.value = await getAiTestcaseConfigStatus()
    } catch (err) {
        console.error('加载配置状态失败:', err)
    }
}

// 辅助函数
function getPriorityType(priority) {
    const map = { P0: 'danger', P1: 'warning', P2: 'info', P3: 'success' }
    return map[priority] || 'info'
}

function getStatusType(status) {
    const map = { pending: 'info', generating: 'warning', success: 'success', failed: 'danger' }
    return map[status] || 'info'
}

function getStatusText(status) {
    const map = { pending: '等待中', generating: '生成中', success: '成功', failed: '失败' }
    return map[status] || status
}

function formatTime(timeStr) {
    if (!timeStr) return ''
    const d = new Date(timeStr)
    const month = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const hours = String(d.getHours()).padStart(2, '0')
    const minutes = String(d.getMinutes()).padStart(2, '0')
    return `${month}-${day} ${hours}:${minutes}`
}

// 初始化
onMounted(() => {
    loadConfigStatus()
    loadHistory()
})

onUnmounted(() => {
    stopTimer()
    stopRegenerateTimer()
    stopReviewTimer()
    stopApplyReviewTimer()
})
</script>

<style scoped>
.ai-testcase-container {
    padding: 20px;
}

/* 页面头部 */
.page-header {
    margin-bottom: 20px;
}

.header-title-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 4px;
}

.header-title-row h2 {
    margin: 0;
    font-size: 18px;
    color: #303133;
    font-weight: 600;
}

.header-desc {
    font-size: 13px;
    color: #909399;
}

/* 连接状态 */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    padding: 2px 10px;
    border-radius: 10px;
    line-height: 20px;
}

.status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    display: inline-block;
}

.status-connected {
    color: #67c23a;
    background: #f0f9eb;
}

.status-connected .status-dot {
    background: #67c23a;
    box-shadow: 0 0 4px rgba(103, 194, 58, 0.6);
}

.status-disconnected {
    color: #f56c6c;
    background: #fef0f0;
}

.status-disconnected .status-dot {
    background: #f56c6c;
}

/* 卡片通用样式 */
.input-card,
.result-card,
.history-card {
    margin-bottom: 20px;
}

.card-header {
    display: flex;
    align-items: center;
    gap: 8px;
}

.card-title {
    font-size: 15px;
    font-weight: 600;
    color: #303133;
    display: flex;
    align-items: center;
    gap: 6px;
}

/* 文件上传区 */
.upload-section {
    margin-top: 16px;
}

.upload-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    font-weight: 500;
    color: #606266;
    margin-bottom: 8px;
}

.upload-label-tip {
    font-size: 12px;
    color: #909399;
    font-weight: normal;
    margin-left: 4px;
}

.upload-dragger :deep(.el-upload-dragger) {
    padding: 16px 20px;
    border: 1px dashed #dcdfe6;
    border-radius: 6px;
    background: #fafafa;
    transition: all 0.2s ease;
}

.upload-dragger :deep(.el-upload-dragger:hover) {
    border-color: #409eff;
    background: #ecf5ff;
}

.upload-dragger :deep(.el-upload) {
    width: 100%;
}

.upload-dragger :deep(.el-upload-dragger) {
    width: 100%;
}

.upload-drag-content {
    text-align: center;
}

.upload-icon {
    font-size: 28px;
    color: #909399;
    margin-bottom: 4px;
}

.upload-drag-text {
    font-size: 13px;
    color: #606266;
    margin-bottom: 4px;
}

.upload-drag-text em {
    color: #409eff;
    font-style: normal;
}

.upload-drag-tip {
    font-size: 12px;
    color: #909399;
}

/* 文件列表样式 */
.upload-dragger :deep(.el-upload-list) {
    margin-top: 8px;
}

.upload-dragger :deep(.el-upload-list__item) {
    border-radius: 4px;
    transition: all 0.2s ease;
}

/* 文件警告 */
.file-warnings {
    margin-top: 8px;
}

.file-warning-item {
    margin-bottom: 4px;
}

.file-warning-item :deep(.el-alert__title) {
    font-size: 12px;
}

/* 输入区 */
.input-actions {
    margin-top: 16px;
    display: flex;
    align-items: center;
    gap: 12px;
}

.generating-timer {
    font-size: 13px;
    color: #909399;
    margin-left: 4px;
}

/* 流式输出 */
.stream-card {
    margin-bottom: 20px;
}

.stream-output {
    max-height: 300px;
    overflow-y: auto;
    background: #fafafa;
    border: 1px solid #e4e7ed;
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 12px;
}

.stream-text {
    margin: 0;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 13px;
    line-height: 1.7;
    color: #303133;
    white-space: pre-wrap;
    word-break: break-all;
}

.stream-indicator {
    display: inline-flex;
    gap: 3px;
    margin-left: 8px;
    align-items: center;
}

.typing-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #409eff;
    animation: typingBounce 1.2s infinite ease-in-out;
}

.typing-dot:nth-child(2) {
    animation-delay: 0.2s;
}

.typing-dot:nth-child(3) {
    animation-delay: 0.4s;
}

@keyframes typingBounce {
    0%, 80%, 100% {
        opacity: 0.3;
        transform: scale(0.8);
    }
    40% {
        opacity: 1;
        transform: scale(1);
    }
}

.stream-output::-webkit-scrollbar {
    width: 4px;
}

.stream-output::-webkit-scrollbar-thumb {
    background: #dcdfe6;
    border-radius: 2px;
}

/* 结果区 */
.result-stats {
    margin-left: auto;
    display: flex;
    gap: 8px;
}

.result-preview {
    max-height: 400px;
    overflow-y: auto;
    padding: 8px 0;
}

:deep(.el-tree-node__content) {
    height: 32px;
}

.tree-node {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
}

.tree-label {
    color: #303133;
}

.result-actions {
    margin-top: 16px;
    display: flex;
    gap: 12px;
    padding-top: 16px;
    border-top: 1px solid #e4e7ed;
}

/* 历史记录 */
.history-list {
    max-height: calc(100vh - 240px);
    overflow-y: auto;
}

.history-item {
    padding: 12px 16px;
    border-radius: 6px;
    background: #fafafa;
    border: 1px solid #e4e7ed;
    margin-bottom: 10px;
    transition: all 0.2s ease;
    cursor: pointer;
}

.history-item:hover {
    border-color: #409eff;
    background: #ecf5ff;
}

.history-item.active {
    border-color: #409eff;
    background: #ecf5ff;
}

.history-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.history-time {
    font-size: 12px;
    color: #909399;
}

.history-requirement {
    font-size: 13px;
    color: #303133;
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    margin-bottom: 8px;
}

.history-meta {
    display: flex;
    gap: 12px;
    font-size: 12px;
    color: #909399;
    margin-bottom: 8px;
}

.history-meta span {
    display: flex;
    align-items: center;
    gap: 4px;
}

.history-actions {
    display: flex;
    gap: 4px;
}

.history-pagination {
    margin-top: 16px;
    display: flex;
    justify-content: center;
}

.empty-history {
    padding: 40px 0;
}

/* 模块调整按钮 */
.module-adjust-btn {
    margin-left: 8px;
    padding: 2px 6px !important;
    font-size: 12px;
    opacity: 0;
    transition: opacity 0.2s ease;
}

:deep(.el-tree-node__content:hover) .module-adjust-btn {
    opacity: 1;
}

/* 模块调整弹窗 */
.regenerate-form {
    padding: 0;
}

.regenerate-hint {
    font-size: 13px;
    color: #606266;
    margin: 0 0 16px 0;
    line-height: 1.6;
}

.regenerate-field {
    margin-bottom: 16px;
}

.regenerate-field-label {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
    font-size: 14px;
    font-weight: 500;
    color: #303133;
}

.regenerate-options {
    margin-top: 4px;
    display: flex;
    align-items: center;
    gap: 16px;
}

.regenerate-stream {
    padding: 0;
}

.regenerate-stream-header {
    margin-bottom: 12px;
}

.regenerate-status {
    display: flex;
    align-items: center;
    font-size: 13px;
    color: #409eff;
}

.regenerate-done {
    color: #67c23a;
    gap: 4px;
}

.regenerate-output {
    max-height: 350px;
}

.regenerate-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
}

/* ============ 评审弹窗 ============ */
.review-intro {
    margin-bottom: 8px;
}

.review-options {
    margin-top: 12px;
    display: flex;
    align-items: center;
    gap: 16px;
}

.review-stream-output {
    max-height: 200px;
}

/* 维度进度 */
.review-progress {
    padding: 0;
}

.review-progress-header {
    margin-bottom: 12px;
}

.review-dim-list {
    margin-bottom: 12px;
}

.review-dim-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-radius: 4px;
    font-size: 13px;
    margin-bottom: 4px;
}

.review-dim-item.done {
    background: #f0f9eb;
}

.review-dim-item.current {
    background: #ecf5ff;
    border: 1px solid #c6e2ff;
}

.review-dim-label {
    font-weight: 500;
    color: #303133;
}

.review-dim-scanning {
    font-size: 12px;
    color: #409eff;
    margin-left: auto;
}

.review-report {
    max-height: 60vh;
    overflow-y: auto;
}

.review-summary {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background: #fafafa;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    color: #303133;
    margin-bottom: 16px;
    border: 1px solid #e4e7ed;
}

.review-select-all {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 0;
    border-bottom: 1px solid #e4e7ed;
    margin-bottom: 12px;
}

.review-select-count {
    font-size: 12px;
    color: #909399;
}

.review-items {
    padding: 0;
}

.review-item {
    padding: 12px 16px;
    border: 1px solid #e4e7ed;
    border-radius: 6px;
    margin-bottom: 10px;
    transition: all 0.2s ease;
    background: #fff;
}

.review-item.selected {
    border-color: #409eff;
    background: #ecf5ff;
}

.review-item:hover {
    border-color: #c6e2ff;
}

.review-item-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
}

.review-item-title {
    font-weight: 500;
    font-size: 14px;
    color: #303133;
}

.review-item-body {
    padding-left: 28px;
    font-size: 13px;
    line-height: 1.7;
    color: #606266;
}

.review-item-desc {
    margin-bottom: 4px;
}

.review-item-suggestion {
    margin-bottom: 4px;
    color: #409eff;
}

.review-item-modules {
    margin-top: 4px;
}

.review-no-issues {
    padding: 20px 0;
}

.review-report::-webkit-scrollbar {
    width: 4px;
}

.review-report::-webkit-scrollbar-thumb {
    background: #dcdfe6;
    border-radius: 2px;
}

/* JSON 预览 */
.json-preview :deep(.el-textarea__inner) {
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 13px;
    line-height: 1.6;
}

/* 滚动条 */
.history-list::-webkit-scrollbar,
.result-preview::-webkit-scrollbar {
    width: 4px;
}

.history-list::-webkit-scrollbar-track,
.result-preview::-webkit-scrollbar-track {
    background: transparent;
}

.history-list::-webkit-scrollbar-thumb,
.result-preview::-webkit-scrollbar-thumb {
    background: #dcdfe6;
    border-radius: 2px;
}
</style>
