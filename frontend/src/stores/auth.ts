// frontend/src/stores/auth.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/utils/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const userEmail = ref<string | null>(localStorage.getItem('user_email'))

  const isAuthenticated = computed(() => !!token.value)

  async function login(formData: FormData) {
    try {
      const response = await api.post('/auth/login', formData)

      const accessToken = response.data.access_token
      token.value = accessToken

      const email = formData.get('username') as string
      userEmail.value = email

      localStorage.setItem('token', accessToken)
      localStorage.setItem('user_email', email)

      return true
    } catch (error) {
      console.error('Error en el login:', error)
      throw error
    }
  }

  function logout() {
    token.value = null
    userEmail.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user_email')
  }

  return {
    token,
    userEmail,
    isAuthenticated,
    login,
    logout
  }
})