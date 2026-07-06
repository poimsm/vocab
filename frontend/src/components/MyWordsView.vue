<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

// ─── Config ───
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost/api';

// ─── Types ───
type WordLevel = 'Beginner' | 'Intermediate' | 'Advanced'
type WordFrequency = 'rare' | 'uncommon' | 'common'
type FilterMode = 'all' | 'favorites'

interface Word {
  id: number
  word: string
  definition: string
  level: WordLevel | number
  category: string
  frequency: WordFrequency
  isFavorite: boolean
  isLearned: boolean
  addedAt: string
  totalExamples: number
  type: string
  examples: string[]
  sourceText?: string
}

// ─── State ───
const words = ref<Word[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const searchQuery = ref('')
const filterMode = ref<FilterMode>('all')
const selectedWord = ref<Word | null>(null)
const showMobileDetail = ref(false)

// ─── Add Word State ───
const showAddDesktop = ref(false)
const showAddMobile = ref(false)
const newWordText = ref('')
const adding = ref(false)

// ─── Helpers ───
const levelColor = (level: WordLevel | number) => {
  const s = typeof level === 'number' ? String(level) : (level || '').toString().toLowerCase()
  if (s === '1' || s === 'beginner') return '#4ade80'
  if (s === '2' || s === 'intermediate') return '#60a5fa'
  if (s === '3' || s === 'advanced') return '#f472b6'
  return '#9c99ab'
}

const levelLabel = (level: WordLevel | number) => {
  if (level === 1) return 'Beginner'
  if (level === 2) return 'Intermediate'
  if (level === 3) return 'Advanced'
  const s = (level || '').toString().toLowerCase()
  if (s === 'beginner') return 'Beginner'
  if (s === 'intermediate') return 'Intermediate'
  if (s === 'advanced') return 'Advanced'
  return level?.toString() || '—'
}

const frequencyColor = (freq: WordFrequency) => {
  switch (freq) {
    case 'rare': return '#4ade80'
    case 'uncommon': return '#60a5fa'
    case 'common': return '#a78bfa'
    default: return '#9c99ab'
  }
}

const frequencyLabel = (freq: WordFrequency) => {
  if (!freq) return ''
  return freq.charAt(0).toUpperCase() + freq.slice(1)
}

// ─── API ───
async function fetchWords() {
  loading.value = true
  error.value = null
  try {
    const res = await fetch(`${API_BASE}/words/words`)
    if (!res.ok) throw new Error('Failed to load words')
    const data = await res.json()
    words.value = (data.items || []).map((item: any) => ({
      id: item.id,
      word: item.main,
      definition: item.meaning,
      level: item.level,
      category: item.context || item.type || 'General',
      frequency: item.frequency,
      isFavorite: item.is_favorite,
      isLearned: item.is_learned,
      addedAt: item.created_at ? item.created_at.split('T')[0] : '—',
      totalExamples: item.total_examples,
      type: item.type,
      examples: [],
      sourceText: item.source_text
    }))
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function fetchWordDetail(id: number) {
  try {
    const res = await fetch(`${API_BASE}/words/words/${id}`)
    if (!res.ok) throw new Error('Failed to load detail')
    const data = await res.json()
    selectedWord.value = {
      id: data.id,
      word: data.main,
      definition: data.meaning,
      level: data.level,
      category: data.context || data.type || 'General',
      frequency: data.frequency,
      isFavorite: data.is_favorite,
      isLearned: data.is_learned,
      addedAt: data.created_at ? data.created_at.split('T')[0] : '—',
      totalExamples: data.total_examples,
      type: data.type,
      sourceText: data.source_text,
      examples: data.examples || []
    }
  } catch (e) {
    alert('Could not load word detail')
  }
}

async function toggleFavoriteApi(word: Word) {
  try {
    const res = await fetch(`${API_BASE}/words/${word.id}/toggle-fav`, { method: 'PATCH' })
    if (!res.ok) throw new Error('Failed')
    const data = await res.json()
    word.isFavorite = data.is_favorite ?? !word.isFavorite
    if (selectedWord.value?.id === word.id) {
      selectedWord.value.isFavorite = word.isFavorite
    }
  } catch (e) {
    alert('Failed to toggle favorite')
  }
}

async function addWordApi() {
  const text = newWordText.value.trim()
  if (!text) return
  adding.value = true
  try {
    const res = await fetch(`${API_BASE}/words`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || 'Failed to add word')
    }
    await fetchWords()
    closeAdd()
  } catch (e: any) {
    alert(e.message)
  } finally {
    adding.value = false
  }
}

async function deleteWordApi(id: number) {
  if (!confirm('Delete this word?')) return
  try {
    const res = await fetch(`${API_BASE}/words/words/${id}`, { method: 'DELETE' })
    if (!res.ok) throw new Error('Failed')
    words.value = words.value.filter(w => w.id !== id)
    if (selectedWord.value?.id === id) {
      selectedWord.value = null
      showMobileDetail.value = false
    }
  } catch (e) {
    alert('Failed to delete word')
  }
}

// ─── Computed ───
const filteredWords = computed(() => {
  let list = words.value

  if (filterMode.value === 'favorites') {
    list = list.filter(w => w.isFavorite)
  }

  const q = searchQuery.value.toLowerCase().trim()
  if (q) {
    list = list.filter(w =>
      w.word.toLowerCase().includes(q) ||
      w.definition.toLowerCase().includes(q) ||
      w.category.toLowerCase().includes(q)
    )
  }

  return list
})

const favoriteCount = computed(() => words.value.filter(w => w.isFavorite).length)

// ─── Methods ───
function toggleFavorite(word: Word) {
  toggleFavoriteApi(word)
}

function deleteWord(id: number) {
  deleteWordApi(id)
}

function openDetail(word: Word) {
  fetchWordDetail(word.id)
  if (window.innerWidth <= 768) {
    showMobileDetail.value = true
  }
}

function closeDetail() {
  selectedWord.value = null
  showMobileDetail.value = false
}

function openAdd() {
  newWordText.value = ''
  if (window.innerWidth <= 768) {
    showAddMobile.value = true
  } else {
    showAddDesktop.value = true
  }
}

function closeAdd() {
  showAddDesktop.value = false
  showAddMobile.value = false
  newWordText.value = ''
}

function addWord() {
  addWordApi()
}

function handleAddKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') addWord()
  if (e.key === 'Escape') closeAdd()
}

onMounted(() => {
  fetchWords()
})
</script>

<template>
  <div class="my-words-view">
    <!-- Header -->
    <header class="words-header">
      <div class="header-left">
        <h1 class="words-title">My Words</h1>
        <p class="words-subtitle">{{ words.length }} words saved</p>
      </div>
      <button class="add-btn" @click="openAdd" :disabled="loading">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/>
        </svg>
        <span>Add Word</span>
      </button>
    </header>

    <!-- Search & Filter Toolbar -->
    <div class="words-toolbar">
      <div class="search-box">
        <svg class="search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search your words..."
          class="search-input"
        />
      </div>
      <div class="filter-tabs">
        <button
          class="filter-tab"
          :class="{ active: filterMode === 'all' }"
          @click="filterMode = 'all'"
        >
          All
        </button>
        <button
          class="filter-tab"
          :class="{ active: filterMode === 'favorites' }"
          @click="filterMode = 'favorites'"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
          </svg>
          <span>Favorites</span>
          <span v-if="favoriteCount > 0" class="fav-count">{{ favoriteCount }}</span>
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading words...</p>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <button @click="fetchWords" class="retry-btn">Retry</button>
    </div>

    <!-- Desktop: Split View -->
    <div v-else class="words-content" :class="{ 'detail-open': selectedWord && !showMobileDetail }">
      <!-- Word List -->
      <div class="word-list">
        <div
          v-for="word in filteredWords"
          :key="word.id"
          class="word-card"
          :class="{ active: selectedWord?.id === word.id }"
          @click="openDetail(word)"
        >
          <div class="word-card-main">
            <div class="word-info">
              <div class="word-name-row">
                <h4 class="word-name">{{ word.word }}</h4>
                <span v-if="word.isFavorite" class="word-fav-indicator">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                  </svg>
                </span>
              </div>
              <p class="word-definition">{{ word.definition }}</p>
            </div>
            <button
              class="fav-btn"
              :class="{ active: word.isFavorite }"
              @click.stop="toggleFavorite(word)"
            >
              <svg v-if="word.isFavorite" width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
              </svg>
              <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
              </svg>
            </button>
          </div>
          <div class="word-meta">
            <span class="meta-tag level" :style="{ color: levelColor(word.level) }">
              {{ levelLabel(word.level) }}
            </span>
            <span class="meta-dot">·</span>
            <span class="meta-tag category">{{ word.category }}</span>
            <span class="meta-dot">·</span>
            <span class="meta-tag frequency" :style="{ color: frequencyColor(word.frequency) }">
              {{ frequencyLabel(word.frequency) }}
            </span>
          </div>
        </div>

        <!-- Empty State -->
        <div v-if="filteredWords.length === 0" class="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
          </svg>
          <p class="empty-text">
            {{ filterMode === 'favorites' ? 'No favorite words yet' : 'No words found' }}
          </p>
          <button class="empty-add-btn" @click="openAdd">Add your first word</button>
        </div>
      </div>

      <!-- Desktop Detail Panel -->
      <transition name="slide-panel">
        <aside v-if="selectedWord && !showMobileDetail" class="detail-panel">
          <div class="detail-header">
            <button class="detail-close" @click="selectedWord = null">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
              </svg>
            </button>
          </div>

          <div class="detail-body">
            <div class="detail-word-header">
              <h2 class="detail-word">{{ selectedWord.word }}</h2>
              <button
                class="detail-fav-btn"
                :class="{ active: selectedWord.isFavorite }"
                @click="toggleFavorite(selectedWord)"
              >
                <svg v-if="selectedWord.isFavorite" width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                </svg>
                <svg v-else width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
                </svg>
              </button>
            </div>

            <p class="detail-definition">{{ selectedWord.definition }}</p>

            <div class="detail-meta-grid">
              <div class="detail-meta-item">
                <span class="meta-label">Level</span>
                <span class="meta-value" :style="{ color: levelColor(selectedWord.level) }">
                  {{ levelLabel(selectedWord.level) }}
                </span>
              </div>
              <div class="detail-meta-item">
                <span class="meta-label">Category</span>
                <span class="meta-value">{{ selectedWord.category }}</span>
              </div>
              <div class="detail-meta-item">
                <span class="meta-label">Frequency</span>
                <span class="meta-value" :style="{ color: frequencyColor(selectedWord.frequency) }">
                  {{ frequencyLabel(selectedWord.frequency) }}
                </span>
              </div>
              <div class="detail-meta-item">
                <span class="meta-label">Added</span>
                <span class="meta-value">{{ selectedWord.addedAt }}</span>
              </div>
              <div class="detail-meta-item">
                <span class="meta-label">Type</span>
                <span class="meta-value">{{ selectedWord.type || '—' }}</span>
              </div>
              <div class="detail-meta-item">
                <span class="meta-label">Examples</span>
                <span class="meta-value">{{ selectedWord.totalExamples || 0 }}</span>
              </div>
            </div>

            <div v-if="selectedWord.examples && selectedWord.examples.length" class="detail-examples">
              <h4 class="examples-title">Examples</h4>
              <ul class="examples-list">
                <li v-for="(ex, i) in selectedWord.examples" :key="i">{{ ex }}</li>
              </ul>
            </div>

            <div class="detail-actions">
              <button class="detail-action-btn danger" @click="deleteWord(selectedWord.id)">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
                <span>Delete</span>
              </button>
            </div>
          </div>
        </aside>
      </transition>
    </div>

    <!-- Mobile Detail Overlay -->
    <transition name="slide-up">
      <div v-if="showMobileDetail && selectedWord" class="mobile-detail-overlay">
        <div class="mobile-detail-header">
          <button class="mobile-back-btn" @click="closeDetail">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
            </svg>
          </button>
          <h3 class="mobile-detail-title">Word Detail</h3>
          <button
            class="mobile-fav-btn"
            :class="{ active: selectedWord.isFavorite }"
            @click="toggleFavorite(selectedWord)"
          >
            <svg v-if="selectedWord.isFavorite" width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
            </svg>
            <svg v-else width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
            </svg>
          </button>
        </div>

        <div class="mobile-detail-content">
          <h2 class="mobile-word">{{ selectedWord.word }}</h2>
          <p class="mobile-definition">{{ selectedWord.definition }}</p>

          <div class="mobile-meta-list">
            <div class="mobile-meta-row">
              <span class="mobile-meta-label">Level</span>
              <span class="mobile-meta-value" :style="{ color: levelColor(selectedWord.level) }">
                {{ levelLabel(selectedWord.level) }}
              </span>
            </div>
            <div class="mobile-meta-row">
              <span class="mobile-meta-label">Category</span>
              <span class="mobile-meta-value">{{ selectedWord.category }}</span>
            </div>
            <div class="mobile-meta-row">
              <span class="mobile-meta-label">Frequency</span>
              <span class="mobile-meta-value" :style="{ color: frequencyColor(selectedWord.frequency) }">
                {{ frequencyLabel(selectedWord.frequency) }}
              </span>
            </div>
            <div class="mobile-meta-row">
              <span class="mobile-meta-label">Added</span>
              <span class="mobile-meta-value">{{ selectedWord.addedAt }}</span>
            </div>
            <div class="mobile-meta-row">
              <span class="mobile-meta-label">Type</span>
              <span class="mobile-meta-value">{{ selectedWord.type || '—' }}</span>
            </div>
            <div class="mobile-meta-row">
              <span class="mobile-meta-label">Examples</span>
              <span class="mobile-meta-value">{{ selectedWord.totalExamples || 0 }}</span>
            </div>
          </div>

          <div v-if="selectedWord.examples && selectedWord.examples.length" class="mobile-examples">
            <h4 class="examples-title">Examples</h4>
            <ul class="examples-list">
              <li v-for="(ex, i) in selectedWord.examples" :key="i">{{ ex }}</li>
            </ul>
          </div>

          <button class="mobile-delete-btn" @click="deleteWord(selectedWord.id)">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
            <span>Delete Word</span>
          </button>
        </div>
      </div>
    </transition>

    <!-- Desktop: Add Word Modal -->
    <transition name="fade">
      <div v-if="showAddDesktop" class="modal-overlay" @click.self="closeAdd">
        <div class="modal-card">
          <div class="modal-header">
            <h3 class="modal-title">Add New Word</h3>
            <button class="modal-close" @click="closeAdd">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
              </svg>
            </button>
          </div>
          <div class="modal-body">
            <p class="modal-hint">
              Enter a word and our AI will automatically generate its definition, level, and category.
            </p>
            <div class="form-group">
              <label class="form-label">Word</label>
              <input
                ref="desktopInput"
                v-model="newWordText"
                type="text"
                placeholder="e.g. ephemeral, wanderlust..."
                class="form-input"
                @keydown="handleAddKeydown"
                autofocus
              />
            </div>
          </div>
          <div class="modal-footer">
            <button class="modal-btn secondary" @click="closeAdd">Cancel</button>
            <button class="modal-btn primary" @click="addWord" :disabled="!newWordText.trim() || adding">
              <span v-if="adding">Adding...</span>
              <span v-else>Add Word</span>
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- Mobile: Add Word Inline Panel -->
    <transition name="slide-up">
      <div v-if="showAddMobile" class="mobile-add-panel">
        <div class="mobile-add-handle" @click="closeAdd">
          <div class="handle-bar"></div>
        </div>
        <div class="mobile-add-content">
          <h3 class="mobile-add-title">Add New Word</h3>
          <p class="mobile-add-hint">
            Our AI will generate the definition, level, and category automatically.
          </p>
          <input
            v-model="newWordText"
            type="text"
            placeholder="Type a word..."
            class="mobile-add-input"
            @keydown="handleAddKeydown"
            autofocus
          />
          <div class="mobile-add-actions">
            <button class="mobile-add-btn secondary" @click="closeAdd">Cancel</button>
            <button class="mobile-add-btn primary" @click="addWord" :disabled="!newWordText.trim() || adding">
              <span v-if="adding">Adding...</span>
              <span v-else>Add</span>
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- Mobile: Backdrop for add panel -->
    <transition name="fade">
      <div v-if="showAddMobile" class="mobile-backdrop" @click="closeAdd"></div>
    </transition>
  </div>
</template>

<style scoped>
/* ─── Root ─── */
.my-words-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px;
  color: #e2e0e8;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* ─── Header ─── */
.words-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 28px;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.words-title {
  font-size: 28px;
  font-weight: 700;
  color: #e2e0e8;
  margin: 0;
  letter-spacing: -0.5px;
}

.words-subtitle {
  font-size: 14px;
  color: #9c99ab;
  margin: 0;
}

.add-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-radius: 12px;
  border: none;
  background: #7c3aed;
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.add-btn:hover:not(:disabled) {
  background: #6d28d9;
  transform: translateY(-1px);
}

.add-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ─── Toolbar ─── */
.words-toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
  align-items: center;
}

