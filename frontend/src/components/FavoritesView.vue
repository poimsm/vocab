<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { Icon } from '@iconify/vue'
import api from '@/utils/api'

interface TextSegment {
  text: string
  is_highlighted: boolean
  target_word?: any
}

interface FavoriteExample {
  id: number
  text: TextSegment[]
  is_marked: boolean
}

// Props
interface Props {
  modelValue: boolean
}

interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'word-click', word: any): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// State
const favoriteExamples = ref<FavoriteExample[]>([])
const favoritesLoading = ref(false)
const favoritesPage = ref(1)
const favoritesTotalPages = ref(1)
const markingExample = ref<number | null>(null)
const showFilterBar = ref(true)
const isInitialLoad = ref(true)
const showDone = ref(false)
const showRandom = ref(false)
const lastSortBy = ref<'done' | 'random' | 'not_marked_first'>('not_marked_first')

const FAVORITES_LIMIT = 10

// Flag para evitar reiniciar cuando se hace scroll
let isUserChangingFilter = false

const displayedExamples = computed(() => {
  return favoriteExamples.value
})

// ─── Scroll tracking robusto (sin jitter) ───
let lastScrollTop = 0
let scrollTopWhenVisible = 0
let scrollTopWhenHidden = 0
let ticking = false

// Methods
async function fetchFavorites() {
  if (favoritesLoading.value) return

  favoritesLoading.value = true

  try {
    const params: any = {
      page: favoritesPage.value,
      limit: FAVORITES_LIMIT,
      sort_by: lastSortBy.value
    }

    const response = await api.get('/examples/favorites', { params })

    if (response.data && response.data.status === 'ok') {
      if (favoritesPage.value === 1) {
        favoriteExamples.value = response.data.items || []
      } else {
        favoriteExamples.value.push(...(response.data.items || []))
      }
      favoritesTotalPages.value = response.data.pages || 1
    }
  } catch (e: any) {
    alert('Failed to load favorite examples: ' + (e.response?.data?.message || e.message))
  } finally {
    favoritesLoading.value = false
  }
}

function nextFavoritesPage() {
  if (favoritesPage.value < favoritesTotalPages.value) {
    favoritesPage.value++
    fetchFavorites()
  }
}

function resetScrollTracking() {
  lastScrollTop = 0
  scrollTopWhenVisible = 0
  scrollTopWhenHidden = 0
  showFilterBar.value = true
}

function handleFavoritesScroll(event: Event) {
  if (ticking) return
  ticking = true

  requestAnimationFrame(() => {
    const target = event.target as HTMLElement
    const scrollTop = target.scrollTop
    const clientHeight = target.clientHeight
    const scrollHeight = target.scrollHeight

    // Guardar posición del scroll
    sessionStorage.setItem('exampleFavoritesScroll', String(scrollTop))

    // Infinite scroll
    if (scrollHeight - (scrollTop + clientHeight) < 200) {
      if (favoritesPage.value < favoritesTotalPages.value && !favoritesLoading.value) {
        nextFavoritesPage()
      }
    }

    // ── Auto-hide con histéresis ──
    // Siempre mostrar en el tope
    if (scrollTop < 10) {
      showFilterBar.value = true
      scrollTopWhenVisible = scrollTop
      lastScrollTop = scrollTop
      ticking = false
      return
    }

    const delta = scrollTop - lastScrollTop

    // Ignorar micro-movimientos (< 3px)
    if (Math.abs(delta) < 3) {
      lastScrollTop = scrollTop
      ticking = false
      return
    }

    if (delta > 0 && showFilterBar.value) {
      // Scrolleando hacia abajo: ocultar solo si bajamos > 50px desde que se mostró
      if (scrollTop - scrollTopWhenVisible > 50) {
        showFilterBar.value = false
        scrollTopWhenHidden = scrollTop
      }
    } else if (delta < 0 && !showFilterBar.value) {
      // Scrolleando hacia arriba: mostrar solo si subimos > 30px desde que se ocultó
      if (scrollTopWhenHidden - scrollTop > 30) {
        showFilterBar.value = true
        scrollTopWhenVisible = scrollTop
      }
    }

    lastScrollTop = scrollTop
    ticking = false
  })
}

