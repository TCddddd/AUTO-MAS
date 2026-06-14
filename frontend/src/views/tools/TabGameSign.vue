<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import {
    PlusOutlined, DeleteOutlined, ReloadOutlined,
    ThunderboltOutlined, SaveOutlined,
} from '@ant-design/icons-vue'
import { useGameSignApi } from '@/composables/useGameSignApi'
import { useStatusTag, createStatusTag } from '@/composables/useStatusTag'
import dayjs from 'dayjs'

defineProps<{ disabled?: boolean }>()

const { signNow, refreshInfo, getStatus, getConfig, updateConfig } = useGameSignApi()
const saveLoading = ref(false)
const signLoading = ref(false)
const refreshLoading = ref(false)
const statusInfo = reactive({
    status: '未知', next_sign_time: '', last_sign_time: '',
    last_report: '', results: [] as any[], infos: [] as any[],
})
const statusTag = useStatusTag(() => statusInfo.status, createStatusTag('未配置', 'default'))

// ==================== 编辑状态（独立管理） ====================
const form = reactive({
    enabled: false, signWindowStart: '08:00', signWindowEnd: '22:00',
    timeoutSeconds: 20, showInfoAfterSign: true, fetchEvents: true,
    mihoyoAccounts: [] as Record<string, any>[],
    kuroAccounts: [] as Record<string, any>[],
    sklandAccounts: [] as Record<string, any>[],
})
const signWindowStartDT = ref(dayjs('08:00', 'HH:mm'))
const signWindowEndDT = ref(dayjs('22:00', 'HH:mm'))

const onStartChange = (time: any) => { if (time) form.signWindowStart = time.format('HH:mm') }
const onEndChange = (time: any) => { if (time) form.signWindowEnd = time.format('HH:mm') }

// ==================== 平台卡片（账号标签 + 签到奖励） ====================
// 后端游戏名 → 前端显示名
const gameNameMap: Record<string, string> = {
    '库街区社区': '战双帕弥什',
}
const mapGameName = (name: string) => gameNameMap[name] || name

const platformCards = computed(() => {
    const platforms = [
        { key: 'mihoyo', name: '米游社', desc: '原神 / 崩铁 / 绝区零 / 崩坏3', color: '#1677ff' },
        { key: 'kuro', name: '库街区', desc: '鸣潮 / 战双帕弥什', color: '#722ed1' },
        { key: 'skland', name: '森空岛', desc: '明日方舟 / 终末地', color: '#13c2c2' },
    ]
    return platforms.map(p => {
        const results = statusInfo.results.filter((r: any) => r.provider === p.key)
        const extractAlias = (account: string) => {
            if (!account) return '未知'
            if (account.includes('/')) {
                return account.split('/', 1)[0].trim()
            }
            return account
        }
        const accountMap = new Map<string, { signed: boolean; rewards: string[]; games: string[] }>()
        for (const r of results) {
            const alias = extractAlias(r.account || '未知')
            const displayName = mapGameName(r.game || '')
            const existing = accountMap.get(alias)
            if (existing) {
                existing.signed = existing.signed || r.success || r.already_signed
                if (r.reward && !existing.rewards.includes(r.reward)) existing.rewards.push(r.reward)
                if (displayName && !existing.games.includes(displayName)) existing.games.push(displayName)
            } else {
                accountMap.set(alias, {
                    signed: r.success || r.already_signed,
                    rewards: r.reward ? [r.reward] : [],
                    games: displayName ? [displayName] : [],
                })
            }
        }
        const accounts = Array.from(accountMap.entries()).map(([name, data]) => ({
            name, ...data,
        }))
        const totalAccounts = accounts.length
        const signedCount = accounts.filter(a => a.signed).length
        // 签到奖励汇总
        const allRewards = accounts.flatMap(a => a.rewards).filter(Boolean)
        return { ...p, accounts, totalAccounts, signedCount, rewards: allRewards }
    })
})

