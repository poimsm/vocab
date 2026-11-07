<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import api from '@/utils/api'
import { useBestOptionsStore } from '@/stores/bestOptions'
import { useAuthStore } from '@/stores/auth'
import { useActivityTracking } from '@/composables/useActivityTracking'
import LoadingCard from '@/components/LoadingCard.vue'

const bestOptionsStore = useBestOptionsStore()
const authStore = useAuthStore()
const { trackButtonClick } = useActivityTracking()

// API base URL from environment
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost/api'

// ─── Local State ───
const isComponentMounted = ref(false)

// ─── Word Dropdown State ───
const showWordDropdown = ref(false)
const wordDropdownData = ref<any>(null)

const BATCH_SIZE = 4
let sseEventSource: EventSource | null = null
let sseActive = ref(false)

// ─── SSE (Server-Sent Events) - RealtimeEventBus ───
function startSSE() {
  console.log('[startSSE] Starting SSE stream')
  console.log('[startSSE] API_BASE:', API_BASE)
  console.log('[startSSE] authStore.token exists:', !!authStore.token)

  // Clean up any previous SSE connection
  if (sseEventSource) {
    console.log('[startSSE] Cleaning up previous EventSource')
    sseEventSource.close()
    sseEventSource = null
  }

  sseActive.value = true

  // Construir URL del SSE con token en query param
  // EventSource no soporta headers Authorization, así que pasamos el token como parámetro
  const sseUrl = new URL(`${API_BASE}/best-options/explore-stream`)
  if (authStore.token) {
    sseUrl.searchParams.append('token', authStore.token)
  }

  const fullUrl = sseUrl.toString()
  console.log('[startSSE] Conectando a:', fullUrl)

  try {
    sseEventSource = new EventSource(fullUrl)

    // ─── Evento: open (conexión establecida) ───
    sseEventSource.addEventListener('open', () => {
      console.log('[SSE:open] ✅ Conexión establecida con servidor')
      bestOptionsStore.setGenerating(true)
    })

    // ─── Evento: error ───
    sseEventSource.addEventListener('error', (event: Event) => {
      console.error('[SSE:error] Error en conexión:', event)
      if (sseEventSource?.readyState === EventSource.CLOSED) {
        console.log('[SSE:error] Conexión cerrada por servidor')
      } else {
        console.error('[SSE:error] Error inesperado en SSE')
        bestOptionsStore.setError('SSE Connection Error')
      }
    })

    // ─── Evento: best_options_explore.started ───
    sseEventSource.addEventListener('best_options_explore.started', (event: MessageEvent) => {
      if (!sseActive.value) {
        console.log('[SSE:best_options_explore.started] Stream disabled, ignoring event')
        return
      }

      try {
        const data = JSON.parse(event.data)
        console.log('[SSE:best_options_explore.started] Exploración iniciada:', data.request_id)
        bestOptionsStore.setGenerating(true)
      } catch (e) {
        console.error('[SSE:best_options_explore.started] Error parsing event:', e)
      }
    })

    // ─── Evento: best_options_explore.processing ───
    sseEventSource.addEventListener('best_options_explore.processing', (event: MessageEvent) => {
      if (!sseActive.value) {
        console.log('[SSE:best_options_explore.processing] Stream disabled, ignoring event')
        return
      }

      try {
        const data = JSON.parse(event.data)
        console.log('[SSE:best_options_explore.processing] Procesando acciones...', data.message)
        bestOptionsStore.setGenerating(true)
      } catch (e) {
        console.error('[SSE:best_options_explore.processing] Error parsing event:', e)
      }
    })

    // ─── Evento: best_options_explore.completed ───
    sseEventSource.addEventListener('best_options_explore.completed', (event: MessageEvent) => {
      if (!sseActive.value) {
        console.log('[SSE:best_options_explore.completed] Stream disabled, ignoring event')
        return
      }

      try {
        const data = JSON.parse(event.data)
        console.log('[SSE:best_options_explore.completed] Exploración completada:', data)

        // Actualizar store con datos recibidos
        bestOptionsStore.setGenerating(false)
        bestOptionsStore.setError(null)
        bestOptionsStore.setNoWords(false)

        // Si hay best_options, cargarlos
        if (data.best_options && data.best_options.length > 0) {
          console.log('[SSE:best_options_explore.completed] Cargando', data.best_options.length, 'best options')
          bestOptionsStore.loadBestOptions(
            data.best_options,
            data.buffer_delivery_ids,
            data.buffer_position
          )
        } else if (data.best_options_count > 0) {
          // Fallback: solo IDs, sin datos de best_options
          console.log('[SSE:best_options_explore.completed] Actualizando buffer con IDs:', data.buffer_delivery_ids)
          bestOptionsStore.setBufferData(data.buffer_delivery_ids, data.buffer_position)
        } else if (data.status === 'generating') {
          console.log('[SSE:best_options_explore.completed] Contenido aún se está generando...')
          bestOptionsStore.setGenerating(true)
          return
        } else if (data.status === 'no_words') {
          console.log('[SSE:best_options_explore.completed] No hay palabras disponibles')
          bestOptionsStore.setNoWords(true)
        }

        sseActive.value = false
        sseEventSource?.close()
      } catch (e) {
        console.error('[SSE:best_options_explore.completed] Error parsing event:', e)
      }
    })

    // ─── Evento: best_options_explore.failed ───
    sseEventSource.addEventListener('best_options_explore.failed', (event: MessageEvent) => {
      if (!sseActive.value) {
        console.log('[SSE:best_options_explore.failed] Stream disabled, ignoring event')
        return
      }

      try {
        const data = JSON.parse(event.data)
        console.error('[SSE:best_options_explore.failed] Error en exploración:', data.error)
        bestOptionsStore.setGenerating(false)
        bestOptionsStore.setError(data.error || 'Failed to process explore action')
        sseActive.value = false
        sseEventSource?.close()
      } catch (e) {
        console.error('[SSE:best_options_explore.failed] Error parsing event:', e)
      }
    })

    sseEventSource.addEventListener('error', (event: Event) => {
      console.error('[SSE] Connection error:', event)
      if (sseEventSource?.readyState === EventSource.CLOSED) {
        console.log('[SSE] Connection closed')
        sseActive.value = false
      } else {
        console.error('[SSE] Unexpected error')
        bestOptionsStore.setGenerating(false)
        bestOptionsStore.setError('Connection error - please try again')
        sseActive.value = false
        sseEventSource?.close()
      }
    })
  } catch (e) {
    console.error('[startSSE] Error creating EventSource:', e)
    bestOptionsStore.setGenerating(false)
    bestOptionsStore.setError('Failed to connect to stream')
  }
}