.search-box {
  flex: 1;
  position: relative;
  max-width: 400px;
}

.search-icon {
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: #9c99ab;
  pointer-events: none;
}

.search-input {
  width: 80%;
  padding: 12px 14px 12px 42px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #e2e0e8;
  font-size: 14px;
  outline: none;
  transition: all 0.2s ease;
}

.search-input::placeholder {
  color: #9c99ab;
}

.search-input:focus {
  border-color: rgba(124, 58, 237, 0.4);
  background: rgba(255, 255, 255, 0.06);
}

/* ─── Filter Tabs ─── */
.filter-tabs {
  display: flex;
  gap: 6px;
  background: rgba(255, 255, 255, 0.04);
  padding: 4px;
  border-radius: 12px;
}

.filter-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #9c99ab;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.filter-tab:hover {
  color: #e2e0e8;
}

.filter-tab.active {
  background: rgba(124, 58, 237, 0.2);
  color: #a78bfa;
}

.fav-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: rgba(244, 114, 182, 0.2);
  color: #f472b6;
  font-size: 10px;
  font-weight: 700;
}

/* ─── Loading / Error ─── */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  gap: 16px;
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
  to { transform: rotate(360deg); }
}

.loading-state p {
  color: #9c99ab;
  font-size: 14px;
  margin: 0;
}

