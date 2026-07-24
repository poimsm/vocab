// frontend/src/stores/auth.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/utils/api'

// Define la interfaz para los datos de credenciales
interface LoginCredentials {
  email: string // o 'email' si tu backend cambió el campo
  password: string
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const userEmail = ref<string | null>(localStorage.getItem('user_email'))

  const isAuthenticated = computed(() => !!token.value)

  // 1. Tipamos las credenciales como un objeto en lugar de FormData
  async function login(credentials: LoginCredentials) {
    try {
      // 2. Pasamos el objeto directamente; Axios se encarga de convertirlo a JSON
      const response = await api.post('/auth/login', credentials)

      const accessToken = response.data.access_token
      token.value = accessToken

      // 3. Leemos la propiedad directamente del objeto (ya no se usa .get())
      const email = credentials.email 
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