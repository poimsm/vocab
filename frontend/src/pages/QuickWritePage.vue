<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Icon } from '@iconify/vue'
import { quickWriteApi, type QuickWriteExercise } from '@/services/quickWriteApi'
import { useActivityTracking } from '@/composables/useActivityTracking'
import { useAuthStore } from '@/stores/auth'

const { trackButtonClick } = useActivityTracking()
const authStore = useAuthStore()

// API base URL from environment
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost/api'

// SSE EventSource
let sseEventSource: EventSource | null = null
let sseActive = ref(false)

const writeMainRef = ref<HTMLElement | null>(null)

interface LocalResponse {
  id: number
  original_content: string
}

const prompts = ref<QuickWriteExercise[]>([])
const isLoading = ref(false)
const isLoadingMore = ref(false)
const loadError = ref('')
const isGenerating = ref(false)
const generateError = ref<string | null>(null)

const responses = ref<Map<number, LocalResponse>>(new Map())
const corrections = ref<Map<number, string>>(new Map())
const isSaving = ref(false)
const saveError = ref('')

const selectedPromptId = ref<number | null>(null)

// Scroll to top when opening a new prompt
watch(selectedPromptId, async (newId) => {
  if (newId !== null) {
    window.scrollTo(0, 0)
    await nextTick()
    await new Promise(resolve => setTimeout(resolve, 100))
    if (writeMainRef.value) {
      writeMainRef.value.scrollTop = 0
    }
  }
})
const currentInput = ref('')
const showError = ref(false)
const manuallyDismissedError = ref(false)
const revealedWords = ref<Set<string>>(new Set())
const hideMaskingEnabled = ref(false)
const isEditMode = ref(false)
const isMobile = ref(window.innerWidth < 768)

const currentPage = ref(1)
const totalPages = ref(1)
const ITEMS_PER_PAGE = 15
const showOnlyCompleted = ref(false)

// Load exercises on mount and setup
onMounted(async () => {
  const stored = localStorage.getItem('quickwrite-hide-masking')
  if (stored !== null) {
    hideMaskingEnabled.value = stored === 'true'
  }

  // Fetch exercises from backend
  await loadExercises()

  // Setup resize listener to detect mobile
  const handleResize = () => {
    isMobile.value = window.innerWidth < 768
  }
  window.addEventListener('resize', handleResize)
  window.addEventListener('scroll', handleWindowScroll)
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleWindowScroll)
  // Clean up SSE connection
  if (sseEventSource) {
    sseEventSource.close()
    sseEventSource = null
  }
})

// Save masking preference to localStorage
watch(hideMaskingEnabled, (newValue) => {
  localStorage.setItem('quickwrite-hide-masking', String(newValue))
})

// Load exercises from API
const loadExercises = async () => {
  isLoading.value = true
  loadError.value = ''
  try {
    const statusFilter = showOnlyCompleted.value ? 'completed' : 'all'
    const data = await quickWriteApi.getExercises(1, ITEMS_PER_PAGE, statusFilter)
    prompts.value = data.items
    totalPages.value = data.pages
    currentPage.value = 1

    // Populate responses and corrections from loaded data
    data.items.forEach(exercise => {
      if (exercise.original_content) {
        responses.value.set(exercise.id, {
          id: exercise.id,
          original_content: exercise.original_content
        })
      }
      if (exercise.corrected_content && exercise.has_corrections) {
        corrections.value.set(exercise.id, exercise.corrected_content)
      }
    })
  } catch (error) {
    loadError.value = 'Failed to load exercises'
    console.error('Error loading exercises:', error)
  } finally {
    isLoading.value = false
  }
}

const loadMoreExercises = async () => {
  if (isLoadingMore.value || currentPage.value >= totalPages.value) {
    return
  }

  isLoadingMore.value = true
  currentPage.value++

  try {
    const statusFilter = showOnlyCompleted.value ? 'completed' : 'all'
    const data = await quickWriteApi.getExercises(currentPage.value, ITEMS_PER_PAGE, statusFilter)
    prompts.value.push(...data.items)

    // Populate responses and corrections from loaded data
    data.items.forEach(exercise => {
      if (exercise.original_content) {
        responses.value.set(exercise.id, {
          id: exercise.id,
          original_content: exercise.original_content
        })
      }
      if (exercise.corrected_content && exercise.has_corrections) {
        corrections.value.set(exercise.id, exercise.corrected_content)
      }
    })
  } catch (error) {
    console.error('Error loading more exercises:', error)
    currentPage.value-- // Revert page number on error
  } finally {
    isLoadingMore.value = false
  }
}

