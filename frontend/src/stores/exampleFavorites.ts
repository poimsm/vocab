import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/utils/api'

interface TargetWord {
  id: number
  main: string
  type: string
  meaning?: string
  level?: number
  is_boosted: boolean
  batch_id?: number
  is_favorite?: boolean
}

interface TextSegment {
  text: string
  is_highlighted: boolean
  target_word?: TargetWord
}

interface FavoriteExample {
  id: number
  text: TextSegment[]
  is_marked: boolean
}

export const useExampleFavoritesStore = defineStore('exampleFavorites', () => {
  const favoriteExamples = ref<FavoriteExample[]>([])
  const favoritesPage = ref(1)
  const favoritesTotalPages = ref(1)
  const favoritesFilter = ref<'all' | 'marked' | 'not_marked'>('all')
  const favoritesLoading = ref(false)

  const FAVORITES_LIMIT = 10

  const displayedExamples = computed(() => {
    if (favoritesFilter.value === 'all') {
      return favoriteExamples.value
    } else if (favoritesFilter.value === 'marked') {
      return favoriteExamples.value.filter(ex => ex.is_marked)
    } else {
      return favoriteExamples.value.filter(ex => !ex.is_marked)
    }
  })

  const hasData = computed(() => favoriteExamples.value.length > 0)

  async function fetchFavorites(page: number = 1, filter: 'all' | 'marked' | 'not_marked' = 'all') {
    if (favoritesLoading.value) return

    favoritesLoading.value = true

    try {
      const params: any = {
        page,
        limit: FAVORITES_LIMIT
      }

      if (filter === 'marked') {
        params.is_marked = true
      } else if (filter === 'not_marked') {
        params.is_marked = false
      }

      const response = await api.get('/examples/favorites', { params })

      if (response.data && response.data.status === 'ok') {
        if (page === 1) {
          favoriteExamples.value = response.data.items || []
        } else {
          favoriteExamples.value.push(...(response.data.items || []))
        }
        favoritesTotalPages.value = response.data.pages || 1
        favoritesPage.value = page
      }
    } catch (e: any) {
      console.error('Failed to load favorite examples:', e)
      throw e
    } finally {
      favoritesLoading.value = false
    }
  }

  function nextPage() {
    if (favoritesPage.value < favoritesTotalPages.value) {
      fetchFavorites(favoritesPage.value + 1, favoritesFilter.value)
    }
  }

  async function toggleMarked(exampleId: number) {
    try {
      const response = await api.patch(`/examples/${exampleId}/toggle-marked`)
      if (response.data && response.data.is_marked !== undefined) {
        const example = favoriteExamples.value.find(ex => ex.id === exampleId)
        if (example) {
          example.is_marked = response.data.is_marked
        }
      }
    } catch (e: any) {
      console.error('Failed to toggle marked status:', e)
      throw e
    }
  }

  function setFilter(filter: 'all' | 'marked' | 'not_marked') {
    favoritesFilter.value = filter
  }

  function resetForNewSession() {
    favoriteExamples.value = []
    favoritesPage.value = 1
    favoritesTotalPages.value = 1
    favoritesFilter.value = 'all'
  }

  return {
    favoriteExamples,
    displayedExamples,
    favoritesPage,
    favoritesTotalPages,
    favoritesFilter,
    favoritesLoading,
    hasData,
    fetchFavorites,
    nextPage,
    toggleMarked,
    setFilter,
    resetForNewSession
  }
})
