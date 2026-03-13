<template>
    <div class="ai-req-container">
        <!-- 页面头部 -->
        <div class="page-header">
            <div class="header-title-row">
                <h2>AI 需求智能体</h2>
                <span class="status-badge status-connected">
                    <span class="status-dot"></span>
                    Kimi K2.5
                </span>
            </div>
            <span class="header-desc">多角色 AI 助手 —— 产品 PRD 撰写 · 开发需求分析 · 测试需求分析</span>
        </div>

        <el-row :gutter="20">
            <!-- 左侧：输入 + 输出 -->
            <el-col :span="14">
                <!-- 输入卡片 -->
                <el-card class="input-card" shadow="hover">
                    <template #header>
                        <div class="card-header">
                            <span class="card-title">
                                <el-icon><Edit /></el-icon>
                                需求输入
                            </span>
                        </div>
                    </template>

                    <!-- 角色 + 任务选择 -->
                    <div class="selector-row">
                        <div class="selector-item">
                            <span class="selector-label">角色</span>
                            <el-radio-group v-model="form.role" @change="onRoleChange">
                                <el-radio-button value="product">
                                    <el-icon><User /></el-icon> 产品
                                </el-radio-button>
                                <el-radio-button value="dev">
                                    <el-icon><Monitor /></el-icon> 开发
                                </el-radio-button>
                                <el-radio-button value="test">
                                    <el-icon><Checked /></el-icon> 测试
                                </el-radio-button>
                            </el-radio-group>
                        </div>
                        <div class="selector-item">
                            <span class="selector-label">任务</span>
                            <el-select v-model="form.taskType" placeholder="选择任务类型" style="width: 220px;">
                                <el-option
                                    v-for="opt in taskTypeOptions"
                                    :key="opt.value"
                                    :label="opt.label"
                                    :value="opt.value"
                                    :disabled="opt.disabled"
                                />
                            </el-select>
                        </div>
                    </div>

                    <!-- 需求描述 -->
                    <el-input
                        v-model="form.requirement"
                        type="textarea"
                        :rows="5"
                        placeholder="请描述你的需求，可以是一句话也可以是详细的功能描述...&#10;&#10;示例：设计一个用户注册登录系统，支持手机号验证码、邮箱密码两种方式"
                        resize="vertical"
                        maxlength="50000"
                        show-word-limit
                        style="margin-top: 12px;"
                    />

                    <!-- 文件上传 -->
                    <div class="upload-section">
                        <div class="upload-label">
                            <el-icon><Paperclip /></el-icon>
                            <span>上传附件</span>
                            <span class="upload-label-tip">需求文档、UI 设计图、技术方案、竞品视频（.mp4/.webm）等</span>
                        </div>
                        <el-upload
                            ref="uploadRef"
                            v-model:file-list="fileList"
                            :auto-upload="false"
                            :limit="10"
                            :on-exceed="() => ElMessage.warning('最多上传 10 个文件')"
                            multiple
                            drag
                            class="upload-dragger"
                            accept=".docx,.pdf,.txt,.md,.png,.jpg,.jpeg,.webp,.mp4,.webm"
                        >
                            <div class="upload-drag-content">
                                <el-icon class="upload-icon"><UploadFilled /></el-icon>
                                <div class="upload-drag-text">
                                    拖拽文件到此处，或 <em>点击上传</em>
                                </div>
                                <div class="upload-drag-tip">
                                    .docx / .pdf / .txt / .md / .png / .jpg / .webp / .mp4 / .webm，文档与图片单文件 10MB，视频单文件 100MB
                                </div>
                            </div>
                        </el-upload>
                    </div>

                    <!-- 高级选项 + 提交 -->
                    <div class="input-actions">
                        <el-button
                            type="primary"
                            size="large"
                            :loading="generating || workflowRunning || maRunning"
                            :disabled="!canSubmit"
                            @click="multiAgentMode ? handleStartMultiAgent() : (deepMode ? handleStartWorkflow() : handleGenerate())"
                        >
                            <el-icon v-if="!generating && !workflowRunning && !maRunning"><MagicStick /></el-icon>
                            {{ (generating || workflowRunning || maRunning) ? '正在生成中...' : (multiAgentMode ? '多智能体协作' : (deepMode ? '深度撰写' : '开始生成')) }}
                        </el-button>
                        <el-button size="large" @click="handleClear" :disabled="generating || workflowRunning">
                            清空
                        </el-button>

                        <div class="options-right">
                            <el-tooltip content="深度模式：竞品分析→PRD撰写→AI评审→人工审批" placement="top">
                                <el-switch
                                    v-model="deepMode"
                                    active-text="深度模式"
                                    inactive-text="快速模式"
                                    :disabled="multiAgentMode || form.role !== 'product' || form.taskType !== 'prd_draft'"
                                />
                            </el-tooltip>
                            <el-tooltip content="多智能体：PM+架构师+测试分析师+调研员协作分析" placement="top">
                                <el-switch
                                    v-model="multiAgentMode"
                                    active-text="多智能体"
                                    inactive-text=""
                                    style="margin-left: 12px;"
                                    :disabled="deepMode"
                                />
                            </el-tooltip>
                            <el-switch
                                v-model="form.useThinking"
                                active-text="深度推理"
                                inactive-text=""
                                style="margin-left: 12px;"
                            />
                        </div>

                        <span v-if="generating || workflowRunning" class="generating-timer">
                            已耗时 {{ elapsedTime }}s
                        </span>
                    </div>
                </el-card>

                <!-- 工作流步骤可视化面板：深度模式开启即显示，未开始时为步骤预览 -->
                <el-card v-if="deepMode" class="workflow-card" shadow="hover">
                    <template #header>
                        <div class="card-header">
                            <span class="card-title">
                                <el-icon><SetUp /></el-icon>
                                PRD 深度撰写工作流
                            </span>
                            <el-tag v-if="workflowActive" :type="workflowStatusType" size="small" effect="dark">
                                {{ workflowStatusText }}
                            </el-tag>
                            <el-tag v-else type="info" size="small">步骤预览</el-tag>
                        </div>
                    </template>

                    <div v-if="!workflowActive" class="workflow-preview-hint">
                        将按以下步骤执行：竞品分析 → PRD 撰写 → AI 评审 → 人工审批 → 完成。点击上方「深度撰写」开始。
                    </div>
                    <div v-else class="workflow-current-step-label">当前步骤</div>
                    <div class="workflow-steps">
                        <el-steps :active="workflowActive ? workflowActiveStep : -1" finish-status="success" align-center>
                            <el-step title="竞品分析" :icon="workflowStepIcon(0)" :status="workflowActive ? workflowStepStatus(0) : 'wait'">
                                <template #description>
                                    <span v-if="workflowTrace[0]">
                                        {{ workflowTrace[0].elapsed_ms ? (workflowTrace[0].elapsed_ms / 1000).toFixed(1) + 's' : '' }}
                                        {{ workflowTrace[0].tokens ? ' · ' + workflowTrace[0].tokens + ' tokens' : '' }}
                                    </span>
                                </template>
                            </el-step>
                            <el-step title="PRD 撰写" :icon="workflowStepIcon(1)" :status="workflowActive ? workflowStepStatus(1) : 'wait'">
                                <template #description>
                                    <span v-if="workflowIteration > 0">第 {{ workflowIteration }} 轮</span>
                                </template>
                            </el-step>
                            <el-step title="AI 评审" :icon="workflowStepIcon(2)" :status="workflowActive ? workflowStepStatus(2) : 'wait'">
                                <template #description>
                                    <span v-if="workflowReviewScore != null">
                                        评分: {{ (workflowReviewScore * 100).toFixed(0) }}%
                                    </span>
                                </template>
                            </el-step>
                            <el-step title="人工审批" :icon="workflowStepIcon(3)" :status="workflowActive ? workflowStepStatus(3) : 'wait'">
                                <template #description>
                                    <span v-if="workflowWaitingApproval" class="step-wait-action">等待您的操作</span>
                                </template>
                            </el-step>
                            <el-step title="完成" :icon="workflowStepIcon(4)" :status="workflowActive ? workflowStepStatus(4) : 'wait'" />
                        </el-steps>
                    </div>

                    <!-- 审批面板 -->
                    <div v-if="workflowWaitingApproval" class="approval-panel">
                        <el-alert
                            :title="workflowError || '工作流等待人工审批'"
                            :type="workflowError ? 'warning' : 'info'"
                            :closable="false"
                            show-icon
                            style="margin-bottom: 16px;"
                        />
                        <div class="approval-prd-preview" v-if="workflowPrdDraft">
                            <el-collapse>
                                <el-collapse-item title="查看 PRD 草稿" name="prd">
                                    <pre class="prd-preview-text">{{ JSON.stringify(workflowPrdDraft, null, 2).slice(0, 3000) }}</pre>
                                </el-collapse-item>
                            </el-collapse>
                        </div>
                        <div v-if="workflowReviewFeedback" class="review-feedback-box">
                            <strong>AI 评审反馈：</strong>
                            <pre style="white-space: pre-wrap; color: #e6a23c; margin-top: 4px;">{{ workflowReviewFeedback }}</pre>
                        </div>
                        <div class="approval-actions">
                            <el-input
                                v-model="approvalComment"
                                type="textarea"
                                :rows="2"
                                placeholder="审批意见（可选）"
                                style="margin-bottom: 12px;"
                            />
                            <el-button type="success" :loading="approvalSubmitting" @click="handleApproval(true)">
                                通过
                            </el-button>
                            <el-button type="danger" :loading="approvalSubmitting" @click="handleApproval(false)">
                                驳回修订
                            </el-button>
                        </div>
                    </div>

                    <!-- 工作流完成 -->
                    <div v-if="workflowCompleted && workflowFinalPrd" class="workflow-result">
                        <el-alert title="工作流已完成" type="success" :closable="false" show-icon style="margin-bottom: 12px;" />
                        <el-button @click="showWorkflowResultDialog = true">
                            <el-icon><View /></el-icon>
                            查看最终 PRD
                        </el-button>
                    </div>
                </el-card>

                <!-- 多智能体协作面板：多智能体模式开启即显示，未开始时为步骤预览 -->
                <el-card v-if="multiAgentMode" class="multi-agent-card" shadow="hover">
                    <template #header>
                        <div class="card-header">
                            <span class="card-title">
                                <el-icon><SetUp /></el-icon>
                                多智能体协作分析
                            </span>
                            <el-tag v-if="maActive" :type="maStatusType" size="small" effect="dark">{{ maStatusText }}</el-tag>
                            <el-tag v-else type="info" size="small">步骤预览</el-tag>
                        </div>
                    </template>

                    <!-- 线性步骤条：调度 → 执行 → 审核 → 完成 -->
                    <div class="ma-steps-row">
                        <el-steps :active="maActive ? maActiveStep : -1" finish-status="success" align-center simple>
                            <el-step title="调度" :description="maActive && maActiveStep >= 0 ? 'Supervisor 分配任务' : ''" />
                            <el-step title="Agent 执行" :description="maActive && maActiveStep >= 1 ? '各角色并行/串行分析' : ''" />
                            <el-step title="人工审核" :description="maWaitingApproval ? '等待您的操作' : ''" />
                            <el-step title="完成" />
                        </el-steps>
                    </div>

                    <div v-if="!maActive" class="workflow-preview-hint">
                        将由 Supervisor 调度 PM、架构师、测试、调研员等 Agent 协作分析，完成后需您审核通过。点击上方「多智能体协作」开始。
                    </div>

                    <!-- 角色 Agent 卡片（仅运行中/待审核时展示） -->
                    <div v-if="maActive" class="ma-agents-grid">
                        <div v-for="agent in maAgentList" :key="agent.key" class="ma-agent-card" :class="maAgentCardClass(agent.key)">
                            <div class="ma-agent-icon">{{ agent.icon }}</div>
                            <div class="ma-agent-name">{{ agent.label }}</div>
                            <div class="ma-agent-status">
                                <el-tag v-if="maAgentStatus(agent.key) === 'done'" type="success" size="small">完成</el-tag>
                                <el-tag v-else-if="maAgentStatus(agent.key) === 'running'" size="small">运行中</el-tag>
                                <el-tag v-else type="info" size="small">等待</el-tag>
                            </div>
                        </div>
                    </div>

                    <!-- Supervisor 决策日志（仅运行中展示） -->
                    <div v-if="maActive && maSupervisorLog.length > 0" class="ma-supervisor-log">
                        <div class="ma-supervisor-title">Supervisor 决策日志</div>
                        <div v-for="(log, idx) in maSupervisorLog" :key="idx" class="ma-log-item">
                            <el-tag size="small" type="info">{{ idx + 1 }}</el-tag>
                            <span class="ma-log-decision">→ {{ maAgentLabel(log.decision) }}</span>
                            <span class="ma-log-reason">{{ log.reason }}</span>
                        </div>
                    </div>

                    <!-- 审核面板（待审核时展示） -->
                    <div v-if="maActive && maWaitingApproval" class="approval-panel">
                        <el-alert title="所有 Agent 分析完毕，请审核各角色输出" type="info" :closable="false" show-icon style="margin-bottom: 16px;" />
                        <el-collapse v-if="maAgentOutputs">
                            <el-collapse-item v-for="(output, key) in maAgentOutputs" :key="key" :title="maAgentLabel(key) + ' 输出'">
                                <pre class="prd-preview-text">{{ JSON.stringify(output, null, 2).slice(0, 2000) }}</pre>
                            </el-collapse-item>
                        </el-collapse>
                        <div style="margin-top: 16px;">
                            <el-input
                                v-model="maApprovalComment"
                                type="textarea"
                                :rows="2"
                                placeholder="审核意见（可选）"
                                style="margin-bottom: 12px;"
                            />
                            <el-button type="success" :loading="maApprovalSubmitting" @click="handleMultiAgentApproval(true)">
                                通过
                            </el-button>
                            <el-button type="danger" :loading="maApprovalSubmitting" @click="handleMultiAgentApproval(false)">
                                驳回
                            </el-button>
                        </div>
                    </div>

                    <!-- 完成（仅完成时展示） -->
                    <div v-if="maActive && maCompleted && maFinalOutput" class="workflow-result">
                        <el-alert title="多智能体协作分析完成" type="success" :closable="false" show-icon style="margin-bottom: 12px;" />
                        <el-button @click="showMaResultDialog = true">
                            <el-icon><View /></el-icon>
                            查看综合分析结果
                        </el-button>
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
                            <div v-if="doneResult" class="result-stats">
                                <el-tag size="small">{{ getRoleLabel(doneResult.role) }}</el-tag>
                                <el-tag type="info" size="small">{{ getTaskLabel(doneResult.task_type) }}</el-tag>
                                <el-tag v-if="doneResult.confidence_score != null" :type="doneResult.confidence_score >= 0.7 ? 'success' : 'warning'" size="small">
                                    置信度 {{ (doneResult.confidence_score * 100).toFixed(0) }}%
                                </el-tag>
                                <el-tag size="small" type="info">
                                    Token: {{ doneResult.usage?.total_tokens || 0 }}
                                </el-tag>
                            </div>
                        </div>
                    </template>

                    <!-- 流式文本输出：生成中且尚无内容时显示占位，便于用户看到“在等输出” -->
                    <div class="stream-output" ref="streamOutputRef">
                        <pre class="stream-text">{{ streamContent || (generating ? '等待输出…' : '') }}</pre>
                    </div>

                    <!-- P1-1：需澄清时展示澄清表单，提交后流式重新生成 -->
                    <div
                        v-if="doneResult && (doneResult.requires_clarification || (doneResult.confidence_score != null && doneResult.confidence_score < 0.7)) && (doneResult.clarification_questions?.length > 0)"
                        class="clarify-section"
                    >
                        <div class="clarify-title">请补充以下信息后重新生成</div>
                        <div v-for="(q, idx) in doneResult.clarification_questions" :key="idx" class="clarify-row">
                            <span class="clarify-q">{{ q }}</span>
                            <el-input
                                v-model="clarifyAnswers[idx]"
                                type="textarea"
                                :rows="2"
                                placeholder="请输入回答"
                                maxlength="2000"
                                show-word-limit
                            />
                        </div>
                        <el-button
                            type="primary"
                            :loading="clarifySubmitting"
                            @click="handleClarifyAndContinue"
                        >
                            提交澄清并重新生成
                        </el-button>
                    </div>

                    <!-- 操作按钮 -->
                    <div v-if="doneResult" class="result-actions">
                        <el-button @click="showJsonDialog = true" v-if="doneResult.result_json">
                            <el-icon><View /></el-icon>
                            查看结构化 JSON
                        </el-button>
                        <el-button @click="handleCopyMarkdown">
                            <el-icon><CopyDocument /></el-icon>
                            复制 Markdown
                        </el-button>
                        <el-button
                            v-if="isProductOrDevRole(doneResult)"
                            @click="handleDownloadWord"
                            :loading="downloadWordLoading"
                        >
                            <el-icon><Download /></el-icon>
                            下载 Word
                        </el-button>
                        <el-button
                            v-if="isTestRole(doneResult)"
                            @click="handleDownloadXmind"
                            :loading="downloadXmindLoading"
                        >
                            <el-icon><Download /></el-icon>
                            下载 XMind
                        </el-button>
                        <!-- 需求 → 用例页桥接：任意任务可带需求文本跳转用例页 -->
                        <el-button
                            v-if="doneResult?.record_id"
                            type="success"
                            @click="handleBridgeToTestcase"
                            :loading="bridging"
                        >
                            <el-icon><Right /></el-icon>
                            生成测试用例
                        </el-button>
                        <!-- P2-3：同步到 Jira / 写入 Confluence（Jira 当前不支持） -->
                        <el-button
                            v-if="doneResult?.record_id"
                            @click="handleSyncToJira"
                            :loading="syncingJira"
                        >
                            <el-icon><Share /></el-icon>
                            同步到 Jira
                        </el-button>
                        <el-button
                            v-if="hasPrdContent(doneResult)"
                            @click="handleSyncToConfluence"
                            :loading="syncingConfluence"
                        >
                            <el-icon><Document /></el-icon>
                            写入 Confluence
                        </el-button>
                        <!-- 多轮对话按钮 -->
                        <el-button
                            v-if="doneResult.requires_clarification || (doneResult.confidence_score != null && doneResult.confidence_score < 0.7)"
                            type="warning"
                            @click="openChatPanel"
                        >
                            <el-icon><ChatDotRound /></el-icon>
                            继续澄清
                        </el-button>
                        <!-- 反馈 -->
                        <div class="feedback-group">
                            <el-button
                                :type="feedbackGiven === 'positive' ? 'success' : ''"
                                circle size="small"
                                @click="handleFeedback('positive')"
                                :disabled="!!feedbackGiven"
                            >👍</el-button>
                            <el-button
                                :type="feedbackGiven === 'negative' ? 'danger' : ''"
                                circle size="small"
                                @click="handleFeedback('negative')"
                                :disabled="!!feedbackGiven"
                            >👎</el-button>
                        </div>
                    </div>
                </el-card>

                <!-- 多轮对话面板 -->
                <el-card v-if="chatVisible" class="chat-card" shadow="hover">
                    <template #header>
                        <div class="card-header">
                            <span class="card-title">
                                <el-icon><ChatDotRound /></el-icon>
                                多轮对话（澄清 & 修订）
                            </span>
                            <el-tag size="small" type="info">会话 {{ chatSessionId }}</el-tag>
                            <el-button text type="danger" style="margin-left: auto;" @click="chatVisible = false">
                                关闭
                            </el-button>
                        </div>
                    </template>

                    <!-- 对话历史 -->
                    <div class="chat-messages" ref="chatMessagesRef">
                        <div v-for="(msg, idx) in chatMessages" :key="idx" :class="['chat-msg', msg.role]">
                            <div class="chat-msg-label">{{ msg.role === 'user' ? '你' : 'AI' }}</div>
                            <pre class="chat-msg-content">{{ msg.content }}</pre>
                        </div>
                        <!-- 流式输出 -->
                        <div v-if="chatGenerating" class="chat-msg assistant">
                            <div class="chat-msg-label">AI</div>
                            <pre class="chat-msg-content">{{ chatStreamContent }}<span class="typing-cursor">|</span></pre>
                        </div>
                    </div>

                    <!-- 输入 -->
                    <div class="chat-input-row">
                        <el-input
                            v-model="chatInput"
                            type="textarea"
                            :rows="2"
                            placeholder="输入澄清信息或修改意见..."
                            :disabled="chatGenerating"
                            @keydown.ctrl.enter="handleChatSend"
                        />
                        <el-button
                            type="primary"
                            :loading="chatGenerating"
                            :disabled="!chatInput.trim()"
                            @click="handleChatSend"
                            style="margin-top: 8px;"
                        >
                            发送 (Ctrl+Enter)
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
                            :class="{ active: doneResult && doneResult.record_id === item.id }"
                            @click="handlePreviewHistory(item)"
                        >
                            <div class="history-header">
                                <el-tag :type="getStatusType(item.status)" size="small" effect="dark">
                                    {{ getStatusText(item.status) }}
                                </el-tag>
                                <div class="history-tags">
                                    <el-tag size="small" type="info">{{ getRoleLabel(item.role) }}</el-tag>
                                    <el-tag size="small">{{ getTaskLabel(item.task_type) }}</el-tag>
                                </div>
                                <span class="history-time">{{ formatTime(item.created_at) }}</span>
                            </div>
                            <div class="history-requirement">{{ item.requirement_input }}</div>
                            <div class="history-meta">
                                <span v-if="item.model_used">
                                    <el-icon><Cpu /></el-icon>
                                    {{ item.model_used }}
                                </span>
                                <span v-if="item.total_tokens">
                                    Token: {{ item.total_tokens }}
                                </span>
                                <span v-if="item.confidence_score != null">
                                    置信度: {{ (item.confidence_score * 100).toFixed(0) }}%
                                </span>
                                <span v-if="item.cost_usd">
                                    ${{ item.cost_usd }}
                                </span>
                            </div>
                            <div class="history-actions">
                                <el-button type="primary" link size="small" @click.stop="handlePreviewHistory(item)">
                                    查看
                                </el-button>
                            </div>
                        </div>
                    </div>

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
            title="结构化 JSON 数据"
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

        <!-- 多智能体结果弹窗 -->
        <el-dialog
            v-model="showMaResultDialog"
            title="多智能体协作分析结果"
            width="80%"
            top="5vh"
        >
            <el-tabs>
                <el-tab-pane v-for="(output, key) in (maFinalOutput || {})" :key="key" :label="maAgentLabel(key)">
                    <el-input
                        type="textarea"
                        :model-value="typeof output === 'string' ? output : JSON.stringify(output, null, 2)"
                        :rows="25"
                        readonly
                        class="json-preview"
                    />
                </el-tab-pane>
            </el-tabs>
        </el-dialog>

        <!-- 工作流结果弹窗 -->
        <el-dialog
            v-model="showWorkflowResultDialog"
            title="最终 PRD（深度模式）"
            width="75%"
            top="5vh"
        >
            <el-input
                type="textarea"
                :model-value="workflowFinalPrdText"
                :rows="30"
                readonly
                class="json-preview"
            />
        </el-dialog>

        <!-- 反馈弹窗 -->
        <el-dialog
            v-model="showFeedbackDialog"
            title="反馈详情"
            width="500px"
        >
            <el-form label-width="80px">
                <el-form-item label="问题类型">
                    <el-select v-model="feedbackForm.issueType" placeholder="选择问题类型" style="width: 100%;">
                        <el-option label="AI 幻觉 / 编造内容" value="hallucination" />
                        <el-option label="遗漏关键信息" value="missing" />
                        <el-option label="格式 / 结构错误" value="format_error" />
                        <el-option label="内容不相关" value="irrelevant" />
                        <el-option label="其他" value="other" />
                    </el-select>
                </el-form-item>
                <el-form-item label="补充说明">
                    <el-input
                        v-model="feedbackForm.comment"
                        type="textarea"
                        :rows="3"
                        placeholder="可选：描述具体问题"
                        maxlength="2000"
                    />
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="showFeedbackDialog = false">取消</el-button>
                <el-button type="primary" @click="submitFeedback">提交反馈</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import {
    Edit, MagicStick, Document, View, Clock, Refresh,
    UploadFilled, Paperclip, User, Monitor, Checked,
    CopyDocument, Right, ChatDotRound, SetUp, Share, Download
} from '@element-plus/icons-vue'
import {
    aiRequirementStream,
    aiRequirementClarifyAndContinue,
    aiRequirementChatStream,
    getAiRequirementTasks,
    submitAiRequirementFeedback,
    bridgeToTestcase,
    aiRequirementSyncToJira,
    aiRequirementSyncToConfluence,
    downloadAiRequirementTaskExport,
    startWorkflowStream,
    approveWorkflowStream,
    startMultiAgentStream,
    approveMultiAgentStream,
} from '@/restful/api'

