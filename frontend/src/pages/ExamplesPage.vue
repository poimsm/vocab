<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import api from '@/utils/api'
import { wordApi } from '@/services/wordApi'
import { useExamplesStore } from '@/stores/examples'
import LoadingCard from '@/components/LoadingCard.vue'
import FavoritesView from '@/components/FavoritesView.vue'
import WordDetailPanel from '@/components/WordDetailPanel.vue'
import MobileWordDetail from '@/components/MobileWordDetail.vue'
import ExtractedWordsModal from '@/components/ExtractedWordsModal.vue'

const router = useRouter()
const examplesStore = useExamplesStore()

interface TargetWord {
  id: number
  main: string
  type: string
  meaning?: string
  level?: string | number
  is_boosted: boolean
  batch_id?: number
  is_favorite?: boolean
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

// ─── Local State ───
const selectedWord = ref<WordDetail | null>(null)
const isMobileDetailOpen = ref(false)
const showExtractedWordsModal = ref(false)
const showFavoritesModal = ref(false)
const showCopiedToast = ref(false)
const comingFromFavorites = ref(false)
const pollTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const isComponentMounted = ref(false)  // Track if component is mounted

const BATCH_SIZE = 4
const POLL_INTERVAL = 3000
const SPEECH_RATES = [0.9, 0.7]
const currentSpeechRateIndex = ref(0)
let pollAbortController: AbortController | null = null
let pollActive = ref(false)  // Track if polling should continue
let consecutiveGeneratingCount = ref(0)  // Track consecutive "generating" responses
const MAX_CONSECUTIVE_GENERATING = 6  // Stop polling after 6 consecutive generating responses

// ─── Polling ───
function startPolling() {
  console.log('[startPolling] Starting poll loop, current state - pollActive:', pollActive.value, 'hasController:', !!pollAbortController)

  // Clean up any previous polling state
  if (pollAbortController) {
    console.log('[startPolling] Cleaning up previous AbortController')
    pollAbortController.abort()
  }

  // Reset consecutive generating counter
  consecutiveGeneratingCount.value = 0

  pollActive.value = true
  pollAbortController = new AbortController()

  const poll = () => {
    // Stop immediately if polling was disabled
    if (!pollActive.value) {
      console.log('[poll] Polling disabled, stopping')
      return
    }

    console.log('[poll] Scheduling next poll in', POLL_INTERVAL, 'ms')
    pollTimer.value = setTimeout(async () => {
      // Double-check before making request
      if (!pollActive.value) {
        console.log('[poll] Polling disabled before timeout, aborting')
        return
      }

      try {
        console.log('[poll] Making request with buffer:', examplesStore.bufferIds)
        const response = await api.post('/examples/explore', {
          actions: ['next'],
          limit: BATCH_SIZE,
          buffer_queue_item_ids: examplesStore.bufferIds,
          buffer_position: examplesStore.currentIndex,
        }, {
          signal: pollAbortController?.signal
        })

        // Check again after response arrives
        if (!pollActive.value) {
          console.log('[poll] Polling disabled after response, ignoring')
          return
        }

        console.log('[poll] Response status:', response.data.status)

        if (response.data.status === 'generating') {
          consecutiveGeneratingCount.value++
          console.log(`[poll] Still generating (${consecutiveGeneratingCount.value}/${MAX_CONSECUTIVE_GENERATING}), scheduling next poll`)

          // Safety check: stop polling after too many consecutive "generating" responses
          if (consecutiveGeneratingCount.value >= MAX_CONSECUTIVE_GENERATING) {
            console.error(`[poll] Reached maximum consecutive generating responses (${MAX_CONSECUTIVE_GENERATING}), stopping polling`)
            examplesStore.setIsPolling(false)
            examplesStore.setGenerating(false)
            examplesStore.setError('Content generation timeout - please try again')
            pollActive.value = false
            return
          }

          // Only schedule next poll if still active
          if (pollActive.value) {
            poll()
          }
          return
        }

        // Reset counter when we get a non-generating response
        consecutiveGeneratingCount.value = 0

        if (response.data.status === 'no_words') {
          console.log('[poll] No words available')
          examplesStore.setIsPolling(false)
          examplesStore.setGenerating(false)
          examplesStore.setNoWords(true)
          pollActive.value = false
          return
        }

        console.log('[poll] Content ready, loading examples')
        examplesStore.setIsPolling(false)
        examplesStore.setGenerating(false)
        examplesStore.loadExamples(
          response.data.examples || [],
          response.data.buffer_queue_item_ids || [],
          response.data.buffer_position ?? 0
        )
        pollActive.value = false
      } catch (e: any) {
        // Ignore abort errors (expected when component unmounts)
        if (e.name === 'AbortError') {
          console.log('[poll] Request aborted')
          pollActive.value = false
          return
        }
        console.error('[poll] Error:', e)
        examplesStore.setIsPolling(false)
        examplesStore.setGenerating(false)
        examplesStore.setError(e.response?.data?.message || e.message || 'Failed to load examples')
        pollActive.value = false
      }
    }, POLL_INTERVAL)
  }
  poll()
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
  utterance.rate = SPEECH_RATES[currentSpeechRateIndex.value]!
  utterance.pitch = 1

  const voices = window.speechSynthesis.getVoices()
  const enVoice = voices.find(v => v.lang.startsWith('en'))
  if (enVoice) {
    utterance.voice = enVoice
  }

  window.speechSynthesis.speak(utterance)

  // Cambiar a la siguiente velocidad para la próxima vez
  currentSpeechRateIndex.value = (currentSpeechRateIndex.value + 1) % SPEECH_RATES.length
}

function speakWord() {
  if (selectedWord.value) {
    speak(selectedWord.value.word)
  }
}

function speakExample() {
  const ex = examplesStore.currentExample
  if (ex) {
    const fullText = ex.text.map(segment => segment.text).join('')
    speak(fullText)
  }
}

function stopPolling() {
  console.log('[stopPolling] Stopping poll loop IMMEDIATELY')
  // Disable polling flag FIRST - this will stop all poll() calls
  pollActive.value = false

  // Cancel any in-flight requests
  if (pollAbortController) {
    console.log('[stopPolling] Aborting HTTP requests')
    pollAbortController.abort()
    pollAbortController = null
  }

  // Clear pending timeout
  if (pollTimer.value) {
    console.log('[stopPolling] Clearing pending timeout:', pollTimer.value)
    clearTimeout(pollTimer.value)
    pollTimer.value = null
  }

  // Reset consecutive generating counter
  consecutiveGeneratingCount.value = 0

  examplesStore.setIsPolling(false)
  console.log('[stopPolling] Poll loop stopped')
}

async function fetchExamples() {
  console.log('[fetchExamples] Called. generating:', examplesStore.generating, 'isPolling:', examplesStore.isPolling)

  if (examplesStore.generating && !examplesStore.isPolling) {
    console.warn('[fetchExamples] Already generating, returning')
    return
  }

  try {
    console.log('[fetchExamples] Awaiting store.fetchExamples...')
    await examplesStore.fetchExamples(BATCH_SIZE)

    console.log('[fetchExamples] Store returned. isPolling:', examplesStore.isPolling)

    // Start polling if content is generating
    if (examplesStore.isPolling || examplesStore.generating) {
      console.log('[fetchExamples] Content generating, starting polling')
      startPolling()
    }
  } catch (e: any) {
    console.error('[fetchExamples] Error:', e)
    examplesStore.setGenerating(false)
    examplesStore.setError(e.response?.data?.message || e.message || 'Failed to generate examples')
  }
}

async function fetchWordDetail(wordId: number) {
  console.log('[fetchWordDetail] Fetching details for word id:', wordId)
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
    console.log('[fetchWordDetail] Word detail loaded:', selectedWord.value.word)
  } catch (e) {
    console.error('[fetchWordDetail] Error:', e)
    alert('Could not load word detail')
  }
}

