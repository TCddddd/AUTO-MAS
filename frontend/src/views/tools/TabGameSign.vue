<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { PlusOutlined, DeleteOutlined, ReloadOutlined, ThunderboltOutlined, SaveOutlined } from '@ant-design/icons-vue'
import { useGameSignApi, type GameSignConfig } from '@/composables/useGameSignApi'
import { useStatusTag, createStatusTag } from '@/composables/useStatusTag'

const props = defineProps<{
    config: GameSignConfig
    disabled?: boolean
    onFieldChange?: (key: string, value: any) => void
}>()

const { loading, signNow, refreshInfo, getStatus, updateConfig } = useGameSignApi()
const saveLoading = ref(false)
const signLoading = ref(false)
const refreshLoading = ref(false)
const statusInfo = reactive({ status: '未知', next_sign_time: '未设定' })

const statusTag = useStatusTag(
    () => statusInfo.status,
    createStatusTag('未配置', 'default')
)

// 本地编辑状态 - 深拷贝配置
const form = reactive({
    enabled: false,
    signWindowStart: '08:00',
    signWindowEnd: '22:00',
    timeoutSeconds: 20,
    showInfoAfterSign: true,
    fetchEvents: true,
    mihoyoAccounts: [] as string[],
    kuroAccounts: [] as string[],
    sklandAccounts: [] as string[],
})

const loadStatus = async () => {
    const s = await getStatus()
    Object.assign(statusInfo, s)
}

const loadForm = async () => {
    try {
        const config = await getConfig()
        form.enabled = config.Enabled ?? false
        form.signWindowStart = config.SignWindowStart ?? '08:00'
        form.signWindowEnd = config.SignWindowEnd ?? '22:00'
        form.timeoutSeconds = config.TimeoutSeconds ?? 20
        form.showInfoAfterSign = config.ShowInfoAfterSign ?? true
        form.fetchEvents = config.FetchEvents ?? true
        form.mihoyoAccounts = (config.MihoyoAccounts || []).map((a: any) => a.cookie || '')
        form.kuroAccounts = (config.KuroAccounts || []).map((a: any) => a.token || '')
        form.sklandAccounts = (config.SklandAccounts || []).map((a: any) => a.token || '')
    } catch {
        // 使用 props.config 的默认值
        form.enabled = props.config.Enabled ?? false
        form.signWindowStart = props.config.SignWindowStart ?? '08:00'
        form.signWindowEnd = props.config.SignWindowEnd ?? '22:00'
        form.timeoutSeconds = props.config.TimeoutSeconds ?? 20
        form.showInfoAfterSign = props.config.ShowInfoAfterSign ?? true
        form.fetchEvents = props.config.FetchEvents ?? true
        form.mihoyoAccounts = (props.config.MihoyoAccounts || []).map((a: any) => a.cookie || '')
        form.kuroAccounts = (props.config.KuroAccounts || []).map((a: any) => a.token || '')
        form.sklandAccounts = (props.config.SklandAccounts || []).map((a: any) => a.token || '')
    }
}

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
            MihoyoAccounts: form.mihoyoAccounts.filter(s => s.trim()).map(cookie => ({ cookie, alias: '', enabled: true, enable_genshin: true, enable_starrail: true, enable_zzz: false, enable_honkai3: false, enable_bbs_tasks: true })),
            KuroAccounts: form.kuroAccounts.filter(s => s.trim()).map(token => ({ token, alias: '', enabled: true, enable_kuro_bbs: true, enable_wuwa: true })),
            SklandAccounts: form.sklandAccounts.filter(s => s.trim()).map(token => ({ token, alias: '', enabled: true, enable_arknights: true, enable_bbs: true })),
        }
        await updateConfig(data)
        await loadStatus()
    } finally {
        saveLoading.value = false
    }
}

const handleSignNow = async () => {
    signLoading.value = true
    try {
        await signNow()
    } finally {
        signLoading.value = false
    }
}

const handleRefreshInfo = async () => {
    refreshLoading.value = true
    try {
        await refreshInfo()
    } finally {
        refreshLoading.value = false
    }
}

