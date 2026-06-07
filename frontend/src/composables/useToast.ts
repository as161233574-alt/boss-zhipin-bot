import { ref } from 'vue'

export interface Toast {
  id: number
  message: string
  type: 'success' | 'error' | 'warning' | 'info'
  duration: number
}

const toasts = ref<Toast[]>([])
let nextId = 0

export function useToast() {
  function show(message: string, type: Toast['type'] = 'info', duration = 3000) {
    const id = nextId++
    toasts.value.push({ id, message, type, duration })
    setTimeout(() => remove(id), duration)
  }

  function remove(id: number) {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }

  return {
    toasts,
    show,
    success: (msg: string) => show(msg, 'success'),
    error: (msg: string) => show(msg, 'error', 5000),
    warning: (msg: string) => show(msg, 'warning'),
    info: (msg: string) => show(msg, 'info'),
    remove,
  }
}
