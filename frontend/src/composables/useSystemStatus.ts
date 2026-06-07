import { onMounted, onUnmounted } from 'vue'
import { useSystemStore } from '@/stores/system'

export function useSystemStatus(intervalMs = 10000) {
  const systemStore = useSystemStore()
  let timer: ReturnType<typeof setInterval> | null = null

  onMounted(() => {
    systemStore.fetchStatus()
    timer = setInterval(() => systemStore.fetchStatus(), intervalMs)
  })

  onUnmounted(() => {
    if (timer) { clearInterval(timer); timer = null }
  })
}
