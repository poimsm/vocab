<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import api from '@/utils/api'
import { useAssetUrl } from '@/composables/useAssetUrl'

const { buildAssetUrl } = useAssetUrl()

interface VocabWord {
  id: string
  word: string
  definition: string
  category: string
  is_added?: boolean
  word_id?: number
}

interface VocabTheme {
  id: string
  name: string
  cover_image: string
  main_image: string
  description: string
  words_count: number
}

// State
const themes = ref<VocabTheme[]>([])
const selectedTheme = ref<VocabTheme | null>(null)
const themeWords = ref<VocabWord[]>([])
const addingWords = ref<Set<string>>(new Set())
const successMessage = ref<string | null>(null)
const errorMessage = ref<string | null>(null)
const searchQuery = ref('')
const selectedCategory = ref<string>('all')
const loadingThemes = ref(false)
const loadingWords = ref(false)
const isImageFullscreen = ref(false)
const imageZoom = ref(1)
const imageOffset = ref({ x: 0, y: 0 })

// Computed
const categories = computed(() => {
  const cats = new Set(themeWords.value.map(item => item.category))
  return ['all', ...Array.from(cats).sort()]
})

const filteredItems = computed(() => {
  return themeWords.value.filter(item => {
    const matchesSearch = item.word.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
                         item.definition.toLowerCase().includes(searchQuery.value.toLowerCase())
    const matchesCategory = selectedCategory.value === 'all' || item.category === selectedCategory.value
    return matchesSearch && matchesCategory
  })
})

// Methods
async function loadThemes() {
  try {
    loadingThemes.value = true
    const response = await api.get('/vocab-imgs/')
    themes.value = response.data.items || []
    errorMessage.value = null
  } catch (error: any) {
    const detail = error.response?.data?.detail || error.response?.data?.message || 'Failed to load themes'
    errorMessage.value = detail
    console.error('Error loading themes:', error)
  } finally {
    loadingThemes.value = false
  }
}

async function selectTheme(theme: VocabTheme) {
  selectedTheme.value = theme
  themeWords.value = []
  searchQuery.value = ''
  selectedCategory.value = 'all'
  successMessage.value = null
  errorMessage.value = null
  window.scrollTo(0, 0)
  await loadThemeWords(theme.id)
}

async function loadThemeWords(themeId: string) {
  try {
    loadingWords.value = true
    const response = await api.get(`/vocab-imgs/${themeId}/words`)
    themeWords.value = response.data.items || []
    errorMessage.value = null
  } catch (error: any) {
    const detail = error.response?.data?.detail || error.response?.data?.message || 'Failed to load words'
    errorMessage.value = detail
    console.error('Error loading theme words:', error)
  } finally {
    loadingWords.value = false
  }
}

function backToThemes() {
  selectedTheme.value = null
  themeWords.value = []
  searchQuery.value = ''
  selectedCategory.value = 'all'
  successMessage.value = null
  errorMessage.value = null
  window.scrollTo(0, 0)
}

async function addWord(item: VocabWord) {
  if (item.is_added) return

  addingWords.value.add(item.id)
  errorMessage.value = null
  successMessage.value = null

  try {
    const response = await api.post('/vocab-imgs/add-word', {
      vocab_image_word_id: item.id,
      word: item.word,
      definition: item.definition
    })

    const data = response.data

    if (data.status === 'error') {
      errorMessage.value = data.message || 'Failed to add word'
      return
    }

    // Mark word as added
    const wordIndex = themeWords.value.findIndex(w => w.id === item.id)
    if (wordIndex !== -1) {
      const word = themeWords.value[wordIndex]
      if (word) {
        word.is_added = true
        word.word_id = data.word_id
      }
    }

    successMessage.value = `"${item.word}" added to your vocabulary!`

    // Clear success message after 2 seconds
    setTimeout(() => {
      successMessage.value = null
    }, 2000)
  } catch (error: any) {
    const detail = error.response?.data?.detail || error.response?.data?.message || 'Failed to add word'
    errorMessage.value = detail
  } finally {
    addingWords.value.delete(item.id)
  }
}