async function toggleExampleFav() {
  const ex = examplesStore.currentExample
  if (!ex) return

  try {
    const response = await api.patch(`/examples/${ex.example_id}/toggle-favorite`)

    if (response.data && response.data.is_favorite !== undefined) {
      examplesStore.updateExampleFavorite(response.data.is_favorite)
    }
  } catch (e) {
    alert('Failed to toggle favorite')
  }
}

// ─── Methods ───
function handleWordClick(word: TargetWord) {
  console.log('[handleWordClick] Clicked word:', word.main, 'id:', word.id, 'isMobile:', window.innerWidth <= 768)
  if (window.innerWidth <= 768) {
    router.push(`/words/${word.id}`)
  } else {
    fetchWordDetail(word.id)
  }
}

function closeWordDetail() {
  console.log('[closeWordDetail] Closing word detail panel')
  selectedWord.value = null
  if (comingFromFavorites.value) {
    showFavoritesModal.value = true
    comingFromFavorites.value = false
  }
}

function closeMobileDetail() {
  console.log('[closeMobileDetail] Closing mobile detail')
  isMobileDetailOpen.value = false
  selectedWord.value = null
  if (comingFromFavorites.value) {
    showFavoritesModal.value = true
    comingFromFavorites.value = false
  }
}

async function handleToggleKnown() {
  if (!selectedWord.value) return

  console.log('[handleToggleKnown] Toggling learned status for word:', selectedWord.value.id)

  try {
    await wordApi.toggleLearned(selectedWord.value.id, true)
    console.log('[handleToggleKnown] Word marked as learned, syncing buffer and fetching examples...')
    closeMobileDetail()
    // Sync buffer (remove learned words) and fetch examples in one atomic call
    await examplesStore.syncAndFetchNext(BATCH_SIZE)

    // Start polling if content is generating
    if (examplesStore.isPolling || examplesStore.generating) {
      console.log('[handleToggleKnown] Content generating, starting polling')
      startPolling()
    }
  } catch (e: any) {
    console.error('[handleToggleKnown] Error:', e)
    alert('Failed to mark word as learned')
  }
}

