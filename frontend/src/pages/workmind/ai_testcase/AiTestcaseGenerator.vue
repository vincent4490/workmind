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
                            <div style="margin-left: auto; display: flex; align-items: center; gap: 16px;">
                                <el-switch
                                    v-model="useAgentMode"
                                    active-text="Agent 生成"
                                    inactive-text=""
                                    :disabled="generating"
                                />
                                <el-switch
                                    v-model="useThinking"
                                    active-text="思考模式"
                                    inactive-text=""
                                />
                            </div>
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
                                    .docx / .pdf / .txt / .md / .png / .jpg / .webp，单文件最大 100MB，最多 10 个
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

                    <!-- 生成模式选择 -->
                    <div class="mode-selection">
                        <div class="mode-label">
                            <el-icon><Setting /></el-icon>
                            <span>生成模式</span>
                        </div>
                        <el-radio-group v-model="generationMode" class="mode-radio-group">
                            <el-radio value="comprehensive" class="mode-radio">
                                <div class="mode-content">
                                    <span class="mode-title">全覆盖模式</span>
                                    <span class="mode-desc">（覆盖更全，条数更多；适合新功能验收/高复杂需求）</span>
                                </div>
                            </el-radio>
                            <el-radio value="focused" class="mode-radio">
                                <div class="mode-content">
                                    <span class="mode-title">聚焦模式</span>
                                    <span class="mode-desc">（聚焦业务和功能；适合日常迭代）</span>
                                </div>
                            </el-radio>
                        </el-radio-group>
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
                            {{ generating ? '正在生成中...' : (useAgentMode ? 'Agent 智能生成' : '智能生成用例') }}
                        </el-button>
                        <el-button size="large" @click="handleClear" :disabled="generating">
                            清空
                        </el-button>
                        <span v-if="generating" class="generating-timer">
                            已耗时 {{ elapsedTime }}s
                        </span>
                    </div>
                </el-card>

                <!-- Agent 进度面板 -->
                <el-card v-if="agentProgress.active" class="agent-progress-card" shadow="hover">
                    <template #header>
                        <div class="card-header">
                            <span class="card-title">
                                <el-icon><Setting /></el-icon>
                                Agent 工作流进度
                            </span>
                            <span v-if="agentProgress.review" class="agent-score-badge" :class="agentProgress.review.score >= 0.8 ? 'score-pass' : 'score-fail'">
                                评审分数: {{ (agentProgress.review.score * 100).toFixed(0) }}分
                            </span>
                        </div>
                    </template>
                    <el-steps :active="agentProgress.currentIndex" finish-status="success" align-center>
                        <el-step title="需求分析" />
                        <el-step title="策略规划" />
                        <el-step title="分模块生成" />
                        <el-step title="评审打分" />
                        <el-step title="完成" />
                    </el-steps>

                    <!-- 步骤 1：需求分析结果 -->
                    <div v-if="agentProgress.analysisData" class="agent-step-content">
                        <div class="step-section-title">识别到 {{ agentProgress.analysisData.modules?.length || 0 }} 个模块</div>
                        <div class="module-tags">
                            <el-tag
                                v-for="mod in agentProgress.analysisData.modules"
                                :key="mod.name"
                                :type="{ simple: 'success', medium: '', complex: 'warning', critical: 'danger' }[mod.complexity] || ''"
                                effect="light"
                                class="module-tag"
                            >
                                {{ mod.name }}
                                <span class="complexity-label">{{ { simple: '简单', medium: '中等', complex: '复杂', critical: '关键' }[mod.complexity] || mod.complexity }}</span>
                            </el-tag>
                        </div>
                        <div v-if="agentProgress.analysisData.global_rules?.length" class="step-rules">
                            <span class="rules-label">全局规则：</span>
                            <span v-for="(rule, i) in agentProgress.analysisData.global_rules" :key="i" class="rule-item">{{ rule }}</span>
                        </div>
                    </div>

                    <!-- 步骤 2：策略规划结果 -->
                    <div v-if="agentProgress.strategyData" class="agent-step-content">
                        <div class="step-section-title">测试策略</div>
                        <el-table :data="agentProgress.strategyData.strategies" size="small" stripe class="strategy-table">
                            <el-table-column prop="module_name" label="模块" width="120" />
                            <el-table-column label="测试方法">
                                <template #default="{ row }">
                                    <el-tag v-for="m in row.methods" :key="m" size="small" type="info" class="method-tag">{{ m }}</el-tag>
                                </template>
                            </el-table-column>
                            <el-table-column label="用例预算" width="110">
                                <template #default="{ row }">
                                    {{ formatCaseBudget(row) }}
                                </template>
                            </el-table-column>
                            <el-table-column prop="special_focus" label="重点关注" show-overflow-tooltip />
                        </el-table>
                    </div>

                    <!-- 步骤 3：分模块生成进度 -->
                    <div v-if="agentProgress.moduleProgress.length > 0" class="agent-step-content">
                        <div class="step-section-title">
                            已生成 {{ agentProgress.moduleProgress.length }} 个模块
                            <span class="step-section-sub">
                                （共 {{ agentProgress.moduleProgress.reduce((s, m) => s + m.caseCount, 0) }} 条用例）
                            </span>
                        </div>
                        <div class="module-progress-list">
                            <div v-for="(mp, i) in agentProgress.moduleProgress" :key="i" class="module-progress-item">
                                <el-icon class="module-done-icon"><CircleCheck /></el-icon>
                                <span class="module-progress-name">{{ mp.name }}</span>
                                <span class="module-progress-stats">{{ mp.functionCount }} 个功能点 · {{ mp.caseCount }} 条用例</span>
                            </div>
                        </div>
                    </div>

                    <!-- 步骤 4：评审结果 -->
                    <div v-if="agentProgress.review" class="agent-step-content">
                        <div class="step-section-title">评审结果</div>
                        <div class="agent-review-info">
                            <div class="review-detail">
                                <span class="review-label">总体评价：</span>
                                <span>{{ agentProgress.review.feedback || '无' }}</span>
                            </div>
                            <div class="review-detail">
                                <span class="review-label">迭代轮次：</span>
                                <span>{{ agentProgress.review.iteration }} / {{ agentProgress.review.max }}</span>
                            </div>
                            <div v-if="agentProgress.reviewIssues.length > 0" class="review-issues-list">
                                <div v-for="(issue, i) in agentProgress.reviewIssues.slice(0, 5)" :key="i" class="review-issue-item">
                                    <el-tag :type="{ high: 'danger', medium: 'warning', low: 'info' }[issue.severity] || 'info'" size="small">
                                        {{ issue.severity === 'high' ? '严重' : issue.severity === 'medium' ? '中等' : '轻微' }}
                                    </el-tag>
                                    <span class="issue-desc">{{ issue.description }}</span>
                                </div>
                                <div v-if="agentProgress.reviewIssues.length > 5" class="review-issues-more">
                                    ...还有 {{ agentProgress.reviewIssues.length - 5 }} 条
                                </div>
                            </div>
                            <div v-if="agentProgress.refining" class="review-detail refining-hint">
                                <el-icon class="is-loading"><Refresh /></el-icon>
                                <span>正在根据评审意见修订用例...</span>
                            </div>
                        </div>
                    </div>
                </el-card>

                <!-- Agent 活动日志面板 -->
                <el-card v-if="agentProgress.active && agentLog.length > 0" class="agent-log-card" shadow="hover">
                    <template #header>
                        <div class="card-header">
                            <span class="card-title">
                                <el-icon><Document /></el-icon>
                                执行日志
                            </span>
                            <span class="log-count">{{ agentLog.length }} 条</span>
                        </div>
                    </template>
                    <div ref="agentLogRef" class="agent-log-container">
                        <div v-for="(entry, i) in agentLog" :key="i" class="agent-log-entry" :class="'log-' + entry.level">
                            <span class="log-time">{{ entry.time }}</span>
                            <span class="log-icon">{{ entry.icon }}</span>
                            <span class="log-text">{{ entry.text }}</span>
                            <span v-if="entry.duration" class="log-duration">({{ entry.duration }})</span>
                        </div>
                        <div v-if="generating && !agentProgress.review" class="agent-log-entry log-running">
                            <span class="log-time">{{ currentTimeStr }}</span>
                            <span class="log-icon">⏳</span>
                            <span class="log-text log-blink">{{ agentProgress.currentNode || '处理中' }}...</span>
                        </div>
                    </div>
                </el-card>

                <!-- 流式输出面板（直接生成模式） -->
                <el-card v-if="(streamContent || generating) && !agentProgress.active" class="stream-card" shadow="hover">
                    <template #header>
                        <div class="card-header card-header-result">
                            <span class="card-title">
                                <el-icon><Document /></el-icon>
                                {{ generating ? 'AI 正在生成...' : '生成结果' }}
                            </span>
                            <div v-if="currentResult" class="result-tree-toolbar result-tree-toolbar--header">
                                <el-select
                                    v-model="filterModule"
                                    placeholder="全部模块"
                                    clearable
                                    filterable
                                    size="small"
                                    class="result-filter-select"
                                >
                                    <el-option
                                        v-for="name in moduleOptions"
                                        :key="name"
                                        :label="name"
                                        :value="name"
                                    />
                                </el-select>
                                <el-select
                                    v-model="filterFunction"
                                    placeholder="全部功能"
                                    clearable
                                    filterable
                                    size="small"
                                    class="result-filter-select"
                                >
                                    <el-option
                                        v-for="name in functionOptions"
                                        :key="name"
                                        :label="name"
                                        :value="name"
                                    />
                                </el-select>
                                <el-button
                                    text
                                    type="primary"
                                    size="small"
                                    @click="showCaseDetails = !showCaseDetails"
                                >
                                    {{ showCaseDetails ? '收起详情' : '展开详情' }}
                                </el-button>
                            </div>
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
                            :data="displayTreeData"
                            :props="treeProps"
                            default-expand-all
                            :expand-on-click-node="false"
                        >
                            <template #default="{ node, data }">
                                <span class="tree-node" :class="{ 'tree-node-case': data.nodeType === 'case' }">
                                    <div class="tree-node-row" :class="{ 'tree-node-row-case': data.nodeType === 'case' }">
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
                                            v-if="data.nodeType === 'case' && currentResult?.id"
                                            class="case-edit-btn"
                                            link type="primary" size="small"
                                            @click.stop="openCaseEditDialog(data)"
                                        >
                                            <el-icon><EditPen /></el-icon>
                                            编辑
                                        </el-button>
                                        <el-button
                                            v-if="data.nodeType === 'module' && !regenerating"
                                            class="module-adjust-btn"
                                            text type="warning" size="small"
                                            @click.stop="openRegenerateDialog(data.label)"
                                        >
                                            <el-icon><EditPen /></el-icon>
                                            调整
                                        </el-button>
                                        <el-button
                                            v-if="data.nodeType === 'function' && !regenerating && !regeneratingFunction"
                                            class="function-adjust-btn"
                                            text type="warning" size="small"
                                            @click.stop="openRegenerateFunctionDialog(getModuleNameForNode(node), data.label)"
                                        >
                                            <el-icon><EditPen /></el-icon>
                                            调整
                                        </el-button>
                                    </div>
                                    <!-- 用例同一层：标题后直接跟前置条件、测试步骤、预期结果，不增加树层级 -->
                                    <div
                                        v-if="showCaseDetails && data.nodeType === 'case' && (data.precondition || data.steps || data.expected)"
                                        class="tree-case-inline"
                                    >
                                        <span v-if="data.precondition" class="case-inline-item"><em>前置条件：</em>{{ data.precondition }}</span>
                                        <span v-if="data.steps" class="case-inline-item"><em>测试步骤：</em><span class="case-inline-steps">{{ data.steps }}</span></span>
                                        <span v-if="data.expected" class="case-inline-item"><em>预期结果：</em>{{ data.expected }}</span>
                                    </div>
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
                        <div class="card-header card-header-result">
                            <span class="card-title">
                                <el-icon><Document /></el-icon>
                                生成结果
                            </span>
                            <div class="result-tree-toolbar result-tree-toolbar--header">
                                <el-select
                                    v-model="filterModule"
                                    placeholder="全部模块"
                                    clearable
                                    filterable
                                    size="small"
                                    class="result-filter-select"
                                >
                                    <el-option
                                        v-for="name in moduleOptions"
                                        :key="name"
                                        :label="name"
                                        :value="name"
                                    />
                                </el-select>
                                <el-select
                                    v-model="filterFunction"
                                    placeholder="全部功能"
                                    clearable
                                    filterable
                                    size="small"
                                    class="result-filter-select"
                                >
                                    <el-option
                                        v-for="name in functionOptions"
                                        :key="name"
                                        :label="name"
                                        :value="name"
                                    />
                                </el-select>
                                <el-button
                                    text
                                    type="primary"
                                    size="small"
                                    @click="showCaseDetails = !showCaseDetails"
                                >
                                    {{ showCaseDetails ? '收起详情' : '展开详情' }}
                                </el-button>
                            </div>
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
                            :data="displayTreeData"
                            :props="treeProps"
                            default-expand-all
                            :expand-on-click-node="false"
                        >
                            <template #default="{ node, data }">
                                <span class="tree-node" :class="{ 'tree-node-case': data.nodeType === 'case' }">
                                    <div class="tree-node-row" :class="{ 'tree-node-row-case': data.nodeType === 'case' }">
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
                                            v-if="data.nodeType === 'case' && currentResult?.id"
                                            class="case-edit-btn"
                                            link type="primary" size="small"
                                            @click.stop="openCaseEditDialog(data)"
                                        >
                                            <el-icon><EditPen /></el-icon>
                                            编辑
                                        </el-button>
                                        <el-button
                                            v-if="data.nodeType === 'module' && !regenerating"
                                            class="module-adjust-btn"
                                            text type="warning" size="small"
                                            @click.stop="openRegenerateDialog(data.label)"
                                        >
                                            <el-icon><EditPen /></el-icon>
                                            调整
                                        </el-button>
                                        <el-button
                                            v-if="data.nodeType === 'function' && !regenerating && !regeneratingFunction"
                                            class="function-adjust-btn"
                                            text type="warning" size="small"
                                            @click.stop="openRegenerateFunctionDialog(getModuleNameForNode(node), data.label)"
                                        >
                                            <el-icon><EditPen /></el-icon>
                                            调整
                                        </el-button>
                                    </div>
                                    <div
                                        v-if="showCaseDetails && data.nodeType === 'case' && (data.precondition || data.steps || data.expected)"
                                        class="tree-case-inline"
                                    >
                                        <span v-if="data.precondition" class="case-inline-item"><em>前置条件：</em>{{ data.precondition }}</span>
                                        <span v-if="data.steps" class="case-inline-item"><em>测试步骤：</em><span class="case-inline-steps">{{ data.steps }}</span></span>
                                        <span v-if="data.expected" class="case-inline-item"><em>预期结果：</em>{{ data.expected }}</span>
                                    </div>
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
                        <div class="card-header history-card-header">
                            <span class="card-title">
                                <el-icon><Clock /></el-icon>
                                生成历史
                            </span>
                            <div class="history-card-header-right">
                                <el-select
                                    v-if="configStatus.can_filter_by_creator"
                                    v-model="historyCreatorFilter"
                                    clearable
                                    filterable
                                    placeholder="按创建人筛选"
                                    class="history-creator-filter"
                                    size="small"
                                    @change="onHistoryCreatorFilterChange"
                                >
                                    <el-option
                                        v-for="u in creatorUserList"
                                        :key="u.id"
                                        :label="formatCreatorOptionLabel(u)"
                                        :value="u.id"
                                    />
                                </el-select>
                                <el-button text type="primary" @click="loadHistory">
                                    <el-icon><Refresh /></el-icon>
                                    刷新
                                </el-button>
                            </div>
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
                            <div
                                v-if="item.created_by_username"
                                class="history-creator"
                            >
                                <el-icon><User /></el-icon>
                                {{ item.created_by_username }}
                            </div>
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

        <!-- 功能点调整弹窗 -->
        <el-dialog
            v-model="showRegenerateFunctionDialog"
            :title="`调整功能点用例 — 模块「${regenerateFunctionModuleName}」- 功能「${regenerateFunctionName}」`"
            width="800px"
            :close-on-click-modal="!regeneratingFunction"
            :close-on-press-escape="!regeneratingFunction"
            @close="handleRegenerateFunctionDialogClose"
        >
            <div v-if="!regeneratingFunction && !regenerateFunctionStreamContent" class="regenerate-form">
                <p class="regenerate-hint">
                    AI 将根据以下信息重新生成该功能点的用例，其他功能点不受影响。两项至少填写一项。
                </p>
                <div class="regenerate-field">
                    <div class="regenerate-field-label">
                        <span>补充功能点需求</span>
                        <el-tag size="small" type="info">可选</el-tag>
                    </div>
                    <el-input
                        v-model="regenerateFunctionRequirement"
                        type="textarea"
                        :rows="6"
                        placeholder="补充该功能点更细节的业务规则、验收要点等..."
                        maxlength="20000"
                        show-word-limit
                    />
                </div>
                <div class="regenerate-field">
                    <div class="regenerate-field-label">
                        <span>调整意见</span>
                        <el-tag size="small" type="info">可选</el-tag>
                    </div>
                    <el-input
                        v-model="regenerateFunctionAdjustment"
                        type="textarea"
                        :rows="4"
                        placeholder="对已有用例的改进要求，如：补充更多异常场景、步骤要更详细..."
                        maxlength="2000"
                        show-word-limit
                    />
                </div>
                <div class="regenerate-options">
                    <el-switch v-model="regenerateFunctionUseThinking" active-text="思考模式" inactive-text="" />
                </div>
            </div>
            <div v-if="regeneratingFunction || regenerateFunctionStreamContent" class="regenerate-stream">
                <div class="regenerate-stream-header">
                    <span v-if="regeneratingFunction" class="regenerate-status">
                        <span class="typing-dot"></span>
                        <span class="typing-dot"></span>
                        <span class="typing-dot"></span>
                        <span style="margin-left: 8px;">AI 正在重新生成「{{ regenerateFunctionName }}」功能点...</span>
                        <span class="generating-timer">{{ regenerateFunctionElapsedTime }}s</span>
                    </span>
                    <span v-else class="regenerate-status regenerate-done">
                        <el-icon><CircleCheck /></el-icon>
                        功能点「{{ regenerateFunctionName }}」已更新
                    </span>
                </div>
                <div class="stream-output regenerate-output" ref="regenerateFunctionStreamRef">
                    <pre class="stream-text">{{ regenerateFunctionStreamContent }}</pre>
                </div>
            </div>
            <template #footer>
                <div class="regenerate-footer">
                    <el-button @click="showRegenerateFunctionDialog = false" :disabled="regeneratingFunction">
                        {{ regenerateFunctionStreamContent && !regeneratingFunction ? '关闭' : '取消' }}
                    </el-button>
                    <el-button
                        v-if="!regenerateFunctionStreamContent || regeneratingFunction"
                        type="primary"
                        :loading="regeneratingFunction"
                        :disabled="!canSubmitRegenerateFunction"
                        @click="handleRegenerateFunction"
                    >
                        {{ regeneratingFunction ? '正在重新生成...' : '开始重新生成' }}
                    </el-button>
                </div>
            </template>
        </el-dialog>

        <!-- 用例编辑弹窗（编辑整条用例：标题、前置条件、测试步骤、预期结果） -->
        <el-dialog
            v-model="showCaseEditDialog"
            title="编辑用例"
            width="640px"
            :close-on-click-modal="!savingCaseEdit"
            @close="showCaseEditDialog = false"
        >
            <el-form label-width="90px" label-position="top">
                <el-form-item label="用例标题">
                    <el-input v-model="caseEditForm.name" placeholder="用例名称" maxlength="500" show-word-limit />
                </el-form-item>
                <el-form-item label="优先级">
                    <el-select v-model="caseEditForm.priority" placeholder="P0/P1/P2" style="width: 120px">
                        <el-option label="P0" value="P0" />
                        <el-option label="P1" value="P1" />
                        <el-option label="P2" value="P2" />
                    </el-select>
                </el-form-item>
                <el-form-item label="前置条件">
                    <el-input v-model="caseEditForm.precondition" type="textarea" :rows="3" placeholder="前置条件" maxlength="2000" show-word-limit />
                </el-form-item>
                <el-form-item label="测试步骤">
                    <el-input v-model="caseEditForm.steps" type="textarea" :rows="5" placeholder="1. 步骤一&#10;2. 步骤二" maxlength="5000" show-word-limit />
                </el-form-item>
                <el-form-item label="预期结果">
                    <el-input v-model="caseEditForm.expected" type="textarea" :rows="3" placeholder="预期结果" maxlength="2000" show-word-limit />
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="showCaseEditDialog = false" :disabled="savingCaseEdit">取消</el-button>
                <el-button type="primary" :loading="savingCaseEdit" @click="saveCaseEdit">保存</el-button>
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
                            AI 将分 4 个维度逐一深入扫描所有用例：重复、冗余、归属、缺失场景。
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
                                （{{ reviewCurrentDim?.index || 0 }}/{{ reviewCurrentDim?.total || reviewDimensions.length || 4 }}）
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
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
    Edit, MagicStick, Document, Download, View,
    Clock, Refresh, Delete, Folder, UploadFilled, Paperclip,
    EditPen, CircleCheck, Search, Select, Warning, Setting, User
} from '@element-plus/icons-vue'
import {
    startAiTestcaseGeneration,
    streamAiTestcaseEvents,
    aiRegenerateModuleStream,
    aiRegenerateFunctionStream,
    aiUpdateCase,
    aiReviewTestcaseStream,
    aiApplyReviewStream,
    getAiTestcaseGenerations,
    deleteAiTestcaseGeneration,
    previewAiTestcase,
    downloadAiTestcaseXmind,
    getAiTestcaseConfigStatus,
    getUserList
} from '@/restful/api'
import { formatCreatorOptionLabel } from '@/utils/creatorLabel.js'

