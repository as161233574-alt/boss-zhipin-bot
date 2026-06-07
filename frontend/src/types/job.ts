export interface Job {
  id: number
  title: string
  company: string
  salary: string
  url: string
  hr_name: string
  hr_title: string
  hr_avatar: string
  location: string
  experience: string
  education: string
  description: string
  skills: string[]
  status: JobStatus
  cv_score: number | null
  quality_score: number | null
  composite_score: number | null
  key_skills: string[]
  gap: string
  advice: string
  summary: string
  legitimacy: 'ok' | 'caution' | 'danger'
  applied_at: string | null
  created_at: string
  updated_at: string
}

export type JobStatus = 'pending' | 'scored' | 'applied' | 'skipped' | 'failed'

export interface SearchParams {
  keyword: string
  city?: string
  max_pages?: number
}

export interface DedupStats {
  total: number
  duplicates: number
  unique: number
}

export interface TrashItem {
  id: number
  job_id: number
  title: string
  company: string
  deleted_at: string
}

export interface Followup {
  id: number
  application_id: number
  job_title: string
  company: string
  hr_name: string
  due_date: string
  status: string
}

export interface Shortlist {
  id: number
  job_id: number
  title: string
  company: string
  salary: string
  notes: string
  created_at: string
}

export interface AutoApplyLog {
  id: number
  job_id: number
  job_title: string
  company: string
  status: string
  message: string
  created_at: string
}
