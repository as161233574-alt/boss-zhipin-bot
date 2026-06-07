import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'

export interface Job {
  id: number
  job_title: string
  company: string
  salary: string
  job_url: string
  city: string
  experience: string
  education: string
  hr_name: string
  hr_title: string
  description: string
  status: string
  score: number | null
  score_detail: string | null
  composite_score: number | null
  hr_activity_score: number | null
  hr_activity: string
  legitimacy: string
  legitimacy_signals: string
  greeting_text: string | null
  greeting_sent_at: string | null
  follow_up_at: string | null
  follow_up_count: number
  created_at: string
  updated_at: string
  deleted_at: string | null
  dedup_key: string
}

export interface ScoreDetail {
  cv_score: number
  quality_score: number
  key_skills: string[]
  gap: string
  advice: string
  summary: string
  quality_notes: string
  has_resume: boolean
}

export function parseScoreDetail(job: Job): ScoreDetail | null {
  if (!job.score_detail) return null
  try {
    return JSON.parse(job.score_detail)
  } catch {
    return null
  }
}

export interface DedupStats {
  total: number
  duplicates: number
  unique: number
}

export const useJobsStore = defineStore('jobs', () => {
  const api = useApi()
  const { success, error, info } = useToast()

  const jobs = ref<Job[]>([])
  const loading = ref(false)
  const total = ref(0)
  const scoreProgress = ref<{ current: number; total: number; job_title: string } | null>(null)

  async function fetchJobs(params?: { status?: string; limit?: number; sort_by?: string }) {
    loading.value = true
    try {
      const query = new URLSearchParams()
      if (params?.status) query.set('status', params.status)
      if (params?.limit) query.set('limit', String(params.limit))
      if (params?.sort_by) query.set('sort_by', params.sort_by)
      const url = `/api/jobs${query.toString() ? '?' + query : ''}`
      const data = await api.get(url)
      jobs.value = data.jobs || []
      total.value = data.total || jobs.value.length
    } catch (e: any) {
      error(`加载岗位失败: ${e.message}`)
    } finally {
      loading.value = false
    }
  }

  async function searchJobs(params: { keyword: string; city?: string; max_pages?: number }) {
    loading.value = true
    try {
      await api.post('/api/jobs/search', params)
      info('搜索已启动，后台评分中...')
    } catch (e: any) {
      error(`搜索失败: ${e.message}`)
    } finally {
      loading.value = false
    }
  }

  async function applyJob(jobId: number) {
    const job = jobs.value.find(j => j.id === jobId)
    if (!job) return
    try {
      await api.post('/api/jobs/apply', { url: job.job_url })
      job.status = 'applied'
    } catch (e: any) {
      error(`投递失败: ${e.message}`)
    }
  }

  async function batchApply(jobIds: number[]) {
    const urls = jobIds.map(id => jobs.value.find(j => j.id === id)?.job_url).filter(Boolean)
    return api.post('/api/jobs/apply-batch', { urls })
  }

  async function scoreJob(jobId: number) {
    return api.post(`/api/jobs/${jobId}/score`)
  }

  async function batchScore(mode: 'unscored' | 'all' = 'unscored') {
    return api.post('/api/jobs/batch-score', { mode })
  }

  async function skipJob(jobId: number) {
    await api.post(`/api/jobs/${jobId}/skip`)
    const job = jobs.value.find(j => j.id === jobId)
    if (job) job.status = 'skipped'
  }

  async function deleteJobs(ids: number[]) {
    await api.post('/api/jobs/delete', { ids })
    jobs.value = jobs.value.filter(j => !ids.includes(j.id))
  }

  // WebSocket handlers
  function handleSearchComplete(data: any) {
    info(`搜索完成，发现 ${data?.count || data?.new_count || 0} 个新岗位`)
    fetchJobs()
  }

  function handleApplyComplete(data: any) {
    if (data?.success) {
      const job = jobs.value.find(j => j.id === data.job_id)
      if (job) job.status = 'applied'
    }
  }

  function handleBatchComplete(data: any) {
    success(`批量投递完成: ${data?.applied || data?.success || 0} 成功`)
    fetchJobs()
  }

  function handleScoreProgress(data: any) {
    scoreProgress.value = data
  }

  function handleScoreComplete(data: any) {
    scoreProgress.value = null
    info(`评分完成: ${data?.scored || 0} 个岗位`)
    fetchJobs()
  }

  function handleAutoApplyComplete(data: any) {
    if (data?.success) fetchJobs()
  }

  function handleAutoApplyBatchComplete(data: any) {
    info(`自动投递批次完成`)
    fetchJobs()
  }

  function handleDeleted(data: any) {
    if (data?.ids) jobs.value = jobs.value.filter(j => !data.ids.includes(j.id))
  }

  function handleCleared() {
    jobs.value = []
  }

  return {
    jobs, loading, total, scoreProgress,
    fetchJobs, searchJobs, applyJob, batchApply, scoreJob, batchScore,
    skipJob, deleteJobs,
    handleSearchComplete, handleApplyComplete, handleBatchComplete,
    handleScoreProgress, handleScoreComplete, handleAutoApplyComplete,
    handleAutoApplyBatchComplete, handleDeleted, handleCleared,
  }
})