const handleWindowScroll = () => {
  const scrollTop = window.scrollY
  const clientHeight = window.innerHeight
  const scrollHeight = document.documentElement.scrollHeight

  // Si está cerca del final (200px), cargar más
  if (scrollHeight - (scrollTop + clientHeight) < 200) {
    if (currentPage.value < totalPages.value && !isLoadingMore.value) {
      loadMoreExercises()
    }
  }
}

const toggleFilter = () => {
  trackButtonClick('toggle_quickwrite_filter', { show_only_completed: !showOnlyCompleted.value })
  showOnlyCompleted.value = !showOnlyCompleted.value
  currentPage.value = 1
  prompts.value = []
  responses.value.clear()
  corrections.value.clear()
  closeModal()
  loadExercises()
}

// ─── SSE (Server-Sent Events) para generación de ejercicios ───
function startSSE() {
  console.log('[startSSE] Starting SSE stream for quick write generation')
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
  const sseUrl = new URL(`${API_BASE}/quick-write/generate-stream`)
  if (authStore.token) {
    sseUrl.searchParams.append('token', authStore.token)
  }

  const fullUrl = sseUrl.toString()
  console.log('[startSSE] Conectando a:', fullUrl)

  try {
    sseEventSource = new EventSource(fullUrl)

    // ─── Evento: open (conexión establecida) ───
    sseEventSource.addEventListener('open', () => {
      console.log('[SSE:open] Conexión SSE establecida exitosamente')
    })

    // ─── Evento: quick_write.completed ───
    sseEventSource.addEventListener('quick_write.completed', async (event: MessageEvent) => {
      if (!sseActive.value) {
        console.log('[SSE:quick_write.completed] Stream disabled, ignoring event')
        return
      }

      try {
        const data = JSON.parse(event.data)
        console.log('[SSE:quick_write.completed] Ejercicios generados:', data)

        sseActive.value = false
        sseEventSource?.close()

        // Recargar ejercicios para obtener los datos actualizados
        currentPage.value = 1
        prompts.value = []
        responses.value.clear()
        corrections.value.clear()
        await loadExercises()

        // Poner en false solo después de que se recargan los ejercicios
        isGenerating.value = false
      } catch (e) {
        console.error('[SSE:quick_write.completed] Error parsing event:', e)
        isGenerating.value = false
      }
    })

    // ─── Evento: quick_write.failed ───
    sseEventSource.addEventListener('quick_write.failed', (event: MessageEvent) => {
      if (!sseActive.value) {
        console.log('[SSE:quick_write.failed] Stream disabled, ignoring event')
        return
      }

      try {
        const data = JSON.parse(event.data)
        console.error('[SSE:quick_write.failed] Error en generación:', data.message)
        generateError.value = data.message || 'Error generating exercises'
        sseActive.value = false
        sseEventSource?.close()
        isGenerating.value = false
      } catch (e) {
        console.error('[SSE:quick_write.failed] Error parsing event:', e)
        isGenerating.value = false
      }
    })

    sseEventSource.addEventListener('error', (event: Event) => {
      console.error('[SSE] Connection error:', event)
      if (sseEventSource?.readyState === EventSource.CLOSED) {
        console.log('[SSE] Connection closed')
        sseActive.value = false
      } else {
        console.error('[SSE] Unexpected error')
        generateError.value = 'Connection error - please try again'
        sseActive.value = false
        sseEventSource?.close()
      }
      isGenerating.value = false
    })
  } catch (e) {
    console.error('[startSSE] Error creating EventSource:', e)
    generateError.value = 'Failed to connect to stream'
  }
}

