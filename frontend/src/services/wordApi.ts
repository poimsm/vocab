import { apiClient } from '@/api/client'

export interface WordDetail {
  id: number
  main: string
  meaning: string
  synonyms: string[] | null
  type: string | null
  frequency: string | null
  level: string
  context: string | null
  source_text: string | null
  is_favorite: boolean
  is_learned: boolean
  created_at: string
  total_examples: number
  examples: string[]
}

export const wordApi = {
  /**
   * Fetch word detail by ID
   */
  async getWordDetail(wordId: number): Promise<WordDetail> {
    const response = await apiClient.get(`/words/words/${wordId}`)
    return response.data
  },

  /**
   * Toggle favorite status for a word
   */
  async toggleFavorite(wordId: number): Promise<{ id: number; is_favorite: boolean }> {
    const response = await apiClient.patch(`/words/words/${wordId}/favorite`)
    return response.data
  },

  /**
   * Mark word as learned
   */
  async markAsLearned(wordId: number): Promise<{
    status: string
    message: string
    word_id: number
    is_learned: boolean
  }> {
    const response = await apiClient.patch(`/words/words/${wordId}/learned`)
    return response.data
  }
}
