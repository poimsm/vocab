<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { quickWriteApi, type QuickWriteExercise } from '@/services/quickWriteApi'

interface LocalResponse {
  id: number
  original_content: string
}

const prompts = ref<QuickWriteExercise[]>([])
const isLoading = ref(false)
const loadError = ref('')

const responses = ref<Map<number, LocalResponse>>(new Map())
const corrections = ref<Map<number, string>>(new Map())
const isSaving = ref(false)
const saveError = ref('')

const selectedPromptId = ref<number | null>(null)
const currentInput = ref('')
const showError = ref(false)
const revealedWords = ref<Set<string>>(new Set())
const hideMaskingEnabled = ref(false)
const isEditMode = ref(false)
const isMobile = ref(window.innerWidth < 768)

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
    const data = await quickWriteApi.getExercises(1, 100)
    prompts.value = data.items

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
  const existing = responses.value.get(promptId)
  if (existing) {
    currentInput.value = existing.original_content
  } else {
    currentInput.value = ''
  }
  selectedPromptId.value = promptId
  showError.value = false
  saveError.value = ''
  isEditMode.value = false
}

const closeModal = () => {
  selectedPromptId.value = null
  currentInput.value = ''
  showError.value = false
  saveError.value = ''
  revealedWords.value.clear()
}