function stopSSE() {
  console.log('[stopSSE] Stopping SSE stream')
  sseActive.value = false

  if (sseEventSource) {
    console.log('[stopSSE] Closing EventSource')
    sseEventSource.close()
    sseEventSource = null
  }

  console.log('[stopSSE] SSE stream stopped')
}

async function fetchBestOptions() {
  console.log('[fetchBestOptions] Loading new batch of best options')

  try {
    console.log('[fetchBestOptions] Enviando POST /explore con acción "next"')

    // Enviar POST /explore para notificar al backend
    await api.post('/best-options/explore', {
      actions: ['next'],
      limit: BATCH_SIZE,
      buffer_delivery_ids: bestOptionsStore.bufferIds,
      buffer_position: bestOptionsStore.currentIndex,
    })

    console.log('[fetchBestOptions] Request enqueued, starting SSE stream')

    // Iniciar SSE para escuchar eventos de progreso
    startSSE()
  } catch (e: any) {
    console.error('[fetchBestOptions] Error:', e)
    bestOptionsStore.setGenerating(false)
    bestOptionsStore.setError(e.response?.data?.message || e.message || 'Failed to generate best options')
  }
}

// ─── Navigation ───
async function refreshBestOption() {
  const currentOpt = bestOptionsStore.currentBestOption
  if (!currentOpt) return

  if (bestOptionsStore.canGoNext) {
    bestOptionsStore.nextBestOption()
    await bestOptionsStore.navigateBestOption(currentOpt.queue_item_id, false, BATCH_SIZE)
    resetState()
    return
  }

  await bestOptionsStore.navigateBestOption(currentOpt.queue_item_id, true, BATCH_SIZE)

  if (bestOptionsStore.generating) {
    await fetchBestOptions()
  }

  resetState()
}