function clearFilters() {
  searchQuery.value = ''
  selectedCategory.value = 'all'
}

function openImageFullscreen() {
  isImageFullscreen.value = true
  imageZoom.value = 1
  imageOffset.value = { x: 0, y: 0 }
  document.body.style.overflow = 'hidden'
}

function closeImageFullscreen() {
  isImageFullscreen.value = false
  imageZoom.value = 1
  imageOffset.value = { x: 0, y: 0 }
  document.body.style.overflow = 'auto'
}

function zoomIn() {
  imageZoom.value = Math.min(imageZoom.value + 0.2, 3)
}

function zoomOut() {
  imageZoom.value = Math.max(imageZoom.value - 0.2, 1)
}

function moveUp() {
  const maxOffsetY = (imageZoom.value - 1) * 300
  imageOffset.value.y = Math.min(maxOffsetY, imageOffset.value.y + 50)
}

function moveDown() {
  const maxOffsetY = (imageZoom.value - 1) * 300
  imageOffset.value.y = Math.max(-maxOffsetY, imageOffset.value.y - 50)
}

function moveLeft() {
  const maxOffsetX = (imageZoom.value - 1) * 300
  imageOffset.value.x = Math.max(-maxOffsetX, imageOffset.value.x - 50)
}

function moveRight() {
  const maxOffsetX = (imageZoom.value - 1) * 300
  imageOffset.value.x = Math.min(maxOffsetX, imageOffset.value.x + 50)
}

// Load themes on mount
onMounted(() => {
  loadThemes()
})
</script>

