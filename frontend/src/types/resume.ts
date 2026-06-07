export interface ResumeAction {
  id: string
  action_type: string
  input_summary: string
  output_summary: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  created_at: string
  duration_ms: number
}

export interface ResumeStats {
  total_actions: number
  success_rate: number
  avg_duration_ms: number
  actions_by_type: Record<string, number>
}
