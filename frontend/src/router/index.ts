// frontend/src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ExamplesPage from '@/pages/ExamplesPage.vue'
import MyWordsPage from '@/pages/MyWordsPage.vue'
import LoginPage from '@/pages/LoginPage.vue'
import HomePage from '@/pages/HomePage.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomePage,
      meta: { requiresGuest: true }
    },
    {
      path: '/login',
      name: 'login',
      component: LoginPage,
      meta: { requiresGuest: true }
    },
    {
      path: '/my-words',
      name: 'my-words',
      component: MyWordsPage,
      meta: { requiresAuth: true }
    },
    {
      path: '/examples',
      name: 'examples',
      component: ExamplesPage,
      meta: { requiresAuth: true }
    }
  ]
})

// Guardia de navegación global
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  // 1. Si la ruta requiere estar autenticado y no lo está
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next({ name: 'login' })
  }
  // 2. Si el usuario ya está logueado e intenta ir al Login
  else if (to.meta.requiresGuest && authStore.isAuthenticated) {
    next({ name: 'home' })
  }
  // 3. De lo contrario, permitir libre tránsito
  else {
    next()
  }
})

export default router