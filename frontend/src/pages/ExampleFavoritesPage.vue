<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useExampleFavoritesStore } from '@/stores/exampleFavorites'

interface TargetWord {
  id: number
  main: string
  type: string
  meaning?: string
  level?: number
  is_boosted: boolean
  batch_id?: number
  is_favorite?: boolean
}

const router = useRouter()
const favoritesStore = useExampleFavoritesStore()

// State
const favoritesContentRef = ref<HTMLElement | null>(null)
const markingExample = ref<number | null>(null)
const showFilterBar = ref(true)
const isInitialLoad = ref(true)
const showDone = ref(false)
const showRandom = ref(false)

// Flag para evitar reiniciar cuando se hace scroll
let isUserChangingFilter = false

// ─── Scroll tracking (non-reactive for performance) ───
let scrollLastY = 0
let scrollAccumulatedDown = 0
let scrollAccumulatedUp = 0
let scrollLastDirection: 'up' | 'down' | null = null

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

  // ── Guardar posición del scroll en cada scroll ──
  sessionStorage.setItem('exampleFavoritesScroll', String(scrollTop))

  // ── Infinite scroll ──
  if (scrollHeight - (scrollTop + clientHeight) < 200) {
    if (favoritesStore.favoritesPage < favoritesStore.favoritesTotalPages && !favoritesStore.favoritesLoading) {
      favoritesStore.nextPage()
    }
  }

  // ── Auto-hiding header logic ──
  if (scrollTop < 10) {
    showFilterBar.value = true
    resetScrollTracking()
    return
  }

  const delta = scrollTop - scrollLastY
  if (Math.abs(delta) < 2) {
    return
  }

  const direction = delta > 0 ? 'down' : 'up'

  if (direction !== scrollLastDirection) {
    scrollAccumulatedDown = 0
    scrollAccumulatedUp = 0
  }

  if (direction === 'up') {
    scrollAccumulatedUp += Math.abs(delta)
    if (scrollAccumulatedUp > 6) {
      showFilterBar.value = true
    }
  } else {
    scrollAccumulatedDown += delta
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
    await favoritesStore.toggleMarked(exampleId)
  } catch (e: any) {
    alert('Failed to toggle marked status: ' + (e.response?.data?.message || e.message))
  } finally {
    markingExample.value = null
  }
}

function goBack() {
  router.back()
}

function handleWordClick(word: TargetWord) {
  // Guardar flag de que estamos navegando (el scroll ya fue guardado en handleFavoritesScroll)
  sessionStorage.setItem('exampleFavoritesNavigatingAway', 'true')
  router.push(`/words/${word.id}`)
}

function restoreScrollPosition() {
  const savedScroll = sessionStorage.getItem('exampleFavoritesScroll')
  if (savedScroll && favoritesContentRef.value) {
    const scrollTop = parseInt(savedScroll, 10)
    favoritesContentRef.value.scrollTop = scrollTop
  }
}

function resetScrollToTop() {
  if (favoritesContentRef.value) {
    setTimeout(() => {
      if (favoritesContentRef.value) {
        favoritesContentRef.value.scrollTop = 0
      }
    }, 0)
  }
  sessionStorage.removeItem('exampleFavoritesScroll')
  sessionStorage.removeItem('exampleFavoritesNavigatingAway')
}

function toggleDone() {
  if (showRandom.value) {
    showRandom.value = false
  }
  showDone.value = !showDone.value
  isUserChangingFilter = true
  fetchFavoritesWithMode()
}

function toggleRandom() {
  if (showDone.value) {
    showDone.value = false
  }
  showRandom.value = !showRandom.value
  isUserChangingFilter = true
  fetchFavoritesWithMode()
}

