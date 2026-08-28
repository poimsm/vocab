import { apiClient } from '@/api/client'

export interface QuickWriteExercise {
  id: number
  prompt: string
  emoji: string
  words?: string[]
  original_content?: string
  corrected_content?: string
  has_corrections: boolean
  is_favorite: boolean
  created_at: string
  updated_at: string
}

export interface QuickWriteListResponse {
  items: QuickWriteExercise[]
  total: number
}

export const quickWriteApi = {
  /**
   * Fetch all quick write exercises for the user
   */
  async getExercises(page: number = 1, limit: number = 100): Promise<QuickWriteListResponse> {
    const response = await apiClient.get('/quick-write', {
      params: { page, limit, sort: 'newest' }
    })
    return response.data
  },

  /**
   * Get a specific exercise by ID
   */
  async getExercise(id: number): Promise<QuickWriteExercise> {
    const response = await apiClient.get(`/quick-write/${id}`)
    return response.data
  },

  /**
   * Create a new quick write exercise
   */
  async createExercise(data: {
    prompt: string
    words?: string[]
    original_content?: string
  }): Promise<QuickWriteExercise> {
    const response = await apiClient.post('/quick-write', data)
    return response.data
  },

  /**
   * Update an exercise with user response (validates language and checks grammar)
   */
  async submitResponse(id: number, original_content: string): Promise<QuickWriteExercise> {
    const response = await apiClient.patch(`/quick-write/${id}`, {
      original_content
    })
    return response.data
  },

  /**
   * Toggle favorite status
   */
  async toggleFavorite(id: number): Promise<{ id: number; is_favorite: boolean }> {
    const response = await apiClient.patch(`/quick-write/${id}/favorite`)
    return response.data
  },

  /**
   * Delete an exercise
   */
  async deleteExercise(id: number): Promise<void> {
    await apiClient.delete(`/quick-write/${id}`)
  },

  /**
   * Check grammar of text (without saving)
   */
  async checkGrammar(text: string): Promise<{
    is_english: boolean
    detected_language: string
    original: string
    corrected: string
    errors: Array<{
      message: string
      offset: number
      length: number
      replacements: string[]
    }>
  }> {
    const response = await apiClient.post('/quick-write/check-grammar', { text })
    return response.data
  }
}