function prevBestOption() {
  trackButtonClick('prev_best_option')
  if (bestOptionsStore.canGoPrev) {
    bestOptionsStore.prevBestOption()
    bestOptionsStore.syncPosition()
    resetState()
  }
}

async function nextBestOption() {
  trackButtonClick('next_best_option')
  if (bestOptionsStore.canGoNext) {
    const currentOpt = bestOptionsStore.currentBestOption
    bestOptionsStore.nextBestOption()

    if (currentOpt) {
      await bestOptionsStore.navigateBestOption(currentOpt.queue_item_id, false, BATCH_SIZE)
    }

    resetState()
  } else {
    await refreshBestOption()
  }
}

// ─── Option Selection ───
const selectedOption = ref<number | null>(null)
const showResult = ref(false)

const isCorrect = computed(() => {
  if (selectedOption.value === null || !bestOptionsStore.currentBestOption) return false
  return selectedOption.value === bestOptionsStore.currentBestOption.correct_option
})

function selectOption(index: number) {
  trackButtonClick('select_best_option', { option_index: index })
  if (showResult.value) return
  selectedOption.value = index
  showResult.value = true
}

function optionClass(index: number): string {
  if (!showResult.value) return selectedOption.value === index ? 'selected' : ''
  const correct = bestOptionsStore.currentBestOption?.correct_option === index
  const picked = selectedOption.value === index
  if (correct) return 'correct'
  if (picked && !correct) return 'wrong'
  return 'dimmed'
}

function resetState() {
  selectedOption.value = null
  showResult.value = false
}

// ─── Word Dropdown Functions ───
async function toggleWordDropdown() {
  if (showWordDropdown.value) {
    showWordDropdown.value = false
    wordDropdownData.value = null
    return
  }

  if (!bestOptionsStore.currentBestOption) return

  const wordId = bestOptionsStore.currentBestOption.word.id
  trackButtonClick('view_word_dropdown')

  try {
    const response = await api.get(`/words/words/${wordId}`)
    const data = response.data

    wordDropdownData.value = {
      definition: data.meaning,
      synonyms: data.synonyms || [],
      level: data.level,
      frequency: data.frequency
    }
    showWordDropdown.value = true
  } catch (e: any) {
    console.error('Failed to fetch word info:', e)
  }
}

function closeWordDropdown() {
  showWordDropdown.value = false
  wordDropdownData.value = null
}

// ─── Mounted ───
onMounted(async () => {
  isComponentMounted.value = true

  try {
    console.log('[onMounted] Iniciando carga de best options')
    bestOptionsStore.setGenerating(true)
    bestOptionsStore.setError(null)

    // Hacer POST request con 'resume' para iniciar el explore
    await api.post('/best-options/explore', {
      actions: ['resume'],
      limit: BATCH_SIZE,
      buffer_delivery_ids: [],
      buffer_position: 0,
    })

    if (!isComponentMounted.value) return

    console.log('[onMounted] Request enqueued, iniciando SSE para escuchar datos')

    // Iniciar SSE para recibir los datos del explore
    startSSE()
  } catch (e) {
    if (isComponentMounted.value) {
      console.error('[onMounted] Error:', e)
      bestOptionsStore.resetBuffer()
      bestOptionsStore.setError('Failed to load best options')
    }
  }
})

onUnmounted(() => {
  isComponentMounted.value = false
  stopSSE()
})
</script>

