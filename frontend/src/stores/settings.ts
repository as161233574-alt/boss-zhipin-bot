import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import type { Settings } from '@/types/settings'

export const useSettingsStore = defineStore('settings', () => {
  const api = useApi()
  const { success, error } = useToast()

  const settings = ref<Settings | null>(null)
  const loading = ref(false)
  const saving = ref(false)

  async function fetchSettings() {
    loading.value = true
    try {
      const data = await api.get('/api/settings')
      settings.value = data.settings || data
    } catch (e: any) {
      error(`加载设置失败: ${e.message}`)
    } finally {
      loading.value = false
    }
  }

  async function updateSettings(data: Partial<Settings>) {
    saving.value = true
    try {
      await api.put('/api/settings', data)
      // 重新获取完整设置
      await fetchSettings()
      success('设置已保存')
    } catch (e: any) {
      error(`保存失败: ${e.message}`)
    } finally {
      saving.value = false
    }
  }

  async function generateSmartGreeting() {
    try {
      const data = await api.post('/api/settings/smart-greeting')
      return data.greeting || data
    } catch (e: any) {
      error(`生成失败: ${e.message}`)
      return null
    }
  }

  async function uploadResume(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    try {
      const data = await api.post('/api/settings/resume/upload', formData)
      success('简历已上传')
      await fetchSettings()
      return data
    } catch (e: any) {
      error(`上传失败: ${e.message}`)
      return null
    }
  }

  async function clearResume() {
    try {
      await api.del('/api/settings/resume')
      success('简历已清除')
      await fetchSettings()
    } catch (e: any) {
      error(`清除失败: ${e.message}`)
    }
  }

  function handleUpdate(data: any) {
    if (data?.settings) settings.value = data.settings
    else fetchSettings()
  }

  return {
    settings, loading, saving,
    fetchSettings, updateSettings, generateSmartGreeting,
    uploadResume, clearResume, handleUpdate,
  }
})
