<script setup lang="ts">
import { ref, computed } from 'vue'
import { Icon } from '@iconify/vue'
import { wordApi } from '@/services/wordApi'

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
  type?: string
  created_at?: string
  total_examples?: number
  explanation?: string
}

interface Props {
  word: WordDetail | null
}

interface Emits {
  (e: 'close'): void
  (e: 'speak'): void
  (e: 'toggle-favorite'): void
  (e: 'toggle-known'): void
  (e: 'delete'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Explanation state
const showExplanation = ref(false)
const isExplaining = ref(false)

// Color helpers
const levelColor = (level: string | number) => {
  const s = typeof level === 'number' ? String(level) : (level || '').toString().toLowerCase()
  if (s === '1' || s === 'beginner') return '#4ade80'
  if (s === '2' || s === 'intermediate') return '#60a5fa'
  if (s === '3' || s === 'advanced') return '#f472b6'
  return '#9c99ab'
}

const levelLabel = (level: string | number) => {
  if (level === 1) return 'Beginner'
  if (level === 2) return 'Intermediate'
  if (level === 3) return 'Advanced'
  const s = (level || '').toString().toLowerCase()
  if (s === 'beginner') return 'Beginner'
  if (s === 'intermediate') return 'Intermediate'
  if (s === 'advanced') return 'Advanced'
  return level?.toString() || '—'
}

const frequencyColor = (freq: string) => {
  switch (freq) {
    case 'rare': return '#4ade80'
    case 'uncommon': return '#60a5fa'
    case 'common': return '#a78bfa'
    default: return '#9c99ab'
  }
}

const frequencyLabel = (freq: string) => {
  if (!freq) return ''
  return freq.charAt(0).toUpperCase() + freq.slice(1)
}

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

async function getAIExplanation() {
  if (!props.word) return

  isExplaining.value = true
  try {
    const result = await wordApi.getWordExplanation(props.word.id)
    if (props.word) {
      props.word.explanation = result.explanation
    }
  } catch (err) {
    console.error('Error getting explanation:', err)
  } finally {
    isExplaining.value = false
  }
}

function toggleExplanation() {
  if (!showExplanation.value && !props.word?.explanation) {
    getAIExplanation()
  }
  showExplanation.value = !showExplanation.value
}

function handleClose() {
  showExplanation.value = false
  emit('close')
}

function handleSpeak() {
  if (props.word) {
    speak(props.word.word)
    emit('speak')
  }
}

function handleToggleFavorite() {
  emit('toggle-favorite')
}

function handleToggleKnown() {
  emit('toggle-known')
}

function handleDelete() {
  emit('delete')
}

const formattedDate = computed(() => {
  if (!props.word?.created_at) return '—'
  return new Date(props.word.created_at).toLocaleDateString()
})
</script>

<template>
  <transition name="slide-panel">
    <aside v-if="word" class="word-panel">
      <!-- Header -->
      <div class="panel-header">
        <button class="panel-close" @click="handleClose" aria-label="Close panel">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
        </button>
      </div>

      <!-- Body -->
      <div class="panel-body">
        <!-- Word Header -->
        <div class="word-header">
          <div class="word-left">
            <h2 class="word-title">{{ word.word }}</h2>
            <button class="speak-btn" @click="handleSpeak" title="Play pronunciation">
              <Icon icon="solar:volume-loud-linear" width="20" />
            </button>
          </div>
          <button
            class="favorite-btn"
            :class="{ active: word.is_favorite }"
            @click="handleToggleFavorite"
            title="Toggle favorite"
          >
            <svg v-if="word.is_favorite" width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
            </svg>
            <svg v-else width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
            </svg>
          </button>
        </div>

        <!-- Definition -->
        <p class="definition">{{ word.definition }}</p>

        <!-- Know It Toggle -->
        <label class="know-it-toggle">
          <input type="checkbox" @change="handleToggleKnown" />
          <span class="toggle-label">Already know this word?</span>
        </label>

        <!-- Synonyms Section -->
        <div v-if="word.synonyms && word.synonyms.length" class="synonyms-section">
          <h4 class="section-title">Synonyms</h4>
          <div class="synonyms-list">
            <span v-for="syn in word.synonyms" :key="syn" class="synonym-tag">
              {{ syn }}
            </span>
          </div>
        </div>

        <!-- Examples Section -->
        <div v-if="word.examples && word.examples.length" class="examples-section">
          <h4 class="section-title">Examples</h4>
          <ul class="examples-list">
            <li v-for="(example, idx) in word.examples" :key="idx">{{ example }}</li>
          </ul>
        </div>

        <!-- Explanation Section -->
        <div v-if="showExplanation" class="explanation-section">
          <h4 class="section-title">AI Explanation</h4>
          <div v-if="isExplaining" class="explanation-loading">
            <div class="spinner-small"></div>
            <p>Generating explanation...</p>
          </div>
          <div v-else-if="word?.explanation" class="explanation-content">
            {{ word.explanation }}
          </div>
          <div v-else class="explanation-empty">
            <p>No explanation available.</p>
          </div>
        </div>

        <!-- Actions -->
        <div class="actions">
          <button
            class="action-btn explain"
            @click="toggleExplanation"
            :disabled="isExplaining"
          >
            <Icon
              :icon="isExplaining ? 'solar:spinner-linear' : 'solar:lightbulb-linear'"
              width="16"
              :class="{ 'spinner-icon': isExplaining }"
            />
            <span>{{ isExplaining ? 'Explaining...' : 'Explain' }}</span>
          </button>
          <button
            class="action-btn delete"
            @click="handleDelete"
            title="Delete word"
          >
            <Icon icon="solar:trash-bin-trash-outline" width="16" />
            <span>Delete</span>
          </button>
        </div>

        <!-- Metadata (Minimalista) -->
        <div class="metadata-minimal">
          <div class="meta-row">
            <span class="meta-label">Level</span>
            <span class="meta-value" :style="{ color: levelColor(word.level) }">{{ levelLabel(word.level) }}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Category</span>
            <span class="meta-value">{{ word.context || '—' }}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Frequency</span>
            <span class="meta-value" :style="{ color: frequencyColor(word.frequency) }">{{ frequencyLabel(word.frequency) }}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Type</span>
            <span class="meta-value">{{ word.type || '—' }}</span>
          </div>
        </div>
      </div>
    </aside>
  </transition>
</template>

<style scoped>
/* ════════════════════════════════════════
   DETAIL PANEL — Sticky, scrolls solo si es más alto que viewport
   ════════════════════════════════════════ */

.word-panel {
  width: 380px;
  flex-shrink: 0;
  background: #36324a;
  border-left: 1px solid rgba(255, 255, 255, 0.06);
  padding: 24px;
  border-radius: 16px 0 0 16px;

  /* Fixed positioning para funcionar en ExamplesPage */
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;

  /* Solo scrollea internamente si el contenido es más alto que la ventana */
  max-height: 100vh;
  overflow-y: auto;
}

.word-panel::-webkit-scrollbar {
  width: 5px;
}

.word-panel::-webkit-scrollbar-track {
  background: transparent;
}

.word-panel::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
}

.panel-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.panel-close {
  width: 32px;
  height: 32px;
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

.panel-close:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
}

.word-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.word-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.word-title {
  font-size: 32px;
  font-weight: 700;
  color: #e2e0e8;
  margin: 0;
  letter-spacing: -0.5px;
}

.speak-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: none;
  background: rgba(167, 139, 250, 0.1);
  color: #a78bfa;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.speak-btn:hover {
  background: rgba(167, 139, 250, 0.2);
  color: #c4b5fd;
}

