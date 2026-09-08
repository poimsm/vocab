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

const speak = () => {
  if (!word.value) return
  const utterance = new SpeechSynthesisUtterance(word.value.main)
  utterance.lang = 'en-US'
  window.speechSynthesis.speak(utterance)
}

onMounted(() => {
  loadWord()
})
</script>

<template>
  <div class="page-wrapper">
    <!-- Loading State -->
    <div v-if="isLoading" class="state-container loading">
      <div class="spinner"></div>
      <p>Loading word...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="state-container error">
      <Icon icon="solar:danger-triangle-bold" width="48" class="error-icon" />
      <p class="error-message">{{ error }}</p>
      <div class="action-group">
        <button @click="loadWord" class="btn btn-primary">
          <Icon icon="solar:refresh-linear" width="16" />
          Retry
        </button>
        <button @click="router.back()" class="btn btn-secondary">
          <Icon icon="solar:arrow-left-linear" width="16" />
          Go Back
        </button>
      </div>
    </div>

    <!-- Content -->
    <template v-else-if="word">
      <!-- ═══ Mobile App Header ═══ -->
      <header class="app-header mobile-only">
        <button @click="router.back()" class="header-btn" aria-label="Go back">
          <Icon icon="solar:arrow-left-linear" width="28" />
        </button>
        <span class="header-center-title"></span>
        <div class="header-right-actions">
          <button
            @click="toggleFavorite"
            :disabled="isSavingFavorite"
            class="header-btn"
            :class="{ 'is-favorite': word.is_favorite }"
            aria-label="Toggle favorite"
          >
            <Icon
              :icon="word.is_favorite ? 'solar:heart-bold' : 'solar:heart-linear'"
              width="25"
            />
          </button>
        </div>
      </header>

      <!-- ═══ Desktop Nav ═══ -->
      <nav class="desktop-nav desktop-only">
        <button @click="router.back()" class="nav-back-link">
          <Icon icon="solar:arrow-left-linear" width="16" />
          Back to list
        </button>
      </nav>

      <!-- ═══ Main Container ═══ -->
      <main class="main-container">
        <!-- Word Hero -->
        <section class="word-hero">
          <div class="word-hero-header">
            <div class="word-title-wrap">
              <h1 class="word-title">{{ word.main }}</h1>
              <button @click="speak" class="speaker-btn" title="Listen pronunciation">
                <Icon icon="solar:volume-loud-linear" width="20" />
              </button>
            </div>
            <!-- Favorite button (desktop only) -->
            <button
              @click="toggleFavorite"
              :disabled="isSavingFavorite"
              class="favorite-btn desktop-only"
              :class="{ 'is-favorite': word.is_favorite }"
              title="Add to favorites"
            >
              <Icon
                :icon="word.is_favorite ? 'solar:heart-bold' : 'solar:heart-linear'"
                width="24"
              />
            </button>
          </div>
          <p class="word-definition">{{ word.meaning }}</p>
        </section>

        <!-- ═══ Desktop Layout (2 columns) ═══ -->
        <div class="desktop-layout desktop-only">
          <!-- Left: Examples + Source -->
          <div class="desktop-main">
            <section v-if="word.examples && word.examples.length > 0" class="content-section">
              <h2 class="section-heading">
                Examples
                <span class="heading-count">({{ word.total_examples }})</span>
              </h2>
              <ul class="example-list">
                <li
                  v-for="(example, idx) in word.examples"
                  :key="idx"
                  class="example-item"
                  :style="{ animationDelay: `${idx * 50}ms` }"
                >
                  {{ example }}
                </li>
              </ul>
            </section>
          </div>

          <!-- Right: Sidebar -->
          <aside class="desktop-sidebar">
            <!-- Learned Toggle -->
            <div class="learned-toggle-card">
              <label class="learned-toggle">
                <input
                  type="checkbox"
                  :checked="word.is_learned"
                  @change="markAsLearned"
                  :disabled="isSavingLearned"
                />
                <span class="toggle-label">Already know this word?</span>
              </label>
            </div>

            <!-- Synonyms -->
            <section
              v-if="word.synonyms && word.synonyms.length > 0"
              class="content-section"
            >
              <h2 class="section-heading">Synonyms</h2>
              <div class="tags-list">
                <span
                  v-for="(synonym, idx) in word.synonyms"
                  :key="idx"
                  class="tag"
                  :style="{ animationDelay: `${idx * 40}ms` }"
                >
                  {{ synonym }}
                </span>
              </div>
            </section>

            <!-- Metadata -->
            <section class="content-section">
              <h2 class="section-heading">Details</h2>
              <div class="metadata-list">
                <div v-if="word.type" class="meta-row">
                  <span class="meta-label">Type</span>
                  <span class="meta-value">{{ word.type }}</span>
                </div>
                <div v-if="word.level" class="meta-row">
                  <span class="meta-label">Level</span>
                  <span class="meta-value meta-value--green">{{ word.level }}</span>
                </div>
                <div v-if="word.frequency" class="meta-row">
                  <span class="meta-label">Frequency</span>
                  <span class="meta-value meta-value--purple">{{ word.frequency }}</span>
                </div>
                <div class="meta-row">
                  <span class="meta-label">Added</span>
                  <span class="meta-value">{{ new Date(word.created_at).toLocaleDateString() }}</span>
                </div>
              </div>
            </section>
          </aside>
        </div>

        <!-- ═══ Mobile Layout (single column) ═══ -->
        <div class="mobile-flow mobile-only">
          <!-- Synonyms -->
          <section
            v-if="word.synonyms && word.synonyms.length > 0"
            class="content-section"
          >
            <h2 class="section-heading">Synonyms</h2>
            <div class="tags-list">
              <span v-for="(synonym, idx) in word.synonyms" :key="idx" class="tag">
                {{ synonym }}
              </span>
            </div>
          </section>

          <!-- Metadata -->
          <section class="content-section metadata-plain">
            <div class="metadata-list">
              <div v-if="word.type" class="meta-row">
                <span class="meta-label">Type</span>
                <span class="meta-value">{{ word.type }}</span>
              </div>
              <div v-if="word.level" class="meta-row">
                <span class="meta-label">Level</span>
                <span class="meta-value meta-value--green">{{ word.level }}</span>
              </div>
              <div v-if="word.frequency" class="meta-row">
                <span class="meta-label">Frequency</span>
                <span class="meta-value meta-value--purple">{{ word.frequency }}</span>
              </div>
              <div class="meta-row">
                <span class="meta-label">Added</span>
                <span class="meta-value">{{ new Date(word.created_at).toLocaleDateString() }}</span>
              </div>
            </div>
          </section>

          <!-- Examples -->
          <section v-if="word.examples && word.examples.length > 0" class="content-section">
            <h2 class="section-heading">
              Examples
              <span class="heading-count">({{ word.total_examples }})</span>
            </h2>
            <ul class="example-list">
              <li v-for="(example, idx) in word.examples" :key="idx" class="example-item">
                {{ example }}
              </li>
            </ul>
          </section>

          <!-- Mobile Learned Toggle -->
          <div class="mobile-learned-toggle">
            <label class="learned-toggle">
              <input
                type="checkbox"
                :checked="word.is_learned"
                @change="markAsLearned"
                :disabled="isSavingLearned"
              />
              <span class="toggle-label">Already know this word?</span>
            </label>
          </div>
        </div>
      </main>
    </template>
  </div>
