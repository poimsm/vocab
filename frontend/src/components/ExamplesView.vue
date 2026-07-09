<!-- ExamplesView.vue (conectado a API) -->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Icon } from '@iconify/vue'

// ─── Config ───
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost/api'

// ─── Types ───
interface WordInExample {
  word_id: number
  main: string
  text_form: string
}

interface ExampleItem {
  id: number
  text: string
  origin: string
  words: WordInExample[]
}

interface WordDetail {
  word: string
  definition: string
  level: string | number
  context: string
  frequency: 'rare' | 'uncommon' | 'common'
  examples: string[]
  synonyms: string[]
}

// ─── State ───
const examples = ref<ExampleItem[]>([])
const currentIndex = ref(0)
const loading = ref(false)
const error = ref<string | null>(null)
const generating = ref(false)

const selectedWord = ref<WordDetail | null>(null)
const isMobileDetailOpen = ref(false)

const BATCH_SIZE = 4

// ─── Computed ───
const currentExample = computed(() => {
  if (examples.value.length === 0) return null
  return examples.value[currentIndex.value]
})

const wordsInSentence = computed(() => {
  const ex = currentExample.value
  if (!ex) return []

  let text = ex.text
  const parts: { text: string; isHighlight: boolean; index: number }[] = []
  let lastIndex = 0
  let partIdx = 0

  // Ordenar words por posición en el texto para procesar de izquierda a derecha
  const sortedWords = [...ex.words].sort((a, b) => {
    const idxA = text.toLowerCase().indexOf(a.text_form.toLowerCase())
    const idxB = text.toLowerCase().indexOf(b.text_form.toLowerCase())
    return idxA - idxB
  })

  // Track posiciones ya usadas para evitar overlaps
  const usedRanges: [number, number][] = []

  for (const word of sortedWords) {
    const lowerText = text.toLowerCase()
    const lowerForm = word.text_form.toLowerCase()
    let searchStart = 0

    // Buscar una ocurrencia que no esté en un rango usado
    while (true) {
      const idx = lowerText.indexOf(lowerForm, searchStart)
      if (idx === -1) break

      const endIdx = idx + word.text_form.length
      const overlaps = usedRanges.some(([s, e]) => !(endIdx <= s || idx >= e))

      if (!overlaps) {
        // Añadir texto antes
        if (idx > lastIndex) {
          parts.push({ text: text.slice(lastIndex, idx), isHighlight: false, index: partIdx++ })
        }
        // Añadir palabra resaltada (usar el texto original para preservar casing)
        parts.push({ text: text.slice(idx, endIdx), isHighlight: true, index: partIdx++ })
        usedRanges.push([idx, endIdx])
        lastIndex = endIdx
        break
      }
      searchStart = idx + 1
    }
  }

  // Añadir resto del texto
  if (lastIndex < text.length) {
    parts.push({ text: text.slice(lastIndex), isHighlight: false, index: partIdx++ })
  }

  return parts
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
function fireAndForgetResolve(exampleId: number) {
  fetch(`${API_BASE}/examples/${exampleId}/resolve-pending`, { method: 'PATCH' })
    .catch(() => {}) // Silencioso, no nos importa si falla
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
    speak(ex.text)
  }
}

// ─── API ───
async function fetchExamples() {
  if (generating.value) return
  generating.value = true
  error.value = null

  try {
    const res = await fetch(`${API_BASE}/examples/explore`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ total_amount: BATCH_SIZE })
    })

    if (!res.ok) throw new Error('Failed to generate examples')
    const data = await res.json()

    // Filtrar solo los nuevos (generated) o mezclar todos
    const newExamples: ExampleItem[] = (data || []).map((item: any) => ({
      id: item.id,
      text: item.text,
      origin: item.origin,
      words: (item.words || []).map((w: any) => ({
        word_id: w.word_id,
        main: w.main,
        text_form: w.text_form
      }))
    }))

    if (newExamples.length > 0 && newExamples[0]) {
      examples.value = newExamples
      currentIndex.value = 0
      // Side effect: marcar el primer ejemplo como visto inmediatamente
      fireAndForgetResolve(newExamples[0].id)
    }
  } catch (e: any) {
    error.value = e.message
  } finally {
    generating.value = false
  }
}

async function fetchWordDetail(wordId: number) {
  try {
    const res = await fetch(`${API_BASE}/words/words/${wordId}`)
    if (!res.ok) throw new Error('Failed')
    const data = await res.json()

    selectedWord.value = {
      word: data.main,
      definition: data.meaning,
      level: data.level,
      context: data.context || data.type || 'General',
      frequency: data.frequency,
      examples: data.examples || [],
      synonyms: data.synonyms || []
    }
  } catch (e) {
    alert('Could not load word detail')
  }
}

async function toggleExampleFav() {
  const ex = currentExample.value
  if (!ex) return

  try {
    const res = await fetch(`${API_BASE}/examples/toggle-fav`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ example_id: ex.id })
    })
    if (!res.ok) throw new Error('Failed')
    // Toggle visual feedback si la API devuelve estado
  } catch (e) {
    alert('Failed to toggle favorite')
  }
}

// ─── Methods ───
function handleWordClick(word: WordInExample) {
  fetchWordDetail(word.word_id)
  if (window.innerWidth <= 768) {
    isMobileDetailOpen.value = true
  }
}

function closeMobileDetail() {
  isMobileDetailOpen.value = false
  selectedWord.value = null
}

