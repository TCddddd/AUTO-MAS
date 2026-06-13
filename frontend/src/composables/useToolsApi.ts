import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { Service, type ToolsConfig } from '@/api'

export function useToolsApi() {
    const loading = ref(false)
    const logger = window.electronAPI.getLogger('工具API')

    /**
     * 获取工具
     */
    const getTools = async (): Promise<ToolsConfig> => {
        loading.value = true
        try {
            logger.info('请求获取工具配置...')
            const response = await Service.getToolsApiToolsGetPost()
            logger.info(`获取工具响应: code=${response.code}, data keys=${Object.keys(response.data || {}).join(',')}`)
            if (response.code !== 200) {
                throw new Error(response.message || '获取工具失败')
            }
            return response.data
        } catch (error) {
            const errorMsg = error instanceof Error ? error.message : String(error)
            logger.error(`获取工具失败: ${errorMsg}`)
            message.error('获取工具失败')
            throw error
        } finally {
            loading.value = false
        }
    }

    /**
     * 更新工具
     */
    const updateTools = async (data: ToolsConfig): Promise<void> => {
        loading.value = true
        try {
            logger.info(`发送更新数据: ${JSON.stringify(data).substring(0, 200)}`)
            const response = await Service.updateToolsApiToolsUpdatePost({ data })
            logger.info(`更新响应: ${JSON.stringify(response).substring(0, 200)}`)
            if (response.code !== 200) {
                throw new Error(response.message || '更新工具失败')
            }
            logger.info('工具更新成功')
            message.success('保存成功')
        } catch (error) {
            const errorMsg = error instanceof Error ? error.message : String(error)
            logger.error(`更新工具失败: ${errorMsg}`)
            logger.error(`错误详情: ${JSON.stringify(error)}`)
            message.error('保存失败')
            throw error
        } finally {
            loading.value = false
        }
    }

    return {
        loading,
        getTools,
        updateTools,
    }
}
