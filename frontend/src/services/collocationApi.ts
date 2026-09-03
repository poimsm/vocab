import { apiClient } from '@/api/client'

export interface Collocation {
  id: number
  phrase: string
  is_marked: boolean
}

export interface CollocationListResponse {
  items: Collocation[]
  total: number
  page: number
  limit: number
  pages: number
  status: string
}

export const collocationApi = {
  /**
   * Fetch collocations for the user with pagination
   * @param status - Filter: 'all', 'marked', or 'not_marked'
   * @param page - Page number (default: 1)
   * @param limit - Items per page (default: 15)
   */
  async getCollocations(
    status: 'all' | 'marked' | 'not_marked' = 'all',
    page: number = 1,
    limit: number = 15
  ): Promise<CollocationListResponse> {
    const response = await apiClient.get('/collocations/list', {
      params: { status, page, limit }
    })
    return response.data
  },

  /**
   * Create a new collocation
   */
  async createCollocation(phrase: string, word_id?: number): Promise<Collocation> {
    const response = await apiClient.post('/collocations/', {
      phrase,
      word_id
    })
    return response.data
  },

  /**
   * Create multiple collocations at once
   */
  async createCollocations(phrases: Array<{ phrase: string; word_id?: number }>): Promise<{
    created: number
    items: Collocation[]
  }> {
    const response = await apiClient.post('/collocations/batch', phrases)
    return response.data
  },

  /**
   * Delete a specific collocation
   */
  async deleteCollocation(id: number): Promise<void> {
    await apiClient.delete(`/collocations/${id}`)
  },

  /**
   * Delete all collocations
   */
  async deleteAllCollocations(): Promise<{ deleted: number }> {
    const response = await apiClient.delete('/collocations/')
    return response.data
  },

  /**
   * Generate initial collocations for the user
   */
  async generateInitial(): Promise<{
    status: 'created' | 'already_exist'
    count: number
    items?: Collocation[]
  }> {
    const response = await apiClient.post('/collocations/generate-initial')
    return response.data
  },

  /**
   * Generate collocations automatically based on user's words
   */
  async generate(): Promise<{
    status: 'created' | 'no_words' | 'generation_failed'
    message?: string
    count: number
    words_used?: number
    items?: Collocation[]
  }> {
    const response = await apiClient.post('/collocations/generate')
    return response.data
  },

  /**
   * Update the marked status of a collocation
   */
  async toggleMarked(id: number, is_marked: boolean): Promise<Collocation> {
    const response = await apiClient.patch(`/collocations/${id}`, {
      is_marked
    })
    return response.data
  }
}