const generateMoreExercises = async () => {
  trackButtonClick('generate_quickwrite_exercises')
  isGenerating.value = true
  generateError.value = null

  try {
    const result = await quickWriteApi.generate()

    if (result.status === 'generating') {
      generateError.value = null
      // Start SSE to listen for generation completion
      // isGenerating will stay true until SSE receives the event and loads exercises
      startSSE()
    } else {
      generateError.value = 'Failed to generate exercises'
      isGenerating.value = false
    }
  } catch (err: any) {
    console.error('Error generating exercises:', err)
    generateError.value = err.message || 'Failed to generate exercises'
    isGenerating.value = false
  }
}

const selectedPrompt = computed(() => {
  if (!selectedPromptId.value) return null
  return prompts.value.find(p => p.id === selectedPromptId.value)
})

const hasCorrected = computed(() => {
  return selectedPromptId.value ? corrections.value.has(selectedPromptId.value) : false
})

const isComplete = computed(() => responses.value.size === prompts.value.length && prompts.value.length > 0)

const hasUsedWord = (text: string, promptId: number): boolean => {
  const prompt = prompts.value.find(p => p.id === promptId)
  if (!prompt || !prompt.words) return false
  const lowerText = text.toLowerCase()
  return prompt.words.some(word => lowerText.includes(word.toLowerCase()))
}

const openPrompt = (promptId: number) => {
  trackButtonClick('open_quickwrite_exercise', { exercise_id: promptId })
  const existing = responses.value.get(promptId)
  if (existing) {
    currentInput.value = existing.original_content
  } else {
    currentInput.value = ''
  }
  selectedPromptId.value = promptId
  showError.value = false
  saveError.value = ''
  manuallyDismissedError.value = false
  isEditMode.value = false
}

const closeModal = () => {
  selectedPromptId.value = null
  currentInput.value = ''
  showError.value = false
  saveError.value = ''
  manuallyDismissedError.value = false
  revealedWords.value.clear()
}

const dismissError = () => {
  manuallyDismissedError.value = true
}

const saveResponse = async () => {
  if (!selectedPromptId.value) return

  trackButtonClick('submit_quickwrite_response', { exercise_id: selectedPromptId.value })

  showError.value = false
  saveError.value = ''
  manuallyDismissedError.value = false

  if (!currentInput.value.trim()) {
    showError.value = true
    return
  }

  if (!hasUsedWord(currentInput.value, selectedPromptId.value)) {
    showError.value = true
    return
  }

  isSaving.value = true
  try {
    // Call API to save response (validates English and checks grammar)
    const result = await quickWriteApi.submitResponse(selectedPromptId.value, currentInput.value)

    // Update local state with the response
    responses.value.set(selectedPromptId.value, {
      id: result.id,
      original_content: result.original_content || ''
    })

    // Store corrections if any
    if (result.has_corrections && result.corrected_content) {
      corrections.value.set(selectedPromptId.value, result.corrected_content)
    }

    isEditMode.value = false
  } catch (error: any) {
    const errorMsg = error.response?.data?.detail || 'Failed to save response'
    saveError.value = errorMsg
    console.error('Error saving response:', error)
  } finally {
    isSaving.value = false
  }
}

const startEdit = () => {
  isEditMode.value = true
}

const restart = () => {
  responses.value.clear()
  corrections.value.clear()
  selectedPromptId.value = null
  currentInput.value = ''
  showError.value = false
  saveError.value = ''
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && e.ctrlKey) {
    saveResponse()
  }
  if (e.key === 'Escape') {
    closeModal()
  }
}

const getPromptResponse = (promptId: number) => {
  return responses.value.get(promptId)?.original_content || ''
}

const maskWord = (word: string): string => {
  // Si está desactivado, devolver la palabra completa
  if (!hideMaskingEnabled.value) return word

  if (revealedWords.value.has(word)) return word

  // Si es una expresión (contiene espacios), procesar palabra por palabra
  if (word.includes(' ')) {
    const words = word.split(' ')
    const maskedWords = words.map(w => maskSingleWord(w))
    return maskedWords.join(' ')
  }

  // Si es una palabra simple
  return maskSingleWord(word)
}

