import { activityApi } from '@/services/activityApi'

/**
 * Composable para rastrear actividades del usuario (clicks, interacciones, etc)
 * Uso: const { trackButtonClick } = useActivityTracking()
 */
export function useActivityTracking() {
  /**
   * Registra un click de botón
   * @param buttonName - nombre descriptivo del botón (ej: 'learn_button', 'mark_favorite')
   * @param details - datos adicionales opcionales (ej: wordId, difficulty)
   */
  const trackButtonClick = (buttonName: string, details?: Record<string, any>) => {
    activityApi.logButtonClick(buttonName, details)
  }

  /**
   * Registra una vista de página
   */
  const trackPageView = (pageName: string, details?: Record<string, any>) => {
    activityApi.logPageView(pageName, details)
  }

  /**
   * Registra una interacción con una característica
   */
  const trackFeatureInteraction = (featureName: string, details?: Record<string, any>) => {
    activityApi.logFeatureInteraction(featureName, details)
  }

  /**
   * Retorna un manejador de eventos que registra el click y ejecuta la acción original
   * Útil para envolver en @click
   * @param buttonName - nombre del botón
   * @param handler - función a ejecutar (opcional)
   * @param details - datos adicionales (opcional)
   */
  const createClickHandler = (
    buttonName: string,
    handler?: () => void | Promise<void>,
    details?: Record<string, any>
  ) => {
    return async () => {
      trackButtonClick(buttonName, details)
      if (handler) {
        await handler()
      }
    }
  }

  return {
    trackButtonClick,
    trackPageView,
    trackFeatureInteraction,
    createClickHandler
  }
}
