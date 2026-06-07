export interface Conversation {
  id: string
  job_title: string
  company: string
  hr_name: string
  hr_title: string
  hr_avatar: string
  last_message: string
  last_message_time: string
  unread_count: number
  auto_reply_enabled: boolean
  status: string
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'hr' | 'system' | 'ai'
  content: string
  created_at: string
  is_ai_generated: boolean
}

export interface WechatExchange {
  id: string
  conversation_id: string
  hr_name: string
  hr_title: string
  company: string
  wechat_id: string
  exchanged_at: string
  job_title: string
}