.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  gap: 16px;
  text-align: center;
}

.error-state p {
  color: #f87171;
  font-size: 14px;
  margin: 0;
}

.retry-btn {
  padding: 10px 20px;
  border-radius: 10px;
  border: none;
  background: rgba(124, 58, 237, 0.2);
  color: #a78bfa;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.retry-btn:hover {
  background: rgba(124, 58, 237, 0.3);
}

/* ─── Content Layout ─── */
.words-content {
  display: flex;
  gap: 0;
  min-height: 400px;
}

.words-content.detail-open .word-list {
  flex: 0 0 55%;
  max-width: 55%;
}

/* ─── Word List ─── */
.word-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: all 0.3s ease;
}

/* ─── Word Card ─── */
.word-card {
  padding: 16px 18px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  cursor: pointer;
  transition: all 0.2s ease;
}

.word-card:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.1);
}

.word-card.active {
  background: rgba(124, 58, 237, 0.1);
  border-color: rgba(124, 58, 237, 0.25);
}

.word-card-main {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 10px;
}

.word-info {
  min-width: 0;
  flex: 1;
}

.word-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.word-name {
  font-size: 16px;
  font-weight: 600;
  color: #e2e0e8;
  margin: 0;
}

.word-fav-indicator {
  color: #f472b6;
  display: flex;
  align-items: center;
}

