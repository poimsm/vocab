<script setup lang="ts">
import { ref, onMounted, watch, onBeforeUnmount } from 'vue'
import { Icon } from '@iconify/vue'
import api from '@/utils/api'

interface RandomWord {
  id: number
  main: string
  meaning: string
  level: number
  frequency: string
  type: string
}

const words = ref<RandomWord[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const showMeanings = ref(false)
const flipped = ref<Set<number>>(new Set())
const isAnimating = ref(false)
const buttonMarginTop = ref('200px')

const calculateButtonMargin = () => {
  if (words.value.length === 0) {
    const viewportHeight = window.innerHeight
    const margin = Math.max(viewportHeight / 3, 120)
    buttonMarginTop.value = `${margin}px`
  } else {
    buttonMarginTop.value = '40px'
  }
}

onMounted(() => {
  const stored = localStorage.getItem('randomizer-show-meanings')
  if (stored !== null) {
    showMeanings.value = stored === 'true'
  }
  calculateButtonMargin()
  window.addEventListener('resize', calculateButtonMargin)
})

watch(words, () => {
  calculateButtonMargin()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', calculateButtonMargin)
})

watch(showMeanings, (newValue) => {
  localStorage.setItem('randomizer-show-meanings', String(newValue))
})

const levelColor = (level: number) => {
  if (level === 1) return '#4ade80'
  if (level === 2) return '#60a5fa'
  if (level === 3) return '#f472b6'
  return '#9c99ab'
}

const levelLabel = (level: number) => {
  if (level === 1) return 'Beginner'
  if (level === 2) return 'Intermediate'
  if (level === 3) return 'Advanced'
  return '—'
}

const toggleFlip = (wordId: number) => {
  if (flipped.value.has(wordId)) {
    flipped.value.delete(wordId)
  } else {
    flipped.value.add(wordId)
  }
}

const isFlipped = (wordId: number) => {
  return flipped.value.has(wordId)
}

const getAnimationDelay = (index: number) => {
  return `${index * 0.08}s`
}

async function randomize() {
  loading.value = true
  error.value = null
  isAnimating.value = true
  try {
    const response = await api.get('/words/random', { params: { limit: 6 } })
    words.value = response.data.items || []
    flipped.value = new Set()
  } catch (e: any) {
    error.value = e.message || 'Failed to load words'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="randomizer-view">
    <header class="randomizer-header">
      <div style="display:none">
        <h1 class="randomizer-title">Randomizer</h1>
        <p class="randomizer-subtitle">Get random words to use however you want 🎲</p>
      </div>
      <button 
        class="toggle-meanings" 
        :class="{ active: showMeanings }" 
        @click="showMeanings = !showMeanings" 
        :title="showMeanings ? 'Hide meanings' : 'Show meanings'"
        style="display:none;"
        >
        <Icon :icon="showMeanings ? 'solar:eye-linear' : 'solar:eye-closed-linear'" width="20" />
        <span class="toggle-label">{{ showMeanings ? 'Visible' : 'Hidden' }}</span>
      </button>
    </header>

    <div class="randomizer-button-container" :style="{ marginTop: buttonMarginTop }">
      <button class="randomize-btn" @click="randomize" :disabled="loading">
        <!-- <Icon icon="solar:dice-3-linear" width="20" /> -->
        <span style="font-weight: bold;">{{ loading ? 'Loading...' : 'Randomize' }}</span>
      </button>
    </div>

    <div v-if="error" class="error-message">
      <p>{{ error }}</p>
    </div>

    <div v-else-if="words.length > 0" class="words-grid">
      <div
        v-for="(word, index) in words"
        :key="word.id"
        class="word-item-container"
        :class="{ 'animate-in': isAnimating }"
        :style="{ '--delay': getAnimationDelay(index) }"
        @click="toggleFlip(word.id)">
        <div class="word-item" :class="{ flipped: isFlipped(word.id) || showMeanings }">
          <div class="word-card word-card-front">
            <h3 class="word-text">{{ word.main }}</h3>
          </div>
          <div class="word-card word-card-back">
            <p class="word-meaning">{{ word.meaning }}</p>
            <div class="word-footer">
              <span class="word-type">{{ word.type }}</span>
              <span class="word-frequency">{{ word.frequency }}</span>
            </div>
            <span class="word-level" :style="{ color: levelColor(word.level) }">
              {{ levelLabel(word.level) }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="empty-state">
      <Icon icon="solar:dice-3-linear" width="48" />
      <p>Click the randomize button to get started</p>
    </div>
  </div>
</template>

<style scoped>
.randomizer-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px;
  color: #e2e0e8;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.randomizer-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 32px;
  gap: 20px;
}

.randomizer-title {
  font-size: 28px;
  font-weight: 700;
  color: #e2e0e8;
  margin: 0;
  letter-spacing: -0.5px;
}

.randomizer-subtitle {
  font-size: 14px;
  color: #9c99ab;
  margin: 6px 0 0 0;
}

.toggle-meanings {
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

.toggle-meanings.active {
  background: rgba(124, 58, 237, 0.2);
  border-color: rgba(124, 58, 237, 0.4);
  color: #a78bfa;
}

.toggle-meanings:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
  color: #e2e0e8;
}

.toggle-label {
  display: none;
}

.randomizer-button-container {
  display: flex;
  justify-content: center;
  margin-bottom: 40px;
  xtransition: margin-top 0.5s ease;
}

.randomize-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 28px;
  border-radius: 12px;
  border: none;
  background: #7c3aed;
  color: white;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.randomize-btn:hover:not(:disabled) {
  background: #6d28d9;
  transform: translateY(-2px);
}

.randomize-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  animation: pulse 1.5s ease-in-out infinite;
}

.randomize-btn:disabled :deep(svg) {
  animation: spin 1s linear infinite;
}

.error-message {
  text-align: center;
  padding: 24px;
  background: rgba(239, 68, 68, 0.1);
  border-radius: 12px;
  color: #f87171;
  margin-bottom: 24px;
}

.error-message p {
  margin: 0;
  font-size: 14px;
}

.words-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 32px;
  padding: 4px;
}

.word-item-container {
  perspective: 1000px;
  cursor: pointer;
  height: 200px;
  box-sizing: border-box;
  --delay: 0s;
  opacity: 1;
  transform: scale(1);
}

.word-item-container.animate-in {
  animation: fadeInScale 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
  animation-delay: var(--delay);
}

.word-item {
  position: relative;
  width: 100%;
  height: 100%;
  transition: transform 0.6s cubic-bezier(0.68, -0.55, 0.265, 1.55);
  transform-style: preserve-3d;
  box-sizing: border-box;
}

.word-item.flipped {
  transform: rotateY(180deg);
}

.word-card {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  padding: 20px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  backface-visibility: hidden;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 10px;
  box-sizing: border-box;
  overflow: hidden;
}

.word-card-front {
  background: rgba(255, 255, 255, 0.04);
  transform: rotateY(0deg);
  transition: background 0.2s ease, border-color 0.2s ease;
}

.word-card-back {
  background: rgba(124, 58, 237, 0.15);
  border-color: rgba(124, 58, 237, 0.3);
  transform: rotateY(180deg);
}

.word-item-container:not(.animate-in):hover .word-card-front {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
}

.word-text {
  font-size: 26px;
  font-weight: 700;
  color: #e2e0e8;
  margin: 0;
  text-align: center;
}

.word-level {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 5px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  white-space: nowrap;
  margin-top: auto;
}

.word-meaning {
  font-size: 15px;
  color: #e2e0e8;
  line-height: 1.5;
  margin: 0;
  text-align: center;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.word-footer {
  display: flex;
  gap: 10px;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  justify-content: center;
}

.word-type {
  color: #a78bfa;
  background: rgba(167, 139, 250, 0.1);
  padding: 4px 10px;
  border-radius: 6px;
  font-weight: 600;
}

.word-frequency {
  color: #9c99ab;
  background: rgba(255, 255, 255, 0.04);
  padding: 4px 10px;
  border-radius: 6px;
  font-weight: 600;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  gap: 16px;
  text-align: center;
  color: #9c99ab;
}

.empty-state p {
  margin: 0;
  font-size: 16px;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(124, 58, 237, 0.7); }
  50% { box-shadow: 0 0 0 10px rgba(124, 58, 237, 0); }
}

@keyframes fadeInScale {
  0% {
    opacity: 0;
    transform: scale(0.97);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}

@media (max-width: 768px) {
  .randomizer-view {
    padding: 24px 16px;
  }

  .randomizer-header {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .randomizer-title {
    font-size: 24px;
  }

  .randomizer-subtitle {
    font-size: 15px;
  }

  .toggle-meanings {
    width: 100%;
    justify-content: center;
  }

  .toggle-label {
    display: inline;
  }

  .words-grid {
    grid-template-columns: 1fr;
    gap: 24px;
    padding: 4px;
  }

  .word-item-container {
    height: 220px;
  }

  .word-text {
    font-size: 30px;
  }

  .word-meaning {
    font-size: 17px;
    -webkit-line-clamp: 4;
  }

  .word-footer {
    font-size: 14px;
    gap: 12px;
  }

  .word-level {
    font-size: 13px;
  }

  .word-card {
    padding: 24px;
  }

  .empty-state {
    padding: 0px 20px;
    margin-top: -20px;
  }
}

@media (max-width: 480px) {
  .word-item-container {
    height: 200px;
  }

  .word-text {
    font-size: 26px;
  }

  .word-meaning {
    font-size: 16px;
  }

  .empty-state {
    padding: 0px 20px;
    margin-top: -20px;
  }
}
</style>