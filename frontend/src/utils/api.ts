// frontend/src/utils/api.ts
import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost/api'

const api = axios.create({
  baseURL: API_BASE,
})

// Interceptor para INYECTAR el token en cada petición
api.interceptors.request.use(
  (config) => {
    const authStore = useAuthStore()
    if (authStore.token) {
      config.headers.Authorization = `Bearer ${authStore.token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
);



// Interceptor para CAPTURAR si el token expiró (Error 401)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      const authStore = useAuthStore()
      authStore.logout()
      // Opcional: Redirigir a la vista de login
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api