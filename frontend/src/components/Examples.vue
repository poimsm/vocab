<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { Icon } from '@iconify/vue'

// ===================== TYPES =====================
interface WordRef {
  word_id: number
  main: string
  text_form: string
}

interface ExampleItem {
  id: number
  text: string
  is_favorite: boolean
  words: WordRef[]
}

interface Meta {
  total_items: number
  total_pages: number
  current_page: number
  limit: number
  has_next: boolean
  has_prev: boolean
}

interface ApiResponse {
  items: ExampleItem[]
  meta: Meta
}

interface WordDetail {
  id: number
  main: string
  meaning: string
  type: string
  frequency: string
  level: number
  context: string
  source_text: string
  is_favorite: boolean
  is_learned: boolean
  created_at: string
  total_examples: number
  examples: string[]
}

// ===================== STATE =====================
const API_BASE = import.meta.env.VITE_API_BASE;

const search = ref('')
const sortBy = ref('newest')
const currentPage = ref(1)
const limit = ref(10)
const showOnlyFavorites = ref(false)

// Data from API
const examples = ref<ExampleItem[]>([])
const meta = ref<Meta | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

// Review mode
const isReviewMode = ref(false)
const reviewIndex = ref(0)
const randomExamples = ref<ExampleItem[]>([])

// Word detail panel (Maneja el estado único por ejemplo y palabra)
const expandedWordState = ref<{ exampleId: number; wordId: number } | null>(null)
const wordDetail = ref<WordDetail | null>(null)
const loadingWordDetail = ref(false)

// Clipboard
const copiedId = ref<number | null>(null)

// Generating
const isGenerating = ref(false)
const generatingWordId = ref<number | null>(null)

// Toast
const toast = ref<{ show: boolean; message: string; type: 'success' | 'error' }>({
  show: false, message: '', type: 'success'
})

// ===================== COMPUTED =====================
const filteredExamples = computed(() => {
  if (!showOnlyFavorites.value) return examples.value
  return examples.value.filter(e => e.is_favorite)
})

const paginatedExamples = computed(() => filteredExamples.value)

const totalPages = computed(() => meta.value?.total_pages || 1)

const reviewCurrent = computed(() =>
  randomExamples.value.length ? randomExamples.value[reviewIndex.value] : null
)

const expandedWordName = computed(() => {
  if (!expandedWordState.value) return null
  const word = examples.value
    .flatMap(e => e.words)
    .find(w => w.word_id === expandedWordState.value?.wordId)
  return word?.main || null
})