async function handleToggleFavorite() {
  if (!selectedWord.value) return

  console.log('[handleToggleFavorite] Toggling favorite for word:', selectedWord.value.word)

  try {
    await api.patch(`words/words/${selectedWord.value.id}/favorite`)
    if (selectedWord.value) {
      selectedWord.value.is_favorite = !selectedWord.value.is_favorite
      console.log('[handleToggleFavorite] Updated, is_favorite:', selectedWord.value.is_favorite)
    }
  } catch (e: any) {
    console.error('[handleToggleFavorite] Error:', e)
    alert('Failed to toggle favorite')
  }
}

async function refreshExample() {
  const currentEx = examplesStore.currentExample
  if (!currentEx) return

  console.log('[refreshExample] Current index:', examplesStore.currentIndex, 'total:', examplesStore.examples.length)

  const isLastItem = examplesStore.currentIndex >= examplesStore.examples.length - 1

  if (examplesStore.canGoNext) {
    console.log('[refreshExample] Can go next, navigating with sync+resolve')
    examplesStore.nextExample()  // Update position FIRST
    await examplesStore.navigateExample(currentEx.queue_item_id, false, BATCH_SIZE)  // Unified navigation
    selectedWord.value = null
    isMobileDetailOpen.value = false
    currentSpeechRateIndex.value = 0
    return
  }

  // At end of buffer, use navigateExample with isLastItem=true (includes next)
  console.log('[refreshExample] At end of buffer, navigating with sync+resolve+next')
  await examplesStore.navigateExample(currentEx.queue_item_id, true, BATCH_SIZE)

  // Always start polling if content is generating
  if (examplesStore.isPolling || examplesStore.generating) {
    console.log('[refreshExample] Content generating/polling, starting poll loop')
    startPolling()
  }

  selectedWord.value = null
  isMobileDetailOpen.value = false
  currentSpeechRateIndex.value = 0
}

async function prevExample() {
  console.log('[prevExample] Attempting previous, canGoPrev:', examplesStore.canGoPrev, 'index:', examplesStore.currentIndex)
  if (examplesStore.canGoPrev) {
    examplesStore.prevExample()
    console.log('[prevExample] Moved to index:', examplesStore.currentIndex)

    await examplesStore.syncPosition()  // Sync position with backend

    selectedWord.value = null
    isMobileDetailOpen.value = false
    currentSpeechRateIndex.value = 0
  }
}

