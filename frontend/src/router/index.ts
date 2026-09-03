// frontend/src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ExamplesPage from '@/pages/ExamplesPage.vue'
import MyWordsPage from '@/pages/MyWordsPage.vue'
import LoginPage from '@/pages/LoginPage.vue'
import HomePage from '@/pages/HomePage.vue'
import BestOptionsPage from '@/pages/BestOptionsPage.vue'
import RandomizerPage from '@/pages/RandomizerPage.vue'
import GameStoryPage from '@/pages/GameStoryPage.vue'
import QuickWritePage from '@/pages/QuickWritePage.vue'
import CollocationsPage from '@/pages/CollocationsPage.vue'
import WordDetailPage from '@/pages/WordDetailPage.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  scrollBehavior(to, from, savedPosition) {
    // Si hay una posición guardada (back button), usarla
    if (savedPosition) {
      return savedPosition
    }
    // Si es una nueva navegación, ir al top
    return { left: 0, top: 0 }
  },
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
    },
    {
      path: '/randomizer',
      name: 'randomizer',
      component: RandomizerPage,
      meta: { requiresAuth: true }
    },
    {
      path: '/game-story',
      name: 'game-story',
      component: GameStoryPage,
      meta: { requiresAuth: true }
    },
    {
      path: '/quick-write',
      name: 'quick-write',
      component: QuickWritePage,
      meta: { requiresAuth: true }
    },
    {
      path: '/collocations',
      name: 'collocations',
      component: CollocationsPage,
      meta: { requiresAuth: true }
    },
    {
      path: '/words/:id',
      name: 'word-detail',
      component: WordDetailPage,
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