.favorite-btn {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  border: none;
  background: rgba(255, 255, 255, 0.06);
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.favorite-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.favorite-btn.active {
  color: #f472b6;
  background: rgba(244, 114, 182, 0.1);
}

.definition {
  font-size: 15px;
  line-height: 1.6;
  color: #b8b5c8;
  margin-bottom: 20px;
}

/* Know It Toggle */
.know-it-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  margin-bottom: 24px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  transition: all 0.2s ease;
}

.know-it-toggle:hover {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.1);
}

.know-it-toggle input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: #4ade80;
  flex-shrink: 0;
}

.know-it-toggle input[type="checkbox"]:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.toggle-label {
  font-size: 13px;
  font-weight: 500;
  color: #b4b1c6;
  transition: color 0.2s ease;
}

.know-it-toggle input[type="checkbox"]:checked ~ .toggle-label {
  color: #4ade80;
  font-weight: 600;
}

/* ─── Synonyms ─── */
.synonyms-section {
  margin-bottom: 28px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #9c99ab;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0 0 12px 0;
}

.synonyms-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.synonym-tag {
  padding: 7px 14px;
  background: rgba(139, 92, 246, 0.1);
  border: 1px solid rgba(139, 92, 246, 0.15);
  border-radius: 20px;
  font-size: 13px;
  color: #c4b5fd;
  font-weight: 500;
  transition: all 0.2s ease;
  cursor: default;
  display: inline-block;
}

.synonym-tag:hover {
  background: rgba(139, 92, 246, 0.18);
  border-color: rgba(139, 92, 246, 0.3);
  transform: translateY(-1px);
}

/* Metadata Minimalista */
.metadata-minimal {
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  font-size: 13px;
}

.meta-label {
  font-weight: 600;
  color: #9c99ab;
  text-transform: uppercase;
  font-size: 11px;
  letter-spacing: 0.5px;
}

.meta-value {
  font-weight: 600;
  color: #e2e0e8;
  font-size: 13px;
}

.examples-section {
  margin-bottom: 28px;
}

.examples-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.examples-list li {
  font-size: 14px;
  color: #b8b5c8;
  padding: 10px 14px;
  background: rgba(0, 0, 0, 0.12);
  border-radius: 10px;
  line-height: 1.5;
}

.actions {
  display: flex;
  gap: 10px;
  margin-bottom: 30px;
}

.action-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  border-radius: 12px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn:hover:not(:disabled) {
  transform: translateY(-2px);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-btn.explain {
  background: rgba(167, 139, 250, 0.1);
  color: #a78bfa;
}

.action-btn.explain:hover:not(:disabled) {
  background: rgba(167, 139, 250, 0.2);
}

.action-btn.delete {
  background: rgba(239, 68, 68, 0.1);
  color: #f87171;
}

.action-btn.delete:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.2);
}

.spinner-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ─── Explanation ─── */
.explanation-section {
  margin-bottom: 28px;
}

.explanation-content {
  font-size: 14px;
  line-height: 1.6;
  color: #b8b5c8;
  padding: 16px 14px;
  background: rgba(0, 0, 0, 0.12);
  border-radius: 10px;
}

.explanation-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 24px;
  min-height: 100px;
}

.spinner-small {
  width: 24px;
  height: 24px;
  border: 2px solid rgba(167, 139, 250, 0.2);
  border-top-color: #a78bfa;
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}

.explanation-loading p {
  color: #9c99ab;
  font-size: 14px;
  margin: 0;
}

.explanation-empty {
  padding: 20px;
  text-align: center;
  color: #9c99ab;
  font-size: 14px;
}

.explanation-empty p {
  margin: 0;
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
</style>
