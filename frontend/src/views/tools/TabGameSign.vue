<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { PlusOutlined, DeleteOutlined, ReloadOutlined, ThunderboltOutlined, SaveOutlined } from '@ant-design/icons-vue'
import { useGameSignApi, type GameSignConfig } from '@/composables/useGameSignApi'
import { useStatusTag, createStatusTag } from '@/composables/useStatusTag'
import dayjs from 'dayjs'

const props = defineProps<{
    config: GameSignConfig
    disabled?: boolean
    onFieldChange?: (key: string, value: any) => void
}>()

const { loading, signNow, refreshInfo, getStatus, updateConfig } = useGameSignApi()
const saveLoading = ref(false)
const signLoading = ref(false)
const refreshLoading = ref(false)
const statusInfo = reactive({
    status: '未知',
    next_sign_time: '',
    last_sign_time: '',
    last_report: '',
    results: [] as any[],
    infos: [] as any[],
})

const statusTag = useStatusTag(
    () => statusInfo.status,
    createStatusTag('未配置', 'default')
)

// ==================== 本地编辑状态 ====================
const form = reactive({
    enabled: false,
    signWindowStart: '08:00',
    signWindowEnd: '22:00',
    timeoutSeconds: 20,
    showInfoAfterSign: true,
    fetchEvents: true,
    mihoyoAccounts: [] as Record<string, any>[],
    kuroAccounts: [] as Record<string, any>[],
    sklandAccounts: [] as Record<string, any>[],
})

// ==================== 时间选择器 ====================
const signWindowStartDT = ref(dayjs('08:00', 'HH:mm'))
const signWindowEndDT = ref(dayjs('22:00', 'HH:mm'))

const onStartChange = (time: any) => {
    if (time) form.signWindowStart = time.format('HH:mm')
}
const onEndChange = (time: any) => {
    if (time) form.signWindowEnd = time.format('HH:mm')
}

// ==================== 数据加载 ====================
const loadForm = async () => {
    try {
        const config = await getConfig()
        form.enabled = config.Enabled ?? false
        form.signWindowStart = config.SignWindowStart ?? '08:00'
        form.signWindowEnd = config.SignWindowEnd ?? '22:00'
        form.timeoutSeconds = config.TimeoutSeconds ?? 20
        form.showInfoAfterSign = config.ShowInfoAfterSign ?? true
        form.fetchEvents = config.FetchEvents ?? true
        form.mihoyoAccounts = (config.MihoyoAccounts || []).map((a: any) => ({ ...a }))
        form.kuroAccounts = (config.KuroAccounts || []).map((a: any) => ({ ...a }))
        form.sklandAccounts = (config.SklandAccounts || []).map((a: any) => ({ ...a }))
        // 同步时间选择器
        signWindowStartDT.value = dayjs(form.signWindowStart, 'HH:mm')
        signWindowEndDT.value = dayjs(form.signWindowEnd, 'HH:mm')
    } catch {
        form.mihoyoAccounts = []
        form.kuroAccounts = []
        form.sklandAccounts = []
    }
}

const loadStatus = async () => {
    const s = await getStatus()
    Object.assign(statusInfo, s)
}

// ==================== 保存 ====================
const handleSave = async () => {
    saveLoading.value = true
    try {
        const data: Record<string, any> = {
            Enabled: form.enabled,
            SignWindowStart: form.signWindowStart,
            SignWindowEnd: form.signWindowEnd,
            TimeoutSeconds: form.timeoutSeconds,
            ShowInfoAfterSign: form.showInfoAfterSign,
            FetchEvents: form.fetchEvents,
            MihoyoAccounts: form.mihoyoAccounts.filter(a => (a.cookie || '').trim()),
            KuroAccounts: form.kuroAccounts.filter(a => (a.token || '').trim()),
            SklandAccounts: form.sklandAccounts.filter(a => (a.token || '').trim()),
        }
        await updateConfig(data)
        await loadStatus()
    } finally {
        saveLoading.value = false
    }
}

// ==================== 操作 ====================
const handleSignNow = async () => {
    signLoading.value = true
    try {
        await signNow()
        await loadStatus()
    } finally {
        signLoading.value = false
    }
}

const handleRefreshInfo = async () => {
    refreshLoading.value = true
    try { await refreshInfo() } finally { refreshLoading.value = false }
}

