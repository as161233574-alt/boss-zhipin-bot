import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'

export interface AppStats {
  today_applications: number
  pending: number
  replied: number
  interview: number
  active_conversations: number
  daily_stats: {
    date: string
    applications_sent: number
    messages_sent: number
    messages_received: number
    auto_replies_sent: number
  }
}

export interface TrendPoint {
  date: string
  applications_sent: number
  messages_sent: number
  messages_received: number
  auto_replies_sent: number
}

export interface FunnelData {
  pending: number
  applied: number
  replied: number
  interview: number
  apply_rate: number
  reply_rate: number
  interview_rate: number
}

export const useApplicationsStore = defineStore('applications', () => {
  const api = useApi()
  const { success, error } = useToast()

  const stats = ref<AppStats | null>(null)
  const trend = ref<TrendPoint[]>([])
  const funnel = ref<FunnelData | null>(null)
  const followups = ref<any[]>([])
  const loading = ref(false)

  async function fetchStats() {
    try {
      stats.value = await api.get('/api/stats')
    } catch {}
  }

  async function fetchTrend(days = 7) {
    try {
      const data = await api.get(`/api/stats/trend?days=${days}`)
      trend.value = data.trend || []
    } catch {}
  }

  async function fetchFunnel() {
    try {
      funnel.value = await api.get('/api/stats/funnel')
    } catch {}
  }

  async function fetchFollowups() {
    try {
      const data = await api.get('/api/followups')
      followups.value = data.overdue || []
    } catch {}
  }

  async function markFollowupDone(id: number) {
    try {
      await api.post(`/api/followups/${id}/done`)
      followups.value = followups.value.filter((f: any) => f.id !== id)
      success('已标记完成')
    } catch (e: any) {
      error(`操作失败: ${e.message}`)
    }
  }

  function handleFollowupDone(data: any) {
    if (data?.id) followups.value = followups.value.filter((f: any) => f.id !== data.id)
  }

  return {
    stats, trend, funnel, followups, loading,
    fetchStats, fetchTrend, fetchFunnel, fetchFollowups,
    markFollowupDone, handleFollowupDone,
  }
})