<template>
  <div class="best-options-view">
    <LoadingCard v-if="bestOptionsStore.generating && bestOptionsStore.bestOptions.length === 0" message="Generating..." />

    <div v-else-if="bestOptionsStore.noWords" class="center-state">
      <p>No more words to review</p>
      <button class="retry" @click="fetchBestOptions">Try Again</button>
    </div>

    <div v-else-if="bestOptionsStore.error" class="center-state">
      <p class="err">{{ bestOptionsStore.error }}</p>
      <button class="retry" @click="fetchBestOptions">Retry</button>
    </div>

    <div v-else-if="!bestOptionsStore.currentBestOption" class="center-state">
      <p>No questions available</p>
      <button class="retry" @click="fetchBestOptions">Load</button>
    </div>

    <div v-else class="quiz">
      <div class="word-container">
        <button class="word" @click="toggleWordDropdown">
          {{ bestOptionsStore.currentBestOption.word.main }}
          <Icon :icon="showWordDropdown ? 'solar:alt-arrow-up-linear' : 'solar:alt-arrow-down-linear'" width="16" />
        </button>

        <!-- Word Dropdown -->
        <transition name="slideDown">
          <div v-if="showWordDropdown && wordDropdownData" class="word-dropdown">
            <p class="definition">{{ wordDropdownData.definition }}</p>
            <div v-if="wordDropdownData.synonyms.length > 0" class="synonyms">
              <span v-for="(syn, i) in wordDropdownData.synonyms.slice(0, 4)" :key="i" class="synonym-tag">
                {{ syn }}
              </span>
            </div>
            <div class="word-meta" style="display:none">
              <span class="label">WORD</span>
              <span class="level">LV.{{ wordDropdownData.level }}</span>
            </div>
          </div>
        </transition>
      </div>

      <p class="question">{{ bestOptionsStore.currentBestOption.question }}</p>

      <div class="options">
        <button
          v-for="(opt, i) in bestOptionsStore.currentBestOption.options"
          :key="i"
          :class="['opt', optionClass(i)]"
          @click="selectOption(i)"
          :disabled="showResult"
        >
          <span class="letter">{{ String.fromCharCode(65 + i) }}</span>
          <span class="text">{{ opt }}</span>
        </button>
      </div>

      <transition name="fade">
        <div v-if="showResult" :class="['result', isCorrect ? 'ok' : 'bad']">
          <Icon :icon="isCorrect ? 'solar:check-circle-bold' : 'solar:close-circle-bold'" width="16" />
          {{ isCorrect ? 'Correct' : 'Incorrect' }}
        </div>
      </transition>

      <div class="progress-bar">
        <div v-for="(_, i) in bestOptionsStore.bestOptions" :key="i" class="progress-dot"
          :class="{ active: i === bestOptionsStore.currentIndex, passed: i < bestOptionsStore.currentIndex }" />
      </div>

      <div class="nav">
        <button class="arrow" @click="prevBestOption" :disabled="!bestOptionsStore.canGoPrev">
          <Icon icon="solar:alt-arrow-left-linear" width="22" />
        </button>
        <button class="arrow" @click="nextBestOption" :disabled="bestOptionsStore.generating">
          <Icon v-if="bestOptionsStore.generating" icon="solar:refresh-circle-linear" width="22" class="spin" />
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

.center-state p {
  color: #9c99ab;
  font-size: 14px;
  margin: 0;
}

.center-state .err {
  color: #f87171;
}

.retry {
  padding: 8px 18px;
  border-radius: 10px;
  border: none;
  background: rgba(124, 58, 237, 0.2);
  color: #a78bfa;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.retry:hover {
  background: rgba(124, 58, 237, 0.3);
}