const route = useRoute()
const router = useRouter()

// 状态
const requirement = ref('')
const useThinking = ref(false)
const generationMode = ref('comprehensive')  // 新增：生成模式
const useAgentMode = ref(false)
const generating = ref(false)

// Agent 进度状态
const agentProgress = ref({
    active: false,
    nodes: [],
    currentNode: '',
    currentIndex: 0,
    totalNodes: 0,
    review: null,
    refining: false,
    analysisData: null,
    strategyData: null,
    moduleProgress: [],
    reviewIssues: [],
})
const currentResult = ref(null)
const configStatus = ref({
    configured: false,
    model: '',
    base_url: '',
    api_key_prefix: '',
    can_filter_by_creator: false
})

// 文件上传
const uploadRef = ref(null)
const fileList = ref([])
const fileWarnings = ref([])

// 流式输出
const streamContent = ref('')
const streamOutputRef = ref(null)

// Agent 活动日志
const agentLog = ref([])
const agentLogRef = ref(null)

// 计时器
const elapsedTime = ref(0)
let timerInterval = null

// 历史记录
const historyList = ref([])
const historyPage = ref(1)
const historyTotal = ref(0)
const historyCreatorFilter = ref(null)
const creatorUserList = ref([])

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

// 功能点调整
const showRegenerateFunctionDialog = ref(false)
const regenerateFunctionModuleName = ref('')
const regenerateFunctionName = ref('')
const regenerateFunctionRequirement = ref('')
const regenerateFunctionAdjustment = ref('')
const regenerateFunctionUseThinking = ref(false)
const regeneratingFunction = ref(false)
const regenerateFunctionStreamContent = ref('')
const regenerateFunctionStreamRef = ref(null)
const regenerateFunctionElapsedTime = ref(0)
let regenerateFunctionTimerInterval = null

