<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
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
const showMeanings = ref(true)

onMounted(() => {
  const stored = localStorage.getItem('randomizer-show-meanings')
  if (stored !== null) {
    showMeanings.value = stored === 'true'
  }
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

async function randomize() {
  loading.value = true
  error.value = null
  try {
    const response = await api.get('/words/random', { params: { limit: 6 } })
    words.value = response.data.items || []
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
      <div>
        <h1 class="randomizer-title">Randomizer</h1>
        <p class="randomizer-subtitle">Get random words to use however you want 🎲</p>
      </div>
      <button class="toggle-meanings" :class="{ active: showMeanings }" @click="showMeanings = !showMeanings" :title="showMeanings ? 'Hide meanings' : 'Show meanings'">
        <Icon :icon="showMeanings ? 'solar:eye-linear' : 'solar:eye-closed-linear'" width="20" />
        <span class="toggle-label">{{ showMeanings ? 'Visible' : 'Hidden' }}</span>
      </button>
    </header>

    <div class="randomizer-button-container">
      <button class="randomize-btn" @click="randomize" :disabled="loading">
        <Icon icon="solar:dice-3-linear" width="20" />
        <span>{{ loading ? 'Loading...' : 'Randomize' }}</span>
      </button>
    </div>

    <div v-if="error" class="error-message">
      <p>{{ error }}</p>
    </div>

    <div v-else-if="words.length > 0" class="words-grid">
      <div v-for="word in words" :key="word.id" class="word-item">
        <div class="word-header">
          <h3 class="word-text">{{ word.main }}</h3>
          <span class="word-level" :style="{ color: levelColor(word.level) }">
            {{ levelLabel(word.level) }}
          </span>
        </div>
        <p v-if="showMeanings" class="word-meaning">{{ word.meaning }}</p>
        <div class="word-footer">
          <span class="word-type">{{ word.type }}</span>
          <span class="word-frequency">{{ word.frequency }}</span>
        </div>
      </div>
    </div>

    <div v-else class="empty-state" style="display:none">
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
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.word-item {
  padding: 16px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition: all 0.2s ease;
  animation: popIn 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) backwards;
}

.word-item:nth-child(1) { animation-delay: 0.08s; }
.word-item:nth-child(2) { animation-delay: 0.16s; }
.word-item:nth-child(3) { animation-delay: 0.24s; }
.word-item:nth-child(4) { animation-delay: 0.32s; }
.word-item:nth-child(5) { animation-delay: 0.4s; }
.word-item:nth-child(6) { animation-delay: 0.48s; }

.word-item:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
}

.word-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 8px;
}

.word-text {
  font-size: 18px;
  font-weight: 700;
  color: #e2e0e8;
  margin: 0;
}

.word-level {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  white-space: nowrap;
}

.word-meaning {
  font-size: 13px;
  color: #9c99ab;
  line-height: 1.5;
  margin: 0 0 12px 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.word-footer {
  display: flex;
  gap: 8px;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.word-type {
  color: #a78bfa;
  background: rgba(167, 139, 250, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
}

.word-frequency {
  color: #9c99ab;
  background: rgba(255, 255, 255, 0.04);
  padding: 2px 8px;
  border-radius: 4px;
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
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@keyframes pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(124, 58, 237, 0.7);
  }
  50% {
    box-shadow: 0 0 0 10px rgba(124, 58, 237, 0);
  }
}

@keyframes popIn {
  from {
    opacity: 0;
    transform: scale(0.3) translateY(30px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

@media (max-width: 768px) {
  .randomizer-view {
    padding: 24px 16px;
  }

  .randomizer-header {
    flex-direction: column;
    align-items: center;
  }

  .randomizer-title {
    font-size: 24px;
  }

  .randomizer-subtitle {
    font-size: 14px;
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
  }

  .randomize-btn {
    font-size: 16px;
  }
}
</style>
