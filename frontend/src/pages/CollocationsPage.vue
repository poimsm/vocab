<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import { collocationApi } from '@/services/collocationApi'

interface Collocation {
  id: number
  phrase: string
  is_marked: boolean
}

const original = ref<Collocation[]>([])
const displayedCollocations = ref<Collocation[]>([])
const isLoading = ref(true)
const isLoadingMore = ref(false)
const error = ref<string | null>(null)
const filterStatus = ref<'all' | 'marked' | 'not_marked'>('all')
const isSavingStatus = ref<number | null>(null)
const isGenerating = ref(false)
const generateError = ref<string | null>(null)
const currentPage = ref(1)
const totalPages = ref(1)
const ITEMS_PER_PAGE = 15

const collocations = computed(() => displayedCollocations.value)

const updateDisplayedCollocations = () => {
  if (filterStatus.value === 'all') {
    displayedCollocations.value = original.value
  } else if (filterStatus.value === 'marked') {
    displayedCollocations.value = original.value.filter(c => c.is_marked)
  } else {
    displayedCollocations.value = original.value.filter(c => !c.is_marked)
  }
}

const toggleMarked = async (collocation: Collocation) => {
  const newStatus = !collocation.is_marked
  isSavingStatus.value = collocation.id

  try {
    const updated = await collocationApi.toggleMarked(collocation.id, newStatus)

    // Update local state - item se queda visible en el filtro actual, no se remueve
    const item = original.value.find(c => c.id === collocation.id)
    if (item) {
      item.is_marked = updated.is_marked
    }
  } catch (err) {
    console.error('Error updating collocation status:', err)
    error.value = 'Failed to update status'
  } finally {
    isSavingStatus.value = null
  }
}

const changeFilter = (newFilter: 'all' | 'marked' | 'not_marked') => {
  filterStatus.value = newFilter
  currentPage.value = 1
  original.value = []
  displayedCollocations.value = []
  loadCollocations()
}

const generateMoreCollocations = async () => {
  isGenerating.value = true
  generateError.value = null

  try {
    const result = await collocationApi.generate()

    if (result.status === 'created' && result.items) {
      // Add new items at the beginning (since they're sorted by created_at DESC)
      original.value.unshift(...result.items)
      // Update displayed items with new collocations
      updateDisplayedCollocations()
    } else if (result.status === 'no_words') {
      generateError.value = 'No words available to generate collocations. Please add some words first.'
    } else {
      generateError.value = 'Failed to generate collocations'
    }
  } catch (err: any) {
    console.error('Error generating collocations:', err)
    generateError.value = err.message || 'Failed to generate collocations'
  } finally {
    isGenerating.value = false
  }
}

const loadCollocations = async () => {
  try {
    isLoading.value = true
    error.value = null
    const response = await collocationApi.getCollocations(filterStatus.value, currentPage.value, ITEMS_PER_PAGE)

    // Generate initial collocations if empty
    if (response.total === 0) {
      const initResult = await collocationApi.generateInitial()
      if (initResult.status === 'created' && initResult.items) {
        original.value = initResult.items
        totalPages.value = 1
      }
    } else {
      if (currentPage.value === 1) {
        original.value = response.items
      } else {
        original.value.push(...response.items)
      }
      totalPages.value = response.pages
    }

    // Update displayed items with the loaded data
    updateDisplayedCollocations()
  } catch (err: any) {
    error.value = err.message || 'Failed to load collocations'
    console.error('Error loading collocations:', err)
  } finally {
    isLoading.value = false
    isLoadingMore.value = false
  }
}

const loadMoreCollocations = async () => {
  if (isLoadingMore.value || currentPage.value >= totalPages.value) {
    return
  }

  isLoadingMore.value = true
  currentPage.value++

  try {
    const response = await collocationApi.getCollocations(filterStatus.value, currentPage.value, ITEMS_PER_PAGE)
    original.value.push(...response.items)
    updateDisplayedCollocations()
  } catch (err: any) {
    console.error('Error loading more collocations:', err)
    currentPage.value-- // Revert page number on error
  } finally {
    isLoadingMore.value = false
  }
}

