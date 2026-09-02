<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import api from '@/utils/api'
import LoadingCard from '@/components/LoadingCard.vue'
import FavoritesView from '@/components/FavoritesView.vue'
import WordDetailPanel from '@/components/WordDetailPanel.vue'
import MobileWordDetail from '@/components/MobileWordDetail.vue'
import ExtractedWordsModal from '@/components/ExtractedWordsModal.vue'

// ─── Types ───
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

interface TextSegment {
  text: string
  is_highlighted: boolean
  target_word?: TargetWord
}

interface ExampleItem {
  queue_item_id: number
  example_id: number
  text: TextSegment[]
  extracted_words: string[]
  is_favorite?: boolean
  is_marked?: boolean
}

interface WordDetail {
  id: number
  word: string
  definition: string
  level: string | number
  context: string
  frequency: 'rare' | 'uncommon' | 'common'
  examples: string[]
  synonyms: string[]
  is_favorite?: boolean
}

// ─── State ───
const examples = ref<ExampleItem[]>([])
const currentIndex = ref(0)
const generating = ref(false)
const error = ref<string | null>(null)
const noWords = ref(false)
const isPolling = ref(false)
const pollTimer = ref<ReturnType<typeof setTimeout> | null>(null)

const selectedWord = ref<WordDetail | null>(null)
const isMobileDetailOpen = ref(false)
const showExtractedWordsModal = ref(false)
const showFavoritesModal = ref(false)
const showCopiedToast = ref(false)

const BATCH_SIZE = 4
const POLL_INTERVAL = 3000

// ─── Computed ───
const currentExample = computed(() => {
  if (examples.value.length === 0) return null
  return examples.value[currentIndex.value]
})

const textSegments = computed(() => {
  const ex = currentExample.value
  if (!ex) return []
  return ex.text
})

const canGoNext = computed(() => {
  return currentIndex.value < examples.value.length - 1
})

const canGoPrev = computed(() => {
  return currentIndex.value > 0
})

// ─── API Calls ───
function resolveOnly(queueItemId: number) {
  api.post('/examples/explore', {
    actions: ['resolve'],
    resolve_queue_item_id: queueItemId
  }).catch(() => { })
}

async function resolveAndFetchNext(queueItemId: number) {
  generating.value = true
  error.value = null

  try {
    const response = await api.post('/examples/explore', {
      actions: ['resolve', 'next'],
      resolve_queue_item_id: queueItemId,
      limit: BATCH_SIZE
    })

    const data = response.data

    if (data.status === 'generating') {
      startPolling()
      return
    }

    if (data.status === 'no_words') {
      generating.value = false
      noWords.value = true
      return
    }

    generating.value = false
    loadExamples(data)
  } catch (e: any) {
    generating.value = false
    error.value = e.response?.data?.message || e.message || 'Failed to fetch examples'
  }
}

// ─── Text-to-Speech ───
function speak(text: string) {
  if (!window.speechSynthesis) {
    console.warn('Speech synthesis not supported')
    return
  }

  window.speechSynthesis.cancel()

  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'en-US'
  utterance.rate = 0.9
  utterance.pitch = 1

  const voices = window.speechSynthesis.getVoices()
  const enVoice = voices.find(v => v.lang.startsWith('en'))
  if (enVoice) {
    utterance.voice = enVoice
  }

  window.speechSynthesis.speak(utterance)
}

function speakWord() {
  if (selectedWord.value) {
    speak(selectedWord.value.word)
  }
}

function speakExample() {
  const ex = currentExample.value
  if (ex) {
    const fullText = ex.text.map(segment => segment.text).join('')
    speak(fullText)
  }
}

// ─── Polling ───
function startPolling() {
  if (isPolling.value) return
  isPolling.value = true
  generating.value = true

  const poll = () => {
    pollTimer.value = setTimeout(async () => {
      try {
        const response = await api.post('/examples/explore', {
          actions: ['next'],
          limit: BATCH_SIZE
        })

        if (response.data.status === 'generating') {
          poll()
          return
        }

        if (response.data.status === 'no_words') {
          isPolling.value = false
          generating.value = false
          noWords.value = true
          return
        }

        isPolling.value = false
        generating.value = false
        loadExamples(response.data)
      } catch (e: any) {
        isPolling.value = false
        generating.value = false
        error.value = e.response?.data?.message || e.message || 'Failed to load examples'
      }
    }, POLL_INTERVAL)
  }
  poll()
}