// 用例编辑（悬停编辑按钮 → 弹窗编辑整条用例）
const showCaseEditDialog = ref(false)
const caseEditForm = ref({
    name: '',
    priority: 'P1',
    precondition: '',
    steps: '',
    expected: ''
})
const caseEditMeta = ref({ moduleName: '', functionName: '', caseIndex: 0 })
const savingCaseEdit = ref(false)

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

// 生成结果：模块/功能筛选 + 全局展开用例详情（前置条件、步骤、预期结果）
const filterModule = ref('')
const filterFunction = ref('')
const showCaseDetails = ref(true)

// 计算属性
const treeData = computed(() => {
    if (!currentResult.value?.data) return []
    return buildTreeData(currentResult.value.data)
})

const moduleOptions = computed(() => {
    const modules = currentResult.value?.data?.modules || []
    return modules.map(m => m.name).filter(Boolean)
})

const functionOptions = computed(() => {
    const modules = currentResult.value?.data?.modules || []
    const modName = filterModule.value
    if (modName) {
        const mod = modules.find(m => m.name === modName)
        if (!mod) return []
        return (mod.functions || []).map(f => f.name).filter(Boolean)
    }
    const seen = new Set()
    const out = []
    for (const m of modules) {
        for (const f of m.functions || []) {
            const n = f.name
            if (n && !seen.has(n)) {
                seen.add(n)
                out.push(n)
            }
        }
    }
    return out
})