const handleWindowScroll = () => {
  const scrollTop = window.scrollY
  const clientHeight = window.innerHeight
  const scrollHeight = document.documentElement.scrollHeight

  // Si está cerca del final (200px), cargar más
  if (scrollHeight - (scrollTop + clientHeight) < 200) {
    if (currentPage.value < totalPages.value && !isLoadingMore.value) {
      loadMoreCollocations()
    }
  }
}

onMounted(() => {
  loadCollocations()
  window.addEventListener('scroll', handleWindowScroll)
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleWindowScroll)
})

onMounted(() => {
  loadCollocations()
})
</script>

<template>
  <div class="collocations-view">
    <!-- Loading State -->
    <div v-if="isLoading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading collocations...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <button @click="loadCollocations" class="retry-btn">Retry</button>
    </div>

    <!-- Empty State -->
    <div v-else-if="original.length === 0" class="empty-state">
      <Icon icon="fluent-emoji:smiling-face" width="48" />
      <p>No collocations yet. Create some to get started!</p>
      <button @click="generateMoreCollocations" class="generate-btn" :disabled="isGenerating">
        <Icon v-if="!isGenerating" icon="solar:bolt-2-linear" width="18" />
        <span v-if="isGenerating">Generating...</span>
        <span v-else>Generate Collocations</span>
      </button>
    </div>

    <!-- Content -->
    <div v-else class="content-wrapper">
      <!-- Header -->
      <div class="page-header">
        <div class="title-section">
          <h1 class="title">Cozy Collocations</h1>
          <Icon icon="fluent-emoji:relaxed-face" width="32" class="emoji" />
        </div>
        <button @click="generateMoreCollocations" class="generate-btn-header" :disabled="isGenerating" :title="isGenerating ? 'Generating...' : 'Generate more collocations'">
          <Icon icon="solar:bolt-linear" width="20" />
          <span v-if="!isGenerating">Generate</span>
          <span v-else class="spinner-small"></span>
        </button>
      </div>

      <!-- Generate Error Alert -->
      <div v-if="generateError" class="generate-error-alert">
        <p>{{ generateError }}</p>
        <button @click="generateError = null" class="close-alert">
          <Icon icon="solar:close-linear" width="16" />
        </button>
      </div>

      <!-- Filter -->
      <div class="filter-section">
        <div class="filter-group">
          <button
            v-for="option in ['all', 'marked', 'not_marked']"
            :key="option"
            class="filter-btn"
            :class="{ active: filterStatus === option }"
            @click="changeFilter(option as any)"
          >
            {{ option === 'all' ? 'All' : option === 'marked' ? 'Marked' : 'Not Marked' }}
          </button>
        </div>
      </div>

      <!-- Cards List with Infinite Scroll -->
      <div class="collocations-cards">
        <div
          v-for="collocation in collocations"
          :key="collocation.id"
          class="collocation-card"
          :class="{ marked: collocation.is_marked }"
        >
          <div class="card-content">
            <button
              class="mark-checkbox"
              @click="toggleMarked(collocation)"
              :disabled="isSavingStatus === collocation.id"
              :title="collocation.is_marked ? 'Unmark' : 'Mark as reviewed'"
            >
              <Icon
                v-if="collocation.is_marked"
                icon="solar:check-circle-bold"
                width="24"
                class="checked"
              />
              <Icon
                v-else
                icon="mdi:checkbox-blank-outline"
                width="24"
              />
            </button>
            <span class="phrase" :class="{ 'line-through': collocation.is_marked }">{{ collocation.phrase }}</span>
          </div>
        </div>

        <!-- Loading More Indicator -->
        <div v-if="isLoadingMore" class="loading-more">
          <div class="spinner-small"></div>
          <p>Loading more...</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.collocations-view {
  min-height: 100vh;
  padding: 24px 16px;
  background: #2d2a3e;
  color: #e2e0e8;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  max-width: 800px;
  margin: 0 auto;
}

