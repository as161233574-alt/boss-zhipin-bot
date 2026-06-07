export interface WsMessage {
  type: string
  data?: any
  message?: string
}

export interface WsScoreProgressData {
  current: number
  total: number
  job_id: number
  job_title: string
}

export interface WsBatchCompleteData {
  total: number
  success: number
  failed: number
}

export interface WsNewMessagesData {
  conversation_id: string
  messages: any[]
}

export interface WsSystemData {
  event: string
  data?: any
  message?: string
}
