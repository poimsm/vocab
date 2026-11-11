import { ref } from 'vue'
import { useExploreSSE, type ExploreEventData } from './useExploreSSE'

/**
 * Composable que coordina el SSE con el store de contenido.
 * Maneja la carga de items, navegación, y sincronización con el backend.
 *
 * Reutilizable para examples, best_options, y otros content types.
 */

export interface ContentStoreActions {
  // Actualizaciones de estado
  setGenerating: (value: boolean) => void
  setError: (error: string | null) => void
  setNoWords: (value: boolean) => void
  loadItems: (items: any[], bufferIds: number[], bufferPosition: number) => void
  setBufferData: (bufferIds: number[], bufferPosition: number) => void
  markQueueItemAsResolved: (queueItemId: number) => void
  nextItem: () => void
  prevItem: () => void

  // Getters
  getBufferIds: () => number[]
  getBufferPosition: () => number
  getCurrentItemQueueId: () => number | null
  canGoNext: () => boolean
  canGoPrev: () => boolean
  isAtEnd: () => boolean
  getItemsCount: () => number
}

export function useExploreContent(
  contentType: 'examples' | 'best_options',
  storeActions: ContentStoreActions,
) {
  const BATCH_SIZE = contentType === 'examples' ? 5 : 6
  const isComponentMounted = ref(true)

  // Crear el servicio SSE
  const sseService = useExploreSSE(
    contentType,

    // onCompleted
    (data: ExploreEventData) => {
      if (!isComponentMounted.value) return

      storeActions.setGenerating(false)

      // Determinar el nombre de la key según el content type
      const contentKey = contentType === 'examples' ? 'examples' : 'best_options'
      const contentCountKey = `${contentKey}_count` as const
      const items = data[contentKey as keyof typeof data] as any[] | undefined
      const itemsCount = (data[contentCountKey as keyof typeof data] as number | undefined) ?? 0

      if (items && items.length > 0) {
        console.log(
          `[useExploreContent:${contentType}] Cargando ${items.length} items`
        )
        storeActions.loadItems(
          items,
          data.buffer_delivery_ids,
          data.buffer_position
        )
      } else if (itemsCount > 0) {
        // Fallback: solo IDs sin datos
        console.log(
          `[useExploreContent:${contentType}] Actualizando buffer con IDs`
        )
        storeActions.setBufferData(data.buffer_delivery_ids, data.buffer_position)
      } else if (data.status === 'generating') {
        console.log(`[useExploreContent:${contentType}] Contenido aún generándose...`)
        storeActions.setGenerating(true)
      } else if (data.status === 'no_words') {
        console.log(`[useExploreContent:${contentType}] No hay palabras disponibles`)
        storeActions.setNoWords(true)
      }
    },

    // onGenerating
    (data: ExploreEventData) => {
      if (!isComponentMounted.value) return
      storeActions.setGenerating(true)
    },

    // onError
    (error: string) => {
      if (!isComponentMounted.value) return
      storeActions.setGenerating(false)
      storeActions.setError(error)
    }
  )

  /**
   * Inicia la sesión: restaura estado guardado o carga nuevo batch
   */
  async function initializeSession() {
    console.log(`[useExploreContent:${contentType}] Initializing session`)

    try {
      // Enviar acción 'resume' para restaurar sesión guardada
      await sseService.resumeSession(BATCH_SIZE)
    } catch (e: any) {
      console.error(
        `[useExploreContent:${contentType}] Error during initialization:`,
        e
      )

      if (isComponentMounted.value) {
        // Fallback: cargar nuevo batch
        await loadNextBatch()
      }
    }
  }

  /**
   * Carga el siguiente batch de items
   */
  async function loadNextBatch() {
    console.log(`[useExploreContent:${contentType}] Loading next batch`)

    if (storeActions.getItemsCount() === 0) {
      storeActions.setGenerating(true)
    }

    try {
      await sseService.loadNextBatch(
        BATCH_SIZE,
        storeActions.getBufferIds(),
        0
      )
    } catch (e: any) {
      console.error(
        `[useExploreContent:${contentType}] Error loading next batch:`,
        e
      )
    }
  }

  /**
   * Navega al siguiente item y resuelve si es necesario
   */
  async function goToNextItem() {
    console.log(`[useExploreContent:${contentType}] Going to next item`)

    const queueItemId = storeActions.getCurrentItemQueueId()
    const canGoNext = storeActions.canGoNext()

    if (!canGoNext) {
      // At end of buffer: resolve + next
      if (queueItemId) {
        try {
          await sseService.resolveAndNext(
            queueItemId,
            BATCH_SIZE,
            storeActions.getBufferIds(),
            storeActions.getBufferPosition()
          )
        } catch (e: any) {
          console.error(
            `[useExploreContent:${contentType}] Error resolving and loading next:`,
            e
          )
        }
      }
    } else {
      // Can go next: just resolve and sync
      storeActions.nextItem()

      if (queueItemId) {
        try {
          await sseService.resolveItem(
            queueItemId,
            storeActions.getBufferIds(),
            storeActions.getBufferPosition()
          )
        } catch (e: any) {
          console.error(
            `[useExploreContent:${contentType}] Error resolving item:`,
            e
          )
        }
      }
    }
  }

  /**
   * Navega al item anterior y sincroniza posición
   */
  async function goToPrevItem() {
    console.log(`[useExploreContent:${contentType}] Going to previous item`)

    const canGoPrev = storeActions.canGoPrev()

    if (canGoPrev) {
      storeActions.prevItem()

      try {
        await sseService.syncPosition(
          storeActions.getBufferIds(),
          storeActions.getBufferPosition()
        )
      } catch (e: any) {
        console.error(
          `[useExploreContent:${contentType}] Error syncing position:`,
          e
        )
      }
    }
  }

  /**
   * Marca una palabra como aprendida y carga nuevo batch
   */
  async function markWordAsLearned() {
    console.log(`[useExploreContent:${contentType}] Marking word as learned`)

    try {
      await sseService.syncBufferAndNext(
        BATCH_SIZE,
        storeActions.getBufferIds(),
        storeActions.getBufferPosition()
      )
    } catch (e: any) {
      console.error(
        `[useExploreContent:${contentType}] Error syncing buffer and loading next:`,
        e
      )
    }
  }

  /**
   * Detiene el SSE cuando se desmonta el componente
   */
  function cleanup() {
    console.log(`[useExploreContent:${contentType}] Cleaning up`)
    isComponentMounted.value = false
    sseService.stopSSE()
  }

  return {
    // Lifecycle
    initializeSession,
    cleanup,

    // Actions
    loadNextBatch,
    goToNextItem,
    goToPrevItem,
    markWordAsLearned,

    // SSE service (exposición para acceso directo si es necesario)
    sseService,
  }
}