.loading-state,
.error-state,
.empty-state {
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
.error-state p,
.empty-state p {
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

.retry-btn {
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

.retry-btn:hover {
  background: rgba(167, 139, 250, 0.2);
  border-color: rgba(167, 139, 250, 0.6);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  gap: 16px;
}

.title-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title {
  font-size: 32px;
  font-weight: 700;
  margin: 0;
  color: #e2e0e8;
  letter-spacing: -0.5px;
}

.emoji {
  flex-shrink: 0;
}

.generate-btn-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 8px;
  border: 1px solid rgba(167, 139, 250, 0.4);
  background: rgba(167, 139, 250, 0.1);
  color: #a78bfa;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.generate-btn-header:hover:not(:disabled) {
  background: rgba(167, 139, 250, 0.2);
  border-color: rgba(167, 139, 250, 0.6);
}

.generate-btn-header:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.generate-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-radius: 8px;
  border: 1px solid rgba(167, 139, 250, 0.4);
  background: rgba(167, 139, 250, 0.1);
  color: #a78bfa;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.generate-btn:hover:not(:disabled) {
  background: rgba(167, 139, 250, 0.2);
  border-color: rgba(167, 139, 250, 0.6);
}

.generate-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(124, 58, 237, 0.2);
  border-top-color: #7c3aed;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.spinner-small {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(167, 139, 250, 0.3);
  border-top-color: #a78bfa;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  display: inline-block;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.generate-error-alert {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-radius: 8px;
  background: rgba(255, 100, 100, 0.1);
  border: 1px solid rgba(255, 100, 100, 0.2);
  margin-bottom: 16px;
}

.generate-error-alert p {
  margin: 0;
  font-size: 14px;
  color: #ff6464;
}

.close-alert {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: #ff6464;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.close-alert:hover {
  color: #ff8888;
}

.filter-section {
  margin-bottom: 12px;
  flex-shrink: 0;
}

.filter-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-btn {
  padding: 6px 12px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.05);
  color: #9c99ab;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.filter-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
}

.filter-btn.active {
  background: rgba(167, 139, 250, 0.15);
  border-color: rgba(167, 139, 250, 0.4);
  color: #a78bfa;
}

.collocations-cards {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.loading-more {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 24px;
  color: #9c99ab;
  font-size: 14px;
}

.loading-more p {
  margin: 0;
}

.collocation-card {
  /* padding: 16px; */
  /* padding: 5px 7px 7px 0; */
  border-radius: 10px;
  /* background: rgba(255, 255, 255, 0.04); */
  /* border: 1px solid rgba(255, 255, 255, 0.08); */
  transition: all 0.2s ease;
}

.collocation-card:hover {
  /* background: rgba(255, 255, 255, 0.06); */
  /* border-color: rgba(255, 255, 255, 0.12); */
}

.collocation-card.marked {
  opacity: 0.6;
}

.card-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.mark-checkbox {
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
  transition: all 0.2s ease;
  border-radius: 8px;
}

.mark-checkbox:hover:not(:disabled) {
  color: #a78bfa;
  background: rgba(167, 139, 250, 0.1);
}

.mark-checkbox:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mark-checkbox .checked {
  color: #bfb0f7;
}

.phrase {
  font-size: 16px;
  font-weight: 500;
  color: #b8b5c8;
  word-break: break-word;
  flex: 1;
}

.phrase.line-through {
  color: #7c7a8a;
}

@media (max-width: 768px) {
  .collocations-view {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .title {
    font-size: 28px;
  }

  .generate-btn-header {
    width: 100%;
  }

  .loading-state,
  .error-state,
  .empty-state {
    padding: 32px 24px;
  }
}

@media (max-width: 480px) {
  .collocations-view {
    padding: 12px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 16px;
  }

  .title {
    font-size: 24px;
  }

  .emoji {
    width: 28px;
    height: 28px;
  }

  .generate-btn-header {
    width: 100%;
    font-size: 16px;
    justify-content: center;
  }

  .collocation-card {
    padding: 14px 0;
    border-radius: 8px;
  }

  .phrase {
    font-size: 18px;
  }

  .mark-checkbox {
    width: 36px;
    height: 36px;
  }

  .loading-state,
  .error-state,
  .empty-state {
    padding: 24px 16px;
  }

  .collocations-cards {
    gap: 0px;
  }

  .filter-btn {
    font-size: 15px;
  }
}
</style>