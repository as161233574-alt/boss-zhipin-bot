import { computed } from 'vue'
import { useJobsStore } from '@/stores/jobs'

export function useScoreProgress() {
  const jobsStore = useJobsStore()

  const progress = computed(() => {
    if (!jobsStore.scoreProgress) return null
    const { current, total } = jobsStore.scoreProgress
    return {
      current,
      total,
      percent: total > 0 ? Math.round((current / total) * 100) : 0,
      isActive: current < total,
    }
  })

  return { progress }
}