const vueRouter = useRouter()

const TASK_MAP = {
    product: [
        { value: 'prd_draft', label: 'PRD 撰写' },
        { value: 'competitive_analysis', label: '竞品分析' },
        { value: 'prd_refine', label: '需求完善' },
    ],
    dev: [
        { value: 'requirement_analysis', label: '需求分析' },
        { value: 'tech_design', label: '技术方案' },
    ],
    test: [
        { value: 'test_requirement_analysis', label: '测试需求分析' },
    ],
}

const ROLE_LABELS = { product: '产品', dev: '开发', test: '测试' }
const TASK_LABELS = {
    competitive_analysis: '竞品分析',
    prd_draft: 'PRD 撰写',
    prd_refine: '需求完善',
    requirement_analysis: '需求分析',
    tech_design: '技术方案',
    test_requirement_analysis: '测试需求分析',
}

// ---- 表单 ----
const form = ref({
    role: 'product',
    taskType: 'prd_draft',
    requirement: '',
    useThinking: false,
})
const fileList = ref([])
const uploadRef = ref(null)

const taskTypeOptions = computed(() => TASK_MAP[form.value.role] || [])
const canSubmit = computed(() => {
    return (form.value.requirement.trim() || fileList.value.length > 0)
        && form.value.taskType
        && !generating.value
})

