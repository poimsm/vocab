// frontend/src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router'
import { defineAsyncComponent } from 'vue'
import { useAuthStore } from '@/stores/auth'

// Lazy load all pages for better performance
const ExamplesPage = defineAsyncComponent(() => import('@/pages/ExamplesPage.vue'))
const ExampleFavoritesPage = defineAsyncComponent(() => import('@/pages/ExampleFavoritesPage.vue'))
const MyWordsPage = defineAsyncComponent(() => import('@/pages/MyWordsPage.vue'))
const LoginPage = defineAsyncComponent(() => import('@/pages/LoginPage.vue'))
const SignupPage = defineAsyncComponent(() => import('@/pages/SignupPage.vue'))
const BestOptionsPage = defineAsyncComponent(() => import('@/pages/BestOptionsPage.vue'))
const RandomizerPage = defineAsyncComponent(() => import('@/pages/RandomizerPage.vue'))
const GameStoryPage = defineAsyncComponent(() => import('@/pages/GameStoryPage.vue'))
const QuickWritePage = defineAsyncComponent(() => import('@/pages/QuickWritePage.vue'))
const CollocationsPage = defineAsyncComponent(() => import('@/pages/CollocationsPage.vue'))
const WordDetailPage = defineAsyncComponent(() => import('@/pages/WordDetailPage.vue'))
const AtlasPage = defineAsyncComponent(() => import('@/pages/AtlasPage.vue'))
const StorePage = defineAsyncComponent(() => import('@/pages/StorePage.vue'))
const LandingPage = defineAsyncComponent(() => import('@/pages/LandingPage.vue'))
const VocabImagePage = defineAsyncComponent(() => import('@/pages/VocabImagePage.vue'))

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
      component: LandingPage,
      meta: { requiresGuest: true }
    },
    // {
    //   path: '/landing',
    //   name: 'landing',
    //   component: LandingPage,
    //   meta: { requiresGuest: true }
    // },
    {
      path: '/login',
      name: 'login',
      component: LoginPage,
      meta: { requiresGuest: true }
    },
    {
      path: '/signup',
      name: 'signup',
      component: SignupPage,
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
      path: '/examples/favorites',
      name: 'example-favorites',
      component: ExampleFavoritesPage,
      meta: { requiresAuth: true, hideLayout: true }
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
      meta: { requiresAuth: true, hideLayout: true }
    },
    {
      path: '/atlas/:theme?',
      name: 'atlas',
      component: AtlasPage,
      meta: { requiresAuth: true }
    },
    {
      path: '/store',
      name: 'store',
      component: StorePage,
      meta: { requiresAuth: true }
    },
    {
      path: '/vocab-images',
      name: 'vocab-images',
      component: VocabImagePage,
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