const displayTreeData = computed(() => {
    const raw = treeData.value
    return filterTreeData(raw, filterModule.value, filterFunction.value)
})

watch(filterModule, () => {
    const opts = functionOptions.value
    if (filterFunction.value && !opts.includes(filterFunction.value)) {
        filterFunction.value = ''
    }
})

watch(
    () => currentResult.value?.id,
    () => {
        filterModule.value = ''
        filterFunction.value = ''
        showCaseDetails.value = true
    }
)

const currentTimeStr = computed(() => {
    const now = new Date()
    return now.toLocaleTimeString('zh-CN', { hour12: false })
})

function appendAgentLog(icon, text, level = 'info', duration = '') {
    const time = new Date().toLocaleTimeString('zh-CN', { hour12: false })
    agentLog.value.push({ time, icon, text, level, duration })
    nextTick(() => {
        if (agentLogRef.value) {
            agentLogRef.value.scrollTop = agentLogRef.value.scrollHeight
        }
    })
}

function formatCaseBudget(row) {
    const budget = row?.case_budget || {}
    const range = budget.suggested_range || []
    const target = budget.target
    if (range.length >= 2 && target) {
        return `${range[0]}-${range[1]}（建议 ${target}）`
    }
    if (range.length >= 2) {
        return `${range[0]}-${range[1]}（建议）`
    }
    if (target) {
        return `建议 ${target}`
    }
    return '按风险动态'
}