const maskSingleWord = (word: string): string => {
  const len = word.length

  // Determinar cuántas letras ocultar basado en longitud
  let hiddenCount = 0
  if (len <= 2) hiddenCount = 0
  else if (len <= 5) hiddenCount = 1
  else if (len <= 7) hiddenCount = 2
  else if (len <= 12) hiddenCount = 3
  else hiddenCount = 4

  // Generar hash consistente para esta palabra
  let hash = 0
  for (let i = 0; i < word.length; i++) {
    hash = ((hash << 5) - hash) + word.charCodeAt(i)
    hash = hash & hash
  }
  hash = Math.abs(hash)

  // Seleccionar posiciones aleatorias para ocultar
  const availablePositions = Array.from({ length: len }, (_, i) => i)
  const toHide = new Set<number>()

  for (let i = 0; i < hiddenCount && availablePositions.length > 0; i++) {
    const idx = (hash + i * 7) % availablePositions.length
    const pos = availablePositions[idx]
    if (pos !== undefined) {
      toHide.add(pos)
    }
    availablePositions.splice(idx, 1)
  }

  // Construir palabra con letras ocultas
  let result = ''
  for (let i = 0; i < len; i++) {
    result += toHide.has(i) ? '_' : word[i]
  }
  return result
}

const revealWord = (word: string, e: Event) => {
  e.stopPropagation()
  revealedWords.value.add(word)
}
</script>