async function toggleMarkedExample(exampleId: number) {
  markingExample.value = exampleId

  try {
    const response = await api.patch(`/examples/${exampleId}/toggle-marked`)

    if (response.data && response.data.is_marked !== undefined) {
      const example = favoriteExamples.value.find(ex => ex.id === exampleId)
      if (example) {
        example.is_marked = response.data.is_marked
      }
    }
  } catch (e: any) {
    alert('Failed to toggle marked status: ' + (e.response?.data?.message || e.message))
  } finally {
    markingExample.value = null
  }
}

function closeModal() {
  emit('update:modelValue', false)
}

function handleWordClick(word: any) {
  emit('word-click', word)
}

function toggleDone() {
  if (showRandom.value) {
    showRandom.value = false
  }
  showDone.value = !showDone.value
  isUserChangingFilter = true
  applyModeChange()
}

function toggleRandom() {
  if (showDone.value) {
    showDone.value = false
  }
  showRandom.value = !showRandom.value
  isUserChangingFilter = true
  applyModeChange()
}

function applyModeChange() {
  const sortBy = showDone.value ? 'done' : showRandom.value ? 'random' : 'not_marked_first'
  lastSortBy.value = sortBy

  showFilterBar.value = true
  scrollTopWhenVisible = 0
  scrollTopWhenHidden = 0
  favoritesPage.value = 1
  favoriteExamples.value = []
  fetchFavorites()

  isUserChangingFilter = false
}

watch(
  () => props.modelValue,
  (newValue) => {
    if (newValue) {
      if (favoriteExamples.value.length > 0) {
        resetScrollTracking()
      } else {
        favoritesPage.value = 1
        lastSortBy.value = 'not_marked_first'
        showDone.value = false
        showRandom.value = false
        isInitialLoad.value = true
        resetScrollTracking()
        fetchFavorites()
        setTimeout(() => {
          isInitialLoad.value = false
        }, 50)
      }
    }
  }
)

onMounted(() => {
  if (props.modelValue) {
    favoritesPage.value = 1
    lastSortBy.value = 'not_marked_first'
    showDone.value = false
    showRandom.value = false
    isInitialLoad.value = true
    resetScrollTracking()
    fetchFavorites()
    setTimeout(() => {
      isInitialLoad.value = false
    }, 50)
  }
})
</script>

<template>
  <div v-show="modelValue" class="favorites-view">
    <!-- Header Bar (grid animation = zero jitter) -->
    <div class="header-bar" :class="{ 'is-hidden': !showFilterBar }">
      <div class="header-inner">
        <div class="favorites-header">
          <h2>Favorite Examples</h2>
          <button class="close-favorites-btn" @click="closeModal" title="Close">
            <Icon icon="solar:close-linear" width="28" />
          </button>
        </div>

        <div class="favorites-filter">
          <button
            class="filter-btn"
            :class="{ active: showDone }"
            @click="toggleDone"
            title="Show only marked items"
          >
            <Icon icon="solar:check-circle-bold" width="16" />
            Done
          </button>
          <button
            class="filter-btn"
            :class="{ active: showRandom }"
            @click="toggleRandom"
            title="Randomize order"
          >
            <Icon icon="solar:shuffle-linear" width="16" />
            Random
          </button>
        </div>
      </div>
    </div>

    <div class="favorites-content" @scroll="handleFavoritesScroll">
      <div v-if="favoritesLoading && favoriteExamples.length === 0" class="loading-state">
        <div class="spinner"></div>
        <p>Loading favorites...</p>
      </div>

      <div v-else-if="displayedExamples.length > 0" class="favorites-items">
        <div
          v-for="example in displayedExamples"
          :key="example.id"
          class="favorite-card"
          :class="{ marked: example.is_marked }"
        >
          <div class="favorite-card-wrapper">
            <button
              class="mark-checkbox"
              @click="toggleMarkedExample(example.id)"
              :disabled="markingExample === example.id"
              :title="example.is_marked ? 'Unmark' : 'Mark as reviewed'"
            >
              <Icon
                v-if="example.is_marked"
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
            <div class="favorite-card-text" :class="{ 'line-through': example.is_marked }">
              <template v-for="(segment, idx) in example.text" :key="idx">
                <span
                  v-if="segment.is_highlighted && segment.target_word"
                  class="word-highlight"
                  @click="handleWordClick(segment.target_word)"
                >
                  {{ segment.text }}
                </span>
                <span v-else>{{ segment.text }}</span>
              </template>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="favoriteExamples.length > 0" class="empty-filtered">
        <p>No matching examples</p>
      </div>

      <div v-else class="empty-favorites">
        <p>No favorite examples yet</p>
      </div>

      <div v-if="favoritesLoading && favoriteExamples.length > 0" class="loading-more">
        <div class="spinner-small"></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