function fetchFavoritesWithMode() {
  showFilterBar.value = true
  scrollAccumulatedDown = 0
  scrollAccumulatedUp = 0
  const sortBy = showDone.value ? 'done' : showRandom.value ? 'random' : 'not_marked_first'
  favoritesStore.fetchFavoritesWithMode(1, sortBy)
  isInitialLoad.value = false
  isUserChangingFilter = false
}


onMounted(async () => {
  resetScrollTracking()

  const wasNavigatingAway = sessionStorage.getItem('exampleFavoritesNavigatingAway') === 'true'

  if (wasNavigatingAway && favoritesStore.favoriteExamples.length > 0) {
    // Volvemos desde word detail: restaurar scroll guardado y mantener datos
    await nextTick()
    restoreScrollPosition()
    isInitialLoad.value = false
  } else {
    // Primera vez que entras desde ejemplos: cargar datos con scroll en 0
    resetScrollToTop()
    isInitialLoad.value = true
    try {
      await favoritesStore.fetchFavoritesWithMode(1, 'not_marked_first')
    } catch (e) {
      console.error('Error loading favorites:', e)
    }
    await nextTick()
    isInitialLoad.value = false
  }
})
</script>

<template>
  <div class="favorites-page">
    <!-- ═══ Mobile App Header ═══ -->
    <div class="mobile-header mobile-only" :class="{ 'is-hidden': !showFilterBar }">
      <button class="back-btn" @click="goBack" title="Go back">
        <Icon icon="solar:arrow-left-linear" width="24" />
      </button>
      <h2>Favorite Examples</h2>
      <div style="width: 40px"></div>
    </div>

    <!-- ═══ Desktop Layout ═══ -->
    <div class="desktop-wrapper desktop-only">
      <!-- Desktop Nav -->
      <nav class="desktop-nav">
        <button @click="goBack" class="nav-back-link">
          <Icon icon="solar:arrow-left-linear" width="16" />
          Back to list
        </button>
      </nav>

      <!-- Desktop Header -->
      <header class="desktop-hero">
        <h1 class="desktop-title">Favorite Examples</h1>
        <p class="desktop-subtitle">
          {{ favoritesStore.displayedExamples.length }}
          {{ favoritesStore.displayedExamples.length === 1 ? 'example' : 'examples' }}
          saved
        </p>
      </header>

      <!-- Desktop Filters -->
      <div class="desktop-filters">
        <button
          class="filter-chip"
          :class="{ active: !showDone && !showRandom }"
          @click="showDone = false; showRandom = false; fetchFavoritesWithMode()"
        >
          <Icon icon="solar:list-linear" width="14" />
          All
        </button>
        <button
          class="filter-chip"
          :class="{ active: showDone }"
          @click="toggleDone"
          title="Show only marked items"
        >
          <Icon icon="solar:check-circle-bold" width="14" />
          Done
        </button>
        <button
          class="filter-chip"
          :class="{ active: showRandom }"
          @click="toggleRandom"
          title="Randomize order"
        >
          <Icon icon="solar:shuffle-linear" width="14" />
          Random
        </button>
      </div>

      <!-- Desktop Content -->
      <div class="desktop-content" @scroll="handleFavoritesScroll">
        <div v-if="favoritesStore.favoritesLoading && favoritesStore.favoriteExamples.length === 0" class="loading-state">
          <div class="spinner"></div>
          <p>Loading favorites...</p>
        </div>

        <div v-else-if="favoritesStore.displayedExamples.length > 0" class="examples-list">
          <div
            v-for="example in favoritesStore.displayedExamples"
            :key="example.id"
            class="example-row"
            :class="{ marked: example.is_marked }"
          >
            <button
              class="check-btn"
              @click="toggleMarkedExample(example.id)"
              :disabled="markingExample === example.id"
              :title="example.is_marked ? 'Unmark' : 'Mark as reviewed'"
            >
              <Icon
                v-if="example.is_marked"
                icon="solar:check-circle-bold"
                width="22"
                class="checked"
              />
              <Icon
                v-else
                icon="mdi:checkbox-blank-outline"
                width="22"
              />
            </button>
            <div class="example-text" :class="{ 'line-through': example.is_marked }">
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

        <div v-else-if="favoritesStore.favoriteExamples.length > 0" class="empty-state">
          <Icon icon="solar:filter-search-linear" width="40" class="empty-icon" />
          <p>No matching examples</p>
        </div>

        <div v-else class="empty-state">
          <Icon icon="solar:heart-slash-linear" width="40" class="empty-icon" />
          <p>No favorite examples yet</p>
        </div>

        <div v-if="favoritesStore.favoritesLoading && favoritesStore.favoriteExamples.length > 0" class="loading-more">
          <div class="spinner-small"></div>
        </div>
      </div>
    </div>

    <!-- ═══ Mobile Layout ═══ -->
    <div class="mobile-wrapper mobile-only">
      <!-- Mobile Filters -->
      <div class="mobile-filters" :class="{ 'is-hidden': !showFilterBar }">
        <button
          class="filter-btn"
          :class="{ active: showDone }"
          @click="toggleDone"
          title="Show only marked items"
        >
          <Icon icon="solar:check-circle-bold" width="18" />
          Done
        </button>
        <button
          class="filter-btn"
          :class="{ active: showRandom }"
          @click="toggleRandom"
          title="Randomize order"
        >
          <Icon icon="solar:shuffle-linear" width="18" />
          Random
        </button>
      </div>

      <!-- Mobile Content -->
      <div ref="favoritesContentRef" class="mobile-content" @scroll="handleFavoritesScroll">
        <div v-if="favoritesStore.favoritesLoading && favoritesStore.favoriteExamples.length === 0" class="loading-state">
          <div class="spinner"></div>
          <p>Loading favorites...</p>
        </div>

        <div v-else-if="favoritesStore.displayedExamples.length > 0" class="favorites-items">
          <div
            v-for="example in favoritesStore.displayedExamples"
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

        <div v-else-if="favoritesStore.favoriteExamples.length > 0" class="empty-filtered">
          <p>No matching examples</p>
        </div>

        <div v-else class="empty-favorites">
          <p>No favorite examples yet</p>
        </div>

        <div v-if="favoritesStore.favoritesLoading && favoritesStore.favoriteExamples.length > 0" class="loading-more">
          <div class="spinner-small"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
