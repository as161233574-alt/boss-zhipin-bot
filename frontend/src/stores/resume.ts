import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import type { ResumeAction, ResumeStats } from '@/types/resume'

export const useResumeStore = defineStore('resume', () => {
  const api = useApi()
  const { success, error } = useToast()

  const history = ref<ResumeAction[]>([])
  const stats = ref<ResumeStats | null>(null)
  const loading = ref(false)
  const result = ref<any>(null)

  async function parseResume(fileBase64: string, fileName: string) {
    loading.value = true
    try {
      const data = await api.post('/api/agents/resume/parse', { file_base64: fileBase64, file_name: fileName })
      result.value = data
      success('简历解析完成')
      return data
    } catch (e: any) {
      error(`解析失败: ${e.message}`)
      return null
    } finally {
      loading.value = false
    }
  }

  async function optimizeResume(jd: string) {
    loading.value = true
    try {
      const data = await api.post('/api/agents/resume/optimize', { jd })
      result.value = data
      success('简历优化完成')
      return data
    } catch (e: any) {
      error(`优化失败: ${e.message}`)
      return null
    } finally {
      loading.value = false
    }
  }

  async function analyzeMatch(jd: string) {
    loading.value = true
    try {
      const data = await api.post('/api/agents/resume/analyze', { jd })
      result.value = data
      success('匹配分析完成')
      return data
    } catch (e: any) {
      error(`分析失败: ${e.message}`)
      return null
    } finally {
      loading.value = false
    }
  }

  async function generateCoverLetter(jd: string) {
    loading.value = true
    try {
      const data = await api.post('/api/agents/resume/cover-letter', { jd })
      result.value = data
      success('求职信生成完成')
      return data
    } catch (e: any) {
      error(`生成失败: ${e.message}`)
      return null
    } finally {
      loading.value = false
    }
  }

  async function fetchHistory() {
    try {
      const data = await api.get('/api/agents/resume/history')
      history.value = data.history || data || []
    } catch {}
  }

  async function fetchStats() {
    try {
      stats.value = await api.get('/api/agents/resume/stats')
    } catch {}
  }

  return {
    history, stats, loading, result,
    parseResume, optimizeResume, analyzeMatch, generateCoverLetter,
    fetchHistory, fetchStats,
  }
})