// ===================== API CALLS =====================
async function fetchExamples() {
  loading.value = true
  error.value = null
  try {
    const params = new URLSearchParams({
      limit: String(limit.value),
      sort: sortBy.value,
      page: String(currentPage.value)
    })
    if (search.value) params.append('search', search.value)
    if (showOnlyFavorites.value) params.append('favorites', 'true')

    const res = await fetch(`${API_BASE}/examples/examples?${params}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data: ApiResponse = await res.json()
    examples.value = data.items
    meta.value = data.meta
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load examples'
    showToast(error.value, 'error')
  } finally {
    loading.value = false
  }
}

async function fetchWordDetail(wordId: number) {
  loadingWordDetail.value = true
  try {
    const res = await fetch(`${API_BASE}/words/words/${wordId}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    wordDetail.value = await res.json()
  } catch (err) {
    showToast('Failed to load word details', 'error')
    wordDetail.value = null
  } finally {
    loadingWordDetail.value = false
  }
}

async function toggleFavorite(id: number) {
  try {
    const res = await fetch(`${API_BASE}/examples/${id}/toggle-fav`, {
      method: 'PATCH'
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const ex = examples.value.find(e => e.id === id)
    if (ex) ex.is_favorite = !ex.is_favorite
    showToast(ex?.is_favorite ? 'Added to favorites' : 'Removed from favorites', 'success')
  } catch (err) {
    showToast('Failed to toggle favorite', 'error')
  }
}

async function generateExamples(wordId?: number) {
  isGenerating.value = true
  generatingWordId.value = wordId || null
  try {
    const body = wordId ? { word_id: wordId } : {}
    const res = await fetch(`${API_BASE}/examples/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    showToast('Examples generated!', 'success')
    await fetchExamples()
  } catch (err) {
    showToast('Failed to generate examples', 'error')
  } finally {
    isGenerating.value = false
    generatingWordId.value = null
  }
}

async function startRandomReview() {
  try {
    const res = await fetch(`${API_BASE}/examples/random`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    randomExamples.value = await res.json()
    reviewIndex.value = 0
    isReviewMode.value = true
  } catch (err) {
    showToast('Failed to load random examples', 'error')
  }
}

// ===================== HELPERS =====================
function showToast(message: string, type: 'success' | 'error') {
  toast.value = { show: true, message, type }
  setTimeout(() => { toast.value.show = false }, 3000)
}

async function copyToClipboard(text: string, id: number) {
  try {
    await navigator.clipboard.writeText(text)
    copiedId.value = id
    setTimeout(() => (copiedId.value = null), 1500)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    copiedId.value = id
    setTimeout(() => (copiedId.value = null), 1500)
  }
}

function playAudio(text: string) {
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'en-US'
  utterance.rate = 0.9
  speechSynthesis.speak(utterance)
}

function toggleWord(exampleId: number, wordId: number) {
  if (expandedWordState.value?.exampleId === exampleId && expandedWordState.value?.wordId === wordId) {
    expandedWordState.value = null
    wordDetail.value = null
  } else {
    expandedWordState.value = { exampleId, wordId }
    fetchWordDetail(wordId)
  }
}

function goToPage(page: number) {
  if (meta.value && page >= 1 && page <= meta.value.total_pages) {
    currentPage.value = page
    fetchExamples()
  }
}

// Limpia el estado al salir del panel o cambiar contextos
function resetWordExpansion() {
  expandedWordState.value = null
  wordDetail.value = null
}

function exitReview() {
  isReviewMode.value = false
  randomExamples.value = []
  reviewIndex.value = 0
  resetWordExpansion()
}

function nextReview() {
  if (reviewIndex.value < randomExamples.value.length - 1) {
    reviewIndex.value++
    resetWordExpansion()
  }
}

function prevReview() {
  if (reviewIndex.value > 0) {
    reviewIndex.value--
    resetWordExpansion()
  }
}

function levelLabel(level: number): string {
  return { 1: 'Beginner', 2: 'Intermediate', 3: 'Advanced' }[level] || 'Unknown'
}

function levelClass(level: number): string {
  return { 1: 'level-beginner', 2: 'level-intermediate', 3: 'level-advanced' }[level] || ''
}

function frequencyColor(freq: string): string {
  return { 'high': '#111', 'medium': '#555', 'low': '#999' }[freq.toLowerCase()] || '#999'
}

function capitalize(str: string | null | undefined): string {
  if (!str) return ''
  return str.charAt(0).toUpperCase() + str.slice(1)
}

// ===================== WATCHERS =====================
watch([sortBy, limit, showOnlyFavorites], () => {
  currentPage.value = 1
  resetWordExpansion()
  fetchExamples()
})

let searchTimeout: ReturnType<typeof setTimeout>
watch(search, () => {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    currentPage.value = 1
    resetWordExpansion()
    fetchExamples()
  }, 400)
})

// ===================== LIFECYCLE =====================
onMounted(() => {
  fetchExamples()
})
</script>

<template>
  <div class="module">
    <Transition name="toast">
      <div v-if="toast.show" class="toast" :class="toast.type">
        <Icon :icon="toast.type === 'success' ? 'solar:check-circle-bold' : 'solar:danger-circle-bold'" width="18" />
        {{ toast.message }}
      </div>
    </Transition>

    <header class="header">
      <div>
        <h1>Examples</h1>
        <p>Explore sentences crafted from your vocabulary.</p>
      </div>

      <div class="header-actions">
        <button
          class="fav-toggle-btn"
          :class="{ active: showOnlyFavorites }"
          @click="showOnlyFavorites = !showOnlyFavorites"
        >
          <Icon
            :icon="showOnlyFavorites ? 'solar:star-bold' : 'solar:star-linear'"
            width="18"
            :color="showOnlyFavorites ? '#f59e0b' : '#9ca3af'"
          />
          Favorites
        </button>

        <button class="randomize-btn" @click="startRandomReview">
          <Icon icon="solar:shuffle-linear" width="18" color="#4b5563" />
          Random Review
        </button>

        <button class="generate-btn" @click="generateExamples()" :disabled="isGenerating">
          <Icon icon="solar:magic-stick-3-linear" width="20" />
          {{ isGenerating ? 'Generating...' : 'Generate with AI' }}
        </button>
      </div>
    </header>

    <div class="toolbar">
      <div class="search">
        <Icon icon="solar:magnifer-linear" width="20" color="#aaa" />
        <input v-model="search" placeholder="Search examples or words..." :disabled="loading">
      </div>

      <div class="toolbar-right">
        <div class="limit-dropdown">
          <select v-model="limit">
            <option :value="5">5 / page</option>
            <option :value="10">10 / page</option>
            <option :value="20">20 / page</option>
            <option :value="50">50 / page</option>
          </select>
          <Icon icon="solar:alt-arrow-down-linear" width="16" class="sort-icon" />
        </div>

        <div class="sort-dropdown">
          <select v-model="sortBy">
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="favorites">Favorites first</option>
          </select>
          <Icon icon="solar:alt-arrow-down-linear" width="16" class="sort-icon" />
        </div>
      </div>
    </div>

    <Transition name="slide-down">
      <div v-if="isReviewMode" class="review-banner">
        <div class="review-banner-inner">
          <div class="review-info">
            <Icon icon="solar:shuffle-linear" width="20" color="#8b5cf6" />
            <span>Random Review</span>
            <span class="review-count">{{ reviewIndex + 1 }} / {{ randomExamples.length }}</span>
          </div>
          <div class="review-controls">
            <button :disabled="reviewIndex === 0" @click="prevReview">
              <Icon icon="solar:alt-arrow-left-linear" width="18" />
            </button>
            <button :disabled="reviewIndex === randomExamples.length - 1" @click="nextReview">
              <Icon icon="solar:alt-arrow-right-linear" width="18" />
            </button>
            <button class="review-close" @click="exitReview">
              <Icon icon="solar:close-circle-linear" width="18" color="#9ca3af" />
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <div v-if="loading && examples.length === 0" class="loading-state">
      <Icon icon="solar:spinner-bold" width="32" color="#8b5cf6" class="spin" />
      <p>Loading examples...</p>
    </div>

    <div v-else-if="error && examples.length === 0" class="empty-state error">
      <Icon icon="solar:danger-circle-bold-duotone" width="48" color="#ef4444" />
      <p>{{ error }}</p>
      <button class="retry-btn" @click="fetchExamples">Try again</button>
    </div>

    <div v-else class="list-wrapper">
      <div v-if="loading" class="list-loading-overlay">
        <Icon icon="solar:spinner-bold" width="24" color="#8b5cf6" class="spin" />
      </div>

      <template v-if="isGenerating && !isReviewMode">
        <div v-for="n in 3" :key="n" class="example-card skeleton">
          <div class="skeleton-text">
            <div class="skeleton-line skeleton-line-long"></div>
            <div class="skeleton-line skeleton-line-short"></div>
          </div>
          <div class="skeleton-chips">
            <div class="skeleton-chip"></div>
            <div class="skeleton-chip"></div>
          </div>
        </div>
      </template>

      <div v-else-if="isReviewMode && reviewCurrent" class="review-card-wrapper">
        <div class="example-card review-active">
          <div class="example-content">
            <p class="example-text">{{ reviewCurrent.text }}</p>
            <div class="example-words">
              <button
                v-for="word in reviewCurrent.words"
                :key="word.word_id"
                class="word-chip"
                :class="{ expanded: expandedWordState?.exampleId === reviewCurrent.id && expandedWordState?.wordId === word.word_id }"
                @click="toggleWord(reviewCurrent.id, word.word_id)"
              >
                {{ word.main }}
              </button>
            </div>

            <Transition name="expand">
              <div v-if="expandedWordState?.exampleId === reviewCurrent.id" class="word-detail-panel">
                <div v-if="loadingWordDetail" class="detail-loading">
                  <Icon icon="solar:spinner-bold" width="20" color="#8b5cf6" class="spin" />
                  Loading details...
                </div>
                <div v-else-if="wordDetail" class="word-detail-inner">
                  <div class="word-detail-header">
                    <h2 class="word-title">{{ wordDetail.main }}</h2>
                    <span class="badge" :class="levelClass(wordDetail.level)">
                      {{ levelLabel(wordDetail.level) }}
                    </span>
                  </div>
                  <div class="detail-meta">
                    <span class="type-badge">{{ capitalize(wordDetail.type) }}</span>
                    <span :style="{ color: frequencyColor(wordDetail.frequency), fontWeight: '600' }">
                      {{ capitalize(wordDetail.frequency) }}
                    </span>
                  </div>
                  <div class="detail-section">
                    <h4>Meaning</h4>
                    <p>{{ wordDetail.meaning }}</p>
                  </div>
                </div>
              </div>
            </Transition>
          </div>
          
          <div class="example-actions">
            <button
              class="action-btn"
              :class="{ active: reviewCurrent.is_favorite }"
              @click="toggleFavorite(reviewCurrent.id)"
            >
              <Icon
                :icon="reviewCurrent.is_favorite ? 'solar:star-bold' : 'solar:star-linear'"
                width="20"
                :color="reviewCurrent.is_favorite ? '#f59e0b' : '#9ca3af'"
              />
            </button>
            <button class="action-btn play" @click="playAudio(reviewCurrent.text)">
              <Icon icon="solar:play-bold" width="18" color="#8b5cf6" />
            </button>
          </div>
        </div>
      </div>

      <template v-else>
        <div
          v-for="example in paginatedExamples"
          :key="example.id"
          class="example-card"
        >
          <div class="example-content">
            <p class="example-text">{{ example.text }}</p>
            <div class="example-words">
              <button
                v-for="word in example.words"
                :key="word.word_id"
                class="word-chip"
                :class="{ expanded: expandedWordState?.exampleId === example.id && expandedWordState?.wordId === word.word_id }"
                @click="toggleWord(example.id, word.word_id)"
              >
                {{ word.main }}
                <Icon
                  :icon="expandedWordState?.exampleId === example.id && expandedWordState?.wordId === word.word_id ? 'solar:alt-arrow-up-linear' : 'solar:alt-arrow-down-linear'"
                  width="14"
                  color="#8b5cf6"
                />
              </button>
            </div>

            <Transition name="expand">
              <div
                v-if="expandedWordState?.exampleId === example.id"
                class="word-detail-panel"
              >
                <div v-if="loadingWordDetail" class="detail-loading">
                  <Icon icon="solar:spinner-bold" width="20" color="#8b5cf6" class="spin" />
                  Loading details...
                </div>
                <div v-else-if="wordDetail" class="word-detail-inner">
                  <div class="word-detail-header">
                    <h2 class="word-title">{{ wordDetail.main }}</h2>
                    <span class="badge" :class="levelClass(wordDetail.level)">
                      {{ levelLabel(wordDetail.level) }}
                    </span>
                  </div>

                  <div class="detail-meta">
                    <span class="type-badge">{{ capitalize(wordDetail.type) }}</span>
                    <span :style="{ color: frequencyColor(wordDetail.frequency), fontWeight: '600' }">
                      {{ capitalize(wordDetail.frequency) }}
                    </span>
                  </div>

                  <div class="detail-section">
                    <h4>Meaning</h4>
                    <p>{{ wordDetail.meaning }}</p>
                  </div>

                  <div class="detail-section" v-if="wordDetail.context">
                    <h4>Context</h4>
                    <p>{{ wordDetail.context }}</p>
                  </div>

                  <div class="detail-section" v-if="wordDetail.examples && wordDetail.examples.length">
                    <h4>Existing Examples ({{ wordDetail.total_examples }})</h4>
                    <div class="sub-examples">
                      <div
                        v-for="(ex, i) in wordDetail.examples"
                        :key="i"
                        class="sub-example"
                      >
                        {{ ex }}
                      </div>
                    </div>
                  </div>

                  <button
                    class="detail-generate-btn"
                    @click="generateExamples(wordDetail.id)"
                    :disabled="isGenerating"
                  >
                    <Icon :icon="isGenerating ? 'solar:spinner-bold' : 'solar:magic-stick-3-linear'" width="18" :class="{ 'spin': isGenerating }" />
                    {{ isGenerating ? 'Generating...' : `Generate more for "${wordDetail.main}"` }}
                  </button>
                </div>
              </div>
            </Transition>
          </div>

          <div class="example-actions">
            <button
              class="action-btn"
              :class="{ active: example.is_favorite }"
              @click="toggleFavorite(example.id)"
              :title="example.is_favorite ? 'Remove from favorites' : 'Add to favorites'"
            >
              <Icon
                :icon="example.is_favorite ? 'solar:star-bold' : 'solar:star-linear'"
                width="20"
                :color="example.is_favorite ? '#f59e0b' : '#9ca3af'"
              />
            </button>

            <button
              class="action-btn"
              @click="copyToClipboard(example.text, example.id)"
              :title="copiedId === example.id ? 'Copied!' : 'Copy to clipboard'"
            >
              <Icon
                :icon="copiedId === example.id ? 'solar:check-circle-bold' : 'solar:copy-linear'"
                width="20"
                :color="copiedId === example.id ? '#22c55e' : '#9ca3af'"
              />
            </button>

            <button class="action-btn play" @click="playAudio(example.text)" title="Listen">
              <Icon icon="solar:play-bold" width="18" color="#8b5cf6" />
            </button>
          </div>
        </div>
      </template>

      <div v-if="!isGenerating && !isReviewMode && paginatedExamples.length === 0" class="empty-state">
        <Icon icon="solar:document-text-bold-duotone" width="48" color="#ddd" />
        <p>No examples found. Try a different search or generate some!</p>
      </div>
    </div>

    <div v-if="!isReviewMode && totalPages > 1" class="footer">
      <span class="results-info">
        Showing {{ paginatedExamples.length }} of {{ meta?.total_items || 0 }} examples
        <span v-if="meta"> · Page {{ meta.current_page }} of {{ meta.total_pages }}</span>
      </span>

      <div class="pagination">
        <button :disabled="!meta?.has_prev || loading" @click="goToPage(currentPage - 1)">
          <Icon icon="solar:alt-arrow-left-linear" width="18" />
        </button>

        <button
          v-for="page in totalPages"
          :key="page"
          :class="{ active: currentPage === page }"
          @click="goToPage(page)"
          :disabled="loading"
        >
          {{ page }}
        </button>

        <button :disabled="!meta?.has_next || loading" @click="goToPage(currentPage + 1)">
          <Icon icon="solar:alt-arrow-right-linear" width="18" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.module {
  display: flex;
  flex-direction: column;
  gap: 20px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  position: relative;
}

/* ===== TOAST ===== */
.toast {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 1000;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 500;
  box-shadow: 0 4px 20px rgba(0,0,0,0.15);
  animation: slideInRight 0.3s ease;
}

.toast.success {
  background: #eaf8ef;
  color: #28a745;
  border: 1px solid #c3e6cb;
}

.toast.error {
  background: #fdeaea;
  color: #ef4444;
  border: 1px solid #f5c6cb;
}

.toast-enter-active, .toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateX(100%); }

@keyframes slideInRight {
  from { opacity: 0; transform: translateX(100%); }
  to { opacity: 1; transform: translateX(0); }
}

/* ===== HEADER ===== */
.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}

.header h1 {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 700;
  color: #1a1a2e;
  letter-spacing: -0.5px;
}

.header p {
  margin: 4px 0 0 0;
  color: #888;
  font-size: 14px;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.generate-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 0;
  color: white;
  background: #8b5cf6;
  padding: 12px 20px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(139, 92, 246, 0.25);
}

.generate-btn:hover:not(:disabled) {
  background: #7c3aed;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(139, 92, 246, 0.35);
}

.generate-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.randomize-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1.5px solid #e5e5e5;
  color: #555;
  background: white;
  padding: 12px 20px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.randomize-btn:hover {
  background: #f5f5f5;
  border-color: #ddd;
}

.fav-toggle-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1.5px solid #e5e5e5;
  color: #555;
  background: white;
  padding: 12px 20px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.fav-toggle-btn:hover {
  background: #fef3c7;
  border-color: #f59e0b;
  color: #b45309;
}

.fav-toggle-btn.active {
  background: #fef3c7;
  border-color: #f59e0b;
  color: #b45309;
}

/* ===== TOOLBAR ===== */
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}

.search {
  flex: 1;
  min-width: 200px;
  max-width: 380px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  border: 1.5px solid #e5e5e5;
  border-radius: 12px;
  background: white;
  height: 44px;
  transition: border-color 0.2s;
}

.search:focus-within { border-color: #8b5cf6; }

.search input {
  border: 0;
  outline: none;
  width: 100%;
  height: 100%;
  font-size: 14px;
  color: #333;
  background: transparent;
}

.search input::placeholder { color: #bbb; }

.limit-dropdown, .sort-dropdown {
  position: relative;
}

.limit-dropdown select, .sort-dropdown select {
  appearance: none;
  -webkit-appearance: none;
  height: 44px;
  padding: 0 36px 0 16px;
  border: 1.5px solid #e5e5e5;
  border-radius: 12px;
  background: white;
  font-size: 13px;
  font-weight: 500;
  color: #555;
  cursor: pointer;
  outline: none;
  transition: border-color 0.2s;
}

.limit-dropdown select { min-width: 100px; }
.sort-dropdown select { min-width: 150px; }

.limit-dropdown select:focus, .sort-dropdown select:focus { border-color: #8b5cf6; }

.sort-icon {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  color: #999;
}

/* ===== REVIEW BANNER ===== */
.review-banner {
  background: #faf8ff;
  border: 1.5px solid #e8e0f7;
  border-radius: 16px;
  padding: 16px 24px;
}

.review-banner-inner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.review-info {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  font-weight: 600;
  color: #7c3aed;
}

.review-count {
  background: white;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 13px;
  color: #8b5cf6;
  border: 1px solid #e8e0f7;
}

.review-controls {
  display: flex;
  gap: 8px;
  align-items: center;
}

.review-controls button {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1.5px solid #e8e0f7;
  border-radius: 10px;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
  color: #7c3aed;
}

.review-controls button:hover:not(:disabled) {
  background: #faf8ff;
  border-color: #c4b5fd;
}

.review-controls button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.review-close { margin-left: 8px; }

/* ===== LOADING STATES ===== */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 20px;
  color: #999;
}

.loading-state p { margin: 0; font-size: 14px; }

.list-loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255,255,255,0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  border-radius: 16px;
}

.spin { animation: spin 1s linear infinite; }

@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.retry-btn {
  margin-top: 12px;
  padding: 10px 20px;
  border: 0;
  border-radius: 10px;
  background: #8b5cf6;
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.retry-btn:hover { background: #7c3aed; }

/* ===== LIST ===== */
.list-wrapper {
  display: flex;
  flex-direction: column;
  gap: 14px;
  position: relative;
}

.example-card {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 20px 24px;
  background: white;
  border: 1px solid #ececec;
  border-radius: 16px;
  transition: all 0.2s;
}

.example-card:hover {
  border-color: #ddd;
  box-shadow: 0 4px 16px rgba(0,0,0,0.06);
  transform: translateY(-1px);
}

.example-card.review-active {
  border-color: #c4b5fd;
  background: #faf8ff;
  box-shadow: 0 4px 20px rgba(139, 92, 246, 0.1);
}

.example-content {
  flex: 1;
  min-width: 0;
}

.example-text {
  margin: 0 0 14px;
  font-size: 15px;
  line-height: 1.7;
  color: #333;
}

.example-words {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.word-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: 1.5px solid #e8e0f7;
  border-radius: 999px;
  background: #faf8ff;
  color: #7c3aed;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.word-chip:hover {
  background: #f4edff;
  border-color: #c4b5fd;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(139, 92, 246, 0.15);
}

.word-chip.expanded {
  background: #8b5cf6;
  color: white;
  border-color: #7c3aed;
}

/* Word Detail Panel */
.word-detail-panel {
  margin-top: 16px;
  padding: 20px;
  background: #fafafa;
  border: 1.5px solid #ececec;
  border-radius: 14px;
  overflow: hidden;
}

.detail-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #999;
  font-size: 14px;
  padding: 20px;
}

.word-detail-inner {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

.word-detail-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ececec;
}

.word-title {
  font-size: 1.3rem;
  font-weight: 800;
  color: #1a1a2e;
  margin: 0;
}

.detail-meta {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 16px;
}

.type-badge {
  display: inline-block;
  padding: 3px 10px;
  background: #f0f0ff;
  color: #6366f1;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: capitalize;
}

.detail-section {
  margin-bottom: 16px;
}

.detail-section h4 {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #aaa;
  margin: 0 0 8px;
  font-weight: 700;
}

.detail-section p {
  margin: 0;
  font-size: 14px;
  color: #555;
  line-height: 1.6;
}

.sub-examples {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sub-example {
  padding: 10px 14px;
  background: white;
  border-radius: 10px;
  font-size: 13px;
  color: #555;
  line-height: 1.5;
  border-left: 3px solid #c4b5fd;
}

.detail-generate-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 12px;
  border: 0;
  border-radius: 10px;
  background: #8b5cf6;
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  margin-top: 4px;
}

.detail-generate-btn:hover:not(:disabled) {
  background: #7c3aed;
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(139, 92, 246, 0.25);
}

.detail-generate-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Level badges */
.badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.level-beginner { background: #eaf8ef; color: #28a745; }
.level-intermediate { background: #eef5ff; color: #3b82f6; }
.level-advanced { background: #f4edff; color: #8b5cf6; }

/* Actions */
.example-actions {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-shrink: 0;
}

.action-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #ececec;
  border-radius: 10px;
  background: white;
  cursor: pointer;
  transition: all 0.15s;
  color: #999;
  padding: 0;
}

.action-btn:hover {
  background: #fafafa;
  border-color: #ddd;
  transform: translateY(-1px);
}

.action-btn.play {
  background: #faf8ff;
  border-color: #e8e0f7;
}

.action-btn.play:hover {
  background: #f4edff;
}

/* Skeleton */
.example-card.skeleton {
  pointer-events: none;
}

.skeleton-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.skeleton-line {
  height: 16px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e8e8e8 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  border-radius: 8px;
  animation: shimmer 1.5s infinite;
}

.skeleton-line-long { width: 85%; }
.skeleton-line-short { width: 60%; }

.skeleton-chips {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.skeleton-chip {
  width: 80px;
  height: 32px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e8e8e8 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  border-radius: 999px;
  animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Empty state */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 20px;
  color: #bbb;
  text-align: center;
}

.empty-state.error { color: #ef4444; }
.empty-state p { margin: 0; font-size: 14px; }

/* Footer */
.footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  border-top: 1px solid #f0f0f0;
  color: #999;
  font-size: 13px;
  flex-wrap: wrap;
  gap: 10px;
}

.results-info { font-size: 13px; color: #999; }

.pagination {
  display: flex;
  gap: 6px;
}

.pagination button {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #ececec;
  border-radius: 10px;
  background: white;
  color: #777;
  cursor: pointer;
  transition: all 0.15s;
  font-size: 13px;
}

.pagination button:hover:not(:disabled) {
  background: #f5f5f5;
  border-color: #ddd;
}

.pagination button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.pagination .active {
  border-color: #8b5cf6;
  color: #8b5cf6;
  font-weight: 600;
  background: #f4edff;
}

/* Transitions */
.expand-enter-active, .expand-leave-active { transition: all 0.3s ease; }
.expand-enter-from, .expand-leave-to { opacity: 0; max-height: 0; margin-top: 0; padding: 0; }

.slide-down-enter-active, .slide-down-leave-active { transition: all 0.3s ease; }
.slide-down-enter-from, .slide-down-leave-to { opacity: 0; transform: translateY(-20px); max-height: 0; padding: 0; margin: 0; overflow: hidden; }

/* ===== RESPONSIVE ===== */
@media (max-width: 768px) {
  .module { gap: 16px; }

  .header {
    flex-direction: column;
    gap: 12px;
  }

  .header h1 { font-size: 1.5rem; }

  .header-actions {
    width: 100%;
  }

  .generate-btn, .randomize-btn, .fav-toggle-btn {
    flex: 1;
    justify-content: center;
    padding: 14px;
  }

  .toolbar {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .toolbar-right {
    margin-left: 0;
    justify-content: space-between;
  }

  .search {
    max-width: none;
    width: 100%;
  }

  .example-card {
    flex-direction: column;
    gap: 14px;
    padding: 18px 20px;
  }

  .example-text { font-size: 14px; }

  .example-actions {
    align-self: flex-end;
  }

  .review-banner-inner {
    flex-direction: column;
    align-items: flex-start;
  }

  .footer {
    flex-direction: column;
    gap: 12px;
    align-items: center;
  }
}
</style>