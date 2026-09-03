<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { wordApi, type WordDetail } from '@/services/wordApi'

const route = useRoute()
const router = useRouter()
const word = ref<WordDetail | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)
const isSavingFavorite = ref(false)
const isSavingLearned = ref(false)

const wordId = parseInt(route.params.id as string)

const loadWord = async () => {
  try {
    isLoading.value = true
    error.value = null
    word.value = await wordApi.getWordDetail(wordId)
  } catch (err: any) {
    error.value = err.message || 'Failed to load word'
    console.error('Error loading word:', err)
  } finally {
    isLoading.value = false
  }
}

const toggleFavorite = async () => {
  if (!word.value) return

  isSavingFavorite.value = true
  try {
    const result = await wordApi.toggleFavorite(wordId)
    word.value.is_favorite = result.is_favorite
  } catch (err) {
    console.error('Error toggling favorite:', err)
    error.value = 'Failed to update favorite status'
  } finally {
    isSavingFavorite.value = false
  }
}

const markAsLearned = async () => {
  if (!word.value) return

  isSavingLearned.value = true
  try {
    const result = await wordApi.markAsLearned(wordId)
    word.value.is_learned = result.is_learned
  } catch (err) {
    console.error('Error marking as learned:', err)
    error.value = 'Failed to mark as learned'
  } finally {
    isSavingLearned.value = false
  }
}

onMounted(() => {
  loadWord()
})
</script>