<template>
  <div class="quick-write-view">
    <!-- List View (Grid of Prompts) -->
    <template v-if="!selectedPromptId">
      <!-- Empty State -->
      <div v-if="prompts.length === 0 && !isLoading" class="empty-state-container">
        <div class="empty-state">
          <Icon icon="fluent-emoji:smiling-face" width="48" />
          <p>Nothing here yet. Generate some to get started!</p>
          <transition name="fade">
            <div v-if="isGenerating" class="progress-bar-container">
              <div class="progress-bar"></div>
            </div>
          </transition>
          <button @click="generateMoreExercises" class="generate-btn" :disabled="isGenerating">
            <span v-if="isGenerating">Generating...</span>
            <span v-else>Generate</span>
          </button>
        </div>
      </div>

      <!-- Content with Prompts -->
      <div v-else class="prompts-container">
        <div class="header-section">
          <div class="header-left">
            <h1 class="title">Quick Write</h1>
            <p class="subtitle">{{ responses.size }}/{{ prompts.length }} completed</p>
          </div>
          <div class="header-buttons">
            <button class="generate-btn-header" @click="generateMoreExercises" :disabled="isGenerating" :title="isGenerating ? 'Generating...' : 'Generate more exercises'">
              <Icon icon="solar:bolt-linear" width="20" />
              <span v-if="!isGenerating">Generate</span>
              <span v-else class="spinner-small"></span>
            </button>
            <button class="toggle-masking" :class="{ active: hideMaskingEnabled }" @click="hideMaskingEnabled = !hideMaskingEnabled" :title="hideMaskingEnabled ? 'Disable masking' : 'Enable masking'">
              <Icon :icon="hideMaskingEnabled ? 'solar:eye-closed-linear' : 'solar:eye-linear'" width="20" />
              <span class="toggle-label">{{ hideMaskingEnabled ? 'Hidden' : 'Visible' }}</span>
            </button>
          </div>
        </div>

        <!-- Generate Error Alert -->
        <div v-if="generateError" class="generate-error-alert">
          <p>{{ generateError }}</p>
          <button @click="generateError = null" class="close-alert">
            <Icon icon="solar:close-linear" width="16" />
          </button>
        </div>

        <!-- Filter -->
        <div class="filter-section">
          <button
            class="filter-toggle"
            :class="{ active: showOnlyCompleted }"
            @click="toggleFilter"
            :title="showOnlyCompleted ? 'Showing completed exercises' : 'Showing all exercises'"
          >
            <Icon icon="solar:star-bold" width="16" />
            <span>{{ showOnlyCompleted ? 'Done' : 'Done' }}</span>
          </button>
        </div>

        <div class="progress-indicator" style="display:none">
          <div v-for="prompt in prompts" :key="prompt.id" class="progress-dot" :class="{ done: responses.has(prompt.id) }"></div>
        </div>

        <div class="prompts-grid">
          <div
            v-for="prompt in prompts"
            :key="prompt.id"
            class="prompt-card"
            :class="{ completed: responses.has(prompt.id) }"
            @click="openPrompt(prompt.id)"
          >
            <div class="card-top">
              <div class="emoji-badge">{{ prompt.emoji }}</div>
              <transition name="check">
                <Icon v-if="responses.has(prompt.id)" icon="solar:check-circle-bold" width="24" class="check-icon" />
              </transition>
            </div>

            <p class="card-text">{{ prompt.prompt }}</p>

            <div v-if="prompt.words && prompt.words.length > 0" class="words-chips">
              <div v-for="word in prompt.words" :key="word" class="chip-wrapper">
                <span class="chip">{{ maskWord(word) }}</span>
                <button v-if="hideMaskingEnabled && !revealedWords.has(word)" class="reveal-btn" @click="revealWord(word, $event)" style="display:none">
                  <Icon icon="solar:lightbulb-linear" width="14" />
                </button>
                <span v-else-if="hideMaskingEnabled && revealedWords.has(word)" class="revealed-indicator">✓</span>
              </div>
            </div>

            <div v-if="responses.has(prompt.id)" class="card-preview">
              {{ getPromptResponse(prompt.id).substring(0, 60) }}...
            </div>
          </div>

          <!-- Loading More Indicator -->
          <div v-if="isLoadingMore" class="loading-more">
            <div class="spinner-small"></div>
            <p>Loading more...</p>
          </div>
        </div>
      </div>
    </template>

    <!-- Fullscreen Writing View -->
    <transition name="fade">
      <div v-if="selectedPromptId" class="fullscreen-write-view">
        <!-- Header with close button -->
        <div class="write-header">
          <div class="write-emoji">{{ selectedPrompt?.emoji }}</div>
          <button class="write-close" @click="closeModal" title="Go back">
            <Icon icon="solar:arrow-left-linear" width="24" />
          </button>
        </div>

        <!-- Main content area -->
        <div class="write-main" ref="writeMainRef">
          <!-- Prompt title -->
          <h2 class="write-prompt-title">{{ selectedPrompt?.prompt }}</h2>

          <!-- Words to use -->
          <div v-if="selectedPrompt?.words && selectedPrompt.words.length > 0" class="write-words">
            <p class="write-words-label">👉 Must use these words:</p>
            <div class="write-words-list">
              <div v-for="word in selectedPrompt.words" :key="word" class="write-word-badge">
                <span>{{ maskWord(word) }}</span>
                <button v-if="hideMaskingEnabled && !revealedWords.has(word)" class="reveal-btn-write" @click="revealWord(word, $event)" title="Reveal">
                  <Icon icon="solar:lightbulb-linear" width="16" />
                </button>
                <span v-else-if="hideMaskingEnabled && revealedWords.has(word)" class="revealed-check">✓</span>
              </div>
            </div>
          </div>

          <!-- AI Feedback Section (if corrections exist) -->
          <div v-if="hasCorrected && !isEditMode" class="ai-feedback-section">
            <div class="feedback-header">
              <Icon icon="solar:bulb-bold" width="18" />
              <span>AI Feedback</span>
            </div>

            <div class="feedback-before">
              <p class="feedback-label">Your response:</p>
              <p class="feedback-text original-text">{{ currentInput }}</p>
            </div>

            <div class="feedback-arrow">
              <Icon icon="solar:arrow-down-linear" width="20" />
            </div>

            <div class="feedback-after">
              <p class="feedback-label">Improved:</p>
              <p class="feedback-text improved-text">{{ corrections.get(selectedPromptId) }}</p>
            </div>

            <button class="edit-btn-write" @click="startEdit">
              <Icon icon="solar:pen-2-linear" width="18" />
              Edit Response
            </button>
          </div>

          <!-- Writing area -->
          <div v-if="!hasCorrected || isEditMode" class="write-textarea-wrapper">
            <textarea
              v-model="currentInput"
              class="write-textarea"
              placeholder="Start writing..."
              @keydown="handleKeydown"
              :disabled="isSaving"
            ></textarea>

          </div>

          <!-- Floating Action Button -->
          <div class="floating-fab-container">
            <!-- Error notification -->
            <transition name="fade">
              <div v-if="(showError || saveError) && !manuallyDismissedError" class="fab-error-badge">
                <Icon icon="solar:info-circle-linear" width="16" />
                <span>{{ saveError || 'Use at least one word above' }}</span>
                <button class="fab-error-close" @click="dismissError" type="button" title="Dismiss">
                  <Icon icon="solar:close-circle-linear" width="16" />
                </button>
              </div>
            </transition>

            <button v-if="!hasCorrected || isEditMode" class="floating-action-btn" @click="saveResponse" :disabled="!currentInput.trim() || isSaving" :title="isSaving ? 'Checking with AI...' : 'Check with AI'">
              <Icon v-if="!isSaving" icon="solar:check-circle-bold" width="28" />
              <span v-else class="spinner-fab"></span>
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.quick-write-view {
  max-width: 900px;
  margin: 0 auto;
  padding: 40px 20px;
  color: #e2e0e8;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  min-height: 100vh;
}

