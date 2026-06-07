import { onMounted, onUnmounted, type Ref } from 'vue'

export function useScrollReveal(
  el: Ref<HTMLElement | undefined>,
  opts: { threshold?: number; delay?: number } = {}
) {
  const { threshold = 0.1, delay = 0 } = opts
  let observer: IntersectionObserver | null = null

  onMounted(() => {
    if (!el.value) return
    el.value.style.opacity = '0'
    el.value.style.transform = 'translateY(16px)'
    el.value.style.transition = `opacity 500ms var(--ease-out-quart) ${delay}ms, transform 500ms var(--ease-out-quart) ${delay}ms`

    observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.style.opacity = '1'
            entry.target.style.transform = 'translateY(0)'
            observer?.unobserve(entry.target)
          }
        })
      },
      { threshold }
    )
    observer.observe(el.value)
  })

  onUnmounted(() => observer?.disconnect())
}
