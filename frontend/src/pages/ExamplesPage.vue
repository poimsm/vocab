<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import api from '@/utils/api'
import LoadingCard from '@/components/LoadingCard.vue'

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
const loading = ref(false)
const error = ref<string | null>(null)
const generating = ref(false)
const noWords = ref(false)
const isPolling = ref(false)
const pollTimer = ref<ReturnType<typeof setTimeout> | null>(null)

const selectedWord = ref<WordDetail | null>(null)
const isMobileDetailOpen = ref(false)
const showExtractedWordsModal = ref(false)
const addedWords = ref<Set<string>>(new Set()) // Track palabras ya agregadas
const addingWord = ref<string | null>(null) // Track palabra en proceso

const showFavoritesModal = ref(false)
const favoriteExamples = ref<any[]>([])
const favoritesLoading = ref(false)
const favoritesPage = ref(1)
const favoritesTotalPages = ref(1)

const BATCH_SIZE = 4
const POLL_INTERVAL = 3000
const FAVORITES_LIMIT = 10

// ─── Computed ───
const currentExample = computed(() => {
  if (examples.value.length === 0) return null
  return examples.value[currentIndex.value]
})

const textSegments = computed(() => {
  const ex = currentExample.value
  if (!ex) return []
  // Los segmentos ya vienen precalculados del backend
  return ex.text
})

const frequencySegments = computed(() => {
  if (!selectedWord.value) return []
  const freq = selectedWord.value.frequency
  return [
    { label: 'RARE', active: freq === 'rare', color: '#4ade80' },
    { label: 'UNCOMMON', active: freq === 'uncommon' || freq === 'common', color: '#60a5fa' },
    { label: 'COMMON', active: freq === 'common', color: '#a78bfa' }
  ]
})

const canGoNext = computed(() => {
  return currentIndex.value < examples.value.length - 1
})

const canGoPrev = computed(() => {
  return currentIndex.value > 0
})

// ─── Side Effects ───
function fireAndForgetResolve(queueItemId: number) {
  api.patch(`/examples/${queueItemId}/resolve`)
    .catch(() => { }) // Silencioso, no nos importa si falla
}

// ─── Text-to-Speech ───
function speak(text: string) {
  if (!window.speechSynthesis) {
    console.warn('Speech synthesis not supported')
    return
  }
  // Cancel any ongoing speech
  window.speechSynthesis.cancel()

  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'en-US'
  utterance.rate = 0.9
  utterance.pitch = 1

  // Try to find an English voice
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
    // Construir el texto completo desde los segmentos
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
        const response = await api.get('/examples/explore', {
          params: { limit: BATCH_SIZE }
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
    is_favorite: item.is_favorite || false
  }))

  if (newExamples.length > 0 && newExamples[0]) {
    examples.value = newExamples
    currentIndex.value = 0
    addedWords.value.clear() // Limpiar palabras agregadas al cargar nuevo batch
    fireAndForgetResolve(newExamples[0].queue_item_id)
  }
}

