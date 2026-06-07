import { useAuthStore } from '@/stores/auth'

export function useApi() {
  const authStore = useAuthStore()

  async function request<T = any>(url: string, options?: RequestInit): Promise<T> {
    const isFormData = options?.body instanceof FormData
    const res = await fetch(url, {
      ...options,
      headers: {
        'Authorization': `Bearer ${authStore.token}`,
        ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
        ...options?.headers,
      },
    })
    if (res.status === 401) {
      authStore.handleExpired()
      throw new Error('Unauthorized')
    }
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      throw new Error(`API error ${res.status}: ${text}`)
    }
    const contentType = res.headers.get('content-type')
    if (contentType && contentType.includes('application/json')) {
      return res.json()
    }
    return res.text() as any
  }

  return {
    get: <T = any>(url: string) => request<T>(url),
    post: <T = any>(url: string, body?: any) => {
      const serialized = body instanceof FormData ? body : (body ? JSON.stringify(body) : undefined)
      return request<T>(url, { method: 'POST', body: serialized })
    },
    put: <T = any>(url: string, body?: any) => {
      const serialized = body instanceof FormData ? body : (body ? JSON.stringify(body) : undefined)
      return request<T>(url, { method: 'PUT', body: serialized })
    },
    del: <T = any>(url: string) => request<T>(url, { method: 'DELETE' }),
  }
}