.header-section {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 32px;
  gap: 20px;
}

.header-left {
  text-align: center;
  flex: 1;
}

.header-buttons {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.title {
  font-size: 32px;
  font-weight: 700;
  color: #e2e0e8;
  margin: 0 0 8px 0;
}

.subtitle {
  font-size: 14px;
  color: #9c99ab;
  margin: 0;
}

.generate-btn-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 10px;
  border: 1px solid rgba(167, 139, 250, 0.4);
  background: rgba(167, 139, 250, 0.1);
  color: #a78bfa;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
  flex-shrink: 0;
}

.generate-btn-header:hover:not(:disabled) {
  background: rgba(167, 139, 250, 0.2);
  border-color: rgba(167, 139, 250, 0.6);
}

.generate-btn-header:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.toggle-masking {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.05);
  color: #9c99ab;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  flex-shrink: 0;
}

.toggle-masking:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
  color: #e2e0e8;
}

.toggle-label {
  display: none;
}

.spinner-small {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(167, 139, 250, 0.3);
  border-top-color: #a78bfa;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  display: inline-block;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.generate-error-alert {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-radius: 8px;
  background: rgba(255, 100, 100, 0.1);
  border: 1px solid rgba(255, 100, 100, 0.2);
  margin-bottom: 16px;
}

.generate-error-alert p {
  margin: 0;
  font-size: 14px;
  color: #ff6464;
}

.close-alert {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: #ff6464;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.close-alert:hover {
  color: #ff8888;
}

.loading-more {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 24px;
  color: #9c99ab;
  font-size: 14px;
  grid-column: 1 / -1;
}

.loading-more p {
  margin: 0;
}

.filter-section {
  margin-bottom: 12px;
  flex-shrink: 0;
}

.filter-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.05);
  color: #9c99ab;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.filter-toggle:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
}

.filter-toggle.active {
  background: rgba(167, 139, 250, 0.15);
  border-color: rgba(167, 139, 250, 0.4);
  color: #a78bfa;
}

.progress-indicator {
  display: flex;
  gap: 8px;
  justify-content: center;
  margin-bottom: 32px;
}

.empty-state-container {
  display: flex;
  justify-content: center;
}

.empty-state {
  padding: 48px 36px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  width: 100%;
  max-width: 600px;
}

.empty-state p {
  font-size: 16px;
  color: #9c99ab;
  margin: 0;
}

.progress-bar-container {
  width: 100%;
  height: 4px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 2px;
  overflow: hidden;
  margin: 8px 0;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #a78bfa, #c4b5fd, #a78bfa);
  border-radius: 2px;
  animation: progressAnimation 1.5s ease-in-out infinite;
}

@keyframes progressAnimation {
  0% {
    transform: translateX(-100%);
  }
  50% {
    transform: translateX(100%);
  }
  100% {
    transform: translateX(-100%);
  }
}

.generate-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-radius: 8px;
  border: 1px solid rgba(167, 139, 250, 0.4);
  background: rgba(167, 139, 250, 0.1);
  color: #a78bfa;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.generate-btn:hover:not(:disabled) {
  background: rgba(167, 139, 250, 0.2);
  border-color: rgba(167, 139, 250, 0.6);
}

.generate-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .header-section {
    flex-direction: column;
    align-items: center;
  }

  .header-left {
    width: 100%;
  }

  .header-buttons {
    width: 100%;
    flex-direction: column;
  }

  .generate-btn-header {
    width: 100%;
    justify-content: center;
    font-size: 15px;
  }

  .toggle-masking {
    width: 100%;
    justify-content: center;
    font-size: 15px;
  }

  .toggle-label {
    display: inline;
  }

  .progress-indicator {
    margin-bottom: 0;
  }

  .empty-state {
    padding: 32px 24px;
  }
}


