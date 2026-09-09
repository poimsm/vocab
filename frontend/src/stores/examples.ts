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
  isPolling: boolean
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
    isPolling: false,
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
    console.log('[loadExamples] Received examples:', examples.length, 'buffer ids:', bufferIds.length, 'position:', bufferPosition)
    console.log('[loadExamples] Current state - currentIndex:', state.value.currentIndex, 'examples before:', state.value.examples.length)

    if (examples.length > 0) {
      const wasEmpty = state.value.examples.length === 0

      // Check if buffer IDs changed (buffer was refilled with new items)
      const bufferChanged = bufferIds.length !== state.value.bufferIds.length ||
                            !bufferIds.every((id, i) => id === state.value.bufferIds[i])

      state.value.examples = examples
      state.value.bufferIds = bufferIds
      state.value.bufferPosition = bufferPosition

      // Reset to 0 if: buffer was empty OR buffer IDs changed (new batch)
      // Clamp to valid range only if: same buffer, just navigating within it
      if (wasEmpty || bufferChanged) {
        state.value.currentIndex = 0
        console.log('[loadExamples]', wasEmpty ? 'Was empty' : 'Buffer changed', ', currentIndex set to 0')
      } else {
        // Clamp currentIndex to valid range
        state.value.currentIndex = Math.min(state.value.currentIndex, examples.length - 1)
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

  function setGenerating(value: boolean) {
    state.value.generating = value
  }

  function setError(error: string | null) {
    state.value.error = error
  }

  function setNoWords(value: boolean) {
    state.value.noWords = value
  }

  function setIsPolling(value: boolean) {
    state.value.isPolling = value
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
      isPolling: false,
    }
  }

  // ─── Actions ───
  async function fetchExamples(limit: number = 4) {
    if (state.value.generating && !state.value.isPolling) {
      console.warn('[fetchExamples] Already generating, skipping')
      return
    }

    state.value.generating = true
    state.value.error = null
    state.value.noWords = false

    console.log('[fetchExamples] Starting with buffer:', state.value.bufferIds, 'resolved:', Array.from(state.value.resolvedQueueItemIds))

    try {
      const response = await api.post('/examples/explore', {
        actions: ['next'],
        limit,
        buffer_queue_item_ids: state.value.bufferIds,
        buffer_position: state.value.currentIndex,
      })

      console.log('[fetchExamples] Response:', response.data)
      const data = response.data

      if (data.status === 'generating') {
        state.value.isPolling = true
        console.log('[fetchExamples] Status is generating, polling enabled')
        return
      }

      if (data.status === 'no_words') {
        state.value.generating = false
        state.value.noWords = true
        console.log('[fetchExamples] No words available')
        return
      }

      state.value.generating = false
      loadExamples(
        data.examples || [],
        data.buffer_queue_item_ids || [],
        data.buffer_position ?? 0
      )
      // Sincronizar resueltos con el servidor (cuando se resetea buffer, el servidor devuelve lista vacía)
      state.value.resolvedQueueItemIds.clear()
      console.log('[fetchExamples] Examples loaded successfully, resolved items cleared for new session')
    } catch (e: any) {
      state.value.generating = false
      const errorMsg = e.response?.data?.message || e.message || 'Failed to load examples'
      state.value.error = errorMsg
      console.error('[fetchExamples] Error:', errorMsg, e)
    }
  }

  async function resolveAndFetchNext(queueItemId: number, limit: number = 4) {
    state.value.generating = true
    state.value.error = null

    try {
      const response = await api.post('/examples/explore', {
        actions: ['resolve', 'next'],
        resolve_queue_item_id: queueItemId,
        limit,
        buffer_queue_item_ids: state.value.bufferIds,
        buffer_position: state.value.currentIndex,
      })

      const data = response.data

      if (data.status === 'generating') {
        state.value.isPolling = true
        return
      }

      if (data.status === 'no_words') {
        state.value.generating = false
        state.value.noWords = true
        return
      }

      state.value.generating = false
      loadExamples(
        data.examples || [],
        data.buffer_queue_item_ids || [],
        data.buffer_position ?? 0
      )
    } catch (e: any) {
      state.value.generating = false
      state.value.error = e.response?.data?.message || e.message || 'Failed to fetch examples'
    }
  }

  async function resolveOrSync(queueItemId: number) {
    console.log('[resolveOrSync] Processing item', queueItemId, 'at position', state.value.currentIndex)

    // Resolve if not yet resolved, or sync position if already resolved
    const alreadyResolved = isQueueItemResolved(queueItemId)
    const actions = alreadyResolved ? ['sync'] : ['resolve']

    if (alreadyResolved) {
      console.log('[resolveOrSync] Item', queueItemId, 'already resolved in session, sending sync action to update position')
    } else {
      console.log('[resolveOrSync] Item', queueItemId, 'not yet resolved, sending resolve action')
    }

    try {
      await api.post('/examples/explore', {
        actions: actions,  // ['sync'] if already resolved, ['resolve'] otherwise
        resolve_queue_item_id: queueItemId,
        buffer_queue_item_ids: state.value.bufferIds,
        buffer_position: state.value.currentIndex,
        limit: 4,
      })

      // Only mark as resolved if we actually sent the resolve action
      if (!alreadyResolved) {
        markQueueItemAsResolved(queueItemId)
      }
    } catch (e: any) {
      console.error('[resolveOrSync] Error:', e)
    }
  }

  async function syncPosition() {
    // Sync current position with backend using 'sync' action
    console.log('[syncPosition] Syncing position:', state.value.currentIndex, 'with buffer:', state.value.bufferIds)

    try {
      await api.post('/examples/explore', {
        actions: ['sync'],  // Sync position only
        limit: 4,
        buffer_queue_item_ids: state.value.bufferIds,
        buffer_position: state.value.currentIndex,
      })
    } catch (e: any) {
      console.error('[syncPosition] Error:', e)
    }
  }

  async function syncBuffer(limit: number = 4) {
    // Sync and refill buffer - used when marking word as learned from WordDetailPage
    // This validates buffer, removes learned words, and fills with new items
    console.log('[syncBuffer] Syncing and refilling buffer after marking word as learned')

    try {
      const response = await api.post('/examples/explore', {
        actions: ['sync-buffer'],
        limit,
        buffer_queue_item_ids: state.value.bufferIds,
        buffer_position: state.value.currentIndex,
      })

      const data = response.data
      console.log('[syncBuffer] Buffer synced and refilled:', data.buffer_queue_item_ids.length, 'items')

      // Update buffer with synced and refilled data
      state.value.bufferIds = data.buffer_queue_item_ids || []
      state.value.bufferPosition = data.buffer_position ?? 0
    } catch (e: any) {
      console.error('[syncBuffer] Error:', e)
    }
  }

  async function syncAndFetchNext(limit: number = 4) {
    // Sync buffer (remove learned words) and fetch next examples in one atomic call
    state.value.generating = true
    state.value.error = null
    state.value.noWords = false

    console.log('[syncAndFetchNext] Syncing buffer and fetching examples')

    try {
      const response = await api.post('/examples/explore', {
        actions: ['sync', 'next'],
        limit,
        buffer_queue_item_ids: state.value.bufferIds,
        buffer_position: state.value.currentIndex,
      })

      const data = response.data

      if (data.status === 'generating') {
        state.value.isPolling = true
        console.log('[syncAndFetchNext] Content is being generated, polling enabled')
        return
      }

      if (data.status === 'no_words') {
        state.value.generating = false
        state.value.noWords = true
        console.log('[syncAndFetchNext] No more words available')
        return
      }

      state.value.generating = false
      loadExamples(
        data.examples || [],
        data.buffer_queue_item_ids || [],
        data.buffer_position ?? 0
      )
      state.value.resolvedQueueItemIds.clear()
      console.log('[syncAndFetchNext] Buffer synced and examples loaded')
    } catch (e: any) {
      state.value.generating = false
      const errorMsg = e.response?.data?.message || e.message || 'Failed to sync and fetch examples'
      state.value.error = errorMsg
      console.error('[syncAndFetchNext] Error:', errorMsg, e)
    }
  }

  async function navigateExample(queueItemId: number, isLastItem: boolean, limit: number = 4) {
    // Unified navigation - always sends 'sync', optionally adds 'resolve' and 'next'
    console.log('[navigateExample] Navigation: queueItemId=', queueItemId, 'isLastItem=', isLastItem, 'currentIndex=', state.value.currentIndex)

    // Build actions array
    const actions: string[] = ['sync']  // Always sync position

    // Add resolve if not already resolved
    const alreadyResolved = isQueueItemResolved(queueItemId)
    if (!alreadyResolved) {
      actions.push('resolve')
      console.log('[navigateExample] Item not resolved, adding resolve action')
    } else {
      console.log('[navigateExample] Item already resolved, skipping resolve')
    }

    // Add next if at last item
    if (isLastItem) {
      actions.push('next')
      state.value.generating = true
      console.log('[navigateExample] At last item, adding next action and enabling generating flag')
    }

    console.log('[navigateExample] Sending actions:', actions)

    try {
      const response = await api.post('/examples/explore', {
        actions,
        resolve_queue_item_id: queueItemId,
        limit,
        buffer_queue_item_ids: state.value.bufferIds,
        buffer_position: state.value.currentIndex,
      })

      const data = response.data

      // Only mark as resolved if we sent the resolve action
      if (!alreadyResolved && actions.includes('resolve')) {
        markQueueItemAsResolved(queueItemId)
      }

      // If next was included, handle the response
      if (actions.includes('next')) {
        if (data.status === 'generating') {
          state.value.isPolling = true
          console.log('[navigateExample] Content generating, polling enabled')
          return
        }

        if (data.status === 'no_words') {
          state.value.generating = false
          state.value.noWords = true
          console.log('[navigateExample] No more words available')
          return
        }

        state.value.generating = false
        loadExamples(
          data.examples || [],
          data.buffer_queue_item_ids || [],
          data.buffer_position ?? 0
        )
        state.value.resolvedQueueItemIds.clear()
        console.log('[navigateExample] New batch loaded')
      }
    } catch (e: any) {
      if (state.value.generating) {
        state.value.generating = false
      }
      console.error('[navigateExample] Error:', e)
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
    isPolling: computed(() => state.value.isPolling),

    // Getters
    currentExample,
    textSegments,
    canGoNext,
    canGoPrev,
    isAtEndOfBuffer,

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
    setIsPolling,
    clearState,
    isQueueItemResolved,
    markQueueItemAsResolved,
    fetchExamples,
    resolveAndFetchNext,
    resolveOrSync,
    syncPosition,
    syncBuffer,
    syncAndFetchNext,
    navigateExample,
  }
})
