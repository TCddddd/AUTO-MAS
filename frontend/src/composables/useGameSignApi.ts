import { ref } from 'vue'
import { message } from 'ant-design-vue'
import axios from 'axios'
import { OpenAPI } from '@/api/core/OpenAPI'

const api = axios.create({ baseURL: OpenAPI.BASE || 'http://localhost:36163' })

export interface GameSignAccount {
    alias?: string
    cookie?: string
    token?: string
    cred?: string
    enabled?: boolean
    enable_genshin?: boolean
    enable_starrail?: boolean
    enable_zzz?: boolean
    enable_honkai3?: boolean
    enable_kuro_bbs?: boolean
    enable_wuwa?: boolean
    enable_arknights?: boolean
}

export interface GameSignConfig {
    Enabled?: boolean
    SignWindowStart?: string
    SignWindowEnd?: string
    TimeoutSeconds?: number
    ShowInfoAfterSign?: boolean
    WidgetRefreshSeconds?: number
    FetchEvents?: boolean
    MihoyoAccounts?: GameSignAccount[]
    KuroAccounts?: GameSignAccount[]
    SklandAccounts?: GameSignAccount[]
    NotifyFormat?: string
}

export function useGameSignApi() {
    const loading = ref(false)
    const logger = window.electronAPI.getLogger('游戏签到API')

    const signNow = async (): Promise<string> => {
        loading.value = true
        try {
            const { data: res } = await api.post('/api/gamesign/sign-now')
            if (res.code !== 200) throw new Error(res.message)
            message.success('签到完成')
            return res.data?.report || ''
        } catch (error) {
            const msg = error instanceof Error ? error.message : String(error)
            logger.error(`签到失败: ${msg}`)
            message.error('签到失败')
            throw error
        } finally {
            loading.value = false
        }
    }

    const refreshInfo = async (): Promise<any[]> => {
        loading.value = true
        try {
            const { data: res } = await api.post('/api/gamesign/refresh-info')
            if (res.code !== 200) throw new Error(res.message)
            return res.data?.infos || []
        } catch (error) {
            message.error('刷新信息失败')
            throw error
        } finally {
            loading.value = false
        }
    }

    const snapshot = async (): Promise<any> => {
        try {
            const { data: res } = await api.post('/api/gamesign/snapshot')
            return res.data || {}
        } catch {
            return {}
        }
    }

    const getConfig = async (): Promise<GameSignConfig> => {
        loading.value = true
        try {
            const { data: res } = await api.post('/api/tools/get')
            return res.data?.GameSign || {}
        } catch (error) {
            message.error('获取配置失败')
            throw error
        } finally {
            loading.value = false
        }
    }

    const updateConfig = async (data: Record<string, any>): Promise<void> => {
        loading.value = true
        try {
            const { data: res } = await api.post('/api/tools/update', { data: { GameSign: data } })
            if (res.code !== 200) throw new Error(res.message)
            message.success('保存成功')
        } catch (error) {
            const msg = error instanceof Error ? error.message : String(error)
            logger.error(`更新配置失败: ${msg}`)
            message.error('保存失败')
            throw error
        } finally {
            loading.value = false
        }
    }

    const getStatus = async (): Promise<any> => {
        try {
            const { data: res } = await api.post('/api/gamesign/status')
            return res.data || {}
        } catch {
            return { status: '未知', next_sign_time: '未知' }
        }
    }

    return { loading, signNow, refreshInfo, snapshot, getConfig, updateConfig, getStatus }
}