// ==================== 账号管理 ====================
const addMihoyo = () => {
    form.mihoyoAccounts.push({ alias: '', cookie: '', enable_genshin: true, enable_starrail: true, enable_zzz: false, enable_honkai3: false, enable_bbs_tasks: true })
}
const addKuro = () => {
    form.kuroAccounts.push({ alias: '', token: '', enable_kuro_bbs: true, enable_wuwa: true })
}
const addSkland = () => {
    form.sklandAccounts.push({ alias: '', token: '', enable_arknights: true, enable_bbs: true })
}

// ==================== 时间格式化 ====================
const formatTime = (t: string) => {
    if (!t) return '--'
    try { return dayjs(t).format('MM-DD HH:mm:ss') } catch { return t }
}

onMounted(() => {
    loadForm()
    loadStatus()
})
</script>

<template>
    <div class="tab-content">
        <div class="tool-intro">
            <div class="card-header">游戏社区签到</div>
            <p class="intro-text">
                自动完成米游社、库街区、森空岛的每日社区签到和游戏签到，支持原神、崩铁、绝区零、鸣潮、明日方舟等多款游戏。
            </p>
        </div>

        <!-- ==================== 签到结果 / 状态 ==================== -->
        <div class="form-section result-section">
            <div class="section-header">
                <h3>签到结果</h3>
                <a-space>
                    <a-button :loading="signLoading" :disabled="disabled" @click="handleSignNow" type="primary">
                        <ThunderboltOutlined /> 立即签到
                    </a-button>
                    <a-button :loading="refreshLoading" :disabled="disabled" @click="handleRefreshInfo">
                        <ReloadOutlined /> 刷新信息
                    </a-button>
                </a-space>
            </div>

            <a-row :gutter="16" class="status-cards">
                <a-col :span="6">
                    <div class="status-card">
                        <div class="status-card-label">运行状态</div>
                        <a-tag v-if="statusTag" :color="statusTag.color">{{ statusTag.text }}</a-tag>
                    </div>
                </a-col>
                <a-col :span="6">
                    <div class="status-card">
                        <div class="status-card-label">上次签到</div>
                        <div class="status-card-value">{{ formatTime(statusInfo.last_sign_time) }}</div>
                    </div>
                </a-col>
                <a-col :span="6">
                    <div class="status-card">
                        <div class="status-card-label">下次签到</div>
                        <div class="status-card-value">{{ formatTime(statusInfo.next_sign_time) }}</div>
                    </div>
                </a-col>
                <a-col :span="6">
                    <div class="status-card">
                        <div class="status-card-label">账号数</div>
                        <div class="status-card-value">
                            {{ form.mihoyoAccounts.length + form.kuroAccounts.length + form.sklandAccounts.length }}
                        </div>
                    </div>
                </a-col>
            </a-row>

            <!-- 签到报告 -->
            <div v-if="statusInfo.last_report" class="sign-report">
                <div class="report-label">最近签到报告</div>
                <pre class="report-content">{{ statusInfo.last_report }}</pre>
            </div>

            <!-- 签到明细 -->
            <div v-if="statusInfo.results && statusInfo.results.length" class="sign-details">
                <div class="report-label">签到明细</div>
                <a-table :data-source="statusInfo.results" :columns="[
                    { title: '平台', dataIndex: 'provider', width: 80 },
                    { title: '游戏', dataIndex: 'game', width: 120 },
                    { title: '账号', dataIndex: 'account' },
                    { title: '状态', dataIndex: 'success', width: 80, customRender: ({text}: any) => text ? '✅ 成功' : '❌ 失败' },
                    { title: '说明', dataIndex: 'message' },
                ]" :pagination="false" size="small" />
            </div>

            <!-- 游戏信息 -->
            <div v-if="statusInfo.infos && statusInfo.infos.length" class="sign-details">
                <div class="report-label">游戏信息</div>
                <a-table :data-source="statusInfo.infos" :columns="[
                    { title: '游戏', dataIndex: 'game', width: 120 },
                    { title: '账号', dataIndex: 'account' },
                    { title: '体力', customRender: ({record}: any) => record.fields?.stamina != null ? `${record.fields.stamina}/${record.fields.stamina_max}` : '--' },
                    { title: '日常', customRender: ({record}: any) => record.fields?.daily_task_done != null ? `${record.fields.daily_task_done}/${record.fields.daily_task_total}` : '--' },
                ]" :pagination="false" size="small" />
            </div>
        </div>

        <!-- ==================== 基础设置 ==================== -->
        <div class="form-section">
            <div class="section-header"><h3>基础设置</h3></div>
            <a-row :gutter="24">
                <a-col :span="8">
                    <div class="form-item">
                        <label>启用签到</label>
                        <a-select v-model:value="form.enabled" :disabled="disabled" style="width:100%">
                            <a-select-option :value="true">启用</a-select-option>
                            <a-select-option :value="false">禁用</a-select-option>
                        </a-select>
                    </div>
                </a-col>
                <a-col :span="8">
                    <div class="form-item">
                        <label>签到窗口起点</label>
                        <a-time-picker v-model:value="signWindowStartDT" format="HH:mm" :minute-step="5"
                            style="width:100%" :disabled="disabled" @change="onStartChange" />
                    </div>
                </a-col>
                <a-col :span="8">
                    <div class="form-item">
                        <label>签到窗口终点</label>
                        <a-time-picker v-model:value="signWindowEndDT" format="HH:mm" :minute-step="5"
                            style="width:100%" :disabled="disabled" @change="onEndChange" />
                    </div>
                </a-col>
                <a-col :span="8">
                    <div class="form-item">
                        <label>请求超时(秒)</label>
                        <a-input-number v-model:value="form.timeoutSeconds" :min="5" :max="120" style="width:100%" :disabled="disabled" />
                    </div>
                </a-col>
                <a-col :span="8">
                    <div class="form-item">
                        <label>签到后显示信息</label>
                        <a-select v-model:value="form.showInfoAfterSign" :disabled="disabled" style="width:100%">
                            <a-select-option :value="true">启用</a-select-option>
                            <a-select-option :value="false">禁用</a-select-option>
                        </a-select>
                    </div>
                </a-col>
                <a-col :span="8">
                    <div class="form-item">
                        <label>获取活动日历</label>
                        <a-select v-model:value="form.fetchEvents" :disabled="disabled" style="width:100%">
                            <a-select-option :value="true">启用</a-select-option>
                            <a-select-option :value="false">禁用</a-select-option>
                        </a-select>
                    </div>
                </a-col>
            </a-row>
        </div>

        <!-- ==================== 账号管理 ==================== -->
        <div class="form-section">
            <div class="section-header"><h3>账号管理</h3></div>

            <a-collapse ghost>
                <!-- 米游社 -->
                <a-collapse-panel key="mihoyo">
                    <template #header>
                        <span class="platform-label">米游社</span>
                        <a-tag v-if="form.mihoyoAccounts.length" color="blue" style="margin-left:8px">{{ form.mihoyoAccounts.length }}</a-tag>
                    </template>
                    <div v-for="(acc, idx) in form.mihoyoAccounts" :key="idx" class="account-card">
                        <div class="account-header">
                            <a-input v-model:value="acc.alias" placeholder="账号别名（可选）" style="width:200px" :disabled="disabled" />
                            <a-button type="text" danger :disabled="disabled" @click="form.mihoyoAccounts.splice(idx, 1)">
                                <DeleteOutlined /> 删除
                            </a-button>
                        </div>
                        <div class="form-item">
                            <label>Cookie</label>
                            <a-input-password v-model:value="acc.cookie" placeholder="粘贴完整 Cookie（包含 ltoken/ltuid/cookie_token 等字段）" :disabled="disabled" visibilityToggle />
                        </div>
                        <a-space class="account-toggles">
                            <a-checkbox v-model:checked="acc.enable_genshin" :disabled="disabled">原神</a-checkbox>
                            <a-checkbox v-model:checked="acc.enable_starrail" :disabled="disabled">崩铁</a-checkbox>
                            <a-checkbox v-model:checked="acc.enable_zzz" :disabled="disabled">绝区零</a-checkbox>
                            <a-checkbox v-model:checked="acc.enable_honkai3" :disabled="disabled">崩坏3</a-checkbox>
                            <a-checkbox v-model:checked="acc.enable_bbs_tasks" :disabled="disabled">米游币任务</a-checkbox>
                        </a-space>
                    </div>
                    <a-button type="link" :disabled="disabled" @click="addMihoyo">
                        <PlusOutlined /> 添加账号
                    </a-button>
                </a-collapse-panel>

                <!-- 库洛 -->
                <a-collapse-panel key="kuro">
                    <template #header>
                        <span class="platform-label">库洛</span>
                        <a-tag v-if="form.kuroAccounts.length" color="blue" style="margin-left:8px">{{ form.kuroAccounts.length }}</a-tag>
                    </template>
                    <div v-for="(acc, idx) in form.kuroAccounts" :key="idx" class="account-card">
                        <div class="account-header">
                            <a-input v-model:value="acc.alias" placeholder="账号别名（可选）" style="width:200px" :disabled="disabled" />
                            <a-button type="text" danger :disabled="disabled" @click="form.kuroAccounts.splice(idx, 1)">
                                <DeleteOutlined /> 删除
                            </a-button>
                        </div>
                        <div class="form-item">
                            <label>Token</label>
                            <a-input-password v-model:value="acc.token" placeholder="粘贴库街区 Token（登录后抓包获取）" :disabled="disabled" visibilityToggle />
                        </div>
                        <a-space class="account-toggles">
                            <a-checkbox v-model:checked="acc.enable_kuro_bbs" :disabled="disabled">库街区社区</a-checkbox>
                            <a-checkbox v-model:checked="acc.enable_wuwa" :disabled="disabled">鸣潮</a-checkbox>
                        </a-space>
                    </div>
                    <a-button type="link" :disabled="disabled" @click="addKuro">
                        <PlusOutlined /> 添加账号
                    </a-button>
                </a-collapse-panel>

                <!-- 森空岛 -->
                <a-collapse-panel key="skland">
                    <template #header>
                        <span class="platform-label">森空岛</span>
                        <a-tag v-if="form.sklandAccounts.length" color="blue" style="margin-left:8px">{{ form.sklandAccounts.length }}</a-tag>
                    </template>
                    <div v-for="(acc, idx) in form.sklandAccounts" :key="idx" class="account-card">
                        <div class="account-header">
                            <a-input v-model:value="acc.alias" placeholder="账号别名（可选）" style="width:200px" :disabled="disabled" />
                            <a-button type="text" danger :disabled="disabled" @click="form.sklandAccounts.splice(idx, 1)">
                                <DeleteOutlined /> 删除
                            </a-button>
                        </div>
                        <div class="form-item">
                            <label>Token</label>
                            <a-input-password v-model:value="acc.token" placeholder="粘贴森空岛 Token" :disabled="disabled" visibilityToggle />
                        </div>
                        <a-space class="account-toggles">
                            <a-checkbox v-model:checked="acc.enable_arknights" :disabled="disabled">明日方舟</a-checkbox>
                            <a-checkbox v-model:checked="acc.enable_bbs" :disabled="disabled">森空岛社区</a-checkbox>
                        </a-space>
                    </div>
                    <a-button type="link" :disabled="disabled" @click="addSkland">
                        <PlusOutlined /> 添加账号
                    </a-button>
                </a-collapse-panel>
            </a-collapse>
        </div>

        <!-- ==================== 保存 ==================== -->
        <div class="save-bar">
            <a-button type="primary" size="large" :loading="saveLoading" :disabled="disabled" @click="handleSave">
                <SaveOutlined /> 保存
            </a-button>
        </div>
    </div>