function onRoleChange() {
    const opts = TASK_MAP[form.value.role]
    const firstEnabled = opts.find(o => !o.disabled)
    form.value.taskType = firstEnabled ? firstEnabled.value : ''
}

function handleClear() {
    form.value.requirement = ''
    fileList.value = []
    streamContent.value = ''
    doneResult.value = null
    feedbackGiven.value = ''
}

// ---- 流式生成 ----
const generating = ref(false)
const streamContent = ref('')
const streamOutputRef = ref(null)
const doneResult = ref(null)
const elapsedTime = ref(0)
let timerInterval = null

// P1-1：澄清并继续
const clarifyAnswers = ref([])
const clarifySubmitting = ref(false)
watch(doneResult, (v) => {
    const qs = v?.clarification_questions
    if (Array.isArray(qs) && qs.length) {
        clarifyAnswers.value = Array.from({ length: qs.length }, () => '')
    } else {
        clarifyAnswers.value = []
    }
}, { immediate: true })

async function handleClarifyAndContinue() {
    if (!doneResult.value?.record_id) return
    const qs = doneResult.value.clarification_questions || []
    const answers = qs.map((_, i) => (clarifyAnswers.value[i] != null ? String(clarifyAnswers.value[i]).trim() : ''))
    clarifySubmitting.value = true
    streamContent.value = ''
    generating.value = true
    try {
        await aiRequirementClarifyAndContinue(
            doneResult.value.record_id,
            answers,
            (chunk) => { streamContent.value += chunk },
            (event) => {
                doneResult.value = {
                    ...event,
                    record_id: event.record_id,
                    result_json: event.result_json,
                    result_md: event.result_md,
                    confidence_score: event.confidence_score,
                    requires_clarification: event.requires_clarification,
                    clarification_questions: event.clarification_questions || [],
                    role: form.value.role,
                    task_type: form.value.taskType,
                    usage: event.usage,
                }
                streamContent.value = event.result_md || event.raw_content || ''
                clarifyAnswers.value = Array.from({ length: (event.clarification_questions || []).length }, () => '')
            },
            (err) => {
                ElMessage.error('澄清并继续失败：' + (err || '未知错误'))
            },
            (e) => {
                if (e?.record_id) streamContent.value = ''
            }
        )
    } finally {
        clarifySubmitting.value = false
        generating.value = false
    }
}