.word-definition {
  font-size: 13px;
  color: #9c99ab;
  margin: 0;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.fav-btn {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s ease;
}

.fav-btn:hover {
  background: rgba(255, 255, 255, 0.06);
}

.fav-btn.active {
  color: #f472b6;
}

/* ─── Meta Tags ─── */
.word-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.meta-tag {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.meta-tag.level {
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
}

.meta-tag.category {
  color: #9c99ab;
}

.meta-tag.frequency {
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
}

.meta-dot {
  color: #9c99ab;
  font-size: 11px;
}

/* ─── Detail Panel (Desktop) ─── */
.detail-panel {
  width: 380px;
  flex-shrink: 0;
  background: #36324a;
  border-left: 1px solid rgba(255, 255, 255, 0.06);
  padding: 24px;
  border-radius: 16px 0 0 16px;
}

.detail-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.detail-close {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.detail-close:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
}

.detail-word-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.detail-word {
  font-size: 32px;
  font-weight: 700;
  color: #e2e0e8;
  margin: 0;
  letter-spacing: -0.5px;
}

.detail-fav-btn {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  border: none;
  background: rgba(255, 255, 255, 0.06);
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.detail-fav-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.detail-fav-btn.active {
  color: #f472b6;
  background: rgba(244, 114, 182, 0.1);
}

.detail-definition {
  font-size: 15px;
  line-height: 1.6;
  color: #b8b5c8;
  margin-bottom: 28px;
}

.detail-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 28px;
}

.detail-meta-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px;
  background: rgba(0, 0, 0, 0.15);
  border-radius: 12px;
}

.meta-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: #9c99ab;
  text-transform: uppercase;
}

