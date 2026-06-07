import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>((window as any).__API_TOKEN__ || localStorage.getItem('boss_api_token') || '')

  function setToken(newToken: string) {
    token.value = newToken
    localStorage.setItem('boss_api_token', newToken)
  }

  function handleExpired() {
    token.value = ''
    localStorage.removeItem('boss_api_token')
  }

  return { token, setToken, handleExpired }
})