* {
  box-sizing: border-box;
}

.favorites-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
  background: #2d2a3e;
  color: #e2e0e8;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
  overflow: hidden;
}

/* ═══════════════════════════════════════════
   HEADER BAR — grid animation (zero jitter)
   ═══════════════════════════════════════════ */
.header-bar {
  display: grid;
  grid-template-rows: 1fr;
  transition: grid-template-rows 0.4s cubic-bezier(0.32, 0.72, 0, 1),
              opacity 0.3s ease;
  flex-shrink: 0;
  z-index: 20;
}

.header-bar.is-hidden {
  grid-template-rows: 0fr;
  opacity: 0;
  pointer-events: none;
}

.header-inner {
  overflow: hidden;
  min-height: 0;
}

/* ─── Header ─── */
.favorites-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  background: #2d2a3e;
}

.favorites-header h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.3px;
}

.close-favorites-btn {
  width: 40px;
  height: 40px;
  border: none;
  background: transparent;
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  transition: all 0.2s ease;
}

.close-favorites-btn:hover {
  color: #e2e0e8;
  background: rgba(255, 255, 255, 0.06);
}

/* ─── Favorites Filter ─── */
.favorites-filter {
  display: flex;
  gap: 8px;
  padding: 14px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  flex-wrap: wrap;
  background: #2d2a3e;
}

.filter-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.05);
  color: #9c99ab;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  font-family: inherit;
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

/* ═══════════════════════════════════════════
   CONTENT
   ═══════════════════════════════════════════ */
.favorites-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  -webkit-overflow-scrolling: touch;
}

.favorites-content::-webkit-scrollbar {
  width: 6px;
}

.favorites-content::-webkit-scrollbar-track {
  background: transparent;
}

.favorites-content::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
}

.favorites-content::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.12);
}

.favorites-items {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.favorite-card {
  padding: 16px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  transition: opacity 0.2s ease;
}

.favorite-card:last-child {
  border-bottom: none;
}

.favorite-card.marked {
  opacity: 0.55;
}

.favorite-card-wrapper {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.favorite-card-text {
  flex: 1;
  font-size: 17px;
  line-height: 1.8;
  color: #b8b5c8;
  word-break: break-word;
}

.favorite-card-text .word-highlight {
  color: #c4b5fd;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.2s ease;
}

.favorite-card-text .word-highlight:hover {
  color: #a78bfa;
  text-decoration: underline;
}

.favorite-card-text.line-through {
  color: #7c7a8a;
}

/* ─── Mark Checkbox ─── */
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
  margin-top: 2px;
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

/* ═══════════════════════════════════════════
   STATES
   ═══════════════════════════════════════════ */
.empty-favorites,
.empty-filtered {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  color: #9c99ab;
  font-size: 16px;
}

.empty-favorites p,
.empty-filtered p {
  margin: 0;
}

.loading-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  min-height: 300px;
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
  width: 24px;
  height: 24px;
  border: 3px solid rgba(124, 58, 237, 0.2);
  border-top-color: #7c3aed;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-more {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

/* ═══════════════════════════════════════════
   RESPONSIVE
   ═══════════════════════════════════════════ */
@media (max-width: 768px) {
  .favorites-header {
    padding: 16px 20px;
  }

  .favorites-header h2 {
    font-size: 20px;
  }

  .favorites-filter {
    padding: 12px 20px;
  }

  .filter-btn {
    font-size: 12px;
    padding: 6px 12px;
  }

  .favorites-content {
    padding: 16px 20px;
  }

  .favorite-card {
    padding: 14px 0;
  }

  .favorite-card-text {
    font-size: 18px;
    line-height: 1.75;
  }

  .mark-checkbox {
    width: 36px;
    height: 36px;
  }
}

@media (max-width: 480px) {
  .favorite-card-text {
    font-size: 17px;
  }
}
</style>