.meta-value {
  font-size: 14px;
  font-weight: 600;
  color: #e2e0e8;
}

.detail-examples {
  margin-bottom: 28px;
}

.examples-title {
  font-size: 13px;
  font-weight: 600;
  color: #9c99ab;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0 0 12px 0;
}

.examples-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.examples-list li {
  font-size: 14px;
  color: #b8b5c8;
  padding: 10px 14px;
  background: rgba(0, 0, 0, 0.12);
  border-radius: 10px;
  line-height: 1.5;
}

.detail-actions {
  display: flex;
  gap: 10px;
}

.detail-action-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  border-radius: 12px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.detail-action-btn.danger {
  background: rgba(239, 68, 68, 0.1);
  color: #f87171;
}

.detail-action-btn.danger:hover {
  background: rgba(239, 68, 68, 0.2);
}

/* ─── Empty State ─── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.empty-state svg {
  color: #9c99ab;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-text {
  font-size: 16px;
  color: #9c99ab;
  margin: 0 0 16px 0;
}

.empty-add-btn {
  padding: 12px 24px;
  border-radius: 12px;
  border: none;
  background: #7c3aed;
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.empty-add-btn:hover {
  background: #6d28d9;
}

/* ─── Desktop Modal ─── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 20px;
}

.modal-card {
  width: 100%;
  max-width: 420px;
  background: #36324a;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.modal-title {
  font-size: 18px;
  font-weight: 700;
  color: #e2e0e8;
  margin: 0;
}

.modal-close {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.modal-close:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
}

.modal-body {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.modal-hint {
  font-size: 13px;
  color: #9c99ab;
  line-height: 1.5;
  margin: 0;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 12px;
  font-weight: 600;
  color: #9c99ab;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.form-input {
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #e2e0e8;
  font-size: 15px;
  outline: none;
  transition: all 0.2s ease;
  font-family: inherit;
}

.form-input:focus {
  border-color: rgba(124, 58, 237, 0.4);
  background: rgba(255, 255, 255, 0.06);
}

.form-input::placeholder {
  color: #9c99ab;
}

.modal-footer {
  display: flex;
  gap: 10px;
  padding: 0 24px 24px;
}

.modal-btn {
  flex: 1;
  padding: 12px;
  border-radius: 12px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.modal-btn.secondary {
  background: rgba(255, 255, 255, 0.06);
  color: #9c99ab;
}

.modal-btn.secondary:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #e2e0e8;
}

.modal-btn.primary {
  background: #7c3aed;
  color: white;
}

.modal-btn.primary:hover:not(:disabled) {
  background: #6d28d9;
}

.modal-btn.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ─── Mobile Add Panel (Bottom Sheet) ─── */
.mobile-add-panel {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  background: #36324a;
  border-radius: 24px 24px 0 0;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding: 8px 20px 28px;
  z-index: 2001;
  max-height: 50vh;
}

