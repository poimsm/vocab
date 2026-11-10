// frontend/src/stores/auth.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/utils/api'
import { useExamplesStore } from './examples'
import { useBestOptionsStore } from './bestOptions'

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

      // Clean up content stores when user logs in
      clearContentStores()

      return true
    } catch (error) {
      console.error('Error en el login:', error)
      throw error
    }
  }

  async function register(credentials: LoginCredentials) {
    try {
      await api.post('/auth/register', {
        email: credentials.email,
        password: credentials.password
      })
      return true
    } catch (error) {
      console.error('Error en el registro:', error)
      throw error
    }
  }

  function logout() {
    token.value = null
    userEmail.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user_email')

    // Clean up content stores when user logs out
    clearContentStores()
  }

  function clearContentStores() {
    // Clear examples and best options stores to prevent data leakage between users
    try {
      const examplesStore = useExamplesStore()
      const bestOptionsStore = useBestOptionsStore()

      examplesStore.clearState()
      console.log('[auth] Cleared examples store')

      bestOptionsStore.clearState()
      console.log('[auth] Cleared best options store')
    } catch (e) {
      console.debug('[auth] Could not clear content stores:', e)
    }
  }

  return {
    token,
    userEmail,
    isAuthenticated,
    login,
    register,
    logout
  }
})