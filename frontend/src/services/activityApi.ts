import { apiClient } from '@/api/client'

export const activityApi = {
  /**
   * Log a button click (fire and forget - no await needed)
   */
  logButtonClick(buttonName: string, details?: Record<string, any>): void {
    // Fire and forget - don't block UI
    apiClient.post('/activities/button-click', {
      button_name: buttonName,
      details: details || {}
    }).catch((error) => {
      console.error(`Failed to log button click "${buttonName}":`, error)
    })
  },

  /**
   * Log a page view (fire and forget)
   */
  logPageView(pageName: string, details?: Record<string, any>): void {
    apiClient.post('/activities/page-view', {
      page_name: pageName,
      details: details || {}
    }).catch((error) => {
      console.error(`Failed to log page view "${pageName}":`, error)
    })
  },

  /**
   * Log a feature interaction (fire and forget)
   */
  logFeatureInteraction(featureName: string, details?: Record<string, any>): void {
    apiClient.post('/activities/feature-interaction', {
      feature_name: featureName,
      details: details || {}
    }).catch((error) => {
      console.error(`Failed to log feature interaction "${featureName}":`, error)
    })
  }
}
