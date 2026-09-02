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
const favoritesFilter = ref<'all' | 'marked' | 'not_marked'>('all')
const markingExample = ref<number | null>(null)
const showFilterMenu = ref(false)
const showFilterBar = ref(true)
const isInitialLoad = ref(true)

const FAVORITES_LIMIT = 10

// ─── Scroll tracking (non-reactive for performance) ───
let scrollLastY = 0
let scrollAccumulatedDown = 0
let scrollAccumulatedUp = 0
let scrollLastDirection: 'up' | 'down' | null = null

// Computed
const filteredFavoriteExamples = computed(() => {
  if (favoritesFilter.value === 'all') {
    return favoriteExamples.value
  } else if (favoritesFilter.value === 'marked') {
    return favoriteExamples.value.filter(ex => ex.is_marked)
  } else {
    return favoriteExamples.value.filter(ex => !ex.is_marked)
  }
})

// Methods
async function fetchFavorites() {
  if (favoritesLoading.value) return

  favoritesLoading.value = true

  try {
    const params: any = {
      page: favoritesPage.value,
      limit: FAVORITES_LIMIT
    }

    // Agregar filtro is_marked si está activo
    if (favoritesFilter.value === 'marked') {
      params.is_marked = true
    } else if (favoritesFilter.value === 'not_marked') {
      params.is_marked = false
    }

    const response = await api.get('/examples/favorites', {
      params
    })

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
  scrollLastY = 0
  scrollAccumulatedDown = 0
  scrollAccumulatedUp = 0
  scrollLastDirection = null
  showFilterBar.value = true
}

function handleFavoritesScroll(event: Event) {
  const target = event.target as HTMLElement
  const scrollTop = target.scrollTop
  const clientHeight = target.clientHeight
  const scrollHeight = target.scrollHeight

  // ── Infinite scroll ──
  if (scrollHeight - (scrollTop + clientHeight) < 200) {
    if (favoritesPage.value < favoritesTotalPages.value && !favoritesLoading.value) {
      nextFavoritesPage()
    }
  }

  // ── Auto-hiding header logic ──
  // Never hide while filter menu is open
  if (showFilterMenu.value) return

  // Always show when at top
  if (scrollTop < 10) {
    showFilterBar.value = true
    resetScrollTracking()
    return
  }

  const delta = scrollTop - scrollLastY
  if (Math.abs(delta) < 2) {
    // Ignore micro-jitter
    return
  }

  const direction = delta > 0 ? 'down' : 'up'

  // Reset accumulated opposite direction immediately
  if (direction !== scrollLastDirection) {
    scrollAccumulatedDown = 0
    scrollAccumulatedUp = 0
  }

  if (direction === 'up') {
    scrollAccumulatedUp += Math.abs(delta)
    // Native apps show header IMMEDIATELY when scrolling up (low threshold)
    if (scrollAccumulatedUp > 6) {
      showFilterBar.value = true
    }
  } else {
    scrollAccumulatedDown += delta
    // Hide only after meaningful scroll down (prevents micro-scroll hides)
    if (scrollAccumulatedDown > 55) {
      showFilterBar.value = false
    }
  }

  scrollLastY = scrollTop
  scrollLastDirection = direction
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
  // No limpiar datos para mantener la posición cuando se reabre
}

function handleWordClick(word: any) {
  emit('word-click', word)
}

// When filter changes, show header so user sees content changed
watch(favoritesFilter, () => {
  showFilterBar.value = true
  scrollAccumulatedDown = 0
  scrollAccumulatedUp = 0
  favoritesPage.value = 1
  favoriteExamples.value = []
  fetchFavorites()
})

watch(
  () => props.modelValue,
  (newValue) => {
    if (newValue) {
      // Si ya tiene datos, solo resetear el scroll
      if (favoriteExamples.value.length > 0) {
        resetScrollTracking()
      } else {
        // Si no tiene datos, traer desde cero
        favoritesPage.value = 1
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
  <!-- Favorites View (Fullscreen) -->
  <div v-show="modelValue" class="favorites-view">
    <div class="favorites-header">
      <h2>Favorite Examples</h2>
      <button class="close-favorites-btn" @click="closeModal" title="Close">
        <Icon icon="solar:close-linear" width="28" />
      </button>
    </div>

    <!-- Filter Buttons (Desktop) -->
    <div class="favorites-filter" v-if="favoriteExamples.length > 0">
      <button
        class="filter-btn"
        :class="{ active: favoritesFilter === 'all' }"
        @click="favoritesFilter = 'all'"
      >
        All
      </button>
      <button
        class="filter-btn"
        :class="{ active: favoritesFilter === 'marked' }"
        @click="favoritesFilter = 'marked'"
      >
        Marked
      </button>
      <button
        class="filter-btn"
        :class="{ active: favoritesFilter === 'not_marked' }"
        @click="favoritesFilter = 'not_marked'"
      >
        Not Marked
      </button>
    </div>

    <!-- Filter Menu (Mobile) -->
    <div
      v-show="favoriteExamples.length > 0"
      class="favorites-filter-mobile"
      :class="{ 'is-hidden': !showFilterBar }"
    >
      <button class="filter-menu-btn" @click="showFilterMenu = !showFilterMenu" title="Filter">
        <Icon icon="solar:filter-linear" width="20" />
        <span class="filter-label">{{ favoritesFilter === 'all' ? 'All' : favoritesFilter === 'marked' ? 'Marked' : 'Not Marked' }}</span>
        <Icon
          icon="solar:alt-arrow-down-linear"
          width="16"
          class="filter-arrow"
          :class="{ 'is-open': showFilterMenu }"
        />
      </button>
      <div v-if="showFilterMenu" class="filter-dropdown">
        <button
          class="filter-option"
          :class="{ active: favoritesFilter === 'all' }"
          @click="favoritesFilter = 'all'; showFilterMenu = false"
        >
          All
        </button>
        <button
          class="filter-option"
          :class="{ active: favoritesFilter === 'marked' }"
          @click="favoritesFilter = 'marked'; showFilterMenu = false"
        >
          Marked
        </button>
        <button
          class="filter-option"
          :class="{ active: favoritesFilter === 'not_marked' }"
          @click="favoritesFilter = 'not_marked'; showFilterMenu = false"
        >
          Not Marked
        </button>
      </div>
    </div>

    <div class="favorites-content" @scroll="handleFavoritesScroll">
      <div v-if="favoritesLoading && favoriteExamples.length === 0" class="loading-state">
        <div class="spinner"></div>
        <p>Loading favorites...</p>
      </div>

      <div v-else-if="filteredFavoriteExamples.length > 0" class="favorites-items">
        <div v-for="example in filteredFavoriteExamples" :key="example.id" class="favorite-card" :class="{ marked: example.is_marked }">
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
                <span v-if="segment.is_highlighted && segment.target_word" class="word-highlight"
                  @click="handleWordClick(segment.target_word)">
                  {{ segment.text }}
                </span>
                <span v-else>{{ segment.text }}</span>
              </template>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="favoriteExamples.length > 0" class="empty-filtered">
        <p>No {{ favoritesFilter }} examples</p>
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
.favorites-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
  background: #2d2a3e;
  color: #e2e0e8;
  overflow: hidden;
}

/* ─── Header: capa superior opaca para ocultar el filtro detrás ─── */
.favorites-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
  /* Fondo sólido que opaca TODO lo que pase por detrás */
  background: #2d2a3e;
  position: relative;
  z-index: 20;
}

.favorites-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
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
  transition: all 0.2s ease;
}

.close-favorites-btn:hover {
  color: #e2e0e8;
}

/* ─── Favorites Filter (Desktop) ─── */
.favorites-filter {
  display: flex;
  gap: 8px;
  padding: 16px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  flex-shrink: 0;
  flex-wrap: wrap;
}

.filter-btn {
  padding: 6px 14px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.05);
  color: #9c99ab;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
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

/* ─── Favorites Filter (Mobile) ─── */
.favorites-filter-mobile {
  display: none;
  position: relative;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  flex-shrink: 0;
  /* GPU-accelerated smooth hide/show */
  will-change: transform, opacity;
  transition: transform 0.4s cubic-bezier(0.32, 0.72, 0, 1),
              opacity 0.35s ease,
              box-shadow 0.35s ease;
  /* Glassmorphism native feel */
  background: rgba(45, 42, 62, 0.92);
  backdrop-filter: blur(16px) saturate(180%);
  -webkit-backdrop-filter: blur(16px) saturate(180%);
  /* Z-index menor que el header: se desliza DETRÁS de él */
  z-index: 10;
}

.favorites-filter-mobile.is-hidden {
  display: none;
}

.filter-menu-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.05);
  color: #9c99ab;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  width: 100%;
  -webkit-tap-highlight-color: transparent;
}