const saveResponse = async () => {
  if (!selectedPromptId.value) return

  showError.value = false
  saveError.value = ''

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
    <!-- Complete Screen -->
    <transition name="fade">
      <div v-if="isComplete" class="complete-overlay">
        <div class="complete-card">
          <div class="complete-header">
            <Icon icon="solar:star-bold" width="52" />
            <h2>All Done!</h2>
          </div>

          <div class="responses-grid">
            <div v-for="prompt in prompts" :key="prompt.id" class="response-card">
              <div class="card-emoji">{{ prompt.emoji }}</div>
              <p class="card-prompt">{{ prompt.prompt }}</p>
              <p class="card-response">{{ getPromptResponse(prompt.id) }}</p>
            </div>
          </div>

          <button class="restart-btn" @click="restart">
            <Icon icon="solar:restart-bold" width="18" />
            Start Over
          </button>
        </div>
      </div>
    </transition>

    <!-- Prompts Grid -->
    <div v-if="!isComplete" class="prompts-container">
      <div class="header-section">
        <div class="header-left">
          <h1 class="title">Quick Write</h1>
          <p class="subtitle">{{ responses.size }}/{{ prompts.length }} completed</p>
        </div>
        <button class="toggle-masking" :class="{ active: hideMaskingEnabled }" @click="hideMaskingEnabled = !hideMaskingEnabled" :title="hideMaskingEnabled ? 'Disable masking' : 'Enable masking'">
          <Icon :icon="hideMaskingEnabled ? 'solar:eye-closed-linear' : 'solar:eye-linear'" width="20" />
          <span class="toggle-label">{{ hideMaskingEnabled ? 'Hidden' : 'Visible' }}</span>
        </button>
      </div>

      <div class="progress-indicator">
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
              <button v-if="hideMaskingEnabled && !revealedWords.has(word)" class="reveal-btn" @click="revealWord(word, $event)">
                <Icon icon="solar:lightbulb-linear" width="14" />
              </button>
              <span v-else-if="hideMaskingEnabled && revealedWords.has(word)" class="revealed-indicator">✓</span>
            </div>
          </div>

          <div v-if="responses.has(prompt.id)" class="card-preview">
            {{ getPromptResponse(prompt.id).substring(0, 60) }}...
          </div>
        </div>
      </div>
    </div>

    <!-- Mobile Fullscreen View -->
    <transition name="slide-up">
      <div v-if="isMobile && selectedPromptId" class="mobile-fullscreen">
        <div class="mobile-header">
          <div class="mobile-emoji">{{ selectedPrompt?.emoji }}</div>
          <button class="mobile-close" @click="closeModal">
            <Icon icon="solar:close-circle-linear" width="28" />
          </button>
        </div>

        <div class="mobile-content">
          <h3 class="mobile-title">{{ selectedPrompt?.prompt }}</h3>

          <div v-if="selectedPrompt?.words && selectedPrompt.words.length > 0" class="mobile-words">
            <div v-for="word in selectedPrompt.words" :key="word" class="word-badge-wrapper">
              <span class="word-badge">{{ maskWord(word) }}</span>
              <button v-if="hideMaskingEnabled && !revealedWords.has(word)" class="reveal-btn-modal" @click="revealWord(word, $event)">
                <Icon icon="solar:lightbulb-linear" width="16" />
              </button>
              <span v-else-if="hideMaskingEnabled && revealedWords.has(word)" class="revealed-badge">✓</span>
            </div>
          </div>

          <!-- AI Corrections Section -->
          <div v-if="hasCorrected && !isEditMode" class="corrections-section">
            <div class="corrections-header">
              <Icon icon="solar:bulb-bold" width="18" />
              <span>AI Feedback</span>
            </div>

            <div class="before-after">
              <div class="text-block">
                <p class="label">Your response:</p>
                <p class="text original">{{ currentInput }}</p>
              </div>

              <div class="arrow">
                <Icon icon="solar:arrow-down-linear" width="20" />
              </div>

              <div class="text-block">
                <p class="label">Improved:</p>
                <p class="text improved">{{ corrections.get(selectedPromptId) }}</p>
              </div>
            </div>

            <button class="edit-btn" @click="startEdit">
              <Icon icon="solar:pen-2-linear" width="18" />
              Edit Response
            </button>
          </div>

          <!-- Write/Edit Section -->
          <div v-if="!hasCorrected || isEditMode" class="write-section">
            <textarea
              v-model="currentInput"
              class="mobile-input"
              placeholder="Write your response..."
              @keydown="handleKeydown"
              rows="4"
              :disabled="isSaving"
            ></textarea>

            <div v-if="showError" class="error-msg">
              Use at least one word above
            </div>

            <div v-if="saveError" class="error-msg">
              {{ saveError }}
            </div>

            <button class="save-btn" @click="saveResponse" :disabled="!currentInput.trim() || isSaving">
              {{ isSaving ? 'Saving...' : 'Save Response' }}
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- Modal (Desktop) -->
    <transition name="modal">
      <div v-if="!isMobile && selectedPromptId" class="modal-overlay" @mousedown.self="closeModal">
        <div class="modal-card" @mousedown.stop @mouseup.stop>
          <div class="modal-header">
            <div class="modal-emoji">{{ selectedPrompt?.emoji }}</div>
            <button class="modal-close" @click="closeModal">
              <Icon icon="solar:close-circle-linear" width="24" />
            </button>
          </div>

          <h3 class="modal-title">{{ selectedPrompt?.prompt }}</h3>

          <div v-if="selectedPrompt?.words && selectedPrompt.words.length > 0" class="modal-words">
            <div v-for="word in selectedPrompt.words" :key="word" class="word-badge-wrapper">
              <span class="word-badge">{{ maskWord(word) }}</span>
              <button v-if="hideMaskingEnabled && !revealedWords.has(word)" class="reveal-btn-modal" @click="revealWord(word, $event)">
                <Icon icon="solar:lightbulb-linear" width="16" />
              </button>
              <span v-else-if="hideMaskingEnabled && revealedWords.has(word)" class="revealed-badge">✓</span>
            </div>
          </div>

          <!-- AI Corrections Section -->
          <div v-if="hasCorrected && !isEditMode" class="corrections-section">
            <div class="corrections-header">
              <Icon icon="solar:bulb-bold" width="18" />
              <span>AI Feedback</span>
            </div>

            <div class="before-after">
              <div class="text-block">
                <p class="label">Your response:</p>
                <p class="text original">{{ currentInput }}</p>
              </div>

              <div class="arrow">
                <Icon icon="solar:arrow-down-linear" width="20" />
              </div>

              <div class="text-block">
                <p class="label">Improved:</p>
                <p class="text improved">{{ corrections.get(selectedPromptId) }}</p>
              </div>
            </div>

            <button class="edit-btn" @click="startEdit">
              <Icon icon="solar:pen-2-linear" width="18" />
              Edit Response
            </button>
          </div>

          <!-- Write/Edit Section -->
          <div v-if="!hasCorrected || isEditMode" class="write-section">
            <textarea
              v-model="currentInput"
              class="modal-input"
              placeholder="Write your response..."
              @keydown="handleKeydown"
              rows="4"
              :disabled="isSaving"
            ></textarea>

            <div v-if="showError" class="error-msg">
              Use at least one word above
            </div>

            <div v-if="saveError" class="error-msg">
              {{ saveError }}
            </div>

            <button class="save-btn" @click="saveResponse" :disabled="!currentInput.trim() || isSaving">
              {{ isSaving ? 'Saving...' : 'Save Response' }}
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

@media (max-width: 768px) {
  .header-section {
    flex-direction: column;
    align-items: center;
  }  

  .header-left {
    width: 100%;
  }

  .toggle-masking {
    width: 100%;
    justify-content: center;
  }

  .toggle-label {
    display: inline;
  }
}

.progress-indicator {
  display: flex;
  gap: 8px;
  justify-content: center;
  margin-bottom: 32px;
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

/* ─── Modal ─── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
  backdrop-filter: blur(4px);
}

.modal-card {
  background: #36324a;
  border-radius: 16px;
  padding: 28px;
  max-width: 500px;
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.modal-emoji {
  font-size: 40px;
}

.modal-close {
  background: transparent;
  border: none;
  color: #9c99ab;
  cursor: pointer;
  transition: all 0.2s ease;
}

.modal-close:hover {
  color: #e2e0e8;
}

.modal-title {
  font-size: 20px;
  font-weight: 600;
  color: #e2e0e8;
  margin: 0 0 16px 0;
}

.modal-words {
  display: flex;
  gap: 6px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.word-badge-wrapper {
  display: flex;
  align-items: center;
  gap: 6px;
}

.word-badge {
  padding: 6px 12px;
  background: rgba(124, 58, 237, 0.15);
  color: #c4b5fd;
  font-size: 12px;
  font-weight: 600;
  border-radius: 6px;
  border: 1px solid rgba(124, 58, 237, 0.25);
  font-family: 'Courier New', monospace;
  letter-spacing: 1px;
  cursor: default;
  user-select: none;
}

.reveal-btn-modal {
  width: 22px;
  height: 22px;
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

.reveal-btn-modal:hover {
  background: rgba(124, 58, 237, 0.25);
  border-color: rgba(124, 58, 237, 0.5);
  transform: scale(1.15);
}

.revealed-badge {
  font-size: 13px;
  color: #22c55e;
  font-weight: 700;
}

.write-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.modal-input {
  width: 100%;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #e2e0e8;
  font-size: 14.5px;
  font-family: inherit;
  resize: none;
  box-sizing: border-box;
  outline: none;
  transition: all 0.2s ease;
}

.modal-input:focus {
  border-color: rgba(124, 58, 237, 0.4);
  background: rgba(255, 255, 255, 0.06);
}

.modal-input::placeholder {
  color: #9c99ab;
}

.error-msg {
  font-size: 12px;
  color: #f87171;
}

.save-btn {
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
}

.save-btn:hover:not(:disabled) {
  background: #6d28d9;
}

.save-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ─── Corrections ─── */
.corrections-section {
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.2);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.corrections-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  color: #22c55e;
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
}

.before-after {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.text-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.label {
  font-size: 11px;
  color: #9c99ab;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0;
  font-weight: 600;
}

.text {
  padding: 10px;
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.5;
  margin: 0;
}

.text.original {
  background: rgba(239, 68, 68, 0.1);
  color: #fca5a5;
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.text.improved {
  background: rgba(34, 197, 94, 0.1);
  color: #86efac;
  border: 1px solid rgba(34, 197, 94, 0.2);
}

.arrow {
  display: flex;
  justify-content: center;
  color: #22c55e;
  opacity: 0.6;
}

.edit-btn {
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
  gap: 6px;
  margin-top: 12px;
}

.edit-btn:hover {
  background: #6d28d9;
}

/* ─── Complete Screen ─── */
.complete-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
  padding: 20px;
  backdrop-filter: blur(4px);
}

.complete-card {
  background: #36324a;
  border-radius: 16px;
  padding: 32px;
  max-width: 600px;
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.08);
  max-height: 90vh;
  overflow-y: auto;
}

.complete-header {
  text-align: center;
  margin-bottom: 28px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #fbbf24;
}

.complete-header h2 {
  font-size: 28px;
  font-weight: 700;
  color: #e2e0e8;
  margin: 0;
}

.responses-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.response-card {
  padding: 14px;
  background: rgba(124, 58, 237, 0.08);
  border-radius: 8px;
  border: 1px solid rgba(124, 58, 237, 0.15);
}

.card-emoji {
  font-size: 24px;
  margin-bottom: 6px;
}

.card-prompt {
  font-size: 12px;
  font-weight: 600;
  color: #a78bfa;
  margin: 0 0 6px 0;
}

.card-response {
  font-size: 12px;
  color: #b8b5c8;
  margin: 0;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.restart-btn {
  width: 100%;
  padding: 12px;
  border-radius: 8px;
  border: none;
  background: #7c3aed;
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.2s ease;
}

.restart-btn:hover {
  background: #6d28d9;
}

/* ─── Mobile Fullscreen ─── */
.mobile-fullscreen {
  position: fixed;
  inset: 0;
  background: #1f1b2e;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.mobile-header {
  position: sticky;
  top: 0;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 20px 20px;
  background: #1f1b2e;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  z-index: 10;
  gap: 12px;
}

.mobile-emoji {
  font-size: 44px;
  flex-shrink: 0;
}

.mobile-close {
  background: transparent;
  border: none;
  color: #9c99ab;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mobile-close:active {
  color: #e2e0e8;
  transform: scale(0.9);
}

.mobile-content {
  flex: 1;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.mobile-title {
  font-size: 22px;
  font-weight: 600;
  color: #e2e0e8;
  margin: 0;
  line-height: 1.4;
}

.mobile-words {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.mobile-input {
  width: 100%;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #e2e0e8;
  font-size: 15px;
  font-family: inherit;
  resize: none;
  box-sizing: border-box;
  outline: none;
  transition: all 0.2s ease;
}

.mobile-input:focus {
  border-color: rgba(124, 58, 237, 0.4);
  background: rgba(255, 255, 255, 0.06);
}

.mobile-input::placeholder {
  color: #9c99ab;
}

/* ─── Transitions ─── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateY(100%);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.modal-enter-active,
.modal-leave-active {
  transition: all 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
  transform: scale(0.95);
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

  .responses-grid {
    grid-template-columns: 1fr;
  }

  .modal-card {
    padding: 20px;
  }

  .complete-card {
    padding: 20px;
  }

  .label {
    font-size: 16px;
  }

  .text {
    font-size: 18.7px;
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

  .mobile-input {
    font-size: 19px;
  }

  .word-badge {
    font-size: 18px;
  }

  .save-btn {
    font-size: 17.5px;
  }

  .edit-btn {
    font-size: 17.5px;
  }
}
</style>