.mobile-add-handle {
  display: flex;
  justify-content: center;
  padding: 8px 0 12px;
  cursor: pointer;
}

.handle-bar {
  width: 40px;
  height: 4px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.15);
}

.mobile-add-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.mobile-add-title {
  font-size: 20px;
  font-weight: 700;
  color: #e2e0e8;
  margin: 0;
}

.mobile-add-hint {
  font-size: 13px;
  color: #9c99ab;
  line-height: 1.5;
  margin: 0;
}

.mobile-add-input {
  width: 100%;
  padding: 16px 18px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #e2e0e8;
  font-size: 16px;
  outline: none;
  transition: all 0.2s ease;
  font-family: inherit;
  box-sizing: border-box;
}

.mobile-add-input:focus {
  border-color: rgba(124, 58, 237, 0.4);
  background: rgba(255, 255, 255, 0.06);
}

.mobile-add-input::placeholder {
  color: #9c99ab;
}

.mobile-add-actions {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}

.mobile-add-btn {
  flex: 1;
  padding: 14px;
  border-radius: 14px;
  border: none;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.mobile-add-btn.secondary {
  background: rgba(255, 255, 255, 0.06);
  color: #9c99ab;
}

.mobile-add-btn.primary {
  background: #7c3aed;
  color: white;
}

.mobile-add-btn.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mobile-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 2000;
}