.filter-menu-btn:active {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
  transform: scale(0.995);
}

.filter-label {
  flex: 1;
  text-align: left;
}

.filter-arrow {
  transition: transform 0.3s cubic-bezier(0.32, 0.72, 0, 1);
  color: #9c99ab;
}

.filter-arrow.is-open {
  transform: rotate(180deg);
}

.filter-dropdown {
  position: absolute;
  top: 100%;
  left: 16px;
  right: 16px;
  margin-top: 8px;
  background: #3d3a52;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  overflow: hidden;
  z-index: 1000;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
  animation: dropdownReveal 0.25s cubic-bezier(0.32, 0.72, 0, 1);
}

@keyframes dropdownReveal {
  from {
    opacity: 0;
    transform: translateY(-6px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.filter-option {
  display: block;
  width: 100%;
  padding: 14px 16px;
  border: none;
  background: transparent;
  color: #9c99ab;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  -webkit-tap-highlight-color: transparent;
}

.filter-option:last-child {
  border-bottom: none;
}

.filter-option:active {
  background: rgba(255, 255, 255, 0.05);
  color: #e2e0e8;
}

.filter-option.active {
  background: rgba(167, 139, 250, 0.15);
  color: #a78bfa;
}

.favorites-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  scrollbar-width: none;
  -ms-overflow-style: none;
  /* Momentum scrolling for iOS */
  -webkit-overflow-scrolling: touch;
}

.favorites-content::-webkit-scrollbar {
  display: none;
}

.favorites-items {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.favorite-card {
  padding: 16px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  transition: all 0.2s ease;
}

.favorite-card:last-child {
  border-bottom: none;
}

.favorite-card.marked {
  opacity: 0.6;
}

.favorite-card-wrapper {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
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
  text-decoration: line-through;
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
  color: #4ade80;
}

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
  to {
    transform: rotate(360deg);
  }
}

.loading-more {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

@media (max-width: 768px) {
  .favorites-filter {
    display: none;
  }

  .favorites-filter-mobile {
    display: block;
  }

  .favorites-header {
    padding: 16px;
  }

  .favorites-header h2 {
    font-size: 20px;
  }

  .favorites-content {
    padding: 16px;
  }

  .favorite-card {
    padding: 16px 0;
  }

  .favorite-card-text {
    font-size: 18px !important;
  }

  .mark-checkbox {
    width: 36px;
    height: 36px;
  }
}
</style>