<template>
  <div class="word-detail-view">
    <!-- Loading State -->
    <div v-if="isLoading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading word...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <button @click="loadWord" class="retry-btn">Retry</button>
      <button @click="router.back()" class="back-btn">Go Back</button>
    </div>

    <!-- Content -->
    <div v-else-if="word" class="content-wrapper">
      <!-- Header -->
      <div class="header">
        <button @click="router.back()" class="back-button" title="Go back">
          <Icon icon="solar:arrow-left-linear" width="26" />
        </button>
        <h1 class="word-title">{{ word.main }}</h1>
        <div class="header-actions">
          <button
            @click="toggleFavorite"
            :disabled="isSavingFavorite"
            class="action-btn favorite-btn"
            :class="{ active: word.is_favorite }"
            :title="word.is_favorite ? 'Remove from favorites' : 'Add to favorites'"
          >
            <Icon
              :icon="word.is_favorite ? 'solar:heart-bold' : 'solar:heart-linear'"
              width="24"
            />
          </button>
          <button
            v-if="!word.is_learned"
            @click="markAsLearned"
            :disabled="isSavingLearned"
            class="action-btn learned-btn"
            title="Mark as learned"
          >
            <Icon icon="solar:check-circle-linear" width="24" />
          </button>
          <span v-else class="badge learned-badge">Learned</span>
        </div>
      </div>

      <!-- Meaning -->
      <div class="section">
        <h2 class="section-title">Meaning</h2>
        <p class="meaning-text">{{ word.meaning }}</p>
      </div>

      <!-- Info Grid -->
      <div class="info-grid">
        <div class="info-card" v-if="word.type">
          <span class="info-label">Type</span>
          <span class="info-value">{{ word.type }}</span>
        </div>
        <div class="info-card" v-if="word.frequency">
          <span class="info-label">Frequency</span>
          <span class="info-value">{{ word.frequency }}</span>
        </div>
        <div class="info-card" v-if="word.level">
          <span class="info-label">Level</span>
          <span class="info-value">{{ word.level }}</span>
        </div>
        <div class="info-card" v-if="word.context">
          <span class="info-label">Context</span>
          <span class="info-value">{{ word.context }}</span>
        </div>
      </div>

      <!-- Synonyms -->
      <div v-if="word.synonyms && word.synonyms.length > 0" class="section">
        <h2 class="section-title">Synonyms</h2>
        <div class="tags">
          <span v-for="(synonym, idx) in word.synonyms" :key="idx" class="tag">
            {{ synonym }}
          </span>
        </div>
      </div>

      <!-- Examples -->
      <div v-if="word.examples && word.examples.length > 0" class="section">
        <h2 class="section-title">Examples ({{ word.total_examples }})</h2>
        <div class="examples-list">
          <div v-for="(example, idx) in word.examples" :key="idx" class="example-card">
            <p class="example-text">{{ example }}</p>
          </div>
        </div>
      </div>

      <!-- Source Text -->
      <div v-if="word.source_text" class="section">
        <h2 class="section-title">Source</h2>
        <p class="source-text">{{ word.source_text }}</p>
      </div>

      <!-- Created Date -->
      <div class="section metadata">
        <span class="metadata-label">Added on {{ new Date(word.created_at).toLocaleDateString() }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.word-detail-view {
  min-height: 100vh;
  padding: 24px 16px;
  background: #2d2a3e;
  color: #e2e0e8;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  max-width: 800px;
  margin: 0 auto;
}

.loading-state,
.error-state {
  padding: 48px 36px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.loading-state p,
.error-state p {
  font-size: 16px;
  color: #9c99ab;
  margin: 0;
}

.error-state {
  border-color: rgba(255, 100, 100, 0.2);
}

.error-state p {
  color: #ff6464;
}

.retry-btn,
.back-btn {
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid rgba(167, 139, 250, 0.4);
  background: rgba(167, 139, 250, 0.1);
  color: #a78bfa;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.retry-btn:hover,
.back-btn:hover {
  background: rgba(167, 139, 250, 0.2);
  border-color: rgba(167, 139, 250, 0.6);
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(124, 58, 237, 0.2);
  border-top-color: #7c3aed;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.content-wrapper {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.header {
  display: flex;
  align-items: center;
  gap: 16px;
  justify-content: space-between;
}

.back-button {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border: none;
  background: transparent;
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  transition: all 0.2s ease;
}

.back-button:hover {
  color: #a78bfa;
  background: rgba(167, 139, 250, 0.1);
}

.word-title {
  font-size: 32px;
  font-weight: 700;
  margin: 0;
  flex: 1;
  color: #e2e0e8;
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.action-btn {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border: none;
  background: rgba(255, 255, 255, 0.05);
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  transition: all 0.2s ease;
}

.action-btn:hover:not(:disabled) {
  color: #a78bfa;
  background: rgba(167, 139, 250, 0.1);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-btn.favorite-btn.active {
  color: #ff6b9d;
  background: rgba(255, 107, 157, 0.1);
}

.action-btn.learned-btn {
  color: #4ade80;
}

.action-btn.learned-btn:hover:not(:disabled) {
  background: rgba(74, 222, 128, 0.1);
}

.badge {
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.learned-badge {
  background: rgba(74, 222, 128, 0.1);
  color: #4ade80;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-title {
  font-size: 14px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #a78bfa;
  margin: 0;
}

.meaning-text {
  font-size: 16px;
  line-height: 1.6;
  color: #b8b5c8;
  margin: 0;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.info-card {
  padding: 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  color: #7c7a8a;
  letter-spacing: 0.5px;
}

.info-value {
  font-size: 14px;
  font-weight: 600;
  color: #b8b5c8;
  text-transform: capitalize;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag {
  padding: 6px 12px;
  background: rgba(167, 139, 250, 0.15);
  border: 1px solid rgba(167, 139, 250, 0.3);
  border-radius: 6px;
  font-size: 13px;
  color: #b8b5c8;
  font-weight: 500;
}

.examples-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.example-card {
  padding: 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.example-text {
  font-size: 14px;
  line-height: 1.5;
  color: #b8b5c8;
  margin: 0;
  flex: 1;
}

.source-text {
  font-size: 13px;
  line-height: 1.6;
  color: #7c7a8a;
  margin: 0;
  font-style: italic;
  padding: 12px;
  background: rgba(255, 255, 255, 0.02);
  border-left: 2px solid rgba(167, 139, 250, 0.3);
}

.metadata {
  gap: 0;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.metadata-label {
  font-size: 12px;
  color: #7c7a8a;
}

@media (max-width: 768px) {
  .word-detail-view {
    padding: 16px;
  }

  .word-title {
    font-size: 24px;
  }

  .info-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 480px) {
  .word-detail-view {
    padding: 12px;
  }

  .header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .header-actions {
    align-self: flex-end;
  }

  .word-title {
    font-size: 25px;
  }

  .section-title {
    font-size: 15px;
  }

  .meaning-text {
    font-size: 19px;
  }

  .info-label {
    font-size: 14px;
  }

  .info-value {
    font-size: 17px;
  }

  .tag {
    font-size: 16px;
  }

  .example-text {
    font-size: 17px;
  }

  .source-text {
    font-size: 16px;
  }

  .metadata-label {
    font-size: 15px;
  }

  .info-grid {
    grid-template-columns: 1fr;
  }
}
</style>
