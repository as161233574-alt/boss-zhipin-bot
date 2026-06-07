import { ref, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useSystemStore } from '@/stores/system'
import { useJobsStore } from '@/stores/jobs'
import { useConversationsStore } from '@/stores/conversations'
import { useApplicationsStore } from '@/stores/applications'
import { useSettingsStore } from '@/stores/settings'
import { useToast } from './useToast'
import type { WsMessage } from '@/types/websocket'

export function useWebSocket() {
  const connected = ref(false)
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let pingTimer: ReturnType<typeof setInterval> | null = null
  const { error: showError } = useToast()

  function connect() {
    const authStore = useAuthStore()
    if (!authStore.token) return

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = location.host
    ws = new WebSocket(`${protocol}//${host}/ws?token=${authStore.token}`)

    ws.onopen = () => {
      connected.value = true
      reconnectAttempts = 0
      if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
      pingTimer = setInterval(() => {
        if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }))
      }, 30000)
    }

    ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data)
        handleMessage(msg)
      } catch (e) {
        console.warn('[WS] Failed to parse message:', e)
      }
    }

    ws.onclose = () => {
      connected.value = false
      if (pingTimer) { clearInterval(pingTimer); pingTimer = null }
      scheduleReconnect()
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  let reconnectAttempts = 0
  const maxReconnectDelay = 30000

  function scheduleReconnect() {
    if (reconnectTimer) return
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), maxReconnectDelay)
    reconnectAttempts++
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect()
    }, delay)
  }

  function handleMessage(msg: WsMessage) {
    const systemStore = useSystemStore()
    const jobsStore = useJobsStore()
    const convStore = useConversationsStore()
    const appStore = useApplicationsStore()
    const settingsStore = useSettingsStore()
    const authStore = useAuthStore()

    switch (msg.type) {
      // System
      case 'system':
        systemStore.handleSystemEvent(msg.data)
        break
      case 'connected':
        systemStore.handleSystemEvent(msg.data)
        break
      case 'session_expired':
        authStore.handleExpired()
        showError('登录会话已过期，请重新登录')
        break
      case 'relogin_ok':
        systemStore.handleRelogin()
        break
      case 'monitor_paused':
        systemStore.setMonitorPaused(true)
        break
      case 'monitor_resumed':
        systemStore.setMonitorPaused(false)
        break

      // Jobs
      case 'search_complete':
        jobsStore.handleSearchComplete(msg.data)
        break
      case 'apply_complete':
        jobsStore.handleApplyComplete(msg.data)
        break
      case 'batch_complete':
        jobsStore.handleBatchComplete(msg.data)
        break
      case 'score_progress':
        jobsStore.handleScoreProgress(msg.data)
        break
      case 'score_complete':
        jobsStore.handleScoreComplete(msg.data)
        break
      case 'auto_apply_complete':
        jobsStore.handleAutoApplyComplete(msg.data)
        break
      case 'auto_apply_batch_complete':
        jobsStore.handleAutoApplyBatchComplete(msg.data)
        break
      case 'jobs_deleted':
        jobsStore.handleDeleted(msg.data)
        break
      case 'jobs_cleared':
        jobsStore.handleCleared()
        break

      // Conversations
      case 'new_messages':
        convStore.handleNewMessages(msg.data)
        break
      case 'auto_reply_sent':
        convStore.handleAutoReply(msg.data)
        break
      case 'manual_message_sent':
        convStore.handleManualMessage(msg.data)
        break
      case 'auto_reply_toggled':
        convStore.handleToggle(msg.data)
        break
      case 'wechat_exchanged':
        convStore.handleWechatExchange(msg.data)
        break

      // Applications
      case 'followup_done':
        appStore.handleFollowupDone(msg.data)
        break

      // Settings
      case 'settings_updated':
        settingsStore.handleUpdate(msg.data)
        break
    }
  }

  function disconnect() {
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
    if (pingTimer) { clearInterval(pingTimer); pingTimer = null }
    ws?.close()
    ws = null
    connected.value = false
  }

  onUnmounted(disconnect)

  return { connected, connect, disconnect }
}
