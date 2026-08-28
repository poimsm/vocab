<!-- BestOptionsView.vue -->
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import api from '@/utils/api'
import LoadingCard from '@/components/LoadingCard.vue'

// ─── Types ───
interface WordExample {
  id: number
  text: string
  is_favorite: boolean
}

interface Word {
  id: number
  main: string
  meaning: string
  type: string
  level: number
  synonyms: string[]
  frequency: 'rare' | 'uncommon' | 'common'
  examples: WordExample[]
}

interface BestOptionItem {
  queue_item_id: number
  best_option_id: number
  word: Word
  question: string
  options: string[]
  correct_option: number
}

// ─── State ───
const items = ref<BestOptionItem[]>([])
const currentIndex = ref(0)
const error = ref<string | null>(null)
const generating = ref(false)
const noWords = ref(false)
const isPolling = ref(false)
const pollTimer = ref<ReturnType<typeof setTimeout> | null>(null)

const selectedOption = ref<number | null>(null)
const showResult = ref(false)
const showWordDetail = ref(false)

const BATCH_SIZE = 4
const POLL_INTERVAL = 3000

// ─── Computed ───
const currentItem = computed(() => {
  if (items.value.length === 0) return null
  return items.value[currentIndex.value]
})

const isCorrect = computed(() => {
  if (selectedOption.value === null || !currentItem.value) return false
  return selectedOption.value === currentItem.value.correct_option
})

const canGoPrev = computed(() => currentIndex.value > 0)
const canGoNext = computed(() => currentIndex.value < items.value.length - 1)

const optionLetters = ['A', 'B', 'C', 'D', 'E']

const frequencySegments = computed(() => {
  if (!currentItem.value) return []
  const freq = currentItem.value.word.frequency
  return [
    { active: freq === 'rare', color: '#4ade80' },
    { active: freq === 'uncommon' || freq === 'common', color: '#60a5fa' },
    { active: freq === 'common', color: '#a78bfa' }
  ]
})

// ─── API Calls with new Unified Endpoint ───

/**
 * Resuelve un item SIN obtener nuevas preguntas.
 * Usado cuando el usuario avanza pero hay más preguntas en el lote.
 */
function resolveOnly(queueItemId: number) {
  api.post('/best-options/explore', {
    actions: ['resolve'],
    resolve_queue_item_id: queueItemId
  }).catch(() => { })
}

/**
 * Resuelve un item Y obtiene nuevas preguntas.
 * Usado cuando el usuario llegó a la última pregunta del lote.
 */
