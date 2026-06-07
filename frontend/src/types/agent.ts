export interface AgentProfile {
  name: string
  display_name: string
  description: string
  model: string
  temperature: number
  max_tokens: number
  system_prompt: string
  tools: string[]
  enabled: boolean
}

export interface AgentStatus {
  name: string
  display_name: string
  status: 'idle' | 'running' | 'error' | 'stopped'
  last_run: string | null
  last_error: string | null
  total_runs: number
  success_rate: number
}

export interface OrchestratorMessage {
  id: string
  agent: string
  type: 'info' | 'success' | 'warning' | 'error'
  content: string
  created_at: string
}