function buildSubmitData(costConfirmed = false) {
    const hasFiles = fileList.value.length > 0
    if (hasFiles) {
        const data = new FormData()
        data.append('role', form.value.role)
        data.append('task_type', form.value.taskType)
        data.append('requirement_input', form.value.requirement.trim())
        data.append('use_thinking', form.value.useThinking)
        if (costConfirmed) data.append('cost_confirmed', 'true')
        for (const f of fileList.value) {
            data.append('files', f.raw)
        }
        return data
    }
    return {
        role: form.value.role,
        task_type: form.value.taskType,
        requirement_input: form.value.requirement.trim(),
        use_thinking: form.value.useThinking,
        ...(costConfirmed ? { cost_confirmed: true } : {}),
    }
}

async function doSubmit(costConfirmed = false) {
    const data = buildSubmitData(costConfirmed)
    await aiRequirementStream(
        data,
        (content) => {
            streamContent.value += content
            nextTick(() => {
                requestAnimationFrame(() => {
                    if (streamOutputRef.value) {
                        streamOutputRef.value.scrollTop = streamOutputRef.value.scrollHeight
                    }
                })
            })
        },
        (result) => {
            stopTimer()
            generating.value = false
            doneResult.value = {
                ...result,
                role: form.value.role,
                task_type: form.value.taskType,
            }
            if (result?.result_md) {
                streamContent.value = result.result_md
            }
            ElMessage.success('生成完成')
            loadHistory()
        },
        (error) => {
            stopTimer()
            generating.value = false
            ElMessage.error(`生成失败：${error}`)
            loadHistory()
        },
        (startData) => {
            if (startData._pii_warning) {
                ElMessage.warning(startData._pii_warning)
            }
        },
        async (ev) => {
            try {
                await ElMessageBox.confirm(
                    ev.message || '预估成本超过阈值，是否继续？',
                    '成本确认',
                    { type: 'warning' }
                )
            } catch {
                generating.value = false
                return
            }
            await doSubmit(true)
        }
    )
}