.progress-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  transition: all 0.2s ease;
}

.progress-dot.done {
  background: #7c3aed;
  width: 10px;
  height: 10px;
}

.prompts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
}

.prompt-card {
  padding: 20px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: relative;
}

.prompt-card:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(124, 58, 237, 0.3);
  transform: translateY(-2px);
}

.prompt-card.completed {
  background: rgba(124, 58, 237, 0.1);
  border-color: rgba(124, 58, 237, 0.25);
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.emoji-badge {
  font-size: 32px;
}

.check-icon {
  color: #7c3aed;
}

.card-text {
  font-size: 15px;
  font-weight: 600;
  color: #e2e0e8;
  margin: 0;
  line-height: 1.4;
}

.words-chips {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.chip-wrapper {
  display: flex;
  align-items: center;
  gap: 4px;
  position: relative;
}

.chip {
  font-size: 11px;
  padding: 3px 8px;
  background: rgba(124, 58, 237, 0.15);
  color: #c4b5fd;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  letter-spacing: 1px;
  cursor: default;
  user-select: none;
}

.reveal-btn {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 3px;
  border: 1px solid rgba(124, 58, 237, 0.3);
  background: rgba(124, 58, 237, 0.1);
  color: #c4b5fd;
  cursor: pointer;
  transition: all 0.2s ease;
  padding: 0;
}

.reveal-btn:hover {
  background: rgba(124, 58, 237, 0.25);
  border-color: rgba(124, 58, 237, 0.5);
  transform: scale(1.1);
}

.revealed-indicator {
  font-size: 11px;
  color: #22c55e;
  font-weight: 700;
}

.card-preview {
  font-size: 12px;
  color: #9c99ab;
  font-style: italic;
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

/* ─── Fullscreen Writing View ─── */
.fullscreen-write-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: inherit;
}

.write-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 30px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  flex-shrink: 0;
  background: inherit;
  z-index: 10;
}

.write-emoji {
  font-size: 36px;
}

.write-close {
  background: transparent;
  border: none;
  color: #9c99ab;
  cursor: pointer;
  transition: all 0.2s ease;
  padding: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.write-close:hover {
  color: #e2e0e8;
  transform: scale(1.1);
}

.write-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 40px 30px;
  gap: 28px;
}

.write-main::-webkit-scrollbar {
  width: 6px;
}

.write-main::-webkit-scrollbar-track {
  background: transparent;
}

.write-main::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
}

.write-prompt-title {
  font-size: 32px;
  font-weight: 600;
  color: #e2e0e8;
  margin: 0;
  line-height: 1.4;
  max-width: 600px;
}

.write-words {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.write-words-label {
  font-size: 12px;
  font-weight: 600;
  color: #9c99ab;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0;
}

.write-words-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.write-word-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: rgba(124, 58, 237, 0.15);
  color: #a78bfa;
  font-size: 15px;
  font-weight: 600;
  border-radius: 8px;
  font-family: 'Courier New', monospace;
  letter-spacing: 0.5px;
  border: 1px solid rgba(124, 58, 237, 0.3);
  cursor: default;
  user-select: none;
}

.reveal-btn-write {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  border: 1px solid rgba(124, 58, 237, 0.3);
  background: rgba(124, 58, 237, 0.1);
  color: #c4b5fd;
  cursor: pointer;
  transition: all 0.2s ease;
  padding: 0;
  flex-shrink: 0;
}

.reveal-btn-write:hover {
  background: rgba(124, 58, 237, 0.25);
  border-color: rgba(124, 58, 237, 0.5);
  transform: scale(1.1);
}

.revealed-check {
  font-size: 14px;
  color: #22c55e;
  font-weight: 700;
}

/* Textarea wrapper and styling */
.write-textarea-wrapper {
  display: flex;
  flex-direction: column;
  flex: 1;
  gap: 16px;
}

.write-textarea {
  flex: 1;
  padding: 0;
  background: transparent;
  color: #e2e0e8;
  font-size: 17px;
  font-family: inherit;
  border: none;
  outline: none;
  resize: none;
  font-weight: 400;
  line-height: 1.6;
  min-height: 300px;
  overflow-y: auto;
  scrollbar-width: none;
}