.spin {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.quiz {
  width: 100%;
  max-width: 480px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 0 15px;
}

.word-container {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.word {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 22px;
  border-radius: 999px;
  background: rgba(124, 58, 237, 0.12);
  border: 1px solid rgba(124, 58, 237, 0.25);
  color: #c4b5fd;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  /* transition: all 0.05s ease; */
  text-transform: capitalize;
}

.word:hover {
  background: rgba(124, 58, 237, 0.2);
  border-color: rgba(124, 58, 237, 0.4);
}

.word-dropdown {
  width: 100%;
  max-width: 320px;
  padding: 14px;
  background: rgba(45, 42, 65, 0.6);
  border: 1px solid rgba(124, 58, 237, 0.15);
  border-radius: 10px;
  box-shadow: inset 0 1px 2px rgba(255, 255, 255, 0.05);
}

.definition {
  margin: 0 0 10px 0;
  color: #d4d2e0;
  font-size: 17px;
  line-height: 1.4;
  font-weight: 400;
}

.synonyms {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.synonym-tag {
  display: inline-block;
  padding: 5px 10px;
  background: rgba(124, 58, 237, 0.08);
  border: 1px solid rgba(124, 58, 237, 0.15);
  border-radius: 16px;
  color: #9c99ab;
  font-size: 14px;
  font-weight: 400;
}

.word-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.label {
  color: #8b89a3;
  font-size: 10px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.level {
  margin-left: auto;
  color: #9c99ab;
  font-size: 11px;
  font-weight: 500;
}

.question {
  font-size: 22px;
  line-height: 1.45;
  color: #e2e0e8;
  text-align: center;
  margin: 0;
  padding: 0 4px;
}

.options {
  width: 100%;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.opt {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1.5px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: #b8b5c8;
  cursor: pointer;
  text-align: left;
  transition: all 0.18s ease;
}

.opt:hover:not(:disabled) {
  border-color: rgba(124, 58, 237, 0.4);
  background: rgba(124, 58, 237, 0.06);
  color: #e2e0e8;
}

.opt.selected {
  border-color: #7c3aed;
  background: rgba(124, 58, 237, 0.1);
  color: #e2e0e8;
}

.opt.correct {
  border-color: #4ade80;
  background: rgba(74, 222, 128, 0.1);
  color: #4ade80;
}

.opt.wrong {
  border-color: #f87171;
  background: rgba(248, 113, 113, 0.1);
  color: #f87171;
}

.opt.dimmed {
  opacity: 0.3;
}

.letter {
  width: 24px;
  height: 24px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: #9c99ab;
  flex-shrink: 0;
}

.opt.selected .letter {
  background: #7c3aed;
  color: white;
}

.opt.correct .letter {
  background: #4ade80;
  color: #064e3b;
}

.opt.wrong .letter {
  background: #f87171;
  color: #450a0a;
}

.text {
  font-size: 15px;
  line-height: 1.3;
}

.result {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
}

.result.ok {
  background: rgba(74, 222, 128, 0.12);
  color: #4ade80;
}

.result.bad {
  background: rgba(248, 113, 113, 0.12);
  color: #f87171;
}

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

.nav {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-top: 4px;
}

.arrow {
  width: 44px;
  height: 44px;
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

.arrow:hover:not(:disabled) {
  border-color: rgba(255, 255, 255, 0.3);
  color: #e2e0e8;
  background: rgba(255, 255, 255, 0.04);
}

.arrow:disabled {
  opacity: 0.25;
  cursor: not-allowed;
}

.fade-enter-active,
.fade-leave-active {
  transition: all 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(4px);
}

.slideDown-enter-active,
.slideDown-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.slideDown-enter-from {
  opacity: 0;
  transform: scaleY(0.8);
  transform-origin: top;
}

.slideDown-leave-to {
  opacity: 0;
  transform: scaleY(0.8);
  transform-origin: top;
}

@media (max-width: 768px) {
  .options {
    grid-template-columns: 1fr;
  }

  .question {
    font-size: 20px;
  }

  .word {
    font-size: 17px;
    padding: 8px 18px;
    margin-top: 50px;
  }

  .definition {
    font-size: 18px;
  }

  .synonym-tag {
    font-size: 16px;
  }
}
</style>
