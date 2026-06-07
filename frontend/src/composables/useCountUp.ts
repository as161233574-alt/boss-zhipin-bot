import { ref, watch, onMounted, onUnmounted } from 'vue'

export function useCountUp(target: () => number, opts: { duration?: number; delay?: number } = {}) {
  const { duration = 600, delay = 0 } = opts
  const display = ref(0)
  let animId: number | null = null
  let delayTimer: ReturnType<typeof setTimeout> | null = null

  function animate(from: number, to: number) {
    if (animId) cancelAnimationFrame(animId)
    const start = performance.now()
    const diff = to - from

    function tick(now: number) {
      const elapsed = now - start
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 4)
      display.value = Math.round(from + diff * eased)
      if (progress < 1) {
        animId = requestAnimationFrame(tick)
      } else {
        animId = null
      }
    }

    animId = requestAnimationFrame(tick)
  }

  onMounted(() => {
    delayTimer = setTimeout(() => {
      animate(0, target())
    }, delay)
  })

  onUnmounted(() => {
    if (animId) {
      cancelAnimationFrame(animId)
      animId = null
    }
    if (delayTimer) {
      clearTimeout(delayTimer)
      delayTimer = null
    }
  })

  watch(target, (newVal, oldVal) => {
    animate(oldVal ?? 0, newVal)
  })

  return display
}
