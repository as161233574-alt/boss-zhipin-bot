export interface Settings {
  ai_platform: string
  ai_api_key: string
  ai_base_url: string
  ai_model: string
  search_keywords: string
  search_city: string
  search_max_pages: number
  auto_apply_enabled: boolean
  auto_apply_min_score: number
  daily_apply_limit: number
  greeting_template: string
  greeting_type: 'intern' | 'dev' | 'general' | 'custom'
  smart_greeting_enabled: boolean
  auto_reply_enabled: boolean
  reply_delay_min: number
  reply_delay_max: number
  reply_style: string
  scheduler_enabled: boolean
  scheduler_interval_minutes: number
  scheduler_active_hours_start: string
  scheduler_active_hours_end: string
  resume_text: string
  resume_file_name: string
  company_blacklist: string[]
  hr_blacklist: string[]
  selectors: Record<string, string>
  updated_at: string
}