.write-textarea::-webkit-scrollbar {
  display: none;
}

.write-textarea::placeholder {
  color: rgba(156, 153, 171, 0.5);
}

.write-textarea:focus {
  outline: none;
}

.write-error {
  font-size: 13px;
  color: #f87171;
  margin: 0;
  padding: 8px 0;
}

/* Floating Action Button */
.floating-fab-container {
  position: fixed;
  bottom: 30px;
  right: 30px;
  z-index: 100;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
}

.fab-error-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 10px 10px 14px;
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  color: #fca5a5;
  font-size: 13px;
  font-weight: 500;
  animation: slideInUp 0.3s ease;
}

.fab-error-badge svg {
  flex-shrink: 0;
}

.fab-error-close {
  background: transparent;
  border: none;
  color: #fca5a5;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
  margin-left: 4px;
}

.fab-error-close:hover {
  color: #ff8a80;
  transform: scale(1.15);
}

.fab-error-close:active {
  transform: scale(0.9);
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.floating-action-btn {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: none;
  background: #7c3aed;
  color: white;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  /* box-shadow: 0 8px 24px rgba(124, 58, 237, 0.4); */
}

.floating-action-btn:hover:not(:disabled) {
  background: #6d28d9;
  transform: scale(1.1);
  /* box-shadow: 0 12px 32px rgba(124, 58, 237, 0.6); */
}

.floating-action-btn:active:not(:disabled) {
  transform: scale(0.95);
}

.floating-action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.spinner-fab {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  display: inline-block;
}

/* AI Feedback Section */
.ai-feedback-section {
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.2);
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin: 12px 0;
}

.feedback-header {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #22c55e;
  font-size: 14px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0;
}

.feedback-before,
.feedback-after {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.feedback-label {
  font-size: 12px;
  color: #9c99ab;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0;
  font-weight: 600;
}

.feedback-text {
  padding: 12px 14px;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.6;
  margin: 0;
}

.original-text {
  background: rgba(239, 68, 68, 0.1);
  color: #fca5a5;
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.improved-text {
  background: rgba(34, 197, 94, 0.1);
  color: #86efac;
  border: 1px solid rgba(34, 197, 94, 0.2);
}

.feedback-arrow {
  display: flex;
  justify-content: center;
  color: #22c55e;
  opacity: 0.5;
}

.edit-btn-write {
  width: 100%;
  padding: 12px;
  border-radius: 8px;
  border: none;
  background: #7c3aed;
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 8px;
}

.edit-btn-write:hover {
  background: #6d28d9;
}

.modal-input::placeholder {
  color: #9c99ab;
}



/* ─── Transitions ─── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.check-enter-active {
  transition: all 0.3s ease;
}

.check-enter-from {
  opacity: 0;
  transform: scale(0);
}

@media (max-width: 768px) {
  .quick-write-view {
    padding: 24px 16px;
  }

  .title {
    font-size: 24px;
  }

  .prompts-grid {
    grid-template-columns: 1fr;
  }

  .write-main {
    padding: 20px 16px;
    gap: 20px;
    overflow-y: auto;
  }

  .write-prompt-title {
    font-size: 26px;
  }

  .write-header {
    padding: 16px 16px;
  }

  .write-emoji {
    font-size: 32px;
  }

  .write-words-label {
    font-size: 13px;
  }

  .write-word-badge {
    font-size: 15px;
    padding: 8px 12px;
  }

  .card-text {
    font-size: 19px;
  }

  .chip {
    font-size: 17px;
  }

  .card-preview {
    font-size: 18px;
  }

  .write-textarea {
    font-size: 17px;
    min-height: 350px;
  }

  .floating-fab-container {
    bottom: 20px;
    right: 20px;
  }

  .floating-action-btn {
    width: 52px;
    height: 52px;
  }

  .fab-error-badge {
    font-size: 12px;
    padding: 10px 8px 10px 12px;
    gap: 6px;
  }

  .fab-error-close {
    padding: 6px;
  }

  .feedback-text {
    font-size: 14px;
  }

  .feedback-label {
    font-size: 12px;
  }
}
</style>
