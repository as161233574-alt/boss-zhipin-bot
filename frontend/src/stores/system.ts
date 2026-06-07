import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'

export interface SystemStatus {
  browser_running: boolean
  auto_reply_enabled: boolean
  monitor_running: boolean
  monitor_paused: boolean
  today_applications: number
  active_conversations: number
  daily_stats: {
    date: string
    applications_sent: number
    messages_sent: number
    messages_received: number
    auto_replies_sent: number
  }
}

export const useSystemStore = defineStore('system', () => {
  const api = useApi()
  const { success, error } = useToast()

  const status = ref<SystemStatus | null>(null)
  const schedulerStatus = ref<any>(null)
  const monitorPaused = ref(false)
  const loading = ref(false)

  async function fetchStatus() {
    try {
      status.value = await api.get('/api/status')
    } catch {}
  }

  async function fetchSchedulerStatus() {
    try {
      schedulerStatus.value = await api.get('/api/scheduler/status')
    } catch {}
  }

  async function startSystem() {
    loading.value = true
    try {
      await api.post('/api/system/start')
      success('系统启动中...')
      await fetchStatus()
    } catch (e: any) {
      error(`启动失败: ${e.message}`)
    } finally {
      loading.value = false
    }
  }

  async function stopSystem() {
    loading.value = true
    try {
      await api.post('/api/system/stop')
      success('系统已停止')
      await fetchStatus()
    } catch (e: any) {
      error(`停止失败: ${e.message}`)
    } finally {
      loading.value = false
    }
  }

  async function relogin() {
    try {
      await api.post('/api/system/relogin')
      success('重新登录已触发，请扫码')
    } catch (e: any) {
      error(`重新登录失败: ${e.message}`)
    }
  }

  async function navigateChat() {
    try {
      await api.post('/api/system/navigate-chat')
    } catch {}
  }

  async function pauseMonitor() {
    try {
      await api.post('/api/monitor/pause')
      monitorPaused.value = true
    } catch {}
  }

  async function resumeMonitor() {
    try {
      await api.post('/api/monitor/resume')
      monitorPaused.value = false
    } catch {}
  }

  function handleSystemEvent(data: any) {
    if (data?.status) status.value = data.status
    if (data?.event === 'started' || data?.event === 'stopped') fetchStatus()
  }

  function handleRelogin() {
    success('重新登录成功')
    fetchStatus()
  }

  function setMonitorPaused(paused: boolean) {
    monitorPaused.value = paused
  }

  return {
    status, schedulerStatus, monitorPaused, loading,
    fetchStatus, fetchSchedulerStatus, startSystem, stopSystem,
    relogin, navigateChat, pauseMonitor, resumeMonitor,
    handleSystemEvent, handleRelogin, setMonitorPaused,
  }
})
