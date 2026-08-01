// frontend/src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ExamplesPage from '@/pages/ExamplesPage.vue'
import MyWordsPage from '@/pages/MyWordsPage.vue'
import LoginPage from '@/pages/LoginPage.vue'
import HomePage from '@/pages/HomePage.vue'
import BestOptionsPage from '@/pages/BestOptionsPage.vue'

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
    },
    {
      path: '/best-options',
      name: 'best-options',
      component: BestOptionsPage,
      meta: { requiresAuth: true }
    }
  ]
})

// Guardia de navegación global
router.beforeEach((to, from) => {
  const authStore = useAuthStore()

  // 1. If route requires auth and user is not authenticated
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return { name: 'login' }
  }
  // 2. If user is authenticated but tries to access guest-only routes
  if (to.meta.requiresGuest && authStore.isAuthenticated) {
    return { name: 'home' }
  }
  // 3. Otherwise, allow navigation
  return true
})

export default router