// ==================== 加载（带重试） ====================
const loadData = async (retries = 3) => {
    for (let i = 0; i < retries; i++) {
        try {
            const config = await getConfig()
            if (config && Object.keys(config).length > 0) {
                form.enabled = config.Enabled ?? false
                form.signWindowStart = config.SignWindowStart ?? '08:00'
                form.signWindowEnd = config.SignWindowEnd ?? '22:00'
                form.timeoutSeconds = config.TimeoutSeconds ?? 20
                form.showInfoAfterSign = config.ShowInfoAfterSign ?? true
                form.fetchEvents = config.FetchEvents ?? true
                form.mihoyoAccounts = (config.MihoyoAccounts || []).map((a: any) => ({ ...a }))
                form.kuroAccounts = (config.KuroAccounts || []).map((a: any) => ({ ...a }))
                form.sklandAccounts = (config.SklandAccounts || []).map((a: any) => ({ ...a }))
                signWindowStartDT.value = dayjs(form.signWindowStart, 'HH:mm')
                signWindowEndDT.value = dayjs(form.signWindowEnd, 'HH:mm')
                return
            }
        } catch { /* 重试 */ }
        await new Promise(r => setTimeout(r, 1000))
    }
    form.mihoyoAccounts = []; form.kuroAccounts = []; form.sklandAccounts = []
}

const loadStatusData = async (retries = 3) => {
    for (let i = 0; i < retries; i++) {
        try {
            const s = await getStatus()
            if (s && s.status) {
                Object.assign(statusInfo, s)
                return
            }
        } catch { /* 重试 */ }
        await new Promise(r => setTimeout(r, 1500))
    }
}

// ==================== 保存 ====================
const handleSave = async () => {
    saveLoading.value = true
    try {
        await updateConfig({
            Enabled: form.enabled, SignWindowStart: form.signWindowStart,
            SignWindowEnd: form.signWindowEnd, TimeoutSeconds: form.timeoutSeconds,
            ShowInfoAfterSign: form.showInfoAfterSign, FetchEvents: form.fetchEvents,
            MihoyoAccounts: form.mihoyoAccounts.filter(a => (a.cookie || '').trim()),
            KuroAccounts: form.kuroAccounts.filter(a => (a.token || '').trim()),
            SklandAccounts: form.sklandAccounts.filter(a => (a.token || '').trim()),
        })
        await loadStatusData()
    } finally { saveLoading.value = false }
}

const handleSignNow = async () => {
    signLoading.value = true
    try { await signNow(); await loadStatusData() } finally { signLoading.value = false }
}
const handleRefreshInfo = async () => {
    refreshLoading.value = true
    try { await refreshInfo(); await loadStatusData() } finally { refreshLoading.value = false }
}

// ==================== 账号管理 ====================
const addMihoyo = () => form.mihoyoAccounts.push({ alias: '', cookie: '', enable_genshin: true, enable_starrail: true, enable_zzz: false, enable_honkai3: false, enable_bbs_tasks: true })
const addKuro = () => form.kuroAccounts.push({ alias: '', token: '', enable_kuro_bbs: true, enable_wuwa: true })
const addSkland = () => form.sklandAccounts.push({ alias: '', token: '', enable_arknights: true })

const formatTime = (t: string) => {
    if (!t) return '--'
    try { return dayjs(t).format('MM-DD HH:mm') } catch { return t }
}
const accountCount = () => form.mihoyoAccounts.length + form.kuroAccounts.length + form.sklandAccounts.length

onMounted(async () => {
    await loadData()
    await loadStatusData()
})
</script>