</template>

<style scoped>
* {
  box-sizing: border-box;
}

.page-wrapper {
  min-height: 100vh;
  background: #2d2a3e;
  color: #e2e0e8;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
  display: flex;
  flex-direction: column;
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
   LOADING & ERROR STATES
   ═══════════════════════════════════════════ */
.state-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  gap: 20px;
}

.state-container.loading p {
  font-size: 17px;
  color: #8b88a4;
  margin: 0;
  animation: pulse 2s ease-in-out infinite;
}

.state-container.error .error-icon {
  color: #f87171;
  opacity: 0.8;
}

.state-container.error .error-message {
  font-size: 16px;
  color: #f87171;
  margin: 0;
  text-align: center;
  max-width: 400px;
  line-height: 1.5;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(139, 136, 164, 0.15);
  border-top-color: #8b5cf6;
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes pulse {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.action-group {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 11px 22px;
  border-radius: 10px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-primary {
  background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
  color: #fff;
  box-shadow: 0 4px 14px rgba(124, 58, 237, 0.25);
}

.btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(124, 58, 237, 0.35);
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.05);
  color: #d1d5db;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.15);
}

/* ═══════════════════════════════════════════
   MOBILE APP HEADER
   ═══════════════════════════════════════════ */
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  position: relative;
}

.header-center-title {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  font-size: 16px;
  font-weight: 600;
  color: #e2e0e8;
  letter-spacing: 0.3px;
}

.header-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  color: #9c99ab;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.header-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
}

.header-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.header-btn.is-favorite {
  color: #f472b6;
}

.header-right-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* ═══════════════════════════════════════════
   DESKTOP NAV
   ═══════════════════════════════════════════ */
