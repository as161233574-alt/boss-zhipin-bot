import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

export function useKeyboard(opts: {
  onCommandPalette?: () => void
  onEscape?: () => void
}) {
  const router = useRouter()

  const routes = [
    { key: '1', name: 'search' },
    { key: '2', name: 'applications' },
    { key: '3', name: 'chat' },
    { key: '4', name: 'wechat' },
    { key: '5', name: 'resume' },
    { key: '6', name: 'agents' },
    { key: '7', name: 'settings' },
  ]

  function handler(e: KeyboardEvent) {
    const target = e.target as HTMLElement
    const isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT' || target.isContentEditable

    // Command palette: Ctrl+K (always works)
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault()
      opts.onCommandPalette?.()
      return
    }

    // Escape
    if (e.key === 'Escape') {
      opts.onEscape?.()
      return
    }

    // Skip if user is typing in an input
    if (isInput) return

    // Number keys 1-7 for navigation
    const route = routes.find(r => r.key === e.key)
    if (route) {
      e.preventDefault()
      router.push({ name: route.name })
    }

    // / to focus search
    if (e.key === '/') {
      e.preventDefault()
      const searchInput = document.querySelector('input[type="text"], input[placeholder*="搜索"]') as HTMLInputElement
      searchInput?.focus()
    }
  }

  onMounted(() => document.addEventListener('keydown', handler))
  onUnmounted(() => document.removeEventListener('keydown', handler))
}
