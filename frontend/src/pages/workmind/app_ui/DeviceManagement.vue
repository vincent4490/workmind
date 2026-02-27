<template>
    <div class="device-management">
        <div class="device-header">
            <h3>设备管理</h3>
            <div class="device-actions">
                <el-button
                    type="primary"
                    :icon="Refresh"
                    :loading="refreshing"
                    @click="refreshDevices"
                >
                    刷新设备
                </el-button>
                <el-button
                    type="success"
                    :icon="Plus"
                    @click="showAddRemoteDialog"
                >
                    添加远程设备
                </el-button>
            </div>
        </div>

        <!-- 设备列表 -->
        <el-table
            v-loading="loading"
            :data="devices"
            style="width: 100%; margin-top: 20px"
            :empty-text="emptyText"
        >
            <el-table-column prop="name" label="设备名称" min-width="150">
                <template #default="scope">
                    <span>{{ scope.row.name || scope.row.device_id }}</span>
                </template>
            </el-table-column>

            <el-table-column prop="device_id" label="设备序列号" min-width="180" />

            <el-table-column prop="status" label="状态" width="100">
                <template #default="scope">
                    <el-tag
                        :type="getStatusType(scope.row.status)"
                        size="small"
                    >
                        {{ getStatusText(scope.row.status) }}
                    </el-tag>
                </template>
            </el-table-column>

            <el-table-column prop="locked_by" label="锁定用户" width="120">
                <template #default="scope">
                    <span v-if="scope.row.locked_by_username">
                        {{ scope.row.locked_by_username }}
                    </span>
                    <span v-else>-</span>
                </template>
            </el-table-column>

            <el-table-column prop="locked_at" label="锁定时间" width="180">
                <template #default="scope">
                    <span v-if="scope.row.locked_at">
                        {{ formatDate(scope.row.locked_at) }}
                    </span>
                    <span v-else>-</span>
                </template>
            </el-table-column>

            <el-table-column prop="android_version" label="Android版本" width="120" />

            <el-table-column prop="connection_type" label="连接类型" width="120">
                <template #default="scope">
                    <el-tag
                        :type="scope.row.connection_type === 'emulator' ? 'primary' : 'warning'"
                        size="small"
                    >
                        {{ scope.row.connection_type === 'emulator' ? '本地模拟器' : '远程模拟器' }}
                    </el-tag>
                </template>
            </el-table-column>

            <el-table-column prop="ip_address" label="IP地址" width="150">
                <template #default="scope">
                    <span v-if="scope.row.ip_address">
                        {{ scope.row.ip_address }}
                    </span>
                    <span v-else>-</span>
                </template>
            </el-table-column>

            <el-table-column prop="updated_at" label="更新时间" width="180">
                <template #default="scope">
                    {{ formatDate(scope.row.updated_at) }}
                </template>
            </el-table-column>

            <el-table-column label="操作" width="200" fixed="right">
                <template #default="scope">
                    <el-button
                        v-if="scope.row.status === 'available' || scope.row.status === 'online'"
                        link
                        size="small"
                        style="color: #409EFF"
                        @click="lockDevice(scope.row)"
                    >
                        锁定
                    </el-button>
                    <el-button
                        v-if="scope.row.status === 'locked'"
                        link
                        size="small"
                        style="color: #67C23A"
                        @click="unlockDevice(scope.row)"
                    >
                        解锁
                    </el-button>
                    <el-button
                        v-if="scope.row.connection_type === 'remote_emulator' && scope.row.status === 'offline'"
                        link
                        size="small"
                        style="color: #E6A23C"
                        :loading="reconnectingDevices[scope.row.id]"
                        @click="reconnectDevice(scope.row)"
                    >
                        重连
                    </el-button>
                    <el-button
                        link
                        size="small"
                        @click="viewDeviceInfo(scope.row)"
                    >
                        详情
                    </el-button>
                    <el-button
                        v-if="scope.row.connection_type === 'remote_emulator' && scope.row.status === 'online'"
                        link
                        size="small"
                        style="color: #f56c6c"
                        @click="disconnectDevice(scope.row)"
                    >
                        断开
                    </el-button>
                </template>
            </el-table-column>
        </el-table>

        <!-- 添加远程设备对话框 -->
        <el-dialog
            title="添加远程设备"
            v-model="addRemoteDialogVisible"
            width="500px"
            :close-on-click-modal="false"
        >
            <el-form
                ref="remoteDeviceForm"
                :model="remoteDeviceFormData"
                :rules="remoteDeviceRules"
                label-width="100px"
            >
                <el-form-item label="IP地址" prop="ip_address">
                    <el-input
                        v-model="remoteDeviceFormData.ip_address"
                        placeholder="请输入远程设备IP地址"
                    />
                </el-form-item>

                <el-form-item label="端口" prop="port">
                    <el-input-number
                        v-model="remoteDeviceFormData.port"
                        :min="1"
                        :max="65535"
                        placeholder="默认5555"
                        style="width: 100%"
                    />
                </el-form-item>

                <el-alert
                    title="提示"
                    type="info"
                    :closable="false"
                    style="margin-top: 10px"
                >
                    <div>请确保：</div>
                    <div>1. 远程设备已开启ADB调试</div>
                    <div>2. 远程设备已开启网络ADB（adb tcpip 5555）</div>
                    <div>3. 网络连接正常</div>
                </el-alert>
            </el-form>

            <template #footer>
                <div class="dialog-footer">
                    <el-button @click="addRemoteDialogVisible = false">取消</el-button>
                    <el-button
                        type="primary"
                        :loading="connecting"
                        @click="connectRemoteDevice"
                    >
                        连接
                    </el-button>
                </div>
            </template>
        </el-dialog>

        <!-- 设备详情对话框 -->
        <el-dialog
            title="设备详情"
            v-model="deviceInfoDialogVisible"
            width="600px"
        >
            <el-descriptions v-if="selectedDevice" :column="2" border>
                <el-descriptions-item label="设备名称">
                    {{ selectedDevice.name || selectedDevice.device_id }}
                </el-descriptions-item>
                <el-descriptions-item label="设备序列号">
                    {{ selectedDevice.device_id }}
                </el-descriptions-item>
                <el-descriptions-item label="状态">
                    <el-tag
                        :type="getStatusType(selectedDevice.status)"
                        size="small"
                    >
                        {{ getStatusText(selectedDevice.status) }}
                    </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="锁定用户">
                    {{ selectedDevice.locked_by_username || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="锁定时间">
                    {{ selectedDevice.locked_at ? formatDate(selectedDevice.locked_at) : '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="Android版本">
                    {{ selectedDevice.android_version || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="连接类型">
                    <el-tag
                        :type="selectedDevice.connection_type === 'emulator' ? 'primary' : 'warning'"
                        size="small"
                    >
                        {{ selectedDevice.connection_type === 'emulator' ? '本地模拟器' : '远程模拟器' }}
                    </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="IP地址">
                    <span v-if="selectedDevice.ip_address">
                        {{ selectedDevice.ip_address }}
                    </span>
                    <span v-else>-</span>
                </el-descriptions-item>
                <el-descriptions-item label="创建时间">
                    {{ formatDate(selectedDevice.created_at) }}
                </el-descriptions-item>
                <el-descriptions-item label="更新时间">
                    {{ formatDate(selectedDevice.updated_at) }}
                </el-descriptions-item>
            </el-descriptions>

            <template #footer>
                <div class="dialog-footer">
                    <el-button @click="deviceInfoDialogVisible = false">关闭</el-button>
                </div>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Plus } from '@element-plus/icons-vue'
import { useGlobalProperties } from '@/composables'

const { $api } = useGlobalProperties()

// refs
const remoteDeviceForm = ref(null)

// 响应式数据
const devices = ref([])
const loading = ref(false)
const refreshing = ref(false)
const connecting = ref(false)
const reconnectingDevices = ref({})
const addRemoteDialogVisible = ref(false)
const deviceInfoDialogVisible = ref(false)
const selectedDevice = ref(null)
const emptyText = ref('暂无设备，请点击刷新设备或添加远程设备')
const refreshTimer = ref(null)

const remoteDeviceFormData = ref({
    ip_address: '',
    port: 5555
})

const remoteDeviceRules = {
    ip_address: [
        { required: true, message: '请输入IP地址', trigger: 'blur' },
        {
            pattern: /^(\d{1,3}\.){3}\d{1,3}$/,
            message: '请输入有效的IP地址',
            trigger: 'blur'
        }
    ],
    port: [
        { required: true, message: '请输入端口号', trigger: 'blur' }
    ]
}

// 方法
const getDevices = async () => {
    loading.value = true
    try {
        const response = await $api.getDeviceList()

        if (response.code === 0) {
            devices.value = response.data
            if (devices.value.length === 0) {
                emptyText.value = '暂无设备，请点击刷新设备或添加远程设备'
            }
        } else {
            ElMessage.error(response.msg || '获取设备列表失败')
        }
    } catch (error) {
        console.error('获取设备列表失败:', error)
        ElMessage.error('获取设备列表失败')
    } finally {
        loading.value = false
    }
}

const refreshDevices = async () => {
    refreshing.value = true
    try {
        const response = await $api.refreshDevices()

        if (response.code === 0) {
            devices.value = response.data
            const msg = response.msg && response.msg !== '刷新成功' ? response.msg : '设备列表已刷新'
            if (msg.includes('ADB') || msg.includes('已返回已有设备列表')) {
                ElMessage.warning(msg)
            } else {
                ElMessage.success(msg)
            }
        } else {
            ElMessage.error(response.msg || '刷新设备列表失败')
        }
    } catch (error) {
        console.error('刷新设备列表失败:', error)
        ElMessage.error('刷新设备列表失败')
    } finally {
        refreshing.value = false
    }
}

const showAddRemoteDialog = () => {
    addRemoteDialogVisible.value = true
    remoteDeviceFormData.value = {
        ip_address: '',
        port: 5555
    }
    if (remoteDeviceForm.value) {
        remoteDeviceForm.value.clearValidate()
    }
}

const connectRemoteDevice = async () => {
    remoteDeviceForm.value.validate(async valid => {
        if (!valid) {
            return false
        }

        connecting.value = true
        try {
            const response = await $api.connectRemoteDevice({
                ip_address: remoteDeviceFormData.value.ip_address,
                port: remoteDeviceFormData.value.port
            })

            if (response.code === 0) {
                ElMessage.success(response.msg || '远程设备连接成功')
                addRemoteDialogVisible.value = false
                await getDevices()
            } else {
                ElMessage.error(response.msg || '连接远程设备失败')
            }
        } catch (error) {
            console.error('连接远程设备失败:', error)
            ElMessage.error('连接远程设备失败')
        } finally {
            connecting.value = false
        }
    })
}

const reconnectDevice = async (device) => {
    if (!device.ip_address || !device.port) {
        ElMessage.error('设备信息不完整，无法重连')
        return
    }

    reconnectingDevices.value[device.id] = true
    
    try {
        const response = await $api.connectRemoteDevice({
            ip_address: device.ip_address,
            port: device.port
        })

        if (response.code === 0) {
            ElMessage.success('设备重连成功')
            await getDevices()
        } else {
            ElMessage.error(response.msg || '设备重连失败，请检查设备网络连接')
        }
    } catch (error) {
        console.error('设备重连失败:', error)
        ElMessage.error('设备重连失败，请检查设备网络连接')
    } finally {
        reconnectingDevices.value[device.id] = false
    }
}

const disconnectDevice = async (device) => {
    try {
        await ElMessageBox.confirm(
            `确定要断开设备 ${device.name || device.device_id} 的连接吗？`,
            '提示',
            {
                confirmButtonText: '确定',
                cancelButtonText: '取消',
                type: 'warning'
            }
        )

        const response = await $api.disconnectDevice(device.id)

        if (response.code === 0) {
            ElMessage.success('设备已断开')
            await getDevices()
        } else {
            ElMessage.error(response.msg || '断开设备失败')
        }
    } catch (error) {
        if (error !== 'cancel') {
            console.error('断开设备失败:', error)
            ElMessage.error('断开设备失败')
        }
    }
}

const viewDeviceInfo = (device) => {
    selectedDevice.value = device
    deviceInfoDialogVisible.value = true
}

const formatDate = (dateString) => {
    if (!dateString) {
        return '-'
    }
    const date = new Date(dateString)
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    })
}

const getStatusType = (status) => {
    const statusMap = {
        'available': 'success',
        'locked': 'warning',
        'online': 'success',
        'offline': 'danger'
    }
    return statusMap[status] || 'info'
}

const getStatusText = (status) => {
    const statusMap = {
        'available': '可用',
        'locked': '已锁定',
        'online': '在线',
        'offline': '离线'
    }
    return statusMap[status] || status
}

const lockDevice = async (device) => {
    try {
        await ElMessageBox.confirm(
            `确定要锁定设备 ${device.name || device.device_id} 吗？`,
            '提示',
            {
                confirmButtonText: '确定',
                cancelButtonText: '取消',
                type: 'warning'
            }
        )

        const response = await $api.lockDevice(device.id)

        if (response.code === 0) {
            ElMessage.success('设备已锁定')
            await getDevices()
        } else {
            ElMessage.error(response.msg || '锁定设备失败')
        }
    } catch (error) {
        if (error !== 'cancel') {
            console.error('锁定设备失败:', error)
            ElMessage.error('锁定设备失败')
        }
    }
}

const unlockDevice = async (device) => {
    try {
        await ElMessageBox.confirm(
            `确定要解锁设备 ${device.name || device.device_id} 吗？`,
            '提示',
            {
                confirmButtonText: '确定',
                cancelButtonText: '取消',
                type: 'warning'
            }
        )

        const response = await $api.unlockDevice(device.id)

        if (response.code === 0) {
            ElMessage.success('设备已解锁')
            await getDevices()
        } else {
            ElMessage.error(response.msg || '解锁设备失败')
        }
    } catch (error) {
        if (error !== 'cancel') {
            console.error('解锁设备失败:', error)
            ElMessage.error('解锁设备失败')
        }
    }
}

// 生命周期
onMounted(() => {
    getDevices()

    refreshTimer.value = setInterval(() => {
        getDevices()
    }, 30000)
})

onBeforeUnmount(() => {
    if (refreshTimer.value) {
        clearInterval(refreshTimer.value)
    }
})
</script>

<style scoped>
.device-management {
    padding: 20px;
}

.device-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}

.device-header h3 {
    margin: 0;
    font-size: 20px;
    color: #303133;
}

.device-actions {
    display: flex;
    gap: 10px;
}

.dialog-footer {
    text-align: right;
}
</style>