async function nextExample() {
  console.log('[nextExample] Attempting next, canGoNext:', examplesStore.canGoNext, 'index:', examplesStore.currentIndex)
  if (examplesStore.canGoNext) {
    const currentEx = examplesStore.currentExample

    examplesStore.nextExample()  // Update position FIRST
    console.log('[nextExample] Moved to index:', examplesStore.currentIndex)

    if (currentEx) {
      await examplesStore.navigateExample(currentEx.queue_item_id, false, BATCH_SIZE)  // Unified navigation with sync+resolve
    }

    selectedWord.value = null
    isMobileDetailOpen.value = false
    currentSpeechRateIndex.value = 0
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
  const ex = examplesStore.currentExample
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
  if (window.innerWidth <= 768) {
    showFavoritesModal.value = false
    router.push(`/words/${word.id}`)
  } else {
    comingFromFavorites.value = true
    handleWordClick(word)
  }
}

function openFavoritesModal() {
  if (window.innerWidth <= 768) {
    router.push('/examples/favorites')
  } else {
    showFavoritesModal.value = true
  }
}

onMounted(async () => {
  console.log('[ExamplesPage] Mounted')
  isComponentMounted.value = true

  try {
    // Restaurar sesión guardada y cargar ejemplos en UNA sola llamada atómica
    // Backend intenta restaurar buffer de sesión guardada si no se proporciona
    // Acción: "resume" (chequea visitados + carga nuevo buffer si todos fueron visitados + obtiene ejemplos)
    console.log('[ExamplesPage] Resuming session and loading examples via explore endpoint')

    const exploreResponse = await api.post('/examples/explore', {
      actions: ['resume'],
      limit: BATCH_SIZE,
      buffer_queue_item_ids: [],  // Empty - backend will restore from saved session
      buffer_position: 0,
    })

    // Check if component is still mounted before processing response
    if (!isComponentMounted.value) {
      console.log('[ExamplesPage] Component unmounted, ignoring response')
      return
    }

    const { examples, buffer_queue_item_ids: bufferIds, buffer_position: bufferPos, status: exploreStatus } = exploreResponse.data

    // Actualizar store con buffer restaurado
    examplesStore.setBufferData(bufferIds, bufferPos)

    // Procesar respuesta según estado
    if (examples.length > 0) {
      examplesStore.loadExamples(examples, bufferIds, bufferPos)
      // Establecer currentIndex DESPUÉS de loadExamples para que no sea sobrescrito
      examplesStore.setCurrentIndex(bufferPos)
    } else if (exploreStatus === 'generating') {
      examplesStore.setGenerating(true)
      startPolling()
    } else if (exploreStatus === 'no_words') {
      examplesStore.setNoWords(true)
    }
  } catch (e) {
    console.error('[ExamplesPage] Error:', e)
    // Only reset if component is still mounted
    if (isComponentMounted.value) {
      examplesStore.resetBuffer()
      await fetchExamples()
    }
  }

  window.speechSynthesis?.getVoices()
})

onUnmounted(() => {
  console.log('[ExamplesPage] Unmounting - setting isComponentMounted to false')
  isComponentMounted.value = false
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
  <div v-if="!showFavoritesModal && !comingFromFavorites" class="examples-view" :class="{ 'panel-open': selectedWord && !isMobileDetailOpen }">
    <!-- Loading / Generating State -->
    <LoadingCard v-if="examplesStore.generating && examplesStore.examples.length === 0" message="Generating..." />

    <!-- No Words State -->
    <div v-else-if="examplesStore.noWords" class="empty-state">
      <p>No more words to review</p>
      <button class="retry-btn" @click="fetchExamples">Try Again</button>
    </div>

    <!-- Error State -->
    <div v-else-if="examplesStore.error" class="error-state">
      <p>{{ examplesStore.error }}</p>
      <button class="retry-btn" @click="fetchExamples">Retry</button>
    </div>

    <!-- Empty State -->
    <div v-else-if="!examplesStore.currentExample" class="empty-state">
      <p>No examples available</p>
      <button class="retry-btn" @click="fetchExamples">Generate</button>
    </div>

    <!-- Center: Example Sentence -->
    <div v-else class="sentence-area" :class="{ 'panel-open': selectedWord && !isMobileDetailOpen }">
      <!-- Top Bar -->
      <div class="sentence-top-bar">
        <button class="top-bar-btn favorites-btn" title="Favorite examples" style="border:0;" @click="openFavoritesModal">
          <Icon icon="ph:list-heart-thin" width="32" />
        </button>
        <button class="top-bar-btn add-words-btn" title="Add words" style="border:0;" @click="showExtractedWordsModal = true">
          <Icon icon="solar:add-linear" width="24" />
        </button>
      </div>

      <div class="sentence-wrapper">
        <p class="sentence-text">
          <template v-for="(segment, idx) in examplesStore.textSegments" :key="idx">
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
        <div v-for="(_, i) in examplesStore.examples" :key="i" class="progress-dot"
          :class="{ active: i === examplesStore.currentIndex, passed: i < examplesStore.currentIndex }" />
      </div>

      <div class="action-buttons">
        <button class="action-btn" @click="toggleExampleFav" title="Favorite" :class="{ favorited: examplesStore.currentExample?.is_favorite }">
          <Icon v-if="examplesStore.currentExample?.is_favorite" icon="solar:heart-bold" width="22" />
          <Icon v-else icon="solar:heart-linear" width="22" />
        </button>
        <button class="action-btn" @click="prevExample" :disabled="!examplesStore.canGoPrev" title="Previous">
          <Icon icon="solar:arrow-left-linear" width="22" />
        </button>
        <button class="action-btn" @click="refreshExample" :disabled="examplesStore.generating" title="Next / New">
          <Icon v-if="examplesStore.generating" icon="solar:refresh-circle-linear" width="22" class="spinning" />
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
    :words="examplesStore.currentExample?.extracted_words || []"
    @update:modelValue="v => showExtractedWordsModal = v"
  />

  <!-- Word Detail Panel (Desktop) -->
  <WordDetailPanel
    :word="selectedWord"
    @close="closeWordDetail"
    @speak="speakWord"
    @toggle-favorite="handleToggleFavorite"
    @toggle-known="handleToggleKnown"
  />

  <!-- Mobile Word Detail -->
  <MobileWordDetail
    :modelValue="isMobileDetailOpen"
    :word="selectedWord"
    @update:modelValue="v => { if (!v) closeMobileDetail() }"
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
    font-size: 25px;
  }

  .sentence-speak-btn {
    position: static;
    transform: none;
    margin: 16px auto 0;
  }

  .action-buttons {
    gap: 24px;
  }
}
</style>