const addAccount = (list: string[]) => { list.push('') }
const removeAccount = (list: string[], index: number) => { list.splice(index, 1) }

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

        <div class="status-bar">
            <a-space>
                <a-tag v-if="statusTag" :color="statusTag.color">{{ statusTag.text }}</a-tag>
                <span v-if="statusInfo.next_sign_time && statusInfo.next_sign_time !== '未设定'" class="status-text">
                    下次签到: {{ statusInfo.next_sign_time }}
                </span>
            </a-space>
            <a-space>
                <a-button type="primary" :loading="signLoading" :disabled="disabled" @click="handleSignNow">
                    <ThunderboltOutlined /> 立即签到
                </a-button>
                <a-button :loading="refreshLoading" :disabled="disabled" @click="handleRefreshInfo">
                    <ReloadOutlined /> 刷新信息
                </a-button>
            </a-space>
        </div>

        <!-- 基础设置 -->
        <div class="form-section">
            <div class="section-header"><h3>基础设置</h3></div>
            <a-row :gutter="24">
                <a-col :span="8">
                    <div class="form-item">
                        <label>启用签到</label>
                        <a-switch v-model:checked="form.enabled" :disabled="disabled" />
                    </div>
                </a-col>
                <a-col :span="8">
                    <div class="form-item">
                        <label>签到窗口起点</label>
                        <a-input v-model:value="form.signWindowStart" placeholder="HH:MM" :disabled="disabled" />
                    </div>
                </a-col>
                <a-col :span="8">
                    <div class="form-item">
                        <label>签到窗口终点</label>
                        <a-input v-model:value="form.signWindowEnd" placeholder="HH:MM" :disabled="disabled" />
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
                        <a-switch v-model:checked="form.showInfoAfterSign" :disabled="disabled" />
                    </div>
                </a-col>
                <a-col :span="8">
                    <div class="form-item">
                        <label>获取活动日历</label>
                        <a-switch v-model:checked="form.fetchEvents" :disabled="disabled" />
                    </div>
                </a-col>
            </a-row>
        </div>

        <!-- 米游社账号 -->
        <div class="form-section">
            <div class="section-header"><h3>米游社账号</h3><span class="hint">公共查询cookie，允许添加多个</span></div>
            <div v-for="(cookie, idx) in form.mihoyoAccounts" :key="idx" class="account-row">
                <a-textarea v-model:value="form.mihoyoAccounts[idx]" :rows="2"
                    placeholder="粘贴完整 Cookie（包含 ltoken / ltuid / cookie_token / account_id 等字段）"
                    :disabled="disabled" />
                <a-button type="text" danger :disabled="disabled" @click="removeAccount(form.mihoyoAccounts, idx)">
                    <DeleteOutlined />
                </a-button>
            </div>
            <a-button type="link" :disabled="disabled" @click="addAccount(form.mihoyoAccounts)">
                <PlusOutlined /> 添加 Cookie
            </a-button>
        </div>

        <!-- 库洛账号 -->
        <div class="form-section">
            <div class="section-header"><h3>库洛账号</h3><span class="hint">库街区 token，允许添加多个</span></div>
            <div v-for="(token, idx) in form.kuroAccounts" :key="idx" class="account-row">
                <a-input v-model:value="form.kuroAccounts[idx]"
                    placeholder="粘贴库街区 Token（登录后抓包获取）"
                    :disabled="disabled" />
                <a-button type="text" danger :disabled="disabled" @click="removeAccount(form.kuroAccounts, idx)">
                    <DeleteOutlined />
                </a-button>
            </div>
            <a-button type="link" :disabled="disabled" @click="addAccount(form.kuroAccounts)">
                <PlusOutlined /> 添加 Token
            </a-button>
        </div>

        <!-- 森空岛账号 -->
        <div class="form-section">
            <div class="section-header"><h3>森空岛账号</h3><span class="hint">Hypergryph 通行证 token，允许添加多个</span></div>
            <div v-for="(token, idx) in form.sklandAccounts" :key="idx" class="account-row">
                <a-input v-model:value="form.sklandAccounts[idx]"
                    placeholder="粘贴森空岛 Token"
                    :disabled="disabled" />
                <a-button type="text" danger :disabled="disabled" @click="removeAccount(form.sklandAccounts, idx)">
                    <DeleteOutlined />
                </a-button>
            </div>
            <a-button type="link" :disabled="disabled" @click="addAccount(form.sklandAccounts)">
                <PlusOutlined /> 添加 Token
            </a-button>
        </div>

        <!-- 保存按钮 -->
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
.tool-intro .card-header {
    font-size: 15px;
    font-weight: 600;
    color: var(--ant-color-primary);
    margin-bottom: 4px;
}
.tool-intro .intro-text {
    margin: 0;
    font-size: 13px;
    color: var(--ant-color-text-secondary);
}

.status-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background: var(--ant-color-bg-container);
    border: 1px solid var(--ant-color-border);
    border-radius: 8px;
    margin-bottom: 16px;
}
.status-text {
    color: var(--ant-color-text-secondary);
    font-size: 13px;
}

.form-section {
    background: var(--ant-color-bg-container);
    border: 1px solid var(--ant-color-border);
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 12px;
}
.section-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
}
.section-header h3 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
}
.section-header .hint {
    font-size: 12px;
    color: var(--ant-color-text-tertiary);
}

.form-item {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 12px;
}
.form-item label {
    font-weight: 500;
    font-size: 13px;
    color: var(--ant-color-text);
}

.account-row {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin-bottom: 8px;
}
.account-row .ant-btn {
    margin-top: 4px;
}

.save-bar {
    display: flex;
    justify-content: center;
    padding: 16px 0;
}
</style>
