import { ref } from 'vue'
import api from '@/utils/api'

export interface ExplorePollResult {
  status: string
  buffer_delivery_ids: number[]
  buffer_position: number
  examples?: any[]
  best_options?: any[]
  error?: string
}

/**
 * Composable para polling de tareas explore usando Redis.
 * Reemplaza SSE con un polling simple cada 1 segundo.
 */
export function useExplorePolling() {
  const isPolling = ref(false)
  let pollInterval: ReturnType<typeof setInterval> | null = null
  let pollTimeout: ReturnType<typeof setTimeout> | null = null
  let currentRequestId: string | null = null

  /**
   * Inicia polling para una tarea explore.
   * Cada 1 segundo consulta el status en Redis.
   * Cuando status == "completed", obtiene los resultados de Postgres.
   */
  async function startPolling(
    requestId: string,
    featureType: 'examples' | 'best_options',
    onResult: (result: ExplorePollResult) => void,
    onError: (error: string) => void
  ) {
    console.log(`[useExplorePolling] Starting polling for ${featureType}`, { requestId })

    if (isPolling.value) {
      console.warn(`[useExplorePolling] Already polling, stopping previous`)
      stopPolling()
    }

    isPolling.value = true
    currentRequestId = requestId

    const endpoint = featureType === 'examples' ? '/examples' : '/best-options'
    let pollCount = 0

    pollInterval = setInterval(async () => {
      pollCount++
      try {
        console.debug(`[useExplorePolling:poll#${pollCount}] Checking status for ${requestId}`)

        // 1. Verificar status en Redis
        const statusResponse = await api.get(`${endpoint}/explore/status/${requestId}`)
        const { status, message } = statusResponse.data

        console.debug(`[useExplorePolling:poll#${pollCount}] Status:`, { status, message })

        if (status === 'processing') {
          // Seguir esperando
          console.debug(`[useExplorePolling:poll#${pollCount}] Still processing...`)
          return
        }

        if (status === 'failed') {
          // Error en la tarea
          const errorMsg = statusResponse.data.error || 'Task failed'
          console.error(`[useExplorePolling] Task failed:`, errorMsg)
          stopPolling()
          onError(errorMsg)
          return
        }

        if (status === 'completed') {
          console.log(`[useExplorePolling] Task completed, fetching results`)

          // 2. Obtener resultados desde Postgres
          const resultsResponse = await api.get(`${endpoint}/explore/results/${requestId}`)
          const results = resultsResponse.data

          console.log(`[useExplorePolling] Results loaded successfully`, {
            buffer_ids_count: results.buffer_delivery_ids?.length || 0,
            items_count: results.examples_count || results.best_options_count || 0,
          })

          stopPolling()
          onResult(results)
        }
      } catch (error: any) {
        console.error(`[useExplorePolling:poll#${pollCount}] Error:`, error)

        // Si el recurso no existe (404) o error de red, puede ser que haya expirado o error
        if (error.response?.status === 404) {
          console.error(`[useExplorePolling] Request not found (may have expired)`)
          stopPolling()
          onError('Request expired - please try again')
        }
      }
    }, 1000) // Poll cada 1 segundo

    // Timeout de seguridad: 5 minutos
    pollTimeout = setTimeout(() => {
      console.warn(`[useExplorePolling] Timeout: polling took too long`)
      stopPolling()
      onError('Task took too long to complete')
    }, 5 * 60 * 1000)
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
    if (pollTimeout) {
      clearTimeout(pollTimeout)
      pollTimeout = null
    }
    isPolling.value = false
    currentRequestId = null
    console.debug(`[useExplorePolling] Polling stopped`)
  }

  return {
    isPolling,
    startPolling,
    stopPolling,
  }
}
