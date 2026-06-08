import { useJobsStore } from '@/stores/jobs'
import { useToast } from './useToast'

export function useJobActions() {
  const jobsStore = useJobsStore()
  const { success, error } = useToast()

  async function applyJob(jobId: number) {
    try {
      await jobsStore.applyJob(jobId)
      success('投递成功')
    } catch (e: any) {
      error(`投递失败: ${e.message}`)
    }
  }

  async function batchApply(jobIds: number[]) {
    try {
      await jobsStore.batchApply(jobIds)
      success(`批量投递已提交 (${jobIds.length} 个岗位)`)
    } catch (e: any) {
      error(`批量投递失败: ${e.message}`)
    }
  }

  async function smartApply() {
    try {
      await jobsStore.smartApply()
      success('智能投递已启动，将自动筛选高分岗位投递')
    } catch (e: any) {
      error(`启动失败: ${e.message}`)
    }
  }

  async function scoreJob(jobId: number) {
    try {
      await jobsStore.scoreJob(jobId)
      success('评分完成')
    } catch (e: any) {
      error(`评分失败: ${e.message}`)
    }
  }

  async function batchScore(mode: 'unscored' | 'all' = 'unscored') {
    try {
      await jobsStore.batchScore(mode)
      success('批量评分已启动')
    } catch (e: any) {
      error(`批量评分失败: ${e.message}`)
    }
  }

  async function skipJob(jobId: number) {
    try {
      await jobsStore.skipJob(jobId)
      success('已跳过')
    } catch (e: any) {
      error(`跳过失败: ${e.message}`)
    }
  }

  return { applyJob, batchApply, smartApply, scoreJob, batchScore, skipJob }
}