function refreshExample() {
  // Side effect: marcar el siguiente ejemplo como visto (si existe)
  const nextExample = examples.value[currentIndex.value + 1]
  if (nextExample) {
    fireAndForgetResolve(nextExample.id)
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

function shareExample() {
  const ex = currentExample.value
  if (!ex) return
  if (navigator.share) {
    navigator.share({ text: ex.text })
  } else {
    navigator.clipboard.writeText(ex.text)
    alert('Copied to clipboard!')
  }
}

onMounted(() => {
  fetchExamples()
  // Preload voices for speech synthesis
  window.speechSynthesis?.getVoices()
})
</script>

<template>
  <div class="examples-view">
    <!-- Loading State -->
    <div v-if="generating && examples.length === 0" class="loading-state">
      <div class="spinner"></div>
      <p>Generating examples...</p>
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
      <div class="sentence-wrapper">
        <p class="sentence-text">
          <template v-for="part in wordsInSentence" :key="part.index">
            <span
              v-if="part.isHighlight"
              class="word-highlight"
              @click="handleWordClick(currentExample!.words.find(w => w.text_form.toLowerCase() === part.text.toLowerCase())!)"
            >
              {{ part.text }}
            </span>
            <span v-else>{{ part.text }}</span>
          </template>
        </p>
        <!-- Play full sentence audio -->
        <button class="sentence-speak-btn" @click="speakExample" title="Play sentence">
          <Icon icon="solar:volume-loud-linear" width="18" />
        </button>
      </div>

      <!-- Progress indicator -->
      <div class="progress-bar">
        <div
          v-for="(_, i) in examples"
          :key="i"
          class="progress-dot"
          :class="{ active: i === currentIndex, passed: i < currentIndex }"
        />
      </div>

      <div class="action-buttons">
        <button class="action-btn" @click="toggleExampleFav" title="Favorite">
          <Icon icon="solar:heart-linear" width="22" />
        </button>
        <button class="action-btn" @click="prevExample" :disabled="!canGoPrev" title="Previous">
          <Icon icon="solar:arrow-left-linear" width="22" />
        </button>
        <button class="action-btn" @click="refreshExample" :disabled="generating" title="Next / New">
          <Icon v-if="generating" icon="solar:refresh-circle-linear" width="22" class="spinning" />
          <Icon v-else icon="solar:refresh-linear" width="22" />
        </button>
        <button class="action-btn" @click="shareExample" title="Share">
          <Icon icon="solar:link-linear" width="22" />
        </button>
      </div>

      <div class="example-meta">
        <span class="origin-badge" :class="currentExample.origin">
          {{ currentExample.origin }}
        </span>
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
            <button class="bookmark-btn" title="Bookmark">
              <Icon icon="solar:bookmark-linear" width="20" />
            </button>
          </div>
        </div>

        <h2 class="panel-word">{{ selectedWord.word }}</h2>
        <p class="panel-definition">{{ selectedWord.definition }}</p>

        <!-- Synonyms Section (Desktop) -->
        <div v-if="selectedWord.synonyms && selectedWord.synonyms.length" class="panel-section">
          <h3 class="section-title">SYNONYMS</h3>
          <div class="synonyms-list">
            <span
              v-for="syn in selectedWord.synonyms"
              :key="syn"
              class="synonym-tag"
              @click="speak(syn)"
              title="Click to hear"
            >
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
            <div
              v-for="(seg, i) in frequencySegments"
              :key="i"
              class="frequency-segment"
              :class="{ active: seg.active }"
              :style="{ background: seg.active ? seg.color : '#3d3a52' }"
            >
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
            <button class="mobile-bookmark-btn" title="Bookmark">
              <Icon icon="solar:bookmark-linear" width="22" />
            </button>
          </div>
        </div>

        <div class="mobile-detail-content">
          <div class="mobile-word-header">
            <h2 class="mobile-word">{{ selectedWord?.word }}</h2>
            <button class="mobile-sound-inline" @click="speakWord" title="Play pronunciation">
              <Icon icon="solar:volume-loud-linear" width="18" />
            </button>
          </div>
          <p class="mobile-meta">{{ selectedWord?.level }} Level · {{ selectedWord?.context }} Context</p>

          <div class="mobile-section">
            <h3 class="mobile-section-title">Definition</h3>
            <p class="mobile-definition">{{ selectedWord?.definition }}</p>
          </div>

          <!-- Synonyms Section (Mobile) -->
          <div class="mobile-section" v-if="selectedWord?.synonyms && selectedWord.synonyms.length">
            <h3 class="mobile-section-title">Synonyms</h3>
            <div class="synonyms-tags">
              <span
                v-for="syn in selectedWord.synonyms"
                :key="syn"
                class="synonym-tag"
                @click="speak(syn)"
                title="Tap to hear"
              >
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
              <input type="checkbox" />
              <span class="toggle-slider"></span>
            </label>
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

.bookmark-btn,
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

.bookmark-btn:hover,
.sound-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
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

.panel-definition {
  font-size: 15px;
  line-height: 1.6;
  color: #b8b5c8;
  margin-bottom: 28px;
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

.badge-sublabel {
  font-size: 12px;
  color: #9c99ab;
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

.mobile-bookmark-btn,
.mobile-sound-btn {
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

.mobile-sound-btn {
  color: #a78bfa;
}

.mobile-sound-btn:hover {
  background: rgba(167, 139, 250, 0.1);
  color: #c4b5fd;
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

.mobile-definition {
  font-size: 15px;
  line-height: 1.6;
  color: #b8b5c8;
  margin: 0;
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
  font-size: 14px;
  line-height: 1.5;
  color: #b8b5c8;
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

.toggle-switch input:checked + .toggle-slider {
  background: #7c3aed;
}

.toggle-switch input:checked + .toggle-slider::before {
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
    min-height: 50vh;
  }

  .sentence-area.panel-open {
    flex: 1;
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
  to { transform: rotate(360deg); }
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
</style>