async function handleGenerate() {
    generating.value = true
    streamContent.value = ''
    doneResult.value = null
    feedbackGiven.value = ''
    elapsedTime.value = 0

    timerInterval = setInterval(() => { elapsedTime.value++ }, 1000)
    await doSubmit(false)
}

function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval)
        timerInterval = null
    }
}

// ---- 历史记录 ----
const historyList = ref([])
const historyPage = ref(1)
const historyTotal = ref(0)

async function loadHistory() {
    try {
        const res = await getAiRequirementTasks({
            page: historyPage.value,
            page_size: 10,
            ordering: '-created_at',
        })
        historyList.value = res.results || res
        historyTotal.value = res.count || historyList.value.length
    } catch (err) {
        console.error('加载历史失败:', err)
    }
}

function handlePreviewHistory(item) {
    if (item.status !== 'success') return
    // 优先展示 Markdown（如 prd_draft 的 markdown_full），其次展示原始输出，再退化到结构化 JSON
    streamContent.value = item.result_md || item.raw_content || JSON.stringify(item.result_json, null, 2)
    doneResult.value = {
        record_id: item.id,
        result_json: item.result_json,
        confidence_score: item.confidence_score,
        role: item.role,
        task_type: item.task_type,
        usage: {
            total_tokens: item.total_tokens,
        },
    }
    feedbackGiven.value = ''
}

// ---- JSON 预览 ----
const showJsonDialog = ref(false)
const jsonPreview = computed(() => {
    if (!doneResult.value?.result_json) return ''
    return JSON.stringify(doneResult.value.result_json, null, 2)
})

// ---- 复制 Markdown ----
function handleCopyMarkdown() {
    if (!streamContent.value) return
    navigator.clipboard.writeText(streamContent.value).then(() => {
        ElMessage.success('已复制到剪贴板')
    }).catch(() => {
        ElMessage.error('复制失败，请手动选择文本复制')
    })
}

function isProductOrDevRole(result) {
    if (!result?.record_id) return false
    const role = result.role || result.task_type
    return role === 'product' || role === 'dev'
}
function isTestRole(result) {
    if (!result?.record_id) return false
    const role = result.role || result.task_type
    return role === 'test' || role === 'test_requirement_analysis'
}

async function handleDownloadWord() {
    if (!doneResult.value?.record_id) return
    downloadWordLoading.value = true
    try {
        const { data, filename } = await downloadAiRequirementTaskExport(doneResult.value.record_id, 'word')
        const url = URL.createObjectURL(new Blob([data]))
        const a = document.createElement('a')
        a.href = url
        a.download = filename
        a.click()
        URL.revokeObjectURL(url)
        ElMessage.success('Word 已开始下载')
    } catch (err) {
        const msg = err.response?.data?.error ?? err.message ?? '下载失败'
        ElMessage.error(typeof msg === 'string' ? msg : (msg.error || '下载失败'))
    } finally {
        downloadWordLoading.value = false
    }
}

async function handleDownloadXmind() {
    if (!doneResult.value?.record_id) return
    downloadXmindLoading.value = true
    try {
        const { data, filename } = await downloadAiRequirementTaskExport(doneResult.value.record_id, 'xmind')
        const url = URL.createObjectURL(new Blob([data]))
        const a = document.createElement('a')
        a.href = url
        a.download = filename
        a.click()
        URL.revokeObjectURL(url)
        ElMessage.success('XMind 已开始下载')
    } catch (err) {
        const msg = err.response?.data?.error ?? err.message ?? '下载失败'
        ElMessage.error(typeof msg === 'string' ? msg : (msg.error || '下载失败'))
    } finally {
        downloadXmindLoading.value = false
    }
}

// ---- 用户反馈 ----
const feedbackGiven = ref('')
const showFeedbackDialog = ref(false)
const feedbackForm = ref({ issueType: '', comment: '' })

function handleFeedback(rating) {
    if (rating === 'positive') {
        doSubmitFeedback(rating, '', '')
    } else {
        feedbackForm.value = { issueType: '', comment: '' }
        showFeedbackDialog.value = true
    }
}

async function submitFeedback() {
    showFeedbackDialog.value = false
    await doSubmitFeedback('negative', feedbackForm.value.issueType, feedbackForm.value.comment)
}

async function doSubmitFeedback(rating, issueType, comment) {
    if (!doneResult.value?.record_id) return
    try {
        await submitAiRequirementFeedback({
            task_id: doneResult.value.record_id,
            rating,
            issue_type: issueType || undefined,
            comment: comment || undefined,
        })
        feedbackGiven.value = rating
        ElMessage.success(rating === 'positive' ? '感谢你的肯定！' : '感谢反馈，我们会持续改进')
    } catch (err) {
        ElMessage.error('反馈提交失败')
    }
}

// ---- 辅助函数 ----
const getRoleLabel = (role) => ROLE_LABELS[role] || role
const getTaskLabel = (type) => TASK_LABELS[type] || type

function getStatusType(status) {
    return { pending: 'info', generating: 'warning', success: 'success', failed: 'danger' }[status] || 'info'
}

function getStatusText(status) {
    return { pending: '等待中', generating: '生成中', success: '成功', failed: '失败' }[status] || status
}