async function resolveAndFetchNext(queueItemId: number) {
  generating.value = true
  error.value = null

  try {
    const { data } = await api.post('/best-options/explore', {
      actions: ['resolve', 'next'],
      resolve_queue_item_id: queueItemId,
      limit: BATCH_SIZE
    })

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
    loadItems(data.items || [])
  } catch (e: any) {
    generating.value = false
    error.value = e.response?.data?.message || e.message || 'Failed to fetch items'
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
        const { data } = await api.post('/best-options/explore', {
          actions: ['next'],
          limit: BATCH_SIZE
        })
        if (data.status === 'generating') {
          poll()
          return
        }
        if (data.status === 'no_words') {
          isPolling.value = false
          generating.value = false
          noWords.value = true
          return
        }
        isPolling.value = false
        generating.value = false
        loadItems(data.items || [])
      } catch (e: any) {
        isPolling.value = false
        generating.value = false
        error.value = e.response?.data?.message || e.message || 'Failed to load'
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

// ─── TTS ───
function speak(text: string) {
  if (!window.speechSynthesis) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(text)
  u.lang = 'en-US'
  u.rate = 0.9
  const voices = window.speechSynthesis.getVoices()
  const en = voices.find(v => v.lang.startsWith('en'))
  if (en) u.voice = en
  window.speechSynthesis.speak(u)
}

// ─── API ───
function loadItems(raw: any[]) {
  if (!raw.length) {
    items.value = []
    return
  }
  items.value = raw.map((item: any) => ({
    queue_item_id: item.queue_item_id,
    best_option_id: item.best_option_id,
    word: {
      id: item.word.id,
      main: item.word.main,
      meaning: item.word.meaning,
      type: item.word.type,
      level: item.word.level,
      synonyms: item.word.synonyms || [],
      frequency: item.word.frequency,
      examples: (item.word.examples || []).map((ex: any) => ({
        id: ex.id,
        text: ex.text,
        is_favorite: ex.is_favorite
      }))
    },
    question: item.question,
    options: item.options || [],
    correct_option: item.correct_option
  }))
  currentIndex.value = 0
  selectedOption.value = null
  showResult.value = false
  showWordDetail.value = false
}

async function fetchItems() {
  if (generating.value && !isPolling.value) return
  generating.value = true
  noWords.value = false
  error.value = null
  try {
    const { data } = await api.post('/best-options/explore', {
      actions: ['next'],
      limit: BATCH_SIZE
    })
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
    loadItems(data.items || [])
  } catch (e: any) {
    generating.value = false
    error.value = e.response?.data?.message || e.message || 'Failed to load'
  }
}

// ─── Interaction ───
function selectOption(index: number) {
  if (showResult.value) return
  selectedOption.value = index
  showResult.value = true
}

function optionClass(index: number): string {
  if (!showResult.value) return selectedOption.value === index ? 'selected' : ''
  const correct = currentItem.value?.correct_option === index
  const picked = selectedOption.value === index
  if (correct) return 'correct'
  if (picked && !correct) return 'wrong'
  return 'dimmed'
}

async function next() {
  const cur = currentItem.value
  if (!cur) return

  // Si hay más preguntas en el lote, resolver y avanzar
  if (canGoNext.value) {
    resolveOnly(cur.queue_item_id)
    currentIndex.value++
    resetState()
    return
  }

  // Si es la última, resolver Y obtener nuevas preguntas (atómico)
  await resolveAndFetchNext(cur.queue_item_id)
  resetState()
}

function prev() {
  if (canGoPrev.value) {
    currentIndex.value--
    resetState()
  }
}

function resetState() {
  selectedOption.value = null
  showResult.value = false
  showWordDetail.value = false
}

function toggleDetail() {
  showWordDetail.value = !showWordDetail.value
}

onMounted(fetchItems)
onUnmounted(stopPolling)
</script>

<template>
  <div class="best-options-view">
    <!-- Loading / Generating State -->
    <LoadingCard v-if="generating" message="Generating..." />

    <!-- No Words State -->
    <div v-else-if="noWords" class="center-state">
      <p>No more words to review</p>
      <button class="retry" @click="fetchItems">Try Again</button>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="center-state">
      <p class="err">{{ error }}</p>
      <button class="retry" @click="fetchItems">Retry</button>
    </div>

    <!-- Empty -->
    <div v-else-if="!currentItem" class="center-state">
      <p>No questions</p>
      <button class="retry" @click="fetchItems">Load</button>
    </div>

    <!-- Quiz -->
    <div v-else class="quiz">
      <!-- Word (clickable) -->
      <button class="word" @click="toggleDetail">
        {{ currentItem.word.main }}
        <Icon
          :icon="showWordDetail ? 'solar:alt-arrow-up-linear' : 'solar:alt-arrow-down-linear'"
          width="14"
        />
      </button>

      <!-- Expandable detail -->
      <transition name="slide">
        <div v-if="showWordDetail" class="detail">
          <p class="meaning">{{ currentItem.word.meaning }}</p>
          <div v-if="currentItem.word.synonyms.length" class="synonyms">
            <span
              v-for="s in currentItem.word.synonyms"
              :key="s"
              class="syn"
              @click.stop="speak(s)"
            >{{ s }}</span>
          </div>
          <div v-if="currentItem.word.examples.length" class="examples">
            <p v-for="ex in currentItem.word.examples" :key="ex.id">{{ ex.text }}</p>
          </div>
          <div class="meta">
            <span>{{ currentItem.word.type }}</span>
            <span>Lv.{{ currentItem.word.level }}</span>
            <div class="freq">
              <div
                v-for="(seg, i) in frequencySegments"
                :key="i"
                class="bar"
                :class="{ on: seg.active }"
                :style="{ background: seg.active ? seg.color : '#3d3a52' }"
              />
            </div>
          </div>
        </div>
      </transition>

      <!-- Question -->
      <p class="question">{{ currentItem.question }}</p>

      <!-- Options -->
      <div class="options">
        <button
          v-for="(opt, i) in currentItem.options"
          :key="i"
          :class="['opt', optionClass(i)]"
          @click="selectOption(i)"
          :disabled="showResult"
        >
          <span class="letter">{{ optionLetters[i] }}</span>
          <span class="text">{{ opt }}</span>
        </button>
      </div>

      <!-- Result -->
      <transition name="fade">
        <div v-if="showResult" :class="['result', isCorrect ? 'ok' : 'bad']">
          <Icon :icon="isCorrect ? 'solar:check-circle-bold' : 'solar:close-circle-bold'" width="16" />
          {{ isCorrect ? 'Correct' : 'Incorrect' }}
        </div>
      </transition>

      <!-- Only 2 buttons -->
      <div class="nav">
        <button class="arrow" @click="prev" :disabled="!canGoPrev">
          <Icon icon="solar:alt-arrow-left-linear" width="22" />
        </button>
        <button class="arrow" @click="next" :disabled="generating">
          <Icon v-if="generating" icon="solar:refresh-circle-linear" width="22" class="spin" />
          <Icon v-else icon="solar:alt-arrow-right-linear" width="22" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.best-options-view {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100%;
}

.center-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 60px 20px;
}
.center-state p { color: #9c99ab; font-size: 14px; margin: 0; }

@media (max-width: 768px) {
  .center-state p {
    font-size: 17px;
  }
}
.center-state .err { color: #f87171; }
.retry {
  padding: 8px 18px; border-radius: 10px; border: none;
  background: rgba(124,58,237,0.2); color: #a78bfa;
  font-size: 13px; font-weight: 600; cursor: pointer;
}

@media (max-width: 768px) {
  .retry {
    font-size: 16px;
  }
}
.retry:hover { background: rgba(124,58,237,0.3); }

.spinner {
  width: 26px; height: 26px;
  border: 3px solid rgba(124,58,237,0.2);
  border-top-color: #7c3aed;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.spin { animation: spin 0.8s linear infinite; }

/* ─── Quiz ─── */
.quiz {
  width: 100%; max-width: 480px;
  display: flex; flex-direction: column; align-items: center; gap: 14px;
}

/* Word */
.word {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 22px; border-radius: 999px;
  background: rgba(124,58,237,0.12);
  border: 1px solid rgba(124,58,237,0.25);
  color: #c4b5fd; font-size: 15px; font-weight: 600;
  cursor: pointer; transition: all 0.2s ease;
  text-transform: capitalize;
}

@media (max-width: 768px) {
  .word {
    font-size: 18px;
  }
}
.word:hover {
  background: rgba(124,58,237,0.2);
  border-color: rgba(124,58,237,0.4);
}

/* Detail */
.detail {
  width: 100%; padding: 14px 16px;
  background: rgba(0,0,0,0.18); border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.06);
  display: flex; flex-direction: column; gap: 10px;
}
.meaning { font-size: 14px; line-height: 1.5; color: #b8b5c8; margin: 0; }

@media (max-width: 768px) {
  .meaning {
    font-size: 17px;
  }
}
.synonyms { display: flex; flex-wrap: wrap; gap: 6px; }
.syn {
  padding: 3px 10px; border-radius: 999px;
  background: rgba(124,58,237,0.12); color: #a78bfa;
  font-size: 12px; font-weight: 600; border: 1px solid rgba(124,58,237,0.2);
  cursor: pointer;
}

@media (max-width: 768px) {
  .syn {
    font-size: 15px;
  }
}
.syn:hover { background: rgba(124,58,237,0.2); color: #c4b5fd; }
.examples { display: flex; flex-direction: column; gap: 4px; }
.examples p {
  font-size: 12px; line-height: 1.45; color: #9c99ab; margin: 0;
  padding-left: 14px; position: relative;
}

@media (max-width: 768px) {
  .examples p {
    font-size: 15px;
  }
}
.examples p::before {
  content: '•'; position: absolute; left: 2px; color: #c4b5fd; font-weight: 700;
}
.meta {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.meta span {
  padding: 2px 8px; border-radius: 999px;
  font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;
  background: rgba(255,255,255,0.06); color: #9c99ab;
}

@media (max-width: 768px) {
  .meta span {
    font-size: 14px;
  }
}
.freq { display: flex; gap: 3px; margin-left: auto; }
.freq .bar { width: 16px; height: 4px; border-radius: 2px; }

/* Question */
.question {
  font-size: 22px; line-height: 1.45; color: #e2e0e8e3;
  text-align: center; margin: 0; padding: 0 4px;
}

@media (max-width: 768px) {
  .question {
    font-size: 26px;
  }
}

/* Options */
.options {
  width: 100%; display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
}
.opt {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 14px; border-radius: 12px;
  border: 1.5px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.03); color: #b8b5c8;
  cursor: pointer; text-align: left; transition: all 0.18s ease;
}
.opt:hover:not(:disabled) {
  border-color: rgba(124,58,237,0.4);
  background: rgba(124,58,237,0.06); color: #e2e0e8;
}
.opt.selected { border-color: #7c3aed; background: rgba(124,58,237,0.1); color: #e2e0e8; }
.opt.correct { border-color: #4ade80; background: rgba(74,222,128,0.1); color: #4ade80; }
.opt.wrong { border-color: #f87171; background: rgba(248,113,113,0.1); color: #f87171; }
.opt.dimmed { opacity: 0.3; }

.letter {
  width: 24px; height: 24px; border-radius: 8px;
  background: rgba(255,255,255,0.06); display: flex;
  align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; color: #9c99ab; flex-shrink: 0;
}

@media (max-width: 768px) {
  .letter {
    font-size: 15px;
  }
}
.opt.selected .letter { background: #7c3aed; color: white; }
.opt.correct .letter { background: #4ade80; color: #064e3b; }
.opt.wrong .letter { background: #f87171; color: #450a0a; }
.text { font-size: 14px; line-height: 1.3; }

@media (max-width: 768px) {
  .text {
    font-size: 16px;
  }
}

/* Result */
.result {
  display: flex; align-items: center; gap: 6px;
  padding: 5px 14px; border-radius: 999px;
  font-size: 13px; font-weight: 600;
}

@media (max-width: 768px) {
  .result {
    font-size: 16px;
  }
}
.result.ok { background: rgba(74,222,128,0.12); color: #4ade80; }
.result.bad { background: rgba(248,113,113,0.12); color: #f87171; }

/* Nav — ONLY 2 buttons */
.nav {
  display: flex; align-items: center; gap: 24px; margin-top: 4px;
}
.arrow {
  width: 44px; height: 44px; border-radius: 50%;
  border: 1.5px solid rgba(255,255,255,0.15);
  background: transparent; color: #9c99ab;
  cursor: pointer; display: flex;
  align-items: center; justify-content: center;
  transition: all 0.2s ease;
}
.arrow:hover:not(:disabled) {
  border-color: rgba(255,255,255,0.3);
  color: #e2e0e8; background: rgba(255,255,255,0.04);
}
.arrow:disabled { opacity: 0.25; cursor: not-allowed; }

/* Transitions */
.fade-enter-active, .fade-leave-active,
.slide-enter-active, .slide-leave-active {
  transition: all 0.2s ease;
}
.fade-enter-from, .fade-leave-to { opacity: 0; transform: translateY(4px); }
.slide-enter-from, .slide-leave-to { opacity: 0; transform: translateY(-6px); }

/* Mobile */
@media (max-width: 480px) {
  .options { grid-template-columns: 1fr; }
  .question { font-size: 22px; }
  .word { font-size: 17px; padding: 8px 18px; margin-top: 50px}
}
</style>