<template>
  <div class="vocab-image-page">
    <!-- Themes Grid View -->
    <template v-if="!selectedTheme">
      <div class="themes-container">
        <div class="themes-header">
          <h1 class="themes-title">Vocabulary by Theme</h1>
          <p class="themes-subtitle">Choose a topic and explore vocabulary with visual learning</p>
        </div>

        <!-- Loading state -->
        <div v-if="loadingThemes" class="loading-state">
          <div class="spinner"></div>
          <p>Loading themes...</p>
        </div>

        <!-- Error state -->
        <div v-else-if="errorMessage" class="error-state">
          <Icon icon="solar:close-circle-linear" width="48" />
          <p>{{ errorMessage }}</p>
          <button @click="loadThemes" class="retry-btn">Retry</button>
        </div>

        <!-- Empty state -->
        <div v-else-if="themes.length === 0" class="empty-state">
          <Icon icon="solar:inbox-linear" width="48" />
          <p>No vocabulary themes available</p>
        </div>

        <!-- Themes grid -->
        <div v-else class="themes-grid">
          <div
            v-for="theme in themes"
            :key="theme.id"
            class="theme-card"
            @click="selectTheme(theme)"
          >
            <div class="theme-cover-wrapper">
              <img :src="buildAssetUrl(theme.cover_image)" :alt="theme.name" class="theme-cover" />
            </div>
            <div class="theme-info">
              <h2 class="theme-name">{{ theme.name }}</h2>
              <!-- <p class="theme-description">{{ theme.description }}</p> -->
              <!-- <div class="theme-footer">
                <span class="word-count">{{ theme.words_count }} words</span>
                <Icon icon="solar:alt-arrow-right-linear" width="18" />
              </div> -->
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Selected Theme View -->
    <template v-else>
      <!-- Back Button -->
      <div class="back-bar">
        <button class="back-btn" @click="backToThemes">
          <Icon icon="solar:alt-arrow-left-linear" width="18" />
          Back to themes
        </button>
      </div>

      <!-- Image Section -->
      <div class="image-section">
        <img
          :src="buildAssetUrl(selectedTheme.main_image)"
          :alt="selectedTheme.name"
          class="vocab-image"
          @click="openImageFullscreen"
        />
      </div>

      <!-- Image Fullscreen Modal -->
      <transition name="fade">
        <div v-if="isImageFullscreen" class="image-fullscreen-overlay" @click="closeImageFullscreen">
          <div class="image-fullscreen-container" @click.stop>
            <button class="close-btn" @click="closeImageFullscreen">
              <Icon icon="solar:close-circle-linear" width="28" />
            </button>
            <img
              :src="buildAssetUrl(selectedTheme.main_image)"
              :alt="selectedTheme.name"
              class="fullscreen-image"
              :style="{
                transform: `scale(${imageZoom}) translate(${imageOffset.x}px, ${imageOffset.y}px)`
              }"
            />
            <div class="image-controls">
              <!-- Navigation Controls -->
              <div class="nav-controls" v-if="imageZoom > 1">
                <button class="nav-btn nav-up" @click="moveUp" title="Move up">
                  <Icon icon="solar:alt-arrow-up-linear" width="18" />
                </button>
                <div class="nav-horizontal">
                  <button class="nav-btn nav-left" @click="moveLeft" title="Move left">
                    <Icon icon="solar:alt-arrow-left-linear" width="18" />
                  </button>
                  <button class="nav-btn nav-right" @click="moveRight" title="Move right">
                    <Icon icon="solar:alt-arrow-right-linear" width="18" />
                  </button>
                </div>
                <button class="nav-btn nav-down" @click="moveDown" title="Move down">
                  <Icon icon="solar:alt-arrow-down-linear" width="18" />
                </button>
              </div>

              <!-- Zoom Controls -->
              <div class="zoom-controls">
                <button class="zoom-btn zoom-minus" @click="zoomOut" :disabled="imageZoom <= 1">
                  <Icon icon="solar:minus-linear" width="20" />
                </button>
                <span class="zoom-level">{{ Math.round(imageZoom * 100) }}%</span>
                <button class="zoom-btn zoom-plus" @click="zoomIn" :disabled="imageZoom >= 3">
                  <Icon icon="solar:add-circle-linear" width="20" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </transition>

      <!-- Vocabulary List Section -->
      <div class="list-section">
        <!-- Header -->
        <div class="list-header">
          <h1 class="title">{{ selectedTheme.name }} - Vocabulary</h1>
          <p class="subtitle">Click to add words to your vocabulary list</p>
        </div>

        <!-- Filters -->
        <div class="filters">
          <!-- <input
            v-model="searchQuery"
            type="text"
            placeholder="Search words..."
            class="search-input"
          /> -->

          <div class="category-filters">
            <button
              v-for="cat in categories"
              :key="cat"
              @click="selectedCategory = cat"
              class="category-btn"
              :class="{ active: selectedCategory === cat }"
            >
              {{ cat }}
            </button>
          </div>

          <button v-if="searchQuery || selectedCategory !== 'all'" @click="clearFilters" class="clear-btn">
            Clear filters
          </button>
        </div>

        <!-- Messages -->
        <transition name="fade">
          <div v-if="successMessage" class="success-message">
            <Icon icon="solar:check-circle-linear" width="20" />
            {{ successMessage }}
          </div>
        </transition>

        <transition name="fade">
          <div v-if="errorMessage" class="error-message">
            <Icon icon="solar:close-circle-linear" width="20" />
            {{ errorMessage }}
          </div>
        </transition>

        <!-- Loading state for words -->
        <div v-if="loadingWords" class="loading-state">
          <div class="spinner"></div>
          <p>Loading words...</p>
        </div>

        <!-- Words List -->
        <div v-else class="words-list">
          <div v-if="filteredItems.length === 0" class="empty-state">
            <Icon icon="solar:magnifer-linear" width="48" />
            <p>No words match your search</p>
          </div>

          <div v-for="item in filteredItems" :key="item.id" class="word-card">
            <div class="word-content">
              <h3 class="word">{{ item.word }}</h3>
              <p class="definition">{{ item.definition }}</p>
              <span class="category-tag">{{ item.category }}</span>
            </div>

            <button
              @click="addWord(item)"
              :disabled="item.is_added || addingWords.has(item.id)"
              class="add-btn"
              :class="{
                added: item.is_added,
                loading: addingWords.has(item.id)
              }"
            >
              <Icon
                :icon="item.is_added ? 'solar:check-circle-linear' : 'solar:add-circle-linear'"
                width="20"
              />
              {{ item.is_added ? 'Added' : 'Add' }}
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.vocab-image-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: #2d2a3e;
  color: #e2e0e8;
  overflow-x: hidden;
  width: 100%;
}