function formatTime(timeStr) {
    if (!timeStr) return ''
    const d = new Date(timeStr)
    return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

// ---- 多轮对话 ----
const chatVisible = ref(false)
const chatSessionId = ref('')
const chatMessages = ref([])
const chatInput = ref('')
const chatGenerating = ref(false)
const chatStreamContent = ref('')
const chatMessagesRef = ref(null)

function openChatPanel() {
    chatVisible.value = true
    if (!chatSessionId.value && doneResult.value?.session_id) {
        chatSessionId.value = doneResult.value.session_id
    }
    if (!chatSessionId.value) {
        chatSessionId.value = ''
    }
    if (chatMessages.value.length === 0 && doneResult.value) {
        chatMessages.value.push({
            role: 'user', content: form.value.requirement
        })
        const preview = streamContent.value || ''
        if (preview) {
            chatMessages.value.push({
                role: 'assistant', content: preview.slice(0, 2000) + (preview.length > 2000 ? '\n...(已截断)' : '')
            })
        }
    }
}

async function handleChatSend() {
    const msg = chatInput.value.trim()
    if (!msg || chatGenerating.value) return

    chatMessages.value.push({ role: 'user', content: msg })
    chatInput.value = ''
    chatGenerating.value = true
    chatStreamContent.value = ''

    nextTick(() => {
        if (chatMessagesRef.value) chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight
    })

    await aiRequirementChatStream(
        {
            session_id: chatSessionId.value,
            role: form.value.role,
            task_type: form.value.taskType,
            message: msg,
            use_thinking: form.value.useThinking,
        },
        (content) => {
            chatStreamContent.value += content
            nextTick(() => {
                if (chatMessagesRef.value) chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight
            })
        },
        (result) => {
            chatGenerating.value = false
            chatMessages.value.push({ role: 'assistant', content: chatStreamContent.value })
            chatStreamContent.value = ''
            if (result.session_id) chatSessionId.value = result.session_id
            if (result.result_json) {
                doneResult.value = {
                    ...doneResult.value,
                    record_id: result.record_id,
                    result_json: result.result_json,
                    confidence_score: result.confidence_score,
                    requires_clarification: result.requires_clarification,
                    usage: result.usage,
                }
            }
            loadHistory()
        },
        (error) => {
            chatGenerating.value = false
            chatStreamContent.value = ''
            ElMessage.error(`对话失败：${error}`)
        },
        (startData) => {
            if (startData.session_id) chatSessionId.value = startData.session_id
        }
    )
}

// ---- 深度模式 / 工作流 ----
const deepMode = ref(false)
const workflowActive = ref(false)
const workflowRunning = ref(false)
const workflowWaitingApproval = ref(false)
const workflowCompleted = ref(false)
const workflowId = ref(null)
const workflowActiveStep = ref(0)
const workflowTrace = ref([])
const workflowIteration = ref(0)
const workflowReviewScore = ref(null)
const workflowReviewFeedback = ref('')
const workflowPrdDraft = ref(null)
const workflowFinalPrd = ref(null)
const workflowError = ref('')
const showWorkflowResultDialog = ref(false)
const approvalComment = ref('')
const approvalSubmitting = ref(false)

const workflowStatusType = computed(() => {
    if (workflowCompleted.value) return 'success'
    if (workflowWaitingApproval.value) return 'warning'
    if (workflowRunning.value) return ''
    if (workflowError.value) return 'danger'
    return 'info'
})
const workflowStatusText = computed(() => {
    if (workflowCompleted.value) return '已完成'
    if (workflowWaitingApproval.value) return '待审批'
    if (workflowRunning.value) return '运行中'
    if (workflowError.value) return '出错'
    return '就绪'
})

const workflowFinalPrdText = computed(() => {
    if (!workflowFinalPrd.value) return ''
    return JSON.stringify(workflowFinalPrd.value, null, 2)
})

const NODE_INDEX_MAP = { research: 0, draft: 1, review: 2, human_approval: 3, waiting_approval: 3, finalize: 4, completed: 5 }

function workflowStepStatus(idx) {
    if (workflowActiveStep.value > idx) return 'success'
    if (workflowActiveStep.value === idx) {
        if (workflowWaitingApproval.value && idx === 3) return 'process'
        if (workflowRunning.value) return 'process'
        return 'process'
    }
    return 'wait'
}

function workflowStepIcon(idx) {
    if (workflowActiveStep.value === idx && workflowRunning.value) return undefined
    return undefined
}

async function handleStartWorkflow() {
    workflowActive.value = true
    workflowRunning.value = true
    workflowWaitingApproval.value = false
    workflowCompleted.value = false
    workflowActiveStep.value = 0
    workflowTrace.value = []
    workflowIteration.value = 0
    workflowReviewScore.value = null
    workflowReviewFeedback.value = ''
    workflowPrdDraft.value = null
    workflowFinalPrd.value = null
    workflowError.value = ''
    workflowId.value = null
    approvalComment.value = ''
    elapsedTime.value = 0
    timerInterval = setInterval(() => { elapsedTime.value++ }, 1000)

    await startWorkflowStream(
        {
            requirement_input: form.value.requirement.trim(),
            use_thinking: form.value.useThinking,
        },
        (event) => {
            handleWorkflowEvent(event)
        },
        (error) => {
            stopTimer()
            workflowRunning.value = false
            workflowError.value = error
            ElMessage.error(`工作流启动失败：${error}`)
        }
    )
}

function handleWorkflowEvent(event) {
    switch (event.type) {
        case 'workflow_start':
            workflowId.value = event.workflow_id
            break
        case 'node_done': {
            const nodeIdx = NODE_INDEX_MAP[event.current_node] ?? NODE_INDEX_MAP[event.node]
            if (nodeIdx != null) workflowActiveStep.value = nodeIdx

            if (event.iteration_count) workflowIteration.value = event.iteration_count
            if (event.review_score != null) workflowReviewScore.value = event.review_score

            const traceEntry = { node: event.node, elapsed_ms: event.elapsed_ms, tokens: event.tokens, status: 'done' }
            workflowTrace.value = [...workflowTrace.value, traceEntry]
            break
        }
        case 'workflow_pause':
            stopTimer()
            workflowRunning.value = false
            workflowWaitingApproval.value = true
            workflowPrdDraft.value = event.prd_draft
            workflowReviewFeedback.value = event.review_feedback || ''
            workflowError.value = event.message || ''
            workflowActiveStep.value = 3
            ElMessage.info('工作流等待人工审批')
            break
        case 'workflow_done':
            stopTimer()
            workflowRunning.value = false
            workflowWaitingApproval.value = false
            workflowCompleted.value = true
            workflowFinalPrd.value = event.final_prd
            workflowActiveStep.value = 4
            if (event.status === 'failed') {
                workflowError.value = event.error || '工作流执行失败'
                ElMessage.error(workflowError.value)
            } else {
                ElMessage.success('PRD 深度撰写完成')
            }
            loadHistory()
            break
        case 'approval_received':
            workflowWaitingApproval.value = false
            workflowRunning.value = true
            elapsedTime.value = 0
            timerInterval = setInterval(() => { elapsedTime.value++ }, 1000)
            break
        case 'error':
            stopTimer()
            workflowRunning.value = false
            workflowError.value = event.error || '未知错误'
            ElMessage.error(`工作流错误：${workflowError.value}`)
            break
    }
}

async function handleApproval(approved) {
    if (!workflowId.value) return
    approvalSubmitting.value = true

    await approveWorkflowStream(
        workflowId.value,
        {
            approved,
            comment: approvalComment.value,
        },
        (event) => {
            handleWorkflowEvent(event)
        },
        (error) => {
            approvalSubmitting.value = false
            ElMessage.error(`审批失败：${error}`)
        }
    )

    approvalSubmitting.value = false
}

// ---- 多智能体协作模式 ----
const multiAgentMode = ref(false)
const maActive = ref(false)
const maRunning = ref(false)
const maWaitingApproval = ref(false)
const maCompleted = ref(false)
const maWorkflowId = ref(null)
const maFinalOutput = ref(null)
const maApprovalComment = ref('')
const maApprovalSubmitting = ref(false)
const showMaResultDialog = ref(false)
const maSupervisorLog = ref([])
const maCompletedAgents = ref([])
const maCurrentAgent = ref('')
const maAgentOutputs = ref(null)
const maActiveStep = ref(0)

const MA_AGENTS = [
    { key: 'research', label: '竞品调研', icon: '🔍' },
    { key: 'pm', label: '产品经理', icon: '📋' },
    { key: 'architect', label: '架构师', icon: '🏗️' },
    { key: 'test', label: '测试分析师', icon: '🧪' },
]
const maAgentList = MA_AGENTS

const MA_LABEL_MAP = {
    research: '竞品调研', pm: '产品经理', architect: '架构师',
    test: '测试分析师', test_analyst: '测试分析师', human: '人工审核',
    supervisor: '协调中心', finalize: '汇总', done: '完成',
    prd: '产品经理', tech_design: '架构师',
}
function maAgentLabel(key) {
    return MA_LABEL_MAP[key] || key
}

const maStatusType = computed(() => {
    if (maCompleted.value) return 'success'
    if (maWaitingApproval.value) return 'warning'
    if (maRunning.value) return ''
    return 'info'
})
const maStatusText = computed(() => {
    if (maCompleted.value) return '已完成'
    if (maWaitingApproval.value) return '待审核'
    if (maRunning.value) return '运行中'
    return '就绪'
})

function maAgentStatus(key) {
    if (maCompletedAgents.value.includes(key)) return 'done'
    if (maCurrentAgent.value === key) return 'running'
    return 'waiting'
}

function maAgentCardClass(key) {
    const s = maAgentStatus(key)
    return { 'ma-agent-done': s === 'done', 'ma-agent-running': s === 'running' }
}

async function handleStartMultiAgent() {
    maActive.value = true
    maRunning.value = true
    maWaitingApproval.value = false
    maCompleted.value = false
    maActiveStep.value = 0
    maWorkflowId.value = null
    maFinalOutput.value = null
    maSupervisorLog.value = []
    maCompletedAgents.value = []
    maCurrentAgent.value = ''
    maAgentOutputs.value = null
    maApprovalComment.value = ''
    elapsedTime.value = 0
    timerInterval = setInterval(() => { elapsedTime.value++ }, 1000)

    await startMultiAgentStream(
        {
            requirement_input: form.value.requirement.trim(),
            use_thinking: form.value.useThinking,
        },
        (event) => { handleMultiAgentEvent(event) },
        (error) => {
            stopTimer()
            maRunning.value = false
            ElMessage.error(`多智能体启动失败：${error}`)
        }
    )
}

function handleMultiAgentEvent(event) {
    switch (event.type) {
        case 'workflow_start':
            maWorkflowId.value = event.workflow_id
            maActiveStep.value = 0
            break
        case 'agent_done': {
            const agent = event.agent
            if (maActiveStep.value < 1) maActiveStep.value = 1
            if (agent === 'supervisor' && event.supervisor_decision) {
                maSupervisorLog.value = [...maSupervisorLog.value, {
                    decision: event.supervisor_decision,
                    reason: event.supervisor_reasoning || '',
                }]
                maCurrentAgent.value = event.supervisor_decision
            } else if (agent !== 'supervisor' && agent !== 'finalize') {
                if (!maCompletedAgents.value.includes(agent)) {
                    maCompletedAgents.value = [...maCompletedAgents.value, agent]
                }
                maCurrentAgent.value = ''
            }
            break
        }
        case 'workflow_pause':
            stopTimer()
            maRunning.value = false
            maWaitingApproval.value = true
            maActiveStep.value = 2
            if (event.agents_completed) {
                maCompletedAgents.value = event.agents_completed
            }
            if (event.agents_outputs) maAgentOutputs.value = event.agents_outputs
            ElMessage.info('多智能体分析完毕，请审核')
            break
        case 'workflow_done':
            stopTimer()
            maRunning.value = false
            maWaitingApproval.value = false
            maCompleted.value = true
            maActiveStep.value = 3
            maFinalOutput.value = event.final_output
            if (event.status === 'failed') {
                ElMessage.error(event.error || '协作失败')
            } else {
                ElMessage.success('多智能体协作分析完成')
            }
            loadHistory()
            break
        case 'approval_received':
            maWaitingApproval.value = false
            maRunning.value = true
            maActiveStep.value = 1
            elapsedTime.value = 0
            timerInterval = setInterval(() => { elapsedTime.value++ }, 1000)
            break
        case 'error':
            stopTimer()
            maRunning.value = false
            ElMessage.error(`多智能体错误：${event.error || ''}`)
            break
    }
}

async function handleMultiAgentApproval(approved) {
    if (!maWorkflowId.value) return
    maApprovalSubmitting.value = true

    await approveMultiAgentStream(
        maWorkflowId.value,
        { approved, comment: maApprovalComment.value },
        (event) => { handleMultiAgentEvent(event) },
        (error) => {
            maApprovalSubmitting.value = false
            ElMessage.error(`审核失败：${error}`)
        }
    )
    maApprovalSubmitting.value = false
}

// ---- 功能点 → 用例智能体跳转 ----
const bridging = ref(false)

// ---- P2-3：Jira / Confluence 同步 ----
const syncingJira = ref(false)
const syncingConfluence = ref(false)
const downloadWordLoading = ref(false)
const downloadXmindLoading = ref(false)

function hasPrdContent(r) {
    if (!r) return false
    if (r.result_md && r.result_md.trim()) return true
    if (r.result_json && r.result_json.markdown_full && r.result_json.markdown_full.trim()) return true
    return false
}

async function handleSyncToJira() {
    if (!doneResult.value?.record_id) return
    syncingJira.value = true
    try {
        const res = await aiRequirementSyncToJira({ task_id: doneResult.value.record_id })
        if (res.success) {
            const n = (res.created || []).length
            ElMessage.success(n ? `已创建 ${n} 个 Jira 工单` : '同步完成')
        } else {
            ElMessage.error(res.error || '同步到 Jira 失败')
        }
    } catch (err) {
        ElMessage.error('同步失败：' + (err.response?.data?.error || err.message || '未知错误'))
    } finally {
        syncingJira.value = false
    }
}

async function handleSyncToConfluence() {
    if (!doneResult.value?.record_id) return
    syncingConfluence.value = true
    try {
        const res = await aiRequirementSyncToConfluence({ task_id: doneResult.value.record_id })
        if (res.success) {
            ElMessage.success('已写入 Confluence')
            if (res.url) window.open(res.url, '_blank')
        } else {
            ElMessage.error(res.error || '写入 Confluence 失败')
        }
    } catch (err) {
        ElMessage.error('写入失败：' + (err.response?.data?.error || err.message || '未知错误'))
    } finally {
        syncingConfluence.value = false
    }
}

async function handleBridgeToTestcase() {
    if (!doneResult.value?.record_id) return
    bridging.value = true
    try {
        const res = await bridgeToTestcase({ task_id: doneResult.value.record_id })
        if (res.status !== 'ok') return
        sessionStorage.setItem('ai_req_bridge_text', res.requirement_text || '')
        sessionStorage.setItem('ai_req_bridge_source', String(res.source_task_id || ''))
        ElMessage.success('已提取需求文本，正在跳转用例页…')
        vueRouter.push({ name: 'AiTestcaseGenerator' })
    } catch (err) {
        ElMessage.error('桥接失败：' + (err.message || '未知错误'))
    } finally {
        bridging.value = false
    }
}

// ---- 生命周期 ----
onMounted(() => { loadHistory() })
onUnmounted(() => { stopTimer() })
</script>

<style scoped>
.ai-req-container {
    padding: 20px;
}

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

/* 输入卡片 */
.input-card,
.stream-card,
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

/* 角色/任务选择器 */
.selector-row {
    display: flex;
    gap: 24px;
    align-items: center;
    flex-wrap: wrap;
}

.selector-item {
    display: flex;
    align-items: center;
    gap: 8px;
}

.selector-label {
    font-size: 14px;
    font-weight: 500;
    color: #606266;
    white-space: nowrap;
}

/* 文件上传 */
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

/* 提交区 */
.input-actions {
    margin-top: 16px;
    display: flex;
    align-items: center;
    gap: 12px;
}

.options-right {
    margin-left: auto;
}

.generating-timer {
    font-size: 13px;
    color: #909399;
    margin-left: 4px;
}

/* 流式输出：保留最小高度，生成中时占位可见 */
.stream-output {
    min-height: 120px;
    max-height: 450px;
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

.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes typingBounce {
    0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
    40% { opacity: 1; transform: scale(1); }
}

.stream-output::-webkit-scrollbar { width: 4px; }
.stream-output::-webkit-scrollbar-thumb { background: #dcdfe6; border-radius: 2px; }

/* 结果操作 */
.result-stats {
    margin-left: auto;
    display: flex;
    gap: 8px;
}

.clarify-section {
    margin-top: 16px;
    padding: 16px;
    background: #fdf6ec;
    border: 1px solid #e6a23c;
    border-radius: 8px;
}
.clarify-title {
    font-weight: 600;
    color: #e6a23c;
    margin-bottom: 12px;
}
.clarify-row {
    margin-bottom: 12px;
}
.clarify-row .clarify-q {
    display: block;
    margin-bottom: 4px;
    color: #606266;
    font-size: 13px;
}
.clarify-section .el-button {
    margin-top: 8px;
}
.result-actions {
    display: flex;
    gap: 12px;
    align-items: center;
    padding-top: 12px;
    border-top: 1px solid #e4e7ed;
}

.feedback-group {
    margin-left: auto;
    display: flex;
    gap: 4px;
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
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;
    flex-wrap: wrap;
}

.history-tags {
    display: flex;
    gap: 4px;
}

.history-time {
    font-size: 12px;
    color: #909399;
    margin-left: auto;
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
    flex-wrap: wrap;
}

.history-meta span {
    display: flex;
    align-items: center;
    gap: 4px;
}

.history-actions {
    margin-top: 8px;
}

.history-pagination {
    margin-top: 16px;
    display: flex;
    justify-content: center;
}

.empty-history {
    padding: 40px 0;
}

/* JSON 预览 */
.json-preview :deep(.el-textarea__inner) {
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 13px;
    line-height: 1.6;
}

/* 多轮对话面板 */
.chat-card {
    margin-bottom: 20px;
}

.chat-messages {
    max-height: 350px;
    overflow-y: auto;
    padding: 8px 0;
    margin-bottom: 12px;
    border: 1px solid #e4e7ed;
    border-radius: 6px;
    background: #fafafa;
}

.chat-msg {
    padding: 8px 16px;
    margin-bottom: 4px;
}

.chat-msg.user {
    background: #ecf5ff;
}

.chat-msg.assistant {
    background: #f0f9eb;
}

.chat-msg-label {
    font-size: 11px;
    font-weight: 600;
    color: #909399;
    margin-bottom: 2px;
}

.chat-msg-content {
    margin: 0;
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-all;
    color: #303133;
}

.typing-cursor {
    animation: cursorBlink 0.8s infinite;
}

@keyframes cursorBlink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
}

.chat-input-row {
    display: flex;
    flex-direction: column;
}

.chat-messages::-webkit-scrollbar { width: 4px; }
.chat-messages::-webkit-scrollbar-thumb { background: #dcdfe6; border-radius: 2px; }

/* 滚动条 */
.history-list::-webkit-scrollbar { width: 4px; }
.history-list::-webkit-scrollbar-thumb { background: #dcdfe6; border-radius: 2px; }

/* 工作流面板 */
.workflow-card {
    margin-bottom: 20px;
}

.workflow-preview-hint {
    padding: 12px 16px;
    margin-bottom: 16px;
    background: #f4f4f5;
    border-radius: 8px;
    color: #606266;
    font-size: 13px;
}
.workflow-current-step-label {
    font-size: 12px;
    color: #909399;
    margin-bottom: 8px;
}
.workflow-steps {
    padding: 16px 0;
}
.step-wait-action {
    color: #e6a23c;
    font-size: 12px;
}
.ma-steps-row {
    padding: 12px 0 20px;
    border-bottom: 1px solid #ebeef5;
    margin-bottom: 16px;
}

.approval-panel {
    margin-top: 20px;
    padding: 16px;
    background: #fdf6ec;
    border-radius: 8px;
    border: 1px solid #f5dab1;
}

.approval-prd-preview {
    margin-bottom: 12px;
}

.prd-preview-text {
    margin: 0;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 12px;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 300px;
    overflow-y: auto;
    color: #606266;
}

.review-feedback-box {
    margin-bottom: 12px;
    padding: 8px 12px;
    background: #fff7e6;
    border-radius: 4px;
    font-size: 13px;
}

.approval-actions {
    display: flex;
    flex-direction: column;
    gap: 0;
}

.approval-actions .el-button + .el-button {
    margin-left: 12px;
}

.approval-actions > div:last-child {
    display: flex;
    gap: 12px;
}

.workflow-result {
    margin-top: 16px;
    text-align: center;
}

/* 多智能体面板 */
.multi-agent-card {
    margin-bottom: 20px;
}

.ma-agents-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 20px;
}

.ma-agent-card {
    text-align: center;
    padding: 16px 8px;
    border-radius: 8px;
    border: 2px solid #e4e7ed;
    background: #fafafa;
    transition: all 0.3s;
}

.ma-agent-card.ma-agent-running {
    border-color: #409eff;
    background: #ecf5ff;
    box-shadow: 0 0 8px rgba(64, 158, 255, 0.3);
}

.ma-agent-card.ma-agent-done {
    border-color: #67c23a;
    background: #f0f9eb;
}

.ma-agent-icon {
    font-size: 28px;
    margin-bottom: 6px;
}

.ma-agent-name {
    font-size: 13px;
    font-weight: 600;
    color: #303133;
    margin-bottom: 6px;
}

.ma-supervisor-log {
    margin-top: 16px;
    padding: 12px;
    background: #f5f7fa;
    border-radius: 6px;
    max-height: 200px;
    overflow-y: auto;
}

.ma-supervisor-title {
    font-size: 13px;
    font-weight: 600;
    color: #606266;
    margin-bottom: 8px;
}

.ma-log-item {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
    font-size: 12px;
}

.ma-log-decision {
    font-weight: 600;
    color: #409eff;
}

.ma-log-reason {
    color: #909399;
}
</style>