function hasBlockingReviewIssues(issues = []) {
    return issues.some(issue => {
        const severity = String(issue?.severity || '').toLowerCase()
        const type = String(issue?.type || '').toLowerCase()
        return severity === 'high' && ['duplicate', 'redundant'].includes(type)
    })
}

const jsonPreview = computed(() => {
    if (!currentResult.value?.data) return ''
    return JSON.stringify(currentResult.value.data, null, 2)
})

// 构建树形数据（用例节点附带 moduleName/functionName/caseIndex 供编辑接口使用）
function buildTreeData(data) {
    const modules = data.modules || []
    return modules.map(mod => ({
        label: mod.name,
        nodeType: 'module',
        children: (mod.functions || []).map(func => ({
            label: func.name,
            nodeType: 'function',
            children: (func.cases || []).map((c, caseIndex) => ({
                label: c.name,
                nodeType: 'case',
                priority: c.priority,
                precondition: c.precondition,
                steps: c.steps,
                expected: c.expected,
                moduleName: mod.name,
                functionName: func.name,
                caseIndex
            }))
        }))
    }))
}

/** 按模块名、功能名过滤树（与筛选下拉联动） */
function filterTreeData(nodes, moduleName, functionName) {
    if (!nodes?.length) return []
    if (!moduleName && !functionName) return nodes
    return nodes
        .filter(m => !moduleName || m.label === moduleName)
        .map(m => {
            let funcs = (m.children || []).filter(f => !functionName || f.label === functionName)
            funcs = funcs
                .map(f => ({
                    ...f,
                    children: [...(f.children || [])]
                }))
                .filter(f => (f.children || []).length > 0)
            if (funcs.length === 0) return null
            return { ...m, children: funcs }
        })
        .filter(Boolean)
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
    generationMode.value = 'comprehensive'
    agentProgress.value = { active: false, nodes: [], currentNode: '', currentIndex: 0, totalNodes: 0, review: null, refining: false, analysisData: null, strategyData: null, moduleProgress: [], reviewIssues: [] }
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
    agentProgress.value = { active: false, nodes: [], currentNode: '', currentIndex: 0, totalNodes: 0, review: null, refining: false, analysisData: null, strategyData: null, moduleProgress: [], reviewIssues: [] }
    agentLog.value = []

    // 启动计时器
    timerInterval = setInterval(() => {
        elapsedTime.value++
    }, 1000)

    // 构建 FormData
    const formData = new FormData()
    formData.append('requirement', requirement.value.trim())
    formData.append('use_thinking', useThinking.value)
    formData.append('mode', generationMode.value)

    // 添加文件
    for (const file of fileList.value) {
        const rawFile = file.raw || file
        if (rawFile instanceof File) {
            formData.append('files', rawFile)
        } else {
            console.error('无效的文件对象:', file)
        }
    }

    if (useAgentMode.value) {
        await handleAgentGenerate(formData)
    } else {
        await handleDirectGenerate(formData)
    }
}

// 直接生成（原逻辑）
async function handleDirectGenerate(formData) {
    const startResp = await startAiTestcaseGeneration(formData, { agent: false })
    const recordId = startResp.record_id

    if (startResp.reused) {
        stopTimer()
        generating.value = false
        const res = await previewAiTestcase(recordId)
        streamContent.value = ''
        currentResult.value = {
            id: recordId,
            record_id: recordId,
            title: res.title,
            module_count: res.module_count,
            case_count: res.case_count,
            data: res.data,
        }
        ElMessage.success('已复用最近一次生成结果')
        loadHistory()
        return
    }

    streamContent.value = `已启动任务 #${recordId}，等待进度...\n`

    await streamAiTestcaseEvents(recordId, {
        after: 0,
        onEvent: (ev) => {
            if (ev.type === 'chunk') {
                streamContent.value += ev.content || ''
                nextTick(() => {
                    if (streamOutputRef.value) {
                        streamOutputRef.value.scrollTop = streamOutputRef.value.scrollHeight
                    }
                })
            } else if (ev.type === 'progress') {
                const p = ev.payload || {}
                streamContent.value += `[${p.stage || 'progress'}] ${p.percent != null ? (p.percent + '% ') : ''}${p.message || ''}\n`
            } else if (ev.type === 'done') {
                stopTimer()
                generating.value = false
                const p = ev.payload || {}
                currentResult.value = {
                    ...p,
                    id: p.record_id,
                    title: p.title || p.data?.title,
                }
                ElMessage.success(`生成成功！共 ${p.module_count} 个模块，${p.case_count} 条用例`)
                loadHistory()
            } else if (ev.type === 'error') {
                stopTimer()
                generating.value = false
                const p = ev.payload || {}
                ElMessage.error(`生成失败：${p.error || '未知错误'}`)
                loadHistory()
            } else if (ev.type === 'cancelled') {
                stopTimer()
                generating.value = false
                ElMessage.warning('任务已取消')
                loadHistory()
            }
        },
        onError: (err) => {
            stopTimer()
            generating.value = false
            ElMessage.error(`事件流失败：${err}`)
            loadHistory()
        }
    })
}