function stopPolling() {
  if (pollTimer.value) {
    clearTimeout(pollTimer.value)
    pollTimer.value = null
  }
  isPolling.value = false
}

function loadExamples(data: any) {
  const rawExamples = data.examples || []
  const newExamples: ExampleItem[] = rawExamples.map((item: any) => ({
    queue_item_id: item.queue_item_id,
    example_id: item.example_id,
    text: item.text || [],
    extracted_words: item.extracted_words || [],
    is_favorite: item.is_favorite || false,
    is_marked: item.is_marked || false
  }))

  if (newExamples.length > 0 && newExamples[0]) {
    examples.value = newExamples
    currentIndex.value = 0
  }
}

async function fetchExamples() {
  if (generating.value && !isPolling.value) return
  generating.value = true
  noWords.value = false
  error.value = null

  try {
    const response = await api.post('/examples/explore', {
      actions: ['next'],
      limit: BATCH_SIZE
    })

    const data = response.data

    if (data.status === 'generating') {
      startPolling()
      return
    }

    if (data.status === 'no_words') {
      generating.value = false
      noWords.value = true
      return
    }

    generating.value = false
    loadExamples(data)
  } catch (e: any) {
    generating.value = false
    error.value = e.response?.data?.message || e.message || 'Failed to generate examples'
  }
}

async function fetchWordDetail(wordId: number) {
  try {
    const response = await api.get(`/words/words/${wordId}`)
    const data = response.data

    selectedWord.value = {
      id: data.id,
      word: data.main,
      definition: data.meaning,
      level: data.level,
      context: data.context || data.type || 'General',
      frequency: data.frequency,
      examples: data.examples || [],
      synonyms: data.synonyms || [],
      is_favorite: data.is_favorite || false
    }
  } catch (e) {
    alert('Could not load word detail')
  }
}

async function toggleExampleFav() {
  const ex = currentExample.value
  if (!ex) return

  try {
    const response = await api.patch(`/examples/${ex.example_id}/toggle-favorite`)

    if (response.data && response.data.is_favorite !== undefined) {
      ex.is_favorite = response.data.is_favorite
    }
  } catch (e) {
    alert('Failed to toggle favorite')
  }
}

// ─── Methods ───
function handleWordClick(word: TargetWord) {
  fetchWordDetail(word.id)
  if (window.innerWidth <= 768) {
    isMobileDetailOpen.value = true
  }
}

function closeMobileDetail() {
  isMobileDetailOpen.value = false
  selectedWord.value = null
}

async function handleToggleKnown() {
  if (!selectedWord.value) return

  try {
    await api.patch(`/words/words/${selectedWord.value.id}/learned`)
    closeMobileDetail()
    fetchExamples()
  } catch (e: any) {
    alert('Failed to mark word as learned')
  }
}

async function handleToggleFavorite() {
  if (!selectedWord.value) return

  try {
    await api.patch(`words/words/${selectedWord.value.id}/favorite`)
    if (selectedWord.value) {
      selectedWord.value.is_favorite = !selectedWord.value.is_favorite
    }
  } catch (e: any) {
    alert('Failed to toggle favorite')
  }
}

async function refreshExample() {
  const currentEx = currentExample.value
  if (!currentEx) return

  if (canGoNext.value) {
    resolveOnly(currentEx.queue_item_id)
    currentIndex.value++
    selectedWord.value = null
    isMobileDetailOpen.value = false
    return
  }

  await resolveAndFetchNext(currentEx.queue_item_id)
  selectedWord.value = null
  isMobileDetailOpen.value = false
}

function prevExample() {
  if (canGoPrev.value) {
    currentIndex.value--
    selectedWord.value = null
    isMobileDetailOpen.value = false
  }
}

async function nextExample() {
  if (canGoNext.value) {
    const currentEx = currentExample.value
    if (currentEx) {
      resolveOnly(currentEx.queue_item_id)
    }

    currentIndex.value++
    selectedWord.value = null
    isMobileDetailOpen.value = false
  } else {
    await refreshExample()
  }
}

function showToast() {
  showCopiedToast.value = true
  setTimeout(() => {
    showCopiedToast.value = false
  }, 2000)
}