</template>

<style scoped>
.tool-intro {
    background: var(--ant-color-bg-container);
    border: 1px solid var(--ant-color-border);
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 16px;
}
.tool-intro .card-header { font-size: 15px; font-weight: 600; color: var(--ant-color-primary); margin-bottom: 4px; }
.tool-intro .intro-text { margin: 0; font-size: 13px; color: var(--ant-color-text-secondary); }

.form-section {
    background: var(--ant-color-bg-container); border: 1px solid var(--ant-color-border);
    border-radius: 8px; padding: 16px 20px; margin-bottom: 12px;
}
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.section-header h3 { margin: 0; font-size: 15px; font-weight: 600; }

.form-item { display: flex; flex-direction: column; gap: 4px; margin-bottom: 8px; }
.form-item label { font-weight: 500; font-size: 13px; color: var(--ant-color-text); }

.platform-label { font-weight: 600; font-size: 14px; }

.account-card {
    border: 1px solid var(--ant-color-border-secondary); border-radius: 6px;
    padding: 12px 16px; margin-bottom: 8px;
}
.account-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.account-toggles { margin-top: 4px; }

.result-section { border-color: var(--ant-color-primary); border-width: 1px; }
.status-cards { margin-bottom: 12px; }
.status-card {
    background: var(--ant-color-fill-secondary); border-radius: 6px;
    padding: 10px 14px; text-align: center;
}
.status-card-label { font-size: 12px; color: var(--ant-color-text-tertiary); margin-bottom: 4px; }
.status-card-value { font-size: 14px; font-weight: 600; color: var(--ant-color-text); }

.sign-report { margin-top: 12px; }
.report-label { font-size: 13px; font-weight: 500; color: var(--ant-color-text-secondary); margin-bottom: 6px; }
.report-content {
    background: var(--ant-color-fill-secondary); border-radius: 6px;
    padding: 12px; font-size: 12px; line-height: 1.6; white-space: pre-wrap;
    max-height: 300px; overflow-y: auto; margin: 0;
}
.sign-details { margin-top: 12px; }

.save-bar { display: flex; justify-content: center; padding: 16px 0; }
</style>
