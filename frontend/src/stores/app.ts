import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useAppStore = defineStore('app', () => {
  const theme = ref<'light' | 'dark'>(
    (localStorage.getItem('theme') as 'light' | 'dark') || 'light'
  )
  const sidebarCollapsed = ref(false)

  function toggleTheme() {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  watch(theme, (val) => {
    localStorage.setItem('theme', val)
    document.documentElement.classList.toggle('dark', val === 'dark')
  }, { immediate: true })

  return { theme, sidebarCollapsed, toggleTheme, toggleSidebar }
})