.desktop-nav {
  max-width: 1000px;
  margin: 0 auto;
  padding: 24px 32px 0;
  width: 100%;
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

/* ═══════════════════════════════════════════
   MAIN CONTAINER
   ═══════════════════════════════════════════ */
.main-container {
  max-width: 1000px;
  margin: 0 auto;
  padding: 28px 32px 48px;
  width: 100%;
}

@media (max-width: 768px) {
  .main-container {
    padding: 20px;
  }
}

/* ═══════════════════════════════════════════
   WORD HERO
   ═══════════════════════════════════════════ */
.word-hero {
  margin-bottom: 36px;
}

@media (max-width: 768px) {
  .word-hero {
    margin-bottom: 28px;
  }
}

.word-hero-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.word-title-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 0;
}

.favorite-btn {
  width: 44px;
  height: 44px;
  border: none;
  background: rgba(255, 255, 255, 0.05);
  color: #9c99ab;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
  margin-top: -8px;
}

.favorite-btn:hover:not(:disabled) {
  background: rgba(244, 114, 182, 0.1);
  color: #f472b6;
  border-color: rgba(244, 114, 182, 0.2);
}

.favorite-btn.is-favorite {
  color: #f472b6;
  background: rgba(244, 114, 182, 0.1);
  border-color: rgba(244, 114, 182, 0.2);
}

.favorite-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.word-title {
  font-size: 38px;
  font-weight: 800;
  color: #f5f3ff;
  margin: 0;
  letter-spacing: -0.6px;
  line-height: 1.1;
}

@media (max-width: 768px) {
  .word-title {
    font-size: 30px;
  }
}

.speaker-btn {
  width: 40px;
  height: 40px;
  border: none;
  background: rgba(139, 92, 246, 0.1);
  color: #a78bfa;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid rgba(139, 92, 246, 0.15);
  flex-shrink: 0;
}

.speaker-btn:hover {
  background: rgba(139, 92, 246, 0.2);
  transform: scale(1.05);
}

.speaker-btn:active {
  transform: scale(0.95);
}

.word-definition {
  font-size: 17px;
  line-height: 1.7;
  color: #b4b1c6;
  margin: 0;
  max-width: 640px;
}

@media (max-width: 768px) {
  .word-definition {
    font-size: 17px;
    line-height: 1.65;
  }
}

/* ═══════════════════════════════════════════
   SECTIONS & HEADINGS
   ═══════════════════════════════════════════ */
.content-section {
  margin-bottom: 32px;
}

.content-section:last-child {
  margin-bottom: 0;
}

.section-heading {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: #9c99ab;
  margin: 0 0 14px 0;
}

.heading-count {
  color: #6b6880;
  font-weight: 600;
}

/* ═══════════════════════════════════════════
   TAGS (Synonyms)
   ═══════════════════════════════════════════ */
.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag {
  padding: 7px 14px;
  background: rgba(139, 92, 246, 0.1);
  border: 1px solid rgba(139, 92, 246, 0.15);
  border-radius: 20px;
  font-size: 13px;
  color: #c4b5fd;
  font-weight: 500;
  transition: all 0.2s ease;
  cursor: default;
  opacity: 0;
  animation: fadeIn 0.4s ease forwards;
}

.tag:hover {
  background: rgba(139, 92, 246, 0.18);
  border-color: rgba(139, 92, 246, 0.3);
  transform: translateY(-1px);
}

/* ═══════════════════════════════════════════
   METADATA
   ═══════════════════════════════════════════ */
.metadata-list {
  display: flex;
  flex-direction: column;
}

.meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.meta-row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.meta-row:first-child {
  padding-top: 0;
}

.meta-label {
  font-size: 14px;
  color: #9c99ab;
}

.meta-value {
  font-size: 14px;
  color: #e2e0e8;
  font-weight: 600;
}

.meta-value--green {
  color: #4ade80;
}

.meta-value--purple {
  color: #a78bfa;
}

/* ═══════════════════════════════════════════
   EXAMPLES
   ═══════════════════════════════════════════ */
.example-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.example-item {
  position: relative;
  padding-left: 20px;
  font-size: 15px;
  line-height: 1.7;
  color: #c4c2d4;
  opacity: 0;
  animation: fadeSlideUp 0.5s ease forwards;
}

.example-item::before {
  content: '•';
  position: absolute;
  left: 0;
  top: 0;
  color: #8b5cf6;
  font-weight: 700;
  font-size: 18px;
  line-height: 1.4;
}

@media (max-width: 768px) {
  .example-item {
    font-size: 16px;
    line-height: 1.65;
  }
}

/* ═══════════════════════════════════════════
   SOURCE
   ═══════════════════════════════════════════ */
.source-text {
  font-size: 14px;
  line-height: 1.7;
  color: #9c99ab;
  font-style: italic;
  margin: 0;
  padding: 16px 20px;
  background: rgba(255, 255, 255, 0.02);
  border-left: 3px solid rgba(139, 92, 246, 0.3);
  border-radius: 0 8px 8px 0;
}