<template>
    <div class="tab-content">
        <div class="tool-intro">
            <div class="card-header">游戏社区签到</div>
            <p class="intro-text">自动完成米游社、库街区、森空岛的每日社区签到和游戏签到。</p>
        </div>

        <!-- ==================== 签到状态概览 ==================== -->
        <div class="status-overview">
            <div class="status-main">
                <div class="status-item">
                    <span class="status-label">状态</span>
                    <a-tag v-if="statusTag" :color="statusTag.color" size="small">{{ statusTag.text }}</a-tag>
                </div>
                <div class="status-item">
                    <span class="status-label">上次签到</span>
                    <span class="status-val">{{ formatTime(statusInfo.last_sign_time) }}</span>
                </div>
                <div class="status-item">
                    <span class="status-label">下次签到</span>
                    <span class="status-val">{{ formatTime(statusInfo.next_sign_time) }}</span>
                </div>
                <div class="status-item">
                    <span class="status-label">账号</span>
                    <span class="status-val">{{ accountCount() }}</span>
                </div>
            </div>
            <div class="status-actions">
                <a-button type="primary" size="small" :loading="signLoading" :disabled="disabled" @click="handleSignNow">
                    <ThunderboltOutlined /> 立即签到
                </a-button>
                <a-button size="small" :loading="refreshLoading" :disabled="disabled" @click="handleRefreshInfo">
                    <ReloadOutlined />
                </a-button>
            </div>
        </div>

        <!-- ==================== 平台卡片（账号标签 + 体力信息） ==================== -->
        <div class="platform-cards">
            <div v-for="p in platformCards" :key="p.key" class="platform-card">
                <!-- 顶部：图标 + 标题 + 描述 + 状态 -->
                <div class="pc-header">
                    <div class="pc-header-left">
                        <div class="pc-icon" :style="{ background: p.color + '14', color: p.color }">
                            <ThunderboltOutlined />
                        </div>
                        <div class="pc-title-group">
                            <span class="pc-name">{{ p.name }}</span>
                            <span class="pc-desc">{{ p.desc }}</span>
                        </div>
                    </div>
                    <div class="pc-status">
                        <span class="pc-status-count">{{ p.signedCount }}</span>
                        <span class="pc-status-label"> / {{ p.totalAccounts }} 可用</span>
                    </div>
                </div>

                <!-- 中间：账号标签 + 签到状态 -->
                <div class="pc-body">
                    <div v-if="p.accounts.length === 0" class="pc-empty">暂无账号</div>
                    <div v-else class="pc-tags">
                        <span v-for="(acc, idx) in p.accounts" :key="idx" class="pc-tag">
                            <span class="pc-tag-label">{{ acc.name }}</span>
                            <span class="pc-tag-dot" :class="acc.signed ? 'pc-tag-dot--green' : 'pc-tag-dot--red'"></span>
                        </span>
                    </div>
                    <!-- 签到结果摘要 -->
                    <div v-if="p.accounts.length > 0" class="pc-results">
                        <div v-for="(acc, idx) in p.accounts" :key="'r' + idx" class="pc-result-row">
                            <span class="pc-result-game">{{ acc.games.join(' / ') }}</span>
                            <span v-if="acc.signed" class="pc-result-status pc-result-status--ok">成功</span>
                            <span v-else class="pc-result-status pc-result-status--fail">未签到</span>
                        </div>
                    </div>
                </div>

                <!-- 底部：签到奖励 -->
                <div v-if="p.rewards.length > 0" class="pc-footer">
                    <div class="pc-info-divider"></div>
                    <div class="pc-rewards-title">签到奖励</div>
                    <div class="pc-rewards-list">
                        <span v-for="(reward, i) in p.rewards" :key="i" class="pc-reward-tag">{{ reward }}</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- ==================== 基础设置 ==================== -->
        <div class="form-section">
            <div class="section-header"><h3>基础设置</h3></div>
            <div class="form-grid">
                <div class="form-field">
                    <label>启用签到</label>
                    <a-select v-model:value="form.enabled" :disabled="disabled" size="large">
                        <a-select-option :value="true">启用</a-select-option>
                        <a-select-option :value="false">禁用</a-select-option>
                    </a-select>
                </div>
                <div class="form-field">
                    <label>签到窗口起点</label>
                    <a-time-picker v-model:value="signWindowStartDT" format="HH:mm" :minute-step="5"
                        size="large" :disabled="disabled" @change="onStartChange" style="width:100%" />
                </div>
                <div class="form-field">
                    <label>签到窗口终点</label>
                    <a-time-picker v-model:value="signWindowEndDT" format="HH:mm" :minute-step="5"
                        size="large" :disabled="disabled" @change="onEndChange" style="width:100%" />
                </div>
                <div class="form-field">
                    <label>请求超时(秒)</label>
                    <a-input-number v-model:value="form.timeoutSeconds" :min="5" :max="120" size="large" style="width:100%" :disabled="disabled" />
                </div>
                <div class="form-field">
                    <label>签到后显示信息</label>
                    <a-select v-model:value="form.showInfoAfterSign" :disabled="disabled" size="large">
                        <a-select-option :value="true">启用</a-select-option>
                        <a-select-option :value="false">禁用</a-select-option>
                    </a-select>
                </div>
                <div class="form-field">
                    <label>获取活动日历</label>
                    <a-select v-model:value="form.fetchEvents" :disabled="disabled" size="large">
                        <a-select-option :value="true">启用</a-select-option>
                        <a-select-option :value="false">禁用</a-select-option>
                    </a-select>
                </div>
            </div>
        </div>

        <!-- ==================== 账号管理 ==================== -->
        <div class="form-section">
            <div class="section-header"><h3>账号管理</h3></div>
            <a-collapse ghost>
                <!-- 米游社 -->
                <a-collapse-panel key="mihoyo">
                    <template #header>
                        <span class="platform-label">米游社</span>
                        <a-tag v-if="form.mihoyoAccounts.length" color="blue" size="small" style="margin-left:8px">{{ form.mihoyoAccounts.length }}</a-tag>
                    </template>
                    <div v-for="(acc, idx) in form.mihoyoAccounts" :key="idx" class="account-card">
                        <div class="account-header">
                            <a-input v-model:value="acc.alias" placeholder="账号别名（可选）" style="width:200px" :disabled="disabled" />
                            <a-button type="text" danger size="small" :disabled="disabled" @click="form.mihoyoAccounts.splice(idx, 1)"><DeleteOutlined /> 删除</a-button>
                        </div>
                        <div class="form-field">
                            <label>Cookie</label>
                            <a-input-password v-model:value="acc.cookie" placeholder="粘贴完整 Cookie" :disabled="disabled" visibilityToggle size="large" />
                        </div>
                    </div>
                    <a-button type="link" size="small" :disabled="disabled" @click="addMihoyo"><PlusOutlined /> 添加账号</a-button>
                </a-collapse-panel>

                <!-- 库洛 -->
                <a-collapse-panel key="kuro">
                    <template #header>
                        <span class="platform-label">库街区</span>
                        <a-tag v-if="form.kuroAccounts.length" color="blue" size="small" style="margin-left:8px">{{ form.kuroAccounts.length }}</a-tag>
                    </template>
                    <div v-for="(acc, idx) in form.kuroAccounts" :key="idx" class="account-card">
                        <div class="account-header">
                            <a-input v-model:value="acc.alias" placeholder="账号别名（可选）" style="width:200px" :disabled="disabled" />
                            <a-button type="text" danger size="small" :disabled="disabled" @click="form.kuroAccounts.splice(idx, 1)"><DeleteOutlined /> 删除</a-button>
                        </div>
                        <div class="form-field">
                            <label>Token</label>
                            <a-input-password v-model:value="acc.token" placeholder="粘贴库街区 Token" :disabled="disabled" visibilityToggle size="large" />
                        </div>
                    </div>
                    <a-button type="link" size="small" :disabled="disabled" @click="addKuro"><PlusOutlined /> 添加账号</a-button>
                </a-collapse-panel>

                <!-- 森空岛 -->
                <a-collapse-panel key="skland">
                    <template #header>
                        <span class="platform-label">森空岛</span>
                        <a-tag v-if="form.sklandAccounts.length" color="blue" size="small" style="margin-left:8px">{{ form.sklandAccounts.length }}</a-tag>
                    </template>
                    <div v-for="(acc, idx) in form.sklandAccounts" :key="idx" class="account-card">
                        <div class="account-header">
                            <a-input v-model:value="acc.alias" placeholder="账号别名（可选）" style="width:200px" :disabled="disabled" />
                            <a-button type="text" danger size="small" :disabled="disabled" @click="form.sklandAccounts.splice(idx, 1)"><DeleteOutlined /> 删除</a-button>
                        </div>
                        <div class="form-field">
                            <label>Token</label>
                            <a-input-password v-model:value="acc.token" placeholder="粘贴森空岛 Token" :disabled="disabled" visibilityToggle size="large" />
                        </div>
                    </div>
                    <a-button type="link" size="small" :disabled="disabled" @click="addSkland"><PlusOutlined /> 添加账号</a-button>
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
    background: var(--ant-color-bg-container); border: 1px solid var(--ant-color-border);
    border-radius: 8px; padding: 14px 18px; margin-bottom: 12px;
}
.tool-intro .card-header { font-size: 15px; font-weight: 600; color: var(--ant-color-primary); margin-bottom: 2px; }
.tool-intro .intro-text { margin: 0; font-size: 12px; color: var(--ant-color-text-secondary); }

