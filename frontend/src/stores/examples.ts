import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/utils/api'

export interface TargetWord {
  id: number
  main: string
  type: string
  meaning?: string
  level?: number
  is_boosted: boolean
  batch_id?: number
  is_favorite?: boolean
}

export interface TextSegment {
  text: string
  is_highlighted: boolean
  target_word?: TargetWord
}

export interface ExampleItem {
  queue_item_id: number
  example_id: number
  text: TextSegment[]
  extracted_words: string[]
  is_favorite?: boolean
  is_marked?: boolean
}

interface ExamplesState {
  // Buffer management
  bufferIds: number[]
  bufferPosition: number

  // Examples in current view
  examples: ExampleItem[]
  currentIndex: number

  // Track resolved items to prevent duplicate API calls
  resolvedQueueItemIds: Set<number>

  // UI state
  generating: boolean
  error: string | null
  noWords: boolean

  // Favorites counter
  unmarkedFavoritesCount: number

  // Flag to notify when favorites list should be refreshed
  favoritesNeedRefresh: boolean
}

export const useExamplesStore = defineStore('examples', () => {
  // ─── State ───
  const state = ref<ExamplesState>({
    bufferIds: [],
    bufferPosition: 0,
    examples: [],
    currentIndex: 0,
    resolvedQueueItemIds: new Set(),
    generating: false,
    error: null,
    noWords: false,
    unmarkedFavoritesCount: 0,
    favoritesNeedRefresh: false,
  })

  // ─── Getters ───
  const currentExample = computed(() => {
    if (state.value.examples.length === 0) return null
    return state.value.examples[state.value.currentIndex]
  })

  const textSegments = computed(() => {
    const ex = currentExample.value
    if (!ex) return []
    return ex.text
  })

  const canGoNext = computed(() => {
    return state.value.currentIndex < state.value.examples.length - 1
  })

  const canGoPrev = computed(() => {
    return state.value.currentIndex > 0
  })

  const isAtEndOfBuffer = computed(() => {
    return state.value.currentIndex >= state.value.examples.length - 1
  })

  const favoriteCount = computed(() => {
    return state.value.examples.filter(ex => ex.is_favorite).length
  })

  // ─── Mutations ───
  function resetBuffer() {
    state.value.bufferIds = []
    state.value.bufferPosition = 0
    state.value.resolvedQueueItemIds.clear()
    console.log('[resetBuffer] Buffer and resolved items cleared')
  }

  function setBufferData(bufferIds: number[], bufferPosition: number) {
    state.value.bufferIds = bufferIds
    state.value.bufferPosition = bufferPosition
  }

  function loadExamples(examples: ExampleItem[], bufferIds: number[], bufferPosition: number) {
    // Ensure examples and bufferIds are arrays
    const safeExamples = Array.isArray(examples) ? examples : []
    const safeBufIds = Array.isArray(bufferIds) ? bufferIds : []
    const previousBufIds = Array.isArray(state.value.bufferIds) ? state.value.bufferIds : []

    console.log('[loadExamples] Received examples:', safeExamples.length, 'buffer ids:', safeBufIds.length, 'position:', bufferPosition)
    console.log('[loadExamples] Current state - currentIndex:', state.value.currentIndex, 'examples before:', state.value.examples.length)
    console.log('[loadExamples] Previous bufferIds:', previousBufIds, 'New bufferIds:', safeBufIds)

    if (safeExamples.length > 0) {
      const wasEmpty = state.value.examples.length === 0

      // Check if buffer IDs changed (buffer was refilled with new items)
      // Compare arrays by length first, then by content
      const bufferChanged = safeBufIds.length !== previousBufIds.length ||
                            safeBufIds.some((id, i) => previousBufIds[i] !== id)

      state.value.examples = safeExamples
      state.value.bufferIds = safeBufIds
      state.value.bufferPosition = bufferPosition

      // Use provided bufferPosition if it's explicitly given (session restoration)
      // Otherwise reset to 0 if buffer changed (new batch) or was empty
      if (bufferPosition > 0 || (wasEmpty && bufferPosition === 0)) {
        // Session restoration case: use the provided bufferPosition
        state.value.currentIndex = Math.min(bufferPosition, safeExamples.length - 1)
        console.log('[loadExamples] Using provided bufferPosition:', bufferPosition, '-> currentIndex:', state.value.currentIndex)
      } else if (wasEmpty || bufferChanged) {
        // New batch case: reset to 0
        state.value.currentIndex = 0
        console.log('[loadExamples]', wasEmpty ? 'Was empty' : 'Buffer changed', ', currentIndex set to 0')
      } else {
        // Same buffer navigation: clamp to valid range
        state.value.currentIndex = Math.min(state.value.currentIndex, safeExamples.length - 1)
        console.log('[loadExamples] Same buffer, currentIndex clamped to:', state.value.currentIndex)
      }
    } else {
      console.log('[loadExamples] No examples to load')
    }
  }

  function setCurrentIndex(index: number) {
    const newIndex = Math.max(0, Math.min(index, state.value.examples.length - 1))
    if (newIndex !== state.value.currentIndex) {
      console.log('[setCurrentIndex] Changed from', state.value.currentIndex, 'to', newIndex)
      state.value.currentIndex = newIndex
    }
  }

  function nextExample() {
    if (canGoNext.value) {
      console.log('[nextExample] Moving from', state.value.currentIndex, 'to', state.value.currentIndex + 1)
      state.value.currentIndex++
    }
  }

  function prevExample() {
    if (canGoPrev.value) {
      console.log('[prevExample] Moving from', state.value.currentIndex, 'to', state.value.currentIndex - 1)
      state.value.currentIndex--
    }
  }

  function updateExampleFavorite(isFavorite: boolean) {
    if (currentExample.value) {
      currentExample.value.is_favorite = isFavorite
    }
  }

  function setUnmarkedFavoritesCount(count: number) {
    state.value.unmarkedFavoritesCount = count
    console.log('[setUnmarkedFavoritesCount] Updated to:', count)
  }

  function markFavoritesNeedRefresh() {
    state.value.favoritesNeedRefresh = true
    console.log('[markFavoritesNeedRefresh] Favorites list marked for refresh')
  }

  function clearFavoritesRefreshFlag() {
    state.value.favoritesNeedRefresh = false
    console.log('[clearFavoritesRefreshFlag] Refresh flag cleared')
  }

  function setGenerating(value: boolean) {
    state.value.generating = value
  }

  function setError(error: string | null) {
    state.value.error = error
  }

  function setNoWords(value: boolean) {
    state.value.noWords = value
  }

  function isQueueItemResolved(queueItemId: number): boolean {
    return state.value.resolvedQueueItemIds.has(queueItemId)
  }

  function markQueueItemAsResolved(queueItemId: number) {
    state.value.resolvedQueueItemIds.add(queueItemId)
    console.log('[markQueueItemAsResolved] Item', queueItemId, 'marked as resolved. Total resolved:', state.value.resolvedQueueItemIds.size)
  }

  function clearState() {
    state.value = {
      bufferIds: [],
      bufferPosition: 0,
      examples: [],
      currentIndex: 0,
      resolvedQueueItemIds: new Set(),
      generating: false,
      error: null,
      noWords: false,
      unmarkedFavoritesCount: 0,
      favoritesNeedRefresh: false,
    }
  }

  // ─── Actions ───
  // Note: All explore actions now handled via POST /explore endpoint
  // with SSE listening for events. No polling-based methods needed anymore.

  async function fetchUnmarkedFavoritesCount() {
    // Fetch the count of unmarked favorite examples from the backend
    console.log('[fetchUnmarkedFavoritesCount] Fetching unmarked favorites count from backend')

    try {
      const response = await api.get('/examples/favorites/count')
      const count = response.data?.count ?? 0

      state.value.unmarkedFavoritesCount = count
      console.log('[fetchUnmarkedFavoritesCount] Count loaded:', count)
    } catch (e: any) {
      console.error('[fetchUnmarkedFavoritesCount] Error:', e)
    }
  }

  return {
    // State
    bufferIds: computed(() => state.value.bufferIds),
    bufferPosition: computed(() => state.value.bufferPosition),
    examples: computed(() => state.value.examples),
    currentIndex: computed(() => state.value.currentIndex),
    generating: computed(() => state.value.generating),
    error: computed(() => state.value.error),
    noWords: computed(() => state.value.noWords),
    unmarkedFavoritesCount: computed(() => state.value.unmarkedFavoritesCount),
    favoritesNeedRefresh: computed(() => state.value.favoritesNeedRefresh),

    // Getters
    currentExample,
    textSegments,
    canGoNext,
    canGoPrev,
    isAtEndOfBuffer,
    favoriteCount,

    // Methods
    resetBuffer,
    setBufferData,
    loadExamples,
    setCurrentIndex,
    nextExample,
    prevExample,
    updateExampleFavorite,
    setGenerating,
    setError,
    setNoWords,
    setUnmarkedFavoritesCount,
    markFavoritesNeedRefresh,
    clearFavoritesRefreshFlag,
    clearState,
    isQueueItemResolved,
    markQueueItemAsResolved,
    fetchUnmarkedFavoritesCount,
  }
})
