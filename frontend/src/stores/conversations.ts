import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'

export interface Conversation {
  id: number
  application_id: number | null
  hr_name: string
  hr_company: string
  job_title: string
  last_message_text: string
  last_message_from: string
  last_message_at: string
  unread_count: number
  status: string
  auto_reply_enabled: boolean
  interest_level: string
  hr_wechat: string | null
  wechat_shared_at: string | null
  resume_sent: boolean
  phone_shared: boolean
  emotion: string
  dialogue_stage: string
  last_follow_up_at: string | null
  created_at: string
  updated_at: string
}

export interface Message {
  id: number
  conversation_id: number
  role: string
  content: string
  created_at: string
  is_ai_generated: boolean
}

export const useConversationsStore = defineStore('conversations', () => {
  const api = useApi()
  const { success, error, info } = useToast()

  const conversations = ref<Conversation[]>([])
  const activeConversation = ref<Conversation | null>(null)
  const messages = ref<Message[]>([])
  const wechatExchanges = ref<any[]>([])
  const loading = ref(false)

  async function fetchConversations() {
    loading.value = true
    try {
      const data = await api.get('/api/conversations')
      conversations.value = data.conversations || data || []
    } catch (e: any) {
      error(`加载会话失败: ${e.message}`)
    } finally {
      loading.value = false
    }
  }

  async function selectConversation(conv: Conversation) {
    activeConversation.value = conv
    await fetchMessages(conv.id)
  }

  async function fetchMessages(convId: number) {
    try {
      const data = await api.get(`/api/conversations/${convId}/messages`)
      messages.value = data.messages || data || []
    } catch {}
  }

  async function syncMessages(convId: number) {
    try {
      await api.post(`/api/conversations/${convId}/sync`)
      await fetchMessages(convId)
      success('消息已同步')
    } catch (e: any) {
      error(`同步失败: ${e.message}`)
    }
  }

  async function sendMessage(convId: number, content: string) {
    try {
      await api.post(`/api/conversations/${convId}/send`, { content })
      await fetchMessages(convId)
    } catch (e: any) {
      error(`发送失败: ${e.message}`)
    }
  }

  async function toggleAutoReply(convId: number, enable: boolean) {
    const action = enable ? 'resume' : 'pause'
    try {
      await api.post(`/api/conversations/${convId}/${action}`)
      const conv = conversations.value.find(c => c.id === convId)
      if (conv) conv.auto_reply_enabled = enable
      success(enable ? '已开启自动回复' : '已暂停自动回复')
    } catch (e: any) {
      error(`操作失败: ${e.message}`)
    }
  }

  async function fetchWechatExchanges() {
    try {
      const data = await api.get('/api/wechat-exchanges')
      wechatExchanges.value = data.exchanges || data || []
    } catch {}
  }

  // WebSocket handlers
  function handleNewMessages(data: any) {
    const convId = data?.conversation_id
    if (convId && activeConversation.value?.id === convId) {
      const newMsgs = data.messages || []
      messages.value.push(...newMsgs)
    }
    const conv = conversations.value.find(c => c.id === convId)
    if (conv && data?.messages?.length) {
      conv.last_message_text = data.messages[data.messages.length - 1].content
      conv.unread_count = (conv.unread_count || 0) + data.messages.length
    }
  }

  function handleAutoReply(data: any) {
    info(`AI 已自动回复`)
  }

  function handleManualMessage(data: any) {
    if (data?.conversation_id && activeConversation.value?.id === data.conversation_id) {
      fetchMessages(data.conversation_id)
    }
  }

  function handleToggle(data: any) {
    if (data?.conversation_id) {
      const conv = conversations.value.find(c => c.id === data.conversation_id)
      if (conv) conv.auto_reply_enabled = data.enabled ?? !conv.auto_reply_enabled
    }
  }

  function handleWechatExchange(data: any) {
    info(`HR 分享了微信`)
    fetchWechatExchanges()
  }

  return {
    conversations, activeConversation, messages, wechatExchanges, loading,
    fetchConversations, selectConversation, fetchMessages, syncMessages,
    sendMessage, toggleAutoReply, fetchWechatExchanges,
    handleNewMessages, handleAutoReply, handleManualMessage,
    handleToggle, handleWechatExchange,
  }
})