* {
  box-sizing: border-box;
}

.favorites-page {
  height: 100vh;
  width: 100%;
  background: #2d2a3e;
  color: #e2e0e8;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
  overflow: hidden;
}

/* ═══════════════════════════════════════════
   UTILITIES: show/hide by breakpoint
   ═══════════════════════════════════════════ */
.desktop-only {
  display: none !important;
}

@media (min-width: 769px) {
  .desktop-only {
    display: block !important;
  }
  .mobile-only {
    display: none !important;
  }
}

/* ═══════════════════════════════════════════
   MOBILE HEADER
   ═══════════════════════════════════════════ */
.mobile-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  background: #2d2a3e;
  transition: transform 0.4s cubic-bezier(0.32, 0.72, 0, 1);
}

.mobile-header.is-hidden {
  display: none;
}

.mobile-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  flex: 1;
  text-align: center;
}

.back-btn {
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

.back-btn:hover {
  color: #e2e0e8;
  background: rgba(255, 255, 255, 0.05);
}

/* ═══════════════════════════════════════════
   MOBILE FILTERS
   ═══════════════════════════════════════════ */
.mobile-filters {
  display: flex;
  gap: 8px;
  padding: 12px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  flex-shrink: 0;
  flex-wrap: wrap;
  background: #2d2a3e;
  transition: transform 0.4s cubic-bezier(0.32, 0.72, 0, 1);
}

.mobile-filters.is-hidden {
  display: none;
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
  font-size: 14.5px;
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
   MOBILE CONTENT
   ═══════════════════════════════════════════ */
.mobile-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.mobile-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  scrollbar-width: none;
  -ms-overflow-style: none;
  -webkit-overflow-scrolling: touch;
}

.mobile-content::-webkit-scrollbar {
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
   DESKTOP LAYOUT
   ═══════════════════════════════════════════ */
.desktop-wrapper {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px 32px 40px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Desktop Nav */
.desktop-nav {
  margin-bottom: 8px;
  flex-shrink: 0;
}

.nav-back-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #9c99ab;
  background: none;
  border: none;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  padding: 8px 12px;
  border-radius: 8px;
  transition: all 0.2s ease;
  font-family: inherit;
}

.nav-back-link:hover {
  color: #e2e0e8;
  background: rgba(255, 255, 255, 0.04);
}

/* Desktop Hero */
.desktop-hero {
  margin-bottom: 20px;
  flex-shrink: 0;
}

.desktop-title {
  font-size: 32px;
  font-weight: 800;
  color: #f5f3ff;
  margin: 0 0 6px 0;
  letter-spacing: -0.5px;
}

.desktop-subtitle {
  font-size: 14px;
  color: #9c99ab;
  margin: 0;
  font-weight: 500;
}

/* Desktop Filters */
.desktop-filters {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.filter-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.04);
  color: #9c99ab;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
}

.filter-chip:hover {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(255, 255, 255, 0.18);
  color: #d1d5db;
}

.filter-chip.active {
  background: rgba(167, 139, 250, 0.12);
  border-color: rgba(167, 139, 250, 0.35);
  color: #a78bfa;
}

/* Desktop Content */
.desktop-content {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0;
  padding-right: 8px;
}

.examples-list {
  display: flex;
  flex-direction: column;
}

.example-row {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 18px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  transition: all 0.2s ease;
}

.example-row:last-child {
  border-bottom: none;
}

.example-row.marked {
  opacity: 0.55;
}

.example-row.marked .example-text {
  color: #7c7a8a;
}

.check-btn {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
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

.check-btn:hover:not(:disabled) {
  color: #a78bfa;
  background: rgba(167, 139, 250, 0.1);
}

.check-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.check-btn .checked {
  color: #bfb0f7;
}

.example-text {
  flex: 1;
  font-size: 16px;
  line-height: 1.75;
  color: #c4c2d4;
  word-break: break-word;
  padding-top: 4px;
}

.example-text .word-highlight {
  color: #c4b5fd;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.2s ease;
}

.example-text .word-highlight:hover {
  color: #a78bfa;
  text-decoration: underline;
}

/* ═══════════════════════════════════════════
   SHARED STATES
   ═══════════════════════════════════════════ */
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

.empty-state,
.empty-filtered,
.empty-favorites {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  gap: 12px;
  color: #9c99ab;
  font-size: 15px;
}

.empty-state p,
.empty-filtered p,
.empty-favorites p {
  margin: 0;
}

.empty-icon {
  color: #6b6880;
  opacity: 0.6;
}

/* ═══════════════════════════════════════════
   SCROLLBAR (desktop only)
   ═══════════════════════════════════════════ */
.desktop-content::-webkit-scrollbar {
  width: 6px;
}
.desktop-content::-webkit-scrollbar-track {
  background: transparent;
}
.desktop-content::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
}
.desktop-content::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.12);
}

/* ═══════════════════════════════════════════
   RESPONSIVE TWEAKS
   ═══════════════════════════════════════════ */
@media (max-width: 768px) {
  .favorite-card-text {
    font-size: 17px;
  }
}

@media (max-width: 480px) {
  .mobile-header h2 {
    font-size: 18px;
  }

  .mobile-content {
    padding: 16px;
  }

  .favorite-card-text {
    font-size: 16px;
    line-height: 1.7;
  }

  .mark-checkbox {
    width: 36px;
    height: 36px;
  }
}
</style>