async function fetchExamples() {
  if (generating.value && !isPolling.value) return
  generating.value = true
  noWords.value = false
  error.value = null

  try {
    const response = await api.get('/examples/explore', {
      params: {
        limit: BATCH_SIZE
      }
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

function openExtractedWordsModal() {
  const ex = currentExample.value
  if (!ex || !ex.extracted_words || ex.extracted_words.length === 0) {
    alert('No words to add from this example')
    return
  }
  showExtractedWordsModal.value = true
}

function closeExtractedWordsModal() {
  showExtractedWordsModal.value = false
}

async function addWordToList(word: string) {
  if (addedWords.value.has(word)) {
    return // Ya fue agregada
  }

  addingWord.value = word

  try {
    const response = await api.post('/words/single', {
      text: word
    })

    if (response.status === 202 || response.data.status === 'queued') {
      addedWords.value.add(word)
    } else {
      alert('Failed to add word')
    }
  } catch (e: any) {
    alert('Failed to add word: ' + (e.response?.data?.message || e.message))
  } finally {
    addingWord.value = null
  }
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

async function openFavoritesModal() {
  showFavoritesModal.value = true
  favoritesPage.value = 1
  await fetchFavorites()
}

function closeFavoritesModal() {
  showFavoritesModal.value = false
  favoriteExamples.value = []
}

async function fetchFavorites() {
  if (favoritesLoading.value) return

  favoritesLoading.value = true

  try {
    const response = await api.get('/examples/favorites', {
      params: {
        page: favoritesPage.value,
        limit: FAVORITES_LIMIT
      }
    })

    if (response.data && response.data.status === 'ok') {
      // Si es la primera página, reemplazar. Si no, agregar a la lista
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

function prevFavoritesPage() {
  if (favoritesPage.value > 1) {
    favoritesPage.value--
    fetchFavorites()
  }
}

function handleFavoritesScroll(event: Event) {
  const target = event.target as HTMLElement
  const scrollTop = target.scrollTop
  const clientHeight = target.clientHeight
  const scrollHeight = target.scrollHeight

  // Si está a menos de 200px del final, cargar más
  if (scrollHeight - (scrollTop + clientHeight) < 200) {
    if (favoritesPage.value < favoritesTotalPages.value && !favoritesLoading.value) {
      nextFavoritesPage()
    }
  }
}

async function removeFavorite(exampleId: number) {
  try {
    await api.patch(`/examples/${exampleId}/toggle-favorite`)

    // Remover el ejemplo de la lista
    favoriteExamples.value = favoriteExamples.value.filter(ex => ex.id !== exampleId)
  } catch (e: any) {
    alert('Failed to remove from favorites: ' + (e.response?.data?.message || e.message))
  }
}

function refreshExample() {
  // Side effect: marcar el siguiente ejemplo como visto (si existe)
  const nextExample = examples.value[currentIndex.value + 1]
  if (nextExample) {
    fireAndForgetResolve(nextExample.queue_item_id)
  }

  // Si hay más ejemplos en el batch, avanzar al siguiente
  if (canGoNext.value) {
    currentIndex.value++
    selectedWord.value = null
    isMobileDetailOpen.value = false
    return
  }

  // Si se acabaron, generar 3 nuevos
  fetchExamples()
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

function nextExample() {
  if (canGoNext.value) {
    currentIndex.value++
    selectedWord.value = null
    isMobileDetailOpen.value = false
  } else {
    // Si no hay más, generar nuevos
    refreshExample()
  }
}

function copyExample() {
  const ex = currentExample.value
  if (!ex) return
  const fullText = ex.text.map(segment => segment.text).join('')
  navigator.clipboard.writeText(fullText).then(() => {
    alert('Copied to clipboard!')
  }).catch(() => {
    alert('Failed to copy')
  })
}

onMounted(() => {
  fetchExamples()
  // Preload voices for speech synthesis
  window.speechSynthesis?.getVoices()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <!-- Favorites View (Fullscreen) -->
  <div v-if="showFavoritesModal" class="favorites-view">
    <div class="favorites-header">
      <h2>Favorite Examples</h2>
      <button class="close-favorites-btn" @click="closeFavoritesModal" title="Close">
        <Icon icon="solar:close-circle-linear" width="28" />
      </button>
    </div>

    <div class="favorites-content" @scroll="handleFavoritesScroll">
      <div v-if="favoritesLoading && favoriteExamples.length === 0" class="loading-state">
        <div class="spinner"></div>
        <p>Loading favorites...</p>
      </div>

      <div v-else-if="favoriteExamples.length > 0" class="favorites-items">
        <div v-for="example in favoriteExamples" :key="example.id" class="favorite-card">
          <div class="favorite-card-wrapper">
            <div class="favorite-card-text">
              <template v-for="(segment, idx) in example.text" :key="idx">
                <span v-if="segment.is_highlighted" class="word-highlight">
                  {{ segment.text }}
                </span>
                <span v-else>{{ segment.text }}</span>
              </template>
            </div>
            <button class="remove-favorite-btn" @click="removeFavorite(example.id)" title="Remove from favorites">
              <Icon icon="solar:trash-bin-minimalistic-2-linear" width="20" />
            </button>
          </div>
        </div>
      </div>

      <div v-else class="empty-favorites">
        <p>No favorite examples yet</p>
      </div>

      <div v-if="favoritesLoading && favoriteExamples.length > 0" class="loading-more">
        <div class="spinner-small"></div>
      </div>
    </div>
  </div>

  <!-- Main Examples View -->
  <div v-else class="examples-view">
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
        <button class="top-bar-btn favorites-btn" title="Favorite examples" style="border:0;" @click="openFavoritesModal">
          <Icon icon="ph:list-heart-thin" width="32" />
        </button>
        <button class="top-bar-btn add-words-btn" title="Add words" style="border:0;">
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
        <!-- Play full sentence audio -->
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

      <div class="example-meta">
        <span class="counter">{{ currentIndex + 1 }} / {{ examples.length }}</span>
      </div>
    </div>

    <!-- Right Panel: Word Detail (Desktop) -->
    <transition name="slide-panel">
      <aside v-if="selectedWord && !isMobileDetailOpen" class="word-panel">
        <div class="panel-header">
          <button class="back-btn" @click="selectedWord = null">
            <Icon icon="solar:arrow-left-linear" width="20" />
          </button>
          <div class="panel-header-actions">
            <button class="sound-btn" @click="speakWord" title="Play pronunciation">
              <Icon icon="solar:volume-loud-linear" width="20" />
            </button>
            <button class="heart-btn" @click="handleToggleFavorite" title="Add to favorites">
              <Icon v-if="selectedWord?.is_favorite" icon="solar:heart-bold" width="20" />
              <Icon v-else icon="solar:heart-linear" width="20" />
            </button>
          </div>
        </div>

        <h2 class="panel-word">{{ selectedWord.word }}</h2>
        <p class="panel-definition">{{ selectedWord.definition }}</p>

        <!-- Synonyms Section (Desktop) -->
        <div v-if="selectedWord.synonyms && selectedWord.synonyms.length" class="panel-section">
          <h3 class="section-title">SYNONYMS</h3>
          <div class="synonyms-list">
            <span v-for="syn in selectedWord.synonyms" :key="syn" class="synonym-tag" @click="speak(syn)"
              title="Click to hear">
              {{ syn }}
            </span>
          </div>
        </div>

        <div class="panel-section">
          <h3 class="section-title">EXAMPLES</h3>
          <ul class="examples-list">
            <li v-for="(ex, i) in selectedWord.examples" :key="i">{{ ex }}</li>
          </ul>
        </div>

        <div class="badges-row">
          <div class="badge">
            <span class="badge-label">{{ selectedWord.level }}</span>
            <span class="badge-sublabel">Level</span>
          </div>
          <div class="badge-divider">/</div>
          <div class="badge">
            <span class="badge-label">{{ selectedWord.context }}</span>
            <span class="badge-sublabel">Context</span>
          </div>
        </div>

        <div class="frequency-section">
          <span class="frequency-label">FREQUENCY</span>
          <div class="frequency-bar">
            <div v-for="(seg, i) in frequencySegments" :key="i" class="frequency-segment"
              :class="{ active: seg.active }" :style="{ background: seg.active ? seg.color : '#3d3a52' }">
              <div v-if="seg.active && selectedWord.frequency === 'common' && i === 2" class="frequency-star">
                <Icon icon="solar:star-bold" width="12" />
              </div>
            </div>
          </div>
          <div class="frequency-labels">
            <span>RARE</span>
            <span>UNCOMMON</span>
            <span>COMMON</span>
          </div>
        </div>
      </aside>
    </transition>

    <!-- Extracted Words Modal (Desktop) -->
    <transition name="fade">
      <div v-if="showExtractedWordsModal && !isMobileDetailOpen" class="modal-overlay" @click="closeExtractedWordsModal">
        <div class="modal-content" @click.stop>
          <div class="modal-header">
            <h3>Add words from this example</h3>
            <button class="modal-close-btn" @click="closeExtractedWordsModal">
              <Icon icon="solar:close-circle-linear" width="24" />
            </button>
          </div>

          <div class="modal-body">
            <div v-if="currentExample?.extracted_words && currentExample.extracted_words.length > 0" class="words-grid">
              <button
                v-for="word in currentExample.extracted_words"
                :key="word"
                class="word-chip"
                :class="{ added: addedWords.has(word), loading: addingWord === word }"
                @click="addWordToList(word)"
                :disabled="addedWords.has(word) || addingWord === word"
              >
                <span class="word-text">{{ word }}</span>
                <Icon v-if="!addedWords.has(word) && addingWord !== word" icon="solar:add-circle-linear" width="18" />
                <Icon v-else-if="addedWords.has(word)" icon="solar:check-circle-bold" width="18" class="check-icon" />
                <Icon v-else icon="solar:refresh-circle-linear" width="18" class="spinning" />
              </button>
            </div>
            <div v-else class="empty-words">
              <p>No words to add</p>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- Mobile Detail Overlay -->
    <transition name="slide-up">
      <div v-if="isMobileDetailOpen" class="mobile-detail-overlay">
        <div class="mobile-detail-header">
          <button class="mobile-back-btn" @click="closeMobileDetail">
            <Icon icon="solar:arrow-left-linear" width="24" />
          </button>
          <div class="mobile-header-actions">
            <button class="mobile-sound-btn" @click="speakWord" title="Play pronunciation">
              <Icon icon="solar:volume-loud-linear" width="22" />
            </button>
            <button class="mobile-heart-btn" @click="handleToggleFavorite" title="Add to favorites">
              <Icon v-if="selectedWord?.is_favorite" icon="solar:heart-bold" width="22" />
              <Icon v-else icon="solar:heart-linear" width="22" />
            </button>
          </div>
        </div>

        <div class="mobile-detail-content">
          <div class="mobile-word-header">
            <h2 class="mobile-word">{{ selectedWord?.word }}</h2>
            <!-- <button class="mobile-sound-inline" @click="speakWord" title="Play pronunciation">
              <Icon icon="solar:volume-loud-linear" width="18" />
            </button> -->
          </div>
          <!-- <p class="mobile-meta">{{ selectedWord?.level }} Level · {{ selectedWord?.context }} Context</p> -->

          <div class="mobile-section">
            <!-- <h3 class="mobile-section-title">Definition</h3> -->
            <p class="mobile-definition">{{ selectedWord?.definition }}</p>
          </div>

          <!-- Synonyms Section (Mobile) -->
          <div class="mobile-section" v-if="selectedWord?.synonyms && selectedWord.synonyms.length">
            <h3 class="mobile-section-title">Synonyms</h3>
            <div class="synonyms-tags">
              <span v-for="syn in selectedWord.synonyms" :key="syn" class="synonym-tag" @click="speak(syn)"
                title="Tap to hear">
                {{ syn }}
              </span>
            </div>
          </div>

          <div class="mobile-section">
            <h3 class="mobile-section-title">Examples</h3>
            <ul class="mobile-examples-list">
              <li v-for="(ex, i) in selectedWord?.examples" :key="i">{{ ex }}</li>
            </ul>
          </div>

          <div class="known-toggle">
            <span>Already know this word?</span>
            <label class="toggle-switch">
              <input type="checkbox" @change="handleToggleKnown" />
              <span class="toggle-slider"></span>
            </label>
          </div>
        </div>
      </div>
    </transition>


    <!-- Mobile Extracted Words Action Sheet -->
    <transition name="slide-up">
      <div v-if="showExtractedWordsModal && isMobileDetailOpen" class="mobile-action-sheet">
        <div class="action-sheet-header">
          <h3>Add words from this example</h3>
          <button class="action-sheet-close" @click="closeExtractedWordsModal">
            <Icon icon="solar:close-circle-linear" width="24" />
          </button>
        </div>

        <div class="action-sheet-content">
          <div v-if="currentExample?.extracted_words && currentExample.extracted_words.length > 0" class="action-sheet-words">
            <button
              v-for="word in currentExample.extracted_words"
              :key="word"
              class="action-sheet-word-item"
              :class="{ added: addedWords.has(word), loading: addingWord === word }"
              @click="addWordToList(word)"
              :disabled="addedWords.has(word) || addingWord === word"
            >
              <span class="action-sheet-word-text">{{ word }}</span>
              <Icon v-if="!addedWords.has(word) && addingWord !== word" icon="solar:add-circle-linear" width="22" />
              <Icon v-else-if="addedWords.has(word)" icon="solar:check-circle-bold" width="22" class="check-icon" />
              <Icon v-else icon="solar:refresh-circle-linear" width="22" class="spinning" />
            </button>
          </div>
          <div v-else class="action-sheet-empty">
            <p>No words to add</p>
          </div>
        </div>
      </div>
    </transition>

  </div>
</template>

<style scoped>
.examples-view {
  display: flex;
  min-height: 100%;
  position: relative;
}

/* ─── Center Sentence Area ─── */
.sentence-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  transition: flex 0.3s ease;
  position: relative;
}

/* ─── Top Bar (Static) ─── */
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


.sentence-area.panel-open {
  flex: 0 0 55%;
}

.sentence-wrapper {
  max-width: 420px;
  text-align: center;
  margin-bottom: 48px;
  position: relative;
}

.sentence-text {
  font-size: 28px;
  line-height: 1.5;
  font-weight: 400;
  color: #b8b5c8;
}

@media (max-width: 768px) {
  .sentence-text {
    font-size: 28px !important;
  }
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

/* Sentence speak button */
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

/* ─── Right Panel (Desktop) ─── */
.word-panel {
  width: 380px;
  flex-shrink: 0;
  background: #36324a;
  border-left: 1px solid rgba(255, 255, 255, 0.06);
  padding: 24px;
  overflow-y: auto;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.panel-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.back-btn {
  width: 36px;
  height: 36px;
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

.back-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
}

.heart-btn,
.sound-btn {
  width: 36px;
  height: 36px;
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

.heart-btn:hover,
.sound-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
}

.heart-btn {
  color: #f472b6;
}

.sound-btn {
  color: #a78bfa;
}

.sound-btn:hover {
  color: #c4b5fd;
  background: rgba(167, 139, 250, 0.1);
}

.panel-word {
  font-size: 32px;
  font-weight: 600;
  color: #9c99ab;
  margin-bottom: 16px;
  letter-spacing: -0.5px;
}

@media (max-width: 768px) {
  .panel-word {
    font-size: 36px;
  }
}

.panel-definition {
  font-size: 15px;
  line-height: 1.6;
  color: #b8b5c8;
  margin-bottom: 28px;
}

@media (max-width: 768px) {
  .panel-definition {
    font-size: 18px;
  }
}

.panel-section {
  margin-bottom: 24px;
}

.section-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.5px;
  color: #9c99ab;
  margin-bottom: 12px;
}

@media (max-width: 768px) {
  .section-title {
    font-size: 15px;
  }
}

.examples-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.examples-list li {
  position: relative;
  padding-left: 16px;
  margin-bottom: 10px;
  font-size: 14px;
  line-height: 1.5;
  color: #b8b5c8;
}

@media (max-width: 768px) {
  .examples-list li {
    font-size: 17px;
  }
}

.examples-list li::before {
  content: '•';
  position: absolute;
  left: 0;
  color: #c4b5fd;
  font-weight: 700;
}

/* ─── Synonyms ─── */
.synonyms-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.synonym-tag {
  padding: 6px 14px;
  border-radius: 999px;
  background: rgba(124, 58, 237, 0.12);
  color: #a78bfa;
  font-size: 13px;
  font-weight: 600;
  border: 1px solid rgba(124, 58, 237, 0.2);
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
}

@media (max-width: 768px) {
  .synonym-tag {
    font-size: 16px;
  }
}

.synonym-tag:hover {
  background: rgba(124, 58, 237, 0.2);
  border-color: rgba(124, 58, 237, 0.35);
  color: #c4b5fd;
}

/* ─── Badges ─── */
.badges-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: rgba(0, 0, 0, 0.15);
  border-radius: 14px;
  margin-bottom: 24px;
}

.badge {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.badge-label {
  font-size: 15px;
  font-weight: 600;
  color: #e2e0e8;
}

@media (max-width: 768px) {
  .badge-label {
    font-size: 18px;
  }
}

.badge-sublabel {
  font-size: 12px;
  color: #9c99ab;
}

@media (max-width: 768px) {
  .badge-sublabel {
    font-size: 15px;
  }
}

.badge-divider {
  font-size: 18px;
  color: #9c99ab;
  font-weight: 300;
}

/* ─── Frequency Bar ─── */
.frequency-section {
  margin-top: 8px;
}

.frequency-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.5px;
  color: #9c99ab;
  margin-bottom: 10px;
  display: block;
}

@media (max-width: 768px) {
  .frequency-label {
    font-size: 14px;
  }
}

.frequency-bar {
  display: flex;
  gap: 4px;
  height: 28px;
  margin-bottom: 8px;
}

.frequency-segment {
  flex: 1;
  border-radius: 6px;
  position: relative;
  transition: all 0.3s ease;
}

.frequency-segment.active {
  box-shadow: 0 0 12px rgba(167, 139, 250, 0.3);
}

.frequency-star {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: rgba(255, 255, 255, 0.6);
}

.frequency-labels {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1px;
  color: #9c99ab;
}

@media (max-width: 768px) {
  .frequency-labels {
    font-size: 14px;
  }
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

.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 0.3s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100%);
}

.mobile-detail-header {
  display: flex;
  align-items: center;
  padding: 16px;
  gap: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.mobile-back-btn {
  margin-right: auto;
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

.mobile-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mobile-heart-btn,
.mobile-sound-btn {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #f472b6;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mobile-sound-btn {
  color: #a78bfa;
}

.mobile-sound-btn:hover {
  background: rgba(167, 139, 250, 0.1);
  color: #c4b5fd;
}

.mobile-heart-btn:hover {
  background: rgba(244, 114, 182, 0.1);
}

.mobile-detail-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.mobile-word-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 4px;
}

.mobile-word {
  font-size: 28px;
  font-weight: 600;
  color: #e2e0e8;
  margin: 0;
}

@media (max-width: 768px) {
  .mobile-word {
    font-size: 32px;
  }
}

.mobile-sound-inline {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  background: rgba(255, 255, 255, 0.06);
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mobile-sound-inline:hover {
  background: rgba(167, 139, 250, 0.1);
  color: #c4b5fd;
}

.mobile-meta {
  font-size: 13px;
  color: #9c99ab;
  margin-bottom: 24px;
}

.mobile-section {
  margin-bottom: 24px;
}

.mobile-section-title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1px;
  color: #9c99ab;
  margin-bottom: 10px;
  text-transform: uppercase;
}

@media (max-width: 768px) {
  .mobile-section-title {
    font-size: 16px;
  }
}

.mobile-definition {
  font-size: 15px;
  line-height: 1.6;
  color: #b8b5c8;
  margin: 0;
}

@media (max-width: 768px) {
  .mobile-definition {
    font-size: 18px;
  }
}

.mobile-examples-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.mobile-examples-list li {
  position: relative;
  padding-left: 16px;
  margin-bottom: 10px;
  font-size: 15px;
  line-height: 1.5;
  color: #b8b5c8;
}

@media (max-width: 768px) {
  .mobile-examples-list li {
    font-size: 18px;
  }
}

.mobile-examples-list li::before {
  content: '•';
  position: absolute;
  left: 0;
  color: #c4b5fd;
  font-weight: 700;
}

.synonyms-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* Mobile synonym tags reuse desktop styles */
.known-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 14px;
  margin-top: 8px;
  font-size: 14px;
  color: #b8b5c8;
}

@media (max-width: 768px) {
  .known-toggle {
    font-size: 17px;
  }
}

.toggle-switch {
  position: relative;
  width: 48px;
  height: 26px;
  cursor: pointer;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: #3d3a52;
  border-radius: 26px;
  transition: 0.3s;
}

.toggle-slider::before {
  content: '';
  position: absolute;
  height: 20px;
  width: 20px;
  left: 3px;
  bottom: 3px;
  background: #9c99ab;
  border-radius: 50%;
  transition: 0.3s;
}

.toggle-switch input:checked+.toggle-slider {
  background: #7c3aed;
}

.toggle-switch input:checked+.toggle-slider::before {
  transform: translateX(22px);
  background: white;
}

/* ─── Responsive ─── */
@media (max-width: 768px) {
  .examples-view {
    flex-direction: column;
  }

  .sentence-area {
    padding: 24px 20px;
    padding-top: 80px;
    min-height: 50vh;
  }

  .sentence-area.panel-open {
    flex: 1;
  }

  .sentence-top-bar {
    top: 16px;
    left: 16px;
    right: 16px;
    justify-content: space-between;
  }

  .sentence-text {
    font-size: 22px;
  }

  .sentence-speak-btn {
    position: static;
    transform: none;
    margin-top: 16px;
    margin-left: auto;
    margin-right: auto;
  }

  .word-panel {
    display: none;
  }

  .action-buttons {
    gap: 24px;
  }
}

@media (min-width: 769px) {
  .mobile-detail-overlay {
    display: none;
  }
}

/* ─── Loading / Error / Empty States ─── */
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

@media (max-width: 768px) {
  .loading-state p,
  .empty-state p {
    font-size: 17px;
  }
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

@media (max-width: 768px) {
  .retry-btn {
    font-size: 17px;
  }
}

.retry-btn:hover {
  background: rgba(124, 58, 237, 0.3);
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

/* ─── Example Meta ─── */
.example-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}

.origin-badge {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.origin-badge.existing {
  background: rgba(96, 165, 250, 0.15);
  color: #60a5fa;
}

.origin-badge.generated {
  background: rgba(167, 139, 250, 0.15);
  color: #a78bfa;
}

.counter {
  font-size: 12px;
  color: #9c99ab;
  font-weight: 500;
}

@media (max-width: 768px) {
  .counter {
    font-size: 15px;
  }
}

/* ─── Action Button Disabled ─── */
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

.action-btn.favorited:hover {
  color: #f472b6;
}

/* ─── Modal (Desktop) ─── */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-content {
  background: #36324a;
  border-radius: 16px;
  width: 90%;
  max-width: 500px;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #e2e0e8;
}

.modal-close-btn {
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
}

.modal-close-btn:hover {
  color: #e2e0e8;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 10px;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.words-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.word-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 999px;
  border: 1.5px solid rgba(167, 139, 250, 0.3);
  background: rgba(124, 58, 237, 0.1);
  color: #a78bfa;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.word-chip:hover:not(:disabled) {
  border-color: rgba(167, 139, 250, 0.6);
  background: rgba(124, 58, 237, 0.2);
  color: #c4b5fd;
}

.word-chip.added {
  border-color: rgba(74, 222, 128, 0.5);
  background: rgba(74, 222, 128, 0.1);
  color: #4ade80;
}

.word-chip:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.word-chip .check-icon {
  color: #4ade80;
}

.empty-words {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  color: #9c99ab;
  font-size: 14px;
}

.empty-words p {
  margin: 0;
}

/* ─── Action Sheet (Mobile) ─── */
.mobile-action-sheet {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #36324a;
  border-radius: 20px 20px 0 0;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  z-index: 1100;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.action-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.action-sheet-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #e2e0e8;
}

.action-sheet-close {
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-sheet-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px 0;
}

.action-sheet-words {
  display: flex;
  flex-direction: column;
}

.action-sheet-word-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border: none;
  background: transparent;
  color: #a78bfa;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.action-sheet-word-item:hover:not(:disabled) {
  background: rgba(124, 58, 237, 0.1);
  color: #c4b5fd;
}

.action-sheet-word-item.added {
  color: #4ade80;
}

.action-sheet-word-item:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.action-sheet-word-text {
  flex: 1;
  text-align: left;
}

.action-sheet-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  color: #9c99ab;
  font-size: 14px;
}

.action-sheet-empty p {
  margin: 0;
}

/* ─── Favorites View (Fullscreen) ─── */
.favorites-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
  background: #2d2a3e;
  color: #e2e0e8;
  overflow: hidden;
}

.favorites-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
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

.favorites-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  /* Esconder scrollbar pero mantener scroll */
  scrollbar-width: none;
  -ms-overflow-style: none;
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
}

.remove-favorite-btn {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.remove-favorite-btn:hover {
  color: #f87171;
}

.empty-favorites {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  color: #9c99ab;
  font-size: 16px;
}

.empty-favorites p {
  margin: 0;
}

.loading-more {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.spinner-small {
  width: 24px;
  height: 24px;
  border: 3px solid rgba(124, 58, 237, 0.2);
  border-top-color: #7c3aed;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* ─── Transitions ─── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* ─── Hide Modal on Mobile ─── */
@media (max-width: 768px) {
  .modal-overlay {
    display: none;
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
    padding: 16px;
  }

  .favorite-card-text {
    font-size: 17px;
  }
}
</style>