/* Themes Grid Container */
.themes-container {
  flex: 1;
  padding: 40px 20px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}

.themes-header {
  text-align: center;
  margin-bottom: 40px;
}

.themes-title {
  font-size: 36px;
  font-weight: 700;
  margin: 0 0 12px 0;
  color: #e2e0e8;
}

.themes-subtitle {
  font-size: 16px;
  color: #9c99ab;
  margin: 0;
}

.themes-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
}

.theme-card {
  display: flex;
  flex-direction: column;
  height: 100%;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition: all 0.3s ease;
  cursor: pointer;
  aspect-ratio: 1;
}

.theme-card:hover {
  border-color: rgba(155, 143, 181, 0.4);
  background: rgba(255, 255, 255, 0.04);
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.3);
}

.theme-cover-wrapper {
  width: 100%;
  height: 85%;
  overflow: hidden;
  background: #1a1825;
  flex-shrink: 0;
}

.theme-cover {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
  transition: transform 0.3s ease;
}

.theme-card:hover .theme-cover {
  transform: scale(1.05);
}

.theme-info {
  padding: 14px;
  display: flex;
  flex-direction: column;
  flex: 1;
  justify-content: space-between;
}

.theme-name {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 4px 0;
  color: #e2e0e8;
  line-height: 1.2;
}

.theme-description {
  font-size: 13px;
  color: #9c99ab;
  margin: 0 0 6px 0;
  flex: 1;
  line-height: 1.3;
}

.theme-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 6px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  color: #9b8fb5;
  font-size: 10px;
  font-weight: 500;
}

.word-count {
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* Back Button Bar */
.back-bar {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(0, 0, 0, 0.2);
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border: 1px solid rgba(155, 143, 181, 0.3);
  border-radius: 6px;
  background: rgba(155, 143, 181, 0.1);
  color: #9b8fb5;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.back-btn:hover {
  background: rgba(155, 143, 181, 0.2);
  border-color: #9b8fb5;
}

/* Image Section */
.image-section {
  width: 100%;
  flex-shrink: 0;
  background: #1a1825;
  padding: 20px;
  overflow-x: hidden;
  overflow-y: visible;
  box-sizing: border-box;
}

.vocab-image {
  width: 100%;
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  cursor: pointer;
  transition: opacity 0.2s ease;
}

.vocab-image:active {
  opacity: 0.9;
}

/* Fullscreen Modal */
.image-fullscreen-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: #000000;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  animation: fadeIn 0.3s ease;
}

.image-fullscreen-container {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  touch-action: pinch-zoom;
}

.fullscreen-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  user-select: none;
  -webkit-user-select: none;
  transition: transform 0.2s ease;
}

.close-btn {
  position: absolute;
  top: 16px;
  right: 16px;
  background: rgba(0, 0, 0, 0.5);
  border: none;
  border-radius: 50%;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  cursor: pointer;
  z-index: 1001;
  transition: all 0.2s ease;
  backdrop-filter: blur(4px);
}

.close-btn:hover {
  background: rgba(0, 0, 0, 0.8);
  transform: scale(1.1);
}