// Agent 智能体生成
async function handleAgentGenerate(formData) {
    agentProgress.value.active = true

    const nodeNameMap = {
        'analyze_requirement': '需求分析',
        'plan_test_strategy': '策略规划',
        'generate_by_module': '分模块生成',
        'merge_and_review': '评审打分',
        'refine_cases': '修订用例',
        'finalize': '完成',
    }

    function getStepIndex(nodeName) {
        if (nodeName === 'analyze_requirement') return 1
        if (nodeName === 'plan_test_strategy') return 2
        if (nodeName === 'generate_by_module' || nodeName.startsWith('generate_module:')) return 3
        if (nodeName === 'merge_and_review') return 4
        if (nodeName === 'refine_cases') return 4
        if (nodeName === 'finalize') return 5
        return 0
    }

    const startResp = await startAiTestcaseGeneration(formData, { agent: true })
    const recordId = startResp.record_id

    if (startResp.reused) {
        stopTimer()
        generating.value = false
        const res = await previewAiTestcase(recordId)
        streamContent.value = ''
        currentResult.value = {
            id: recordId,
            record_id: recordId,
            title: res.title,
            module_count: res.module_count,
            case_count: res.case_count,
            data: res.data,
        }
        ElMessage.success('已复用最近一次生成结果')
        loadHistory()
        return
    }

    appendAgentLog('🚀', `任务已启动 #${recordId}`, 'info')
    appendAgentLog('🔍', '开始执行智能体流程...', 'running')

    await streamAiTestcaseEvents(recordId, {
        after: 0,
        onEvent: (ev) => {
            if (ev.type === 'progress') {
                const p = ev.payload || {}
                const stage = p.stage || 'agent_step'
                let displayName = nodeNameMap[stage] || stage
                if (stage.startsWith('generate_module:')) {
                    displayName = '分模块生成'
                }
                agentProgress.value.currentNode = displayName
                agentProgress.value.currentIndex = getStepIndex(stage)
                agentProgress.value.refining = stage === 'refine_cases'

                if (p.phase === 'running' && p.message) {
                    appendAgentLog('⏳', p.message, 'running')
                }

                if (p.data && stage === 'analyze_requirement' && p.phase !== 'running') {
                    agentProgress.value.analysisData = p.data
                }
                if (p.data && stage === 'plan_test_strategy') {
                    agentProgress.value.strategyData = p.data
                }
                if (p.data?.reset_module_progress) {
                    agentProgress.value.moduleProgress = []
                    appendAgentLog('🔁', '评审仍未达标，已升级策略并重新分模块生成', 'warn')
                }
                if (p.data && p.data.module_name) {
                    agentProgress.value.moduleProgress.push({
                        name: p.data.module_name,
                        functionCount: p.data.function_count || 0,
                        caseCount: p.data.case_count || 0,
                    })
                }
            } else if (ev.type === 'review') {
                const p = ev.payload || {}
                const scorePercent = (((p.score || 0) * 100)).toFixed(0)
                agentProgress.value.review = {
                    score: p.score,
                    feedback: p.feedback || '',
                    iteration: p.iteration,
                    max: p.max || 3,
                }
                agentProgress.value.reviewIssues = p.issues || []
                if ((p.score || 0) >= 0.8 && !hasBlockingReviewIssues(p.issues || [])) {
                    appendAgentLog('🎉', `评审通过！分数: ${scorePercent}分`, 'success')
                } else {
                    appendAgentLog('⚠️', `评审分数: ${scorePercent}分，仍有待修订问题，将自动定向修订`, 'warn')
                }
            } else if (ev.type === 'done') {
                stopTimer()
                generating.value = false
                agentProgress.value.currentIndex = 5
                agentProgress.value.refining = false
                const p = ev.payload || {}
                currentResult.value = {
                    ...p,
                    id: p.record_id,
                    title: p.title || p.data?.title,
                }
                appendAgentLog('🏁', `Agent 生成完成！${p.module_count} 个模块, ${p.case_count} 条用例`, 'done')
                ElMessage.success(`Agent 生成成功！共 ${p.module_count} 个模块，${p.case_count} 条用例`)
                loadHistory()
            } else if (ev.type === 'error') {
                stopTimer()
                generating.value = false
                agentProgress.value.active = false
                const p = ev.payload || {}
                appendAgentLog('❌', `失败：${p.error || '未知错误'}`, 'error')
                ElMessage.error(`Agent 生成失败：${p.error || '未知错误'}`)
                loadHistory()
            } else if (ev.type === 'cancelled') {
                stopTimer()
                generating.value = false
                agentProgress.value.active = false
                appendAgentLog('🛑', '任务已取消', 'warn')
                ElMessage.warning('任务已取消')
                loadHistory()
            }
        },
        onError: (error) => {
            stopTimer()
            generating.value = false
            agentProgress.value.active = false
            appendAgentLog('❌', `事件流失败：${error}`, 'error')
            ElMessage.error(`Agent 生成失败：${error}`)
            loadHistory()
        },
    })
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
    const id = currentResult.value.id
    const title =
        currentResult.value?.data?.title ||
        currentResult.value?.title ||
        `testcase_${id}`
    await doDownload(id, title)
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
        const safeTitle = (title || `testcase_${id}`).trim() || `testcase_${id}`
        link.download = `${safeTitle}.xmind`
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

// ============ 用例编辑（悬停编辑按钮） ============
function openCaseEditDialog(data) {
    if (!currentResult.value?.id) return
    caseEditForm.value = {
        name: data.label || '',
        priority: data.priority || 'P1',
        precondition: data.precondition || '',
        steps: data.steps || '',
        expected: data.expected || ''
    }
    caseEditMeta.value = {
        moduleName: data.moduleName || '',
        functionName: data.functionName || '',
        caseIndex: data.caseIndex ?? 0
    }
    showCaseEditDialog.value = true
}

async function saveCaseEdit() {
    if (!currentResult.value?.id) return
    const payload = {
        record_id: currentResult.value.id,
        module_name: caseEditMeta.value.moduleName,
        function_name: caseEditMeta.value.functionName,
        case_index: caseEditMeta.value.caseIndex,
        name: caseEditForm.value.name.trim(),
        priority: caseEditForm.value.priority,
        precondition: caseEditForm.value.precondition || '',
        steps: caseEditForm.value.steps || '',
        expected: caseEditForm.value.expected || ''
    }
    if (!payload.name) {
        ElMessage.warning('请填写用例标题')
        return
    }
    savingCaseEdit.value = true
    try {
        const res = await aiUpdateCase(payload)
        currentResult.value = {
            ...currentResult.value,
            data: res.data,
            module_count: res.module_count,
            case_count: res.case_count
        }
        showCaseEditDialog.value = false
        ElMessage.success('用例已保存')
    } catch (e) {
        ElMessage.error(e?.response?.data?.error || e?.message || '保存失败')
    } finally {
        savingCaseEdit.value = false
    }
}

// ============ 功能点调整 ============
function getModuleNameForNode(node) {
    return node?.parent?.data?.label ?? ''
}

function openRegenerateFunctionDialog(moduleName, functionName) {
    if (!currentResult.value?.id) {
        ElMessage.warning('请先查看一条用例记录')
        return
    }
    regenerateFunctionModuleName.value = moduleName
    regenerateFunctionName.value = functionName
    regenerateFunctionRequirement.value = ''
    regenerateFunctionAdjustment.value = ''
    regenerateFunctionStreamContent.value = ''
    regenerateFunctionElapsedTime.value = 0
    showRegenerateFunctionDialog.value = true
}

function handleRegenerateFunctionDialogClose() {
    if (regeneratingFunction.value) return
    regenerateFunctionStreamContent.value = ''
    regenerateFunctionRequirement.value = ''
    regenerateFunctionAdjustment.value = ''
}

const canSubmitRegenerateFunction = computed(() => {
    return regenerateFunctionRequirement.value.trim() || regenerateFunctionAdjustment.value.trim()
})

function stopRegenerateFunctionTimer() {
    if (regenerateFunctionTimerInterval) {
        clearInterval(regenerateFunctionTimerInterval)
        regenerateFunctionTimerInterval = null
    }
}

async function handleRegenerateFunction() {
    if (!canSubmitRegenerateFunction.value) {
        ElMessage.warning('请至少填写「补充功能点需求」或「调整意见」中的一项')
        return
    }
    regeneratingFunction.value = true
    regenerateFunctionStreamContent.value = ''
    regenerateFunctionElapsedTime.value = 0
    regenerateFunctionTimerInterval = setInterval(() => {
        regenerateFunctionElapsedTime.value++
    }, 1000)

    await aiRegenerateFunctionStream(
        {
            record_id: currentResult.value.id,
            module_name: regenerateFunctionModuleName.value,
            function_name: regenerateFunctionName.value,
            function_requirement: regenerateFunctionRequirement.value.trim(),
            adjustment: regenerateFunctionAdjustment.value.trim(),
            use_thinking: regenerateFunctionUseThinking.value
        },
        (content) => {
            regenerateFunctionStreamContent.value += content
            nextTick(() => {
                if (regenerateFunctionStreamRef.value) {
                    regenerateFunctionStreamRef.value.scrollTop = regenerateFunctionStreamRef.value.scrollHeight
                }
            })
        },
        (result) => {
            stopRegenerateFunctionTimer()
            regeneratingFunction.value = false
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
            ElMessage.success(`功能点「${regenerateFunctionName.value}」已重新生成，共 ${result.case_count} 条用例`)
            loadHistory()
        },
        (error) => {
            stopRegenerateFunctionTimer()
            regeneratingFunction.value = false
            ElMessage.error(`功能点调整失败：${error}`)
        },
        () => {}
    )
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

function onHistoryCreatorFilterChange() {
    historyPage.value = 1
    loadHistory()
}

async function loadCreatorOptions() {
    if (!configStatus.value.can_filter_by_creator) return
    try {
        const list = await getUserList()
        creatorUserList.value = Array.isArray(list) ? list.filter(u => u && u.id) : []
    } catch (err) {
        console.error('加载用户列表失败:', err)
    }
}

// 加载历史记录
async function loadHistory() {
    try {
        const params = {
            page: historyPage.value,
            page_size: 10,
            ordering: '-created_at'
        }
        if (
            configStatus.value.can_filter_by_creator &&
            historyCreatorFilter.value != null &&
            historyCreatorFilter.value !== ''
        ) {
            params.created_by = historyCreatorFilter.value
        }
        const res = await getAiTestcaseGenerations(params)
        historyList.value = res.results || res
        historyTotal.value = res.count || historyList.value.length
    } catch (err) {
        console.error('加载历史记录失败:', err)
    }
}

// 加载配置状态
async function loadConfigStatus() {
    try {
        const data = await getAiTestcaseConfigStatus()
        configStatus.value = {
            ...configStatus.value,
            ...data,
            can_filter_by_creator: !!data?.can_filter_by_creator
        }
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
    const year = d.getFullYear()
    const month = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const hours = String(d.getHours()).padStart(2, '0')
    const minutes = String(d.getMinutes()).padStart(2, '0')
    return `${year}-${month}-${day} ${hours}:${minutes}`
}

// 初始化
onMounted(async () => {
    await loadConfigStatus()
    await loadCreatorOptions()
    await loadHistory()

    // 从需求智能体结构直传跳转：打开指定 record_id 的生成结果
    const recordId = route.query.record_id
    if (recordId) {
        try {
            const res = await previewAiTestcase(Number(recordId))
            streamContent.value = ''
            currentResult.value = {
                id: Number(recordId),
                title: res.title,
                module_count: res.module_count,
                case_count: res.case_count,
                data: res.data,
                usage: res.usage || {}
            }
            router.replace({ name: 'AiTestcaseGenerator' })
        } catch (e) {
            ElMessage.warning('无法加载该用例记录')
            router.replace({ name: 'AiTestcaseGenerator' })
        }
        return
    }

    // 接收 AI 需求智能体的功能点桥接数据（方案 B：原文）
    const bridgeText = sessionStorage.getItem('ai_req_bridge_text')
    if (bridgeText) {
        requirement.value = bridgeText
        sessionStorage.removeItem('ai_req_bridge_text')
        sessionStorage.removeItem('ai_req_bridge_source')
        ElMessage.info('已从 AI 需求智能体导入功能点，可直接点击"智能生成用例"')
    }
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

.history-card-header {
    justify-content: space-between;
    flex-wrap: wrap;
    row-gap: 8px;
    width: 100%;
}

.history-card-header-right {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: auto;
}

.history-creator-filter {
    width: 160px;
}

.history-creator {
    font-size: 12px;
    color: #909399;
    margin-top: 4px;
    display: flex;
    align-items: center;
    gap: 4px;
}

/* 生成结果：标题 + 筛选/展开 与统计同一行，窄屏可换行 */
.card-header-result {
    flex-wrap: wrap;
    row-gap: 8px;
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

/* 生成模式选择 */
.mode-selection {
    margin-top: 16px;
    margin-bottom: 16px;
    padding: 16px;
    background: #f8f9fa;
    border-radius: 6px;
    border: 1px solid #e4e7ed;
}

.mode-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    font-weight: 500;
    color: #303133;
    margin-bottom: 12px;
}

.mode-radio-group {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
}

.mode-radio {
    margin-right: 0 !important;
    padding: 12px 16px;
    border-radius: 6px;
    transition: all 0.2s ease;
    border: 1px solid #e4e7ed;
    background: #fff;
    flex: 1;
    min-width: 140px;
}

.mode-radio:hover {
    background: #ecf5ff;
    border-color: #c6e2ff;
}

.mode-radio.is-checked {
    background: #ecf5ff;
    border-color: #409eff;
    box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.2);
}

.mode-content {
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    gap: 4px;
}

.mode-title {
    font-weight: 500;
    color: #303133;
    font-size: 14px;
    line-height: 1.2;
}

.mode-desc {
    font-size: 12px;
    color: #909399;
    line-height: 1.2;
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

.result-tree-toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
}

.result-tree-toolbar--header {
    flex: 1 1 auto;
    min-width: 0;
    margin-bottom: 0;
}

.result-filter-select {
    width: 180px;
}

:deep(.el-tree-node__content) {
    min-height: 32px;
    height: auto;
    align-items: flex-start;
    padding-top: 4px;
    padding-bottom: 4px;
}

.tree-node {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    flex-wrap: wrap;
}

.tree-node.tree-node-case {
    flex-direction: column;
    align-items: stretch;
    gap: 6px;
}

.tree-node-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}

/* 用例行：悬停时显示编辑按钮 */
.tree-node-row-case .case-edit-btn {
    opacity: 0;
    margin-left: 4px;
    transition: opacity 0.15s ease;
}
.tree-node-row-case:hover .case-edit-btn {
    opacity: 1;
}

/* 用例同一层：标题后紧跟的前置条件、测试步骤、预期结果（不增加树层级） */
.tree-case-inline {
    font-size: 12px;
    color: #606266;
    line-height: 1.5;
    padding-left: 12px;
    border-left: 2px solid #e4e7ed;
    max-height: 120px;
    overflow-y: auto;
}

.tree-case-inline .case-inline-item {
    display: block;
    margin-bottom: 4px;
    word-break: break-word;
}

.tree-case-inline .case-inline-item:last-child {
    margin-bottom: 0;
}

.tree-case-inline .case-inline-item em {
    color: #909399;
    font-style: normal;
    margin-right: 4px;
}

.tree-case-inline .case-inline-steps {
    white-space: pre-line;
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

:deep(.el-tree-node__content:hover) .module-adjust-btn,
:deep(.el-tree-node__content:hover) .function-adjust-btn {
    opacity: 1;
}

.function-adjust-btn {
    margin-left: 8px;
    padding: 2px 6px !important;
    font-size: 12px;
    opacity: 0;
    transition: opacity 0.2s ease;
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

/* Agent 进度面板 */
.agent-progress-card {
    margin-bottom: 16px;
    border-left: 3px solid #409eff;
}

.agent-progress-card .el-steps {
    padding: 12px 0;
}

.agent-score-badge {
    font-size: 13px;
    font-weight: 600;
    padding: 2px 10px;
    border-radius: 12px;
}

.agent-score-badge.score-pass {
    background: #f0f9eb;
    color: #67c23a;
}

.agent-score-badge.score-fail {
    background: #fef0f0;
    color: #f56c6c;
}

/* Agent 步骤内容区 */
.agent-step-content {
    margin-top: 16px;
    padding: 14px;
    background: #f5f7fa;
    border-radius: 8px;
    border-left: 3px solid #e4e7ed;
}

.agent-step-content + .agent-step-content {
    margin-top: 12px;
}

.step-section-title {
    font-size: 14px;
    font-weight: 600;
    color: #303133;
    margin-bottom: 10px;
}

.step-section-sub {
    font-weight: 400;
    color: #909399;
    font-size: 13px;
}

.module-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.module-tag {
    font-size: 13px;
    padding: 4px 12px;
}

.module-tag .complexity-label {
    margin-left: 4px;
    opacity: 0.7;
    font-size: 11px;
}

.step-rules {
    margin-top: 8px;
    font-size: 12px;
    color: #606266;
}

.rules-label {
    color: #909399;
}

.rule-item {
    display: inline-block;
    margin: 2px 4px;
    padding: 1px 6px;
    background: #ecf5ff;
    color: #409eff;
    border-radius: 3px;
    font-size: 12px;
}

.strategy-table {
    margin-top: 4px;
}

.method-tag {
    margin: 1px 3px;
}

/* 分模块生成进度 */
.module-progress-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.module-progress-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    padding: 4px 0;
}

.module-done-icon {
    color: #67c23a;
    font-size: 16px;
    flex-shrink: 0;
}

.module-progress-name {
    font-weight: 500;
    color: #303133;
}

.module-progress-stats {
    color: #909399;
    font-size: 12px;
}

/* 评审问题列表 */
.review-issues-list {
    margin-top: 10px;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.review-issue-item {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    font-size: 12px;
}

.issue-desc {
    color: #606266;
    line-height: 1.5;
}

.review-issues-more {
    font-size: 12px;
    color: #909399;
    padding-left: 4px;
}

.agent-review-info {
    padding: 12px;
    background: #fff;
    border-radius: 6px;
    font-size: 13px;
    border: 1px solid #ebeef5;
}

.review-detail {
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 4px;
}

.review-detail:last-child {
    margin-bottom: 0;
}

.review-label {
    color: #909399;
    flex-shrink: 0;
}

.refining-hint {
    color: #e6a23c;
    font-weight: 500;
}

/* Agent 活动日志 */
.agent-log-card {
    margin-bottom: 16px;
}

.log-count {
    font-size: 12px;
    color: #909399;
}

.agent-log-container {
    max-height: 280px;
    overflow-y: auto;
    font-family: 'Consolas', 'Monaco', 'Menlo', monospace;
    font-size: 13px;
    line-height: 1.8;
    padding: 4px 0;
}

.agent-log-entry {
    display: flex;
    align-items: baseline;
    gap: 8px;
    padding: 2px 8px;
    border-radius: 4px;
}

.agent-log-entry:hover {
    background: #f5f7fa;
}

.log-time {
    color: #c0c4cc;
    font-size: 12px;
    flex-shrink: 0;
    min-width: 70px;
}

.log-icon {
    flex-shrink: 0;
    width: 20px;
    text-align: center;
}

.log-text {
    color: #303133;
    flex: 1;
}

.log-duration {
    color: #c0c4cc;
    font-size: 12px;
    flex-shrink: 0;
}

.log-success .log-text { color: #67c23a; }
.log-warn .log-text { color: #e6a23c; }
.log-error .log-text { color: #f56c6c; }
.log-done .log-text { color: #409eff; font-weight: 600; }
.log-running .log-text { color: #909399; }

@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
}

.log-blink {
    animation: blink 1.5s ease-in-out infinite;
}

.agent-log-container::-webkit-scrollbar {
    width: 4px;
}

.agent-log-container::-webkit-scrollbar-track {
    background: transparent;
}

.agent-log-container::-webkit-scrollbar-thumb {
    background: #dcdfe6;
    border-radius: 2px;
}
</style>