/* 签到状态概览 */
.status-overview {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 16px; margin-bottom: 12px;
    background: var(--ant-color-bg-container); border: 1px solid var(--ant-color-border); border-radius: 8px;
}
.status-main { display: flex; align-items: center; gap: 20px; }
.status-actions { display: flex; gap: 8px; }
.status-item { display: flex; flex-direction: column; align-items: center; gap: 2px; min-width: 80px; }
.status-label { font-size: 11px; color: var(--ant-color-text-tertiary); }
.status-val { font-size: 13px; font-weight: 500; }

/* ==================== 平台卡片（账号标签 + 体力信息） ==================== */
.platform-cards {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
    margin-bottom: 12px;
}
.platform-card {
    background: #fff; border: 1px solid #e8e8e8; border-radius: 10px;
    padding: 16px; display: flex; flex-direction: column; gap: 12px;
    transition: box-shadow 0.2s;
}
.platform-card:hover { box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06); }

/* 顶部 */
.pc-header {
    display: flex; align-items: flex-start; justify-content: space-between;
}
.pc-header-left { display: flex; align-items: center; gap: 10px; }
.pc-icon {
    width: 36px; height: 36px; border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 16px; flex-shrink: 0;
}
.pc-title-group { display: flex; flex-direction: column; gap: 1px; }
.pc-name { font-size: 14px; font-weight: 600; color: #1a1a1a; }
.pc-desc { font-size: 11px; color: #999; }
.pc-status { text-align: right; flex-shrink: 0; }
.pc-status-count { font-size: 16px; font-weight: 700; color: #1677ff; }
.pc-status-label { font-size: 11px; color: #999; }

/* 中间：账号标签 */
.pc-body { min-height: 40px; }
.pc-empty { font-size: 12px; color: #bbb; text-align: center; padding: 12px 0; }
.pc-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.pc-tag {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 5px 10px; border-radius: 20px;
    background: #f5f5f5; border: 1px solid #e8e8e8;
    font-size: 12px; color: #333; user-select: none;
}
.pc-tag-label { max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pc-tag-dot {
    width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
}
.pc-tag-dot--green { background: #52c41a; }
.pc-tag-dot--red { background: #ff4d4f; }

/* 签到结果摘要 */
.pc-results { display: flex; flex-direction: column; gap: 3px; }
.pc-result-row {
    display: flex; align-items: center; justify-content: space-between;
    font-size: 12px;
}
.pc-result-game { color: #666; }
.pc-result-status { font-weight: 500; }
.pc-result-status--ok { color: #52c41a; }
.pc-result-status--fail { color: #ff4d4f; }

/* 底部：签到奖励 */
.pc-footer { }
.pc-info-divider { height: 1px; background: #f0f0f0; margin: 8px 0; }
.pc-rewards-title { font-size: 12px; font-weight: 500; color: #333; margin-bottom: 6px; }
.pc-rewards-list { display: flex; flex-wrap: wrap; gap: 6px; }
.pc-reward-tag {
    padding: 3px 8px; border-radius: 4px; font-size: 11px;
    background: #f6ffed; color: #52c41a; border: 1px solid #b7eb8f;
}

/* ==================== 表单区域（MAS 风格） ==================== */
.form-section {
    background: var(--ant-color-bg-container); border: 1px solid var(--ant-color-border);
    border-radius: 8px; padding: 16px 20px; margin-bottom: 12px;
}
.section-header {
    margin-bottom: 16px; padding-bottom: 8px;
    border-bottom: 1px solid var(--ant-color-border-secondary);
}
.section-header h3 {
    margin: 0; font-size: 15px; font-weight: 700; color: var(--ant-color-text);
}

.form-grid {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px 24px;
}
.form-field { display: flex; flex-direction: column; gap: 6px; }
.form-field label {
    font-size: 13px; font-weight: 500; color: var(--ant-color-text);
    display: flex; align-items: center; gap: 4px;
}

/* 账号管理 */
.platform-label { font-weight: 600; font-size: 13px; }
.account-card {
    border: 1px solid var(--ant-color-border-secondary); border-radius: 8px;
    padding: 12px 14px; margin-bottom: 8px;
}
.account-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }

.save-bar { display: flex; justify-content: center; padding: 12px 0; }
</style>
