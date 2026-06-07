import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import type { AgentProfile } from '@/types/agent'

export interface AgentStatusItem {
  name: string
  status: string
  queue_size: number
  stats: {
    tasks_completed: number
    errors: number
    last_active: string | null
    action_stats?: Record<string, any>
    cache_size?: number
  }
  profile: {
    display_name: string
    model: string
    temperature: number
    enabled: boolean
  }
}

export const useAgentsStore = defineStore('agents', () => {
  const api = useApi()
  const { success, error } = useToast()

  const profiles = ref<Record<string, AgentProfile>>({})
  const agentStatuses = ref<AgentStatusItem[]>([])
  const loading = ref(false)

  async function fetchProfiles() {
    loading.value = true
    try {
      const data = await api.get('/api/agents/profiles')
      profiles.value = data.profiles || {}
    } catch (e: any) {
      error(`加载 Agent 配置失败: ${e.message}`)
    } finally {
      loading.value = false
    }
  }

  async function updateProfile(name: string, data: Partial<AgentProfile>) {
    try {
      await api.put(`/api/agents/profiles/${name}`, data)
      success(`${name} 配置已更新`)
      await fetchProfiles()
    } catch (e: any) {
      error(`更新失败: ${e.message}`)
    }
  }

  async function resetProfile(name: string) {
    try {
      await api.post(`/api/agents/profiles/${name}/reset`)
      success(`${name} 已恢复默认`)
      await fetchProfiles()
    } catch (e: any) {
      error(`重置失败: ${e.message}`)
    }
  }

  async function fetchAgentStatus() {
    try {
      const data = await api.get('/api/agents/status')
      agentStatuses.value = data.agents || []
    } catch {}
  }

  async function startAgent(name: string) {
    try {
      await api.post(`/api/agents/${name}/start`)
      success(`${name} 已启动`)
      await fetchAgentStatus()
    } catch (e: any) {
      error(`启动失败: ${e.message}`)
    }
  }

  async function stopAgent(name: string) {
    try {
      await api.post(`/api/agents/${name}/stop`)
      success(`${name} 已停止`)
      await fetchAgentStatus()
    } catch (e: any) {
      error(`停止失败: ${e.message}`)
    }
  }

  async function runPipeline() {
    try {
      await api.post('/api/agents/pipeline')
      success('全流程已启动')
    } catch (e: any) {
      error(`启动失败: ${e.message}`)
    }
  }

  function getAgentStatus(name: string) {
    return agentStatuses.value.find(s => s.name === name)
  }

  return {
    profiles, agentStatuses, loading,
    fetchProfiles, updateProfile, resetProfile,
    fetchAgentStatus, startAgent, stopAgent, runPipeline, getAgentStatus,
  }
})