/* ═══════════════════════════════════════════
   LEARNED TOGGLE
   ═══════════════════════════════════════════ */
.learned-toggle-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 14px;
  padding: 16px 20px;
  margin-bottom: 24px;
  transition: all 0.3s ease;
  margin-top: 30px;
}

.learned-toggle-card:hover {
  border-color: rgba(255, 255, 255, 0.1);
}

.learned-toggle {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  user-select: none;
}

.learned-toggle input[type="checkbox"] {
  width: 20px;
  height: 20px;
  cursor: pointer;
  accent-color: #4ade80;
  flex-shrink: 0;
}

.learned-toggle input[type="checkbox"]:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.toggle-label {
  font-size: 14px;
  font-weight: 500;
  color: #b4b1c6;
  transition: color 0.2s ease;
}

.learned-toggle input[type="checkbox"]:checked ~ .toggle-label {
  color: #4ade80;
  font-weight: 600;
}

/* ═══════════════════════════════════════════
   DESKTOP LAYOUT (2 columns)
   ═══════════════════════════════════════════ */
.desktop-layout {
  display: grid;
  grid-template-columns: 1.5fr 1fr;
  gap: 48px;
  align-items: start;
}

.desktop-main {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.desktop-sidebar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  position: sticky;
  top: 24px;
}

/* Sidebar cards */
.sidebar-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 14px;
  padding: 20px;
  margin-bottom: 24px;
  transition: all 0.3s ease;
}

.sidebar-card:hover {
  border-color: rgba(255, 255, 255, 0.1);
}

.sidebar-action-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.05);
  color: #d1d5db;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-bottom: 10px;
  font-family: inherit;
}

.sidebar-action-btn:last-child {
  margin-bottom: 0;
}

.sidebar-action-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.15);
  transform: translateY(-1px);
}

.sidebar-action-btn:active:not(:disabled) {
  transform: translateY(0);
}

.sidebar-action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.sidebar-action-btn.active {
  background: rgba(244, 114, 182, 0.1);
  color: #f472b6;
  border-color: rgba(244, 114, 182, 0.2);
}

.sidebar-action-btn.learn:hover:not(:disabled) {
  background: rgba(74, 222, 128, 0.1);
  color: #4ade80;
  border-color: rgba(74, 222, 128, 0.2);
}

.learned-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  border-radius: 10px;
  background: rgba(74, 222, 128, 0.08);
  color: #4ade80;
  font-size: 14px;
  font-weight: 700;
  border: 1px solid rgba(74, 222, 128, 0.15);
}

/* ═══════════════════════════════════════════
   MOBILE FLOW
   ═══════════════════════════════════════════ */
.mobile-flow {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.metadata-plain .meta-row {
  padding: 14px 0;
}

.metadata-plain .meta-label {
  font-size: 17px;
}

.metadata-plain .meta-value {
  font-size: 17px;
}

/* Mobile Learned Toggle */
.mobile-learned-toggle {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 16px;
  margin-top: 28px;
  transition: all 0.3s ease;
}

.mobile-learned-toggle:active {
  border-color: rgba(255, 255, 255, 0.1);
}

.mobile-learned-toggle .learned-toggle {
  gap: 10px;
}

.mobile-learned-toggle .learned-toggle input[type="checkbox"] {
  width: 18px;
  height: 18px;
}

.mobile-learned-toggle .toggle-label {
  font-size: 17px;
}

/* ═══════════════════════════════════════════
   ANIMATIONS
   ═══════════════════════════════════════════ */
@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.96); }
  to   { opacity: 1; transform: scale(1); }
}

@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ═══════════════════════════════════════════
   SCROLLBAR
   ═══════════════════════════════════════════ */
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.12);
}

/* ═══════════════════════════════════════════
   RESPONSIVE TWEAKS
   ═══════════════════════════════════════════ */
@media (max-width: 768px) {
  .content-section {
    margin-bottom: 28px;
  }
}

@media (max-width: 480px) {
  .header-btn { 
    width: auto;
    height: auto;
  }
  .word-title {
    font-size: 28px;
    color: #e2e0e8;
  }
  .word-definition {
    font-size: 18px;
  }
  .section-heading {
    margin-bottom: 12px;
    font-size: 14px;
  }
  .tag {
    padding: 6px 12px;
    font-size: 16px;
  }
  .example-item {
    padding-left: 18px;
    font-size: 18px;
  }
  .meta-label,
  .meta-value {
    font-size: 15px;
  }
  .mobile-flow {
    gap: 8px;
  }
}
</style>