.close-btn:active {
  transform: scale(0.95);
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* Image Controls Container (Desktop only) */
.image-controls {
  position: absolute;
  bottom: 24px;
  right: 24px;
  display: none;
  flex-direction: column;
  gap: 12px;
  z-index: 1001;
}

/* Navigation Controls */
.nav-controls {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  background: rgba(0, 0, 0, 0.6);
  padding: 12px;
  border-radius: 12px;
  backdrop-filter: blur(4px);
}

.nav-horizontal {
  display: flex;
  gap: 8px;
}

.nav-btn {
  background: rgba(155, 143, 181, 0.2);
  border: 1px solid rgba(155, 143, 181, 0.4);
  border-radius: 6px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.nav-btn:hover {
  background: rgba(155, 143, 181, 0.4);
  border-color: #9b8fb5;
  transform: scale(1.1);
}

.nav-btn:active {
  transform: scale(0.95);
}

/* Zoom Controls */
.zoom-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(0, 0, 0, 0.6);
  padding: 12px 16px;
  border-radius: 12px;
  backdrop-filter: blur(4px);
}

.zoom-btn {
  background: rgba(155, 143, 181, 0.2);
  border: 1px solid rgba(155, 143, 181, 0.4);
  border-radius: 6px;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  cursor: pointer;
  transition: all 0.2s ease;
}

.zoom-btn:hover:not(:disabled) {
  background: rgba(155, 143, 181, 0.4);
  border-color: #9b8fb5;
  transform: scale(1.05);
}

.zoom-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.zoom-btn:active:not(:disabled) {
  transform: scale(0.95);
}

.zoom-level {
  color: #e2e0e8;
  font-size: 12px;
  font-weight: 600;
  min-width: 40px;
  text-align: center;
}

/* List Section */
.list-section {
  flex: 1;
  padding: 24px 20px;
  max-width: 100%;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
}

.list-header {
  margin-bottom: 24px;
}

.title {
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 8px 0;
  color: #e2e0e8;
}

.subtitle {
  margin: 0;
  font-size: 15px;
  color: #9c99ab;
}

/* Filters */
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 24px;
  align-items: center;
}

.search-input {
  flex: 1;
  min-width: 200px;
  padding: 10px 14px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  color: #e2e0e8;
  font-size: 14px;
  transition: all 0.2s ease;
}

.search-input::placeholder {
  color: #9c99ab;
}

.search-input:focus {
  outline: none;
  border-color: rgba(155, 143, 181, 0.5);
  background: rgba(255, 255, 255, 0.06);
}

.category-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.category-btn {
  padding: 8px 14px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  background: transparent;
  color: #9c99ab;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
  text-transform: capitalize;
}

.category-btn:hover {
  border-color: rgba(155, 143, 181, 0.5);
  color: #e2e0e8;
}

.category-btn.active {
  background: rgba(155, 143, 181, 0.2);
  border-color: #9b8fb5;
  color: #9b8fb5;
}

.clear-btn {
  padding: 8px 14px;
  border: 1px solid rgba(248, 113, 113, 0.3);
  border-radius: 20px;
  background: transparent;
  color: #f87171;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.clear-btn:hover {
  background: rgba(248, 113, 113, 0.1);
  border-color: #f87171;
}

/* Messages */
.success-message,
.error-message {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 14px;
  animation: slideDown 0.3s ease;
}

.success-message {
  background: rgba(74, 222, 128, 0.1);
  color: #4ade80;
  border: 1px solid rgba(74, 222, 128, 0.3);
}

.error-message {
  background: rgba(248, 113, 113, 0.1);
  color: #f87171;
  border: 1px solid rgba(248, 113, 113, 0.3);
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Loading State */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #9c99ab;
  text-align: center;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(155, 143, 181, 0.2);
  border-top-color: #9b8fb5;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Error State */
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #f87171;
  text-align: center;
}

.retry-btn {
  margin-top: 16px;
  padding: 10px 24px;
  border: 1px solid rgba(248, 113, 113, 0.3);
  border-radius: 6px;
  background: rgba(248, 113, 113, 0.1);
  color: #f87171;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.retry-btn:hover {
  background: rgba(248, 113, 113, 0.2);
  border-color: #f87171;
}

/* Empty State */
.empty-state {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #9c99ab;
  text-align: center;
}