function copyExample() {
  const ex = currentExample.value
  if (!ex) return
  const fullText = ex.text.map(segment => segment.text).join('')

  const isMobile = window.innerWidth <= 768

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(fullText)
      .then(() => {
        if (!isMobile) {
          showToast()
        }
      })
      .catch(() => {
        copyFallback(fullText)
      })
  } else {
    copyFallback(fullText)
  }
}

function copyFallback(text: string) {
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)

  try {
    textarea.select()
    const successful = document.execCommand('copy')
    if (successful) {
      showToast()
    } else {
      alert('Failed to copy')
    }
  } catch (e) {
    alert('Failed to copy')
  } finally {
    document.body.removeChild(textarea)
  }
}

function handleFavoritesWordClick(word: TargetWord) {
  handleWordClick(word)
  showFavoritesModal.value = false
}

onMounted(() => {
  fetchExamples()
  window.speechSynthesis?.getVoices()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <!-- Favorites View -->
  <FavoritesView
    :modelValue="showFavoritesModal"
    @update:modelValue="v => showFavoritesModal = v"
    @word-click="handleFavoritesWordClick"
  />

  <!-- Main Examples View -->
  <div v-if="!showFavoritesModal" class="examples-view" :class="{ 'panel-open': selectedWord && !isMobileDetailOpen }">
    <!-- Loading / Generating State -->
    <LoadingCard v-if="generating && examples.length === 0" message="Generating..." />

    <!-- No Words State -->
    <div v-else-if="noWords" class="empty-state">
      <p>No more words to review</p>
      <button class="retry-btn" @click="fetchExamples">Try Again</button>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <button class="retry-btn" @click="fetchExamples">Retry</button>
    </div>

    <!-- Empty State -->
    <div v-else-if="!currentExample" class="empty-state">
      <p>No examples available</p>
      <button class="retry-btn" @click="fetchExamples">Generate</button>
    </div>

    <!-- Center: Example Sentence -->
    <div v-else class="sentence-area" :class="{ 'panel-open': selectedWord && !isMobileDetailOpen }">
      <!-- Top Bar -->
      <div class="sentence-top-bar">
        <button class="top-bar-btn favorites-btn" title="Favorite examples" style="border:0;" @click="showFavoritesModal = true">
          <Icon icon="ph:list-heart-thin" width="32" />
        </button>
        <button class="top-bar-btn add-words-btn" title="Add words" style="border:0;" @click="showExtractedWordsModal = true">
          <Icon icon="solar:add-linear" width="24" />
        </button>
      </div>

      <div class="sentence-wrapper">
        <p class="sentence-text">
          <template v-for="(segment, idx) in textSegments" :key="idx">
            <span v-if="segment.is_highlighted && segment.target_word" class="word-highlight"
              @click="handleWordClick(segment.target_word)">
              {{ segment.text }}
            </span>
            <span v-else>{{ segment.text }}</span>
          </template>
        </p>
        <button class="sentence-speak-btn" @click="speakExample" title="Play sentence">
          <Icon icon="solar:volume-loud-linear" width="18" />
        </button>
      </div>

      <!-- Progress indicator -->
      <div class="progress-bar">
        <div v-for="(_, i) in examples" :key="i" class="progress-dot"
          :class="{ active: i === currentIndex, passed: i < currentIndex }" />
      </div>

      <div class="action-buttons">
        <button class="action-btn" @click="toggleExampleFav" title="Favorite" :class="{ favorited: currentExample?.is_favorite }">
          <Icon v-if="currentExample?.is_favorite" icon="solar:heart-bold" width="22" />
          <Icon v-else icon="solar:heart-linear" width="22" />
        </button>
        <button class="action-btn" @click="prevExample" :disabled="!canGoPrev" title="Previous">
          <Icon icon="solar:arrow-left-linear" width="22" />
        </button>
        <button class="action-btn" @click="refreshExample" :disabled="generating" title="Next / New">
          <Icon v-if="generating" icon="solar:refresh-circle-linear" width="22" class="spinning" />
          <Icon v-else icon="solar:arrow-right-linear" width="22" />
        </button>
        <button class="action-btn" @click="copyExample" title="Copy">
          <Icon icon="solar:copy-linear" width="22" />
        </button>
      </div>
    </div>
  </div>

  <!-- Extracted Words Modal -->
  <ExtractedWordsModal
    :modelValue="showExtractedWordsModal"
    :words="currentExample?.extracted_words || []"
    @update:modelValue="v => showExtractedWordsModal = v"
  />

  <!-- Word Detail Panel (Desktop) -->
  <WordDetailPanel
    :word="selectedWord"
    @close="selectedWord = null"
    @speak="speakWord"
    @toggle-favorite="handleToggleFavorite"
    @toggle-known="handleToggleKnown"
  />

  <!-- Mobile Word Detail -->
  <MobileWordDetail
    :modelValue="isMobileDetailOpen"
    :word="selectedWord"
    @update:modelValue="v => isMobileDetailOpen = v"
    @speak-word="speakWord"
    @speak="speak"
    @toggle-favorite="handleToggleFavorite"
    @toggle-known="handleToggleKnown"
  />

  <!-- Copy Toast Notification -->
  <transition name="fade">
    <div v-if="showCopiedToast" class="copy-toast">
      Copied
    </div>
  </transition>
</template>

<style scoped>
.examples-view {
  display: flex;
  min-height: 100%;
  position: relative;
}

.examples-view.panel-open {
  margin-right: 380px;
}

/* ─── Center Sentence Area ─── */
.sentence-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  position: relative;
}

.sentence-top-bar {
  position: absolute;
  top: 24px;
  left: 24px;
  right: 24px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  z-index: 10;
}

.top-bar-btn {
  width: auto;
  height: auto;
  border: none;
  background: transparent;
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  padding: 10px;
}

.top-bar-btn:hover {
  color: #e2e0e8;
}

.sentence-wrapper {
  max-width: 420px;
  text-align: center;
  margin-bottom: 48px;
  position: relative;
}

.sentence-text {
  font-size: 25px;
  line-height: 1.5;
  font-weight: 400;
  color: #b8b5c8;
}

.word-highlight {
  color: #c4b5fd;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.2s ease;
}

.word-highlight:hover {
  color: #a78bfa;
  text-decoration: underline;
  text-decoration-color: rgba(167, 139, 250, 0.4);
  text-underline-offset: 4px;
}

.sentence-speak-btn {
  position: absolute;
  right: -48px;
  top: 50%;
  transform: translateY(-50%);
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1.5px solid rgba(255, 255, 255, 0.15);
  background: transparent;
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.sentence-speak-btn:hover {
  border-color: rgba(255, 255, 255, 0.3);
  color: #e2e0e8;
  background: rgba(255, 255, 255, 0.04);
}

/* ─── Action Buttons ─── */
.action-buttons {
  display: flex;
  gap: 32px;
  align-items: center;
}

.action-btn {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: 1.5px solid rgba(255, 255, 255, 0.15);
  background: transparent;
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.action-btn:hover {
  border-color: rgba(255, 255, 255, 0.3);
  color: #e2e0e8;
  background: rgba(255, 255, 255, 0.04);
}

.action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.action-btn:disabled:hover {
  border-color: rgba(255, 255, 255, 0.15);
  background: transparent;
  color: #9c99ab;
}

.action-btn.favorited {
  color: #f472b6;
}

/* ─── Progress Bar ─── */
.progress-bar {
  display: flex;
  gap: 6px;
  margin-bottom: 24px;
}

.progress-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  transition: all 0.3s ease;
}

.progress-dot.active {
  background: #7c3aed;
  transform: scale(1.2);
}

.progress-dot.passed {
  background: rgba(124, 58, 237, 0.4);
}

/* ─── States ─── */
.loading-state,
.error-state,
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  gap: 16px;
  min-height: 50vh;
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

.spinning {
  animation: spin 0.8s linear infinite;
}

.loading-state p,
.empty-state p {
  color: #9c99ab;
  font-size: 14px;
  margin: 0;
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

/* ─── Copy Toast ─── */
.copy-toast {
  position: fixed;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%);
  background: #36324a;
  color: #4ade80;
  padding: 12px 24px;
  border-radius: 8px;
  border: 1px solid rgba(74, 222, 128, 0.3);
  font-size: 14px;
  font-weight: 600;
  z-index: 3000;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* ─── Responsive ─── */
@media (max-width: 768px) {
  .examples-view {
    flex-direction: column;
  }

  .examples-view.panel-open {
    margin-right: 0;
  }

  .sentence-area {
    padding: 24px 20px;
    padding-top: 80px;
    min-height: 50vh;
  }

  .sentence-text {
    font-size: 22px;
  }

  .sentence-speak-btn {
    position: static;
    transform: none;
    margin-top: 16px;
  }

  .action-buttons {
    gap: 24px;
  }
}
</style>
