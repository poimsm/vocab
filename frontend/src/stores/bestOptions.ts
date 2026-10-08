import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/utils/api'

export interface BestOptionWord {
  id: number
  main: string
  meaning?: string
  type?: string
  level: number
  synonyms?: string[]
  frequency?: 'rare' | 'uncommon' | 'common'
  examples?: any[]
}

export interface BestOptionItem {
  queue_item_id: number
  best_option_id: number
  word: BestOptionWord
  question: string
  options: string[]
  correct_option: number
}

interface BestOptionsState {
  // Buffer management
  bufferIds: number[]
  bufferPosition: number

  // Best options in current view
  bestOptions: BestOptionItem[]
  currentIndex: number

  // Track resolved items to prevent duplicate API calls
  resolvedQueueItemIds: Set<number>

  // UI state
  generating: boolean
  error: string | null
  noWords: boolean
}

export const useBestOptionsStore = defineStore('bestOptions', () => {
  // ─── State ───
  const state = ref<BestOptionsState>({
    bufferIds: [],
    bufferPosition: 0,
    bestOptions: [],
    currentIndex: 0,
    resolvedQueueItemIds: new Set(),
    generating: false,
    error: null,
    noWords: false,
  })

  // ─── Getters ───
  const currentBestOption = computed(() => {
    if (state.value.bestOptions.length === 0) return null
    return state.value.bestOptions[state.value.currentIndex]
  })

  const canGoNext = computed(() => {
    return state.value.currentIndex < state.value.bestOptions.length - 1
  })

  const canGoPrev = computed(() => {
    return state.value.currentIndex > 0
  })

  const isAtEndOfBuffer = computed(() => {
    return state.value.currentIndex >= state.value.bestOptions.length - 1
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

  function loadBestOptions(bestOptions: BestOptionItem[], bufferIds: number[], bufferPosition: number) {
    const safeBestOptions = Array.isArray(bestOptions) ? bestOptions : []
    const safeBufIds = Array.isArray(bufferIds) ? bufferIds : []
    const previousBufIds = Array.isArray(state.value.bufferIds) ? state.value.bufferIds : []

    console.log('[loadBestOptions] Received best options:', safeBestOptions.length, 'buffer ids:', safeBufIds.length, 'position:', bufferPosition)

    if (safeBestOptions.length > 0) {
      const wasEmpty = state.value.bestOptions.length === 0
      const bufferChanged = safeBufIds.length !== previousBufIds.length ||
                            safeBufIds.some((id, i) => previousBufIds[i] !== id)

      state.value.bestOptions = safeBestOptions
      state.value.bufferIds = safeBufIds
      state.value.bufferPosition = bufferPosition

      if (wasEmpty || bufferChanged) {
        // Use bufferPosition if available, otherwise start at 0
        const startIndex = Math.min(bufferPosition, safeBestOptions.length - 1)
        state.value.currentIndex = startIndex
        console.log('[loadBestOptions]', wasEmpty ? 'Was empty' : 'Buffer changed', ', currentIndex set to', startIndex, '(bufferPosition:', bufferPosition, ')')
      } else {
        state.value.currentIndex = Math.min(state.value.currentIndex, safeBestOptions.length - 1)
        console.log('[loadBestOptions] Same buffer, currentIndex clamped to:', state.value.currentIndex)
      }
    }
  }

  function setCurrentIndex(index: number) {
    const newIndex = Math.max(0, Math.min(index, state.value.bestOptions.length - 1))
    if (newIndex !== state.value.currentIndex) {
      console.log('[setCurrentIndex] Changed from', state.value.currentIndex, 'to', newIndex)
      state.value.currentIndex = newIndex
    }
  }

  function nextBestOption() {
    if (canGoNext.value) {
      console.log('[nextBestOption] Moving from', state.value.currentIndex, 'to', state.value.currentIndex + 1)
      state.value.currentIndex++
    }
  }

  function prevBestOption() {
    if (canGoPrev.value) {
      console.log('[prevBestOption] Moving from', state.value.currentIndex, 'to', state.value.currentIndex - 1)
      state.value.currentIndex--
    }
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
      bestOptions: [],
      currentIndex: 0,
      resolvedQueueItemIds: new Set(),
      generating: false,
      error: null,
      noWords: false,
    }
  }

  // ─── Actions ───
  // Note: All explore actions now handled via POST /explore endpoint
  // with SSE listening for events. No polling-based methods needed anymore.

  async function navigateBestOption(queueItemId: number, isLastItem: boolean, limit: number = 4) {
    console.log('[navigateBestOption] Navigation: queueItemId=', queueItemId, 'isLastItem=', isLastItem, 'currentIndex=', state.value.currentIndex)

    const actions: string[] = ['sync']
    const alreadyResolved = isQueueItemResolved(queueItemId)

    if (!alreadyResolved) {
      actions.push('resolve')
      console.log('[navigateBestOption] Item not resolved, adding resolve action')
    } else {
      console.log('[navigateBestOption] Item already resolved, skipping resolve')
    }

    if (isLastItem) {
      actions.push('next')
      state.value.generating = true
      console.log('[navigateBestOption] At last item, adding next action and enabling generating flag')
    }

    console.log('[navigateBestOption] Sending actions:', actions)

    try {
      await api.post('/best-options/explore', {
        actions,
        resolve_queue_item_id: queueItemId,
        limit,
        buffer_delivery_ids: state.value.bufferIds,
        buffer_position: state.value.currentIndex,
      })

      if (!alreadyResolved && actions.includes('resolve')) {
        markQueueItemAsResolved(queueItemId)
      }

      // Note: If 'next' action was included, SSE will handle the response
      // in the component via startSSE()
      console.log('[navigateBestOption] Actions sent to backend, SSE will handle response if needed')
    } catch (e: any) {
      if (state.value.generating) {
        state.value.generating = false
      }
      console.error('[navigateBestOption] Error:', e)
    }
  }

  async function syncPosition() {
    console.log('[syncPosition] Syncing position:', state.value.currentIndex, 'with buffer:', state.value.bufferIds)

    try {
      await api.post('/best-options/explore', {
        actions: ['sync'],
        limit: 4,
        buffer_delivery_ids: state.value.bufferIds,
        buffer_position: state.value.currentIndex,
      })
    } catch (e: any) {
      console.error('[syncPosition] Error:', e)
    }
  }

  return {
    // State
    bufferIds: computed(() => state.value.bufferIds),
    bufferPosition: computed(() => state.value.bufferPosition),
    bestOptions: computed(() => state.value.bestOptions),
    currentIndex: computed(() => state.value.currentIndex),
    generating: computed(() => state.value.generating),
    error: computed(() => state.value.error),
    noWords: computed(() => state.value.noWords),

    // Getters
    currentBestOption,
    canGoNext,
    canGoPrev,
    isAtEndOfBuffer,

    // Methods
    resetBuffer,
    setBufferData,
    loadBestOptions,
    setCurrentIndex,
    nextBestOption,
    prevBestOption,
    setGenerating,
    setError,
    setNoWords,
    clearState,
    isQueueItemResolved,
    markQueueItemAsResolved,
    navigateBestOption,
    syncPosition,
  }
})
