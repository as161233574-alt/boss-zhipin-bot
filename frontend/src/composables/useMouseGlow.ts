import { ref, onMounted, onUnmounted, type Ref } from 'vue'

export function useMouseGlow(el: Ref<HTMLElement | undefined>) {
  const mouseX = ref(50)
  const mouseY = ref(50)
  let cachedEl: HTMLElement | null = null

  function onMove(e: MouseEvent) {
    if (!cachedEl) return
    const rect = cachedEl.getBoundingClientRect()
    mouseX.value = ((e.clientX - rect.left) / rect.width) * 100
    mouseY.value = ((e.clientY - rect.top) / rect.height) * 100
    cachedEl.style.setProperty('--mouse-x', `${mouseX.value}%`)
    cachedEl.style.setProperty('--mouse-y', `${mouseY.value}%`)
  }

  onMounted(() => {
    cachedEl = el.value ?? null
    cachedEl?.addEventListener('mousemove', onMove)
  })
  onUnmounted(() => {
    cachedEl?.removeEventListener('mousemove', onMove)
    cachedEl = null
  })

  return { mouseX, mouseY }
}