.empty-state p {
  margin-top: 12px;
  font-size: 16px;
}

/* Words List */
.words-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

/* Word Card */
.word-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.02);
  transition: all 0.2s ease;
}

.word-card:hover {
  border-color: rgba(155, 143, 181, 0.3);
  background: rgba(255, 255, 255, 0.04);
}

.word-content {
  margin-bottom: 12px;
}

.word {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
  color: #e2e0e8;
}

.definition {
  margin: 0 0 12px 0;
  font-size: 15px;
  color: #9c99ab;
  line-height: 1.4;
}

.category-tag {
  display: inline-block;
  padding: 4px 8px;
  background: rgba(155, 143, 181, 0.1);
  color: #9b8fb5;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* Add Button */
.add-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 16px;
  border: 1px solid rgba(155, 143, 181, 0.3);
  border-radius: 6px;
  background: rgba(155, 143, 181, 0.1);
  color: #9b8fb5;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.add-btn:hover:not(:disabled) {
  background: rgba(155, 143, 181, 0.2);
  border-color: #9b8fb5;
}

.add-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.add-btn.loading {
  animation: pulse 1.5s ease-in-out infinite;
}

.add-btn.added {
  background: rgba(74, 222, 128, 0.1);
  border-color: rgba(74, 222, 128, 0.3);
  color: #4ade80;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

/* Responsive */

/* Desktop - Show image controls */
@media (min-width: 1025px) {
  .image-controls {
    display: flex;
  }
}

@media (max-width: 1024px) {
  .themes-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 768px) {
  .themes-container {
    padding: 20px 12px;
  }

  .themes-title {
    font-size: 24px;
    margin-bottom: 20px;
  }

  .themes-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
  }

  .theme-card {
    aspect-ratio: 1 / 1.1;
  }

  .theme-cover-wrapper {
    height: 80%;
  }

  .list-section {
    padding: 16px 12px;
  }

  .title {
    font-size: 22px;
  }

  .words-list {
    grid-template-columns: 1fr;
    margin-bottom: 150px;
  }

  .filters {
    flex-direction: column;
    align-items: stretch;
    gap: 16px;
  }

  .search-input {
    width: 100%;
    min-width: auto;
    font-size: 16px;
    padding: 14px 16px;
    min-height: 48px;
    box-sizing: border-box;
  }

  .category-filters {
    width: 100%;
    gap: 12px;
  }

  .category-btn {
    font-size: 15px;
    padding: 12px 18px;
    min-height: 44px;
  }

  .clear-btn {
    font-size: 15px;
    padding: 12px 18px;
    min-height: 44px;
  }

  .back-bar {
    padding: 12px 16px;
  }
}

@media (max-width: 480px) {
  .themes-container {
    padding: 16px 12px;
  }

  .themes-title {
    font-size: 20px;
    margin-bottom: 16px;
  }

  .themes-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .theme-card {
    aspect-ratio: 1 / 1;
  }

  .theme-cover-wrapper {
    height: 80%;
  }

  .theme-info {
    padding: 10px;
  }

  .theme-name {
    font-size: 14px;
  }

  .theme-description {
    font-size: 14px;
  }

  .list-section {
    padding: 14px 12px;
  }

  .title {
    font-size: 20px;
  }

  .filters {
    flex-direction: column;
    align-items: stretch;
    gap: 16px;
  }

  .search-input {
    width: 100%;
    font-size: 16px;
    padding: 14px 16px;
    min-height: 48px;
    box-sizing: border-box;
  }

  .category-filters {
    width: 100%;
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
  }

  .category-btn {
    font-size: 14px;
    padding: 12px 18px;
    min-height: 44px;
  }

  .clear-btn {
    font-size: 14px;
    padding: 12px 18px;
    min-height: 44px;
  }

  .word-card {
    padding: 14px;
  }

  .word {
    font-size: 16px;
  }

  .add-btn {
    padding: 12px 16px;
    font-size: 14px;
    min-height: 44px;
  }
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