/* ─── Mobile Detail Overlay ─── */
.mobile-detail-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: #2d2a3e;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.mobile-detail-header {
  display: flex;
  align-items: center;
  padding: 16px 20px;
  gap: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.mobile-back-btn {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mobile-detail-title {
  flex: 1;
  font-size: 16px;
  font-weight: 600;
  color: #e2e0e8;
  margin: 0;
  text-align: center;
}

.mobile-fav-btn {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mobile-fav-btn.active {
  color: #f472b6;
}

.mobile-detail-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px 20px;
}

.mobile-word {
  font-size: 32px;
  font-weight: 700;
  color: #e2e0e8;
  margin: 0 0 12px 0;
  letter-spacing: -0.5px;
}

.mobile-definition {
  font-size: 15px;
  line-height: 1.6;
  color: #b8b5c8;
  margin: 0 0 28px 0;
}

.mobile-meta-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 28px;
}

.mobile-meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.mobile-meta-label {
  font-size: 13px;
  color: #9c99ab;
}

.mobile-meta-value {
  font-size: 14px;
  font-weight: 600;
  color: #e2e0e8;
}

.mobile-examples {
  margin-bottom: 28px;
}

.mobile-delete-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px;
  border-radius: 14px;
  border: none;
  background: rgba(239, 68, 68, 0.1);
  color: #f87171;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.mobile-delete-btn:hover {
  background: rgba(239, 68, 68, 0.2);
}

/* ─── Transitions ─── */
.slide-panel-enter-active,
.slide-panel-leave-active {
  transition: all 0.3s ease;
}

.slide-panel-enter-from,
.slide-panel-leave-to {
  transform: translateX(20px);
  opacity: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100%);
}

/* ─── Responsive ─── */
@media (max-width: 768px) {
  .my-words-view {
    padding: 16px;
  }

  .words-header {
    flex-direction: row;
    align-items: center;
    gap: 12px;
  }

  .words-title {
    font-size: 22px;
  }

  .add-btn span {
    display: none;
  }

  .add-btn {
    padding: 10px;
    border-radius: 12px;
  }

  .words-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .search-box {
    max-width: none;
  }

  .filter-tabs {
    align-self: flex-start;
  }

  .words-content.detail-open .word-list {
    flex: 1;
    max-width: none;
  }

  .detail-panel {
    display: none;
  }

  .word-card {
    padding: 14px 16px;
  }

  .word-definition {
    -webkit-line-clamp: 1;
  }
}

@media (min-width: 769px) {
  .mobile-detail-overlay,
  .mobile-add-panel,
  .mobile-backdrop {
    display: none;
  }
}
</style>