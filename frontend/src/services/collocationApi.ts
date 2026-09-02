import { apiClient } from '@/api/client'

export interface Collocation {
  id: number
  phrase: string
  is_marked: boolean
}

export interface CollocationListResponse {
  items: Collocation[]
  total: number
}

export const collocationApi = {
  /**
   * Fetch all collocations for the user
   * @param status - Filter: 'all', 'marked', or 'not_marked'
   */
  async getCollocations(status: 'all' | 'marked' | 'not_marked' = 'all'): Promise<CollocationListResponse> {
    const response = await apiClient.get('/collocations/list', {
      params: { status }
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
   * Update the marked status of a collocation
   */
  async toggleMarked(id: number, is_marked: boolean): Promise<Collocation> {
    const response = await apiClient.patch(`/collocations/${id}`, {
      is_marked
    })
    return response.data
  }
}
