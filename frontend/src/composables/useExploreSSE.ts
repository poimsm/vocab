import { ref, computed } from 'vue'
import api from '@/utils/api'
import { useAuthStore } from '@/stores/auth'

/**
 * Composable genérico para manejar SSE de explore.
 * Reutilizable para examples, best_options, y otros tipos de contenido.
 */

export interface ExploreAction {
  action: string
  resolve_queue_item_id?: number | null
  limit: number
  buffer_delivery_ids: number[]
  buffer_position: number
}

export interface ExploreEventData {
  request_id: string
  status?: string
  buffer_delivery_ids: number[]
  buffer_position: number
  message?: string
  error?: string
  examples?: any[]
  examples_count?: number
  best_options?: any[]
  best_options_count?: number
  timestamp: number
}

export function useExploreSSE(
  contentType: 'examples' | 'best_options',
  onCompleted?: (data: ExploreEventData) => void,
  onGenerating?: (data: ExploreEventData) => void,
  onError?: (error: string) => void,
) {
  const authStore = useAuthStore()
  const API_BASE = import.meta.env.VITE_API_BASE || '/api'

  // Estado local
  let sseEventSource: EventSource | null = null
  let sseActive = ref(false)

  /**
   * Inicia la conexión SSE y configura listeners para los eventos
   */
  function startSSE() {
    console.log(`[useExploreSSE:${contentType}] Starting SSE stream`)

    // Limpiar conexión previa
    if (sseEventSource) {
      console.log(`[useExploreSSE:${contentType}] Cleaning up previous EventSource`)
      sseEventSource.close()
      sseEventSource = null
    }

    sseActive.value = true

    // Construir URL del SSE stream
    const baseUrl = API_BASE.startsWith('http') ? API_BASE : `${window.location.origin}${API_BASE}`
    const endpoint = contentType === 'examples' ? '/examples/explore-stream' : '/best-options/explore-stream'
    const sseUrl = new URL(`${baseUrl}${endpoint}`)

    if (authStore.token) {
      sseUrl.searchParams.append('token', authStore.token)
    }

    const fullUrl = sseUrl.toString()
    console.log(`[useExploreSSE:${contentType}] Connecting to: ${fullUrl}`)

    try {
      sseEventSource = new EventSource(fullUrl)

      // Evento: open (conexión establecida)
      sseEventSource.addEventListener('open', () => {
        console.log(`[useExploreSSE:${contentType}:open] Connection established`)
      })

      // Evento: started
      const startedEventName = `${contentType === 'examples' ? 'examples' : 'best_options'}_explore.started`
      sseEventSource.addEventListener(startedEventName, (event: MessageEvent) => {
        if (!sseActive.value) {
          console.log(`[useExploreSSE:${contentType}:started] Stream disabled, ignoring event`)
          return
        }

        try {
          const data = JSON.parse(event.data)
          console.log(`[useExploreSSE:${contentType}:started] Exploration started:`, data.request_id)
          onGenerating?.(data)
        } catch (e) {
          console.error(`[useExploreSSE:${contentType}:started] Error parsing event:`, e)
        }
      })

      // Evento: processing
      const processingEventName = `${contentType === 'examples' ? 'examples' : 'best_options'}_explore.processing`
      sseEventSource.addEventListener(processingEventName, (event: MessageEvent) => {
        if (!sseActive.value) {
          console.log(`[useExploreSSE:${contentType}:processing] Stream disabled, ignoring event`)
          return
        }

        try {
          const data = JSON.parse(event.data)
          console.log(`[useExploreSSE:${contentType}:processing] Processing actions...`, data.message)
          onGenerating?.(data)
        } catch (e) {
          console.error(`[useExploreSSE:${contentType}:processing] Error parsing event:`, e)
        }
      })

      // Evento: completed
      const completedEventName = `${contentType === 'examples' ? 'examples' : 'best_options'}_explore.completed`
      sseEventSource.addEventListener(completedEventName, (event: MessageEvent) => {
        if (!sseActive.value) {
          console.log(`[useExploreSSE:${contentType}:completed] Stream disabled, ignoring event`)
          return
        }

        try {
          const data = JSON.parse(event.data)
          console.log(`[useExploreSSE:${contentType}:completed] Exploration completed:`, data)

          sseActive.value = false
          sseEventSource?.close()

          onCompleted?.(data)
        } catch (e) {
          console.error(`[useExploreSSE:${contentType}:completed] Error parsing event:`, e)
        }
      })

      // Evento: failed
      const failedEventName = `${contentType === 'examples' ? 'examples' : 'best_options'}_explore.failed`
      sseEventSource.addEventListener(failedEventName, (event: MessageEvent) => {
        if (!sseActive.value) {
          console.log(`[useExploreSSE:${contentType}:failed] Stream disabled, ignoring event`)
          return
        }

        try {
          const data = JSON.parse(event.data)
          console.error(`[useExploreSSE:${contentType}:failed] Exploration failed:`, data.error)

          sseActive.value = false
          sseEventSource?.close()

          onError?.(data.error || 'Failed to process explore action')
        } catch (e) {
          console.error(`[useExploreSSE:${contentType}:failed] Error parsing event:`, e)
        }
      })

      // Evento: error de conexión
      sseEventSource.addEventListener('error', (event: Event) => {
        console.error(`[useExploreSSE:${contentType}:error] Connection error:`, event)

        if (sseEventSource?.readyState === EventSource.CLOSED) {
          console.log(`[useExploreSSE:${contentType}:error] Connection closed`)
          sseActive.value = false
        } else {
          console.error(`[useExploreSSE:${contentType}:error] Unexpected error`)
          sseActive.value = false
          sseEventSource?.close()
          onError?.('Connection error - please try again')
        }
      })
    } catch (e) {
      console.error(`[useExploreSSE:${contentType}] Error creating EventSource:`, e)
      sseActive.value = false
      onError?.('Failed to connect to stream')
    }
  }

  /**
   * Detiene la conexión SSE
   */
  function stopSSE() {
    console.log(`[useExploreSSE:${contentType}] Stopping SSE stream`)
    sseActive.value = false

    if (sseEventSource) {
      console.log(`[useExploreSSE:${contentType}] Closing EventSource`)
      sseEventSource.close()
      sseEventSource = null
    }
  }

  /**
   * Envía una solicitud de explore al backend y inicia SSE si es necesario
   */
  async function sendExploreRequest(
    actions: string[],
    options: {
      resolve_queue_item_id?: number | null
      limit: number
      buffer_delivery_ids: number[]
      buffer_position: number
    }
  ) {
    const endpoint = contentType === 'examples' ? '/examples/explore' : '/best-options/explore'

    console.log(
      `[useExploreSSE:${contentType}] Sending POST ${endpoint}`,
      'actions:',
      actions
    )

    try {
      const response = await api.post(endpoint, {
        actions,
        resolve_queue_item_id: options.resolve_queue_item_id,
        limit: options.limit,
        buffer_delivery_ids: options.buffer_delivery_ids,
        buffer_position: options.buffer_position,
      })

      console.log(`[useExploreSSE:${contentType}] POST request enqueued:`, response.data)

      // Iniciar SSE para escuchar respuesta si es necesario
      if (!sseActive.value && (actions.includes('next') || actions.includes('resume'))) {
        console.log(`[useExploreSSE:${contentType}] Starting SSE for response`)
        startSSE()
      }

      return response.data
    } catch (e: any) {
      console.error(`[useExploreSSE:${contentType}] Error sending explore request:`, e)
      const errorMsg = e.response?.data?.message || e.message || 'Failed to send explore request'
      onError?.(errorMsg)
      throw e
    }
  }

  /**
   * Acción: cargar nuevo batch (acción 'next')
   */
  async function loadNextBatch(limit: number, bufferIds: number[], bufferPosition: number) {
    console.log(`[useExploreSSE:${contentType}] loadNextBatch`)
    return sendExploreRequest(['next'], {
      limit,
      buffer_delivery_ids: bufferIds,
      buffer_position: bufferPosition,
    })
  }

  /**
   * Acción: resume sesión (acción 'resume')
   */
  async function resumeSession(limit: number) {
    console.log(`[useExploreSSE:${contentType}] resumeSession`)
    return sendExploreRequest(['resume'], {
      limit,
      buffer_delivery_ids: [],
      buffer_position: 0,
    })
  }

  /**
   * Acción: sincronizar posición (acción 'sync')
   */
  async function syncPosition(bufferIds: number[], bufferPosition: number) {
    console.log(`[useExploreSSE:${contentType}] syncPosition`)
    return sendExploreRequest(['sync'], {
      limit: 5,
      buffer_delivery_ids: bufferIds,
      buffer_position: bufferPosition,
    })
  }

  /**
   * Acción: resolver item (acción 'resolve')
   */
  async function resolveItem(
    queueItemId: number,
    bufferIds: number[],
    bufferPosition: number
  ) {
    console.log(`[useExploreSSE:${contentType}] resolveItem`, queueItemId)
    return sendExploreRequest(['resolve', 'sync'], {
      resolve_queue_item_id: queueItemId,
      limit: 5,
      buffer_delivery_ids: bufferIds,
      buffer_position: bufferPosition,
    })
  }

  /**
   * Acción: resolver y cargar siguiente (acción 'resolve' + 'next')
   */
  async function resolveAndNext(
    queueItemId: number,
    limit: number,
    bufferIds: number[],
    bufferPosition: number
  ) {
    console.log(`[useExploreSSE:${contentType}] resolveAndNext`, queueItemId)
    return sendExploreRequest(['resolve', 'next'], {
      resolve_queue_item_id: queueItemId,
      limit,
      buffer_delivery_ids: bufferIds,
      buffer_position: bufferPosition,
    })
  }

  /**
   * Acción: sincronizar buffer y cargar siguiente (para cuando se marca una palabra como learned)
   */
  async function syncBufferAndNext(
    limit: number,
    bufferIds: number[],
    bufferPosition: number
  ) {
    console.log(`[useExploreSSE:${contentType}] syncBufferAndNext`)
    return sendExploreRequest(['sync-buffer', 'next'], {
      limit,
      buffer_delivery_ids: bufferIds,
      buffer_position: bufferPosition,
    })
  }

  return {
    // Estado
    sseActive: computed(() => sseActive.value),

    // Métodos principales
    startSSE,
    stopSSE,
    sendExploreRequest,

    // Acciones específicas
    loadNextBatch,
    resumeSession,
    syncPosition,
    resolveItem,
    resolveAndNext,
    syncBufferAndNext,
  }
}
