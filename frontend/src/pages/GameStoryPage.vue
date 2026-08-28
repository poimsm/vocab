<script setup lang="ts">
import { ref, computed } from 'vue'
import { Icon } from '@iconify/vue'

interface Spark {
  id: number
  narration: string
  words: string[]
}

interface StoryProgress {
  sparkId: number
  userText: string
}

const sparks: Spark[] = [
  {
    id: 1,
    narration: 'You wake up in a strange hotel room. There is only one door.',
    words: ['rusty', 'whisper', 'suitcase']
  },
  {
    id: 2,
    narration: 'The door opens. Something is waiting outside.',
    words: ['shadow', 'stumble', 'hallway']
  },
  {
    id: 3,
    narration: 'You find a suitcase hidden under the floorboards.',
    words: ['letter', 'bizarre', 'hide']
  },
  {
    id: 4,
    narration: 'Someone knocks loudly on the door. Three sharp knocks.',
    words: ['pretend', 'nervous', 'footsteps']
  },
  {
    id: 5,
    narration: 'The lights go out. Everything is dark now.',
    words: ['crawl', 'scream', 'flashlight']
  }
]

const currentSparkIndex = ref(0)
const userInputs = ref<StoryProgress[]>([])
const currentInput = ref('')
const showError = ref(false)
const storyComplete = ref(false)

const currentSpark = computed(() => sparks[currentSparkIndex.value])

const hasUsedWord = (text: string): boolean => {
  const lowerText = text.toLowerCase()
  return currentSpark.value.words.some(word => lowerText.includes(word.toLowerCase()))
}

const validateAndContinue = () => {
  showError.value = false

  if (!currentInput.value.trim()) {
    showError.value = true
    return
  }

  if (!hasUsedWord(currentInput.value)) {
    showError.value = true
    return
  }

  userInputs.value.push({
    sparkId: currentSpark.value.id,
    userText: currentInput.value
  })

  if (currentSparkIndex.value < sparks.length - 1) {
    currentSparkIndex.value++
    currentInput.value = ''
  } else {
    storyComplete.value = true
  }
}

const restartStory = () => {
  currentSparkIndex.value = 0
  userInputs.value = []
  currentInput.value = ''
  storyComplete.value = false
  showError.value = false
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && e.ctrlKey) {
    validateAndContinue()
  }
}
</script>

<template>
  <div class="game-story-view">
    <!-- Story Complete Screen -->
    <transition name="fade">
      <div v-if="storyComplete" class="story-complete">
        <div class="complete-card">
          <div class="complete-icon">
            <Icon icon="solar:star-bold" width="56" />
          </div>
          <h2 class="complete-title">Done!</h2>

          <div class="story-summary">
            <div v-for="(item, idx) in userInputs" :key="idx" class="summary-item">
              <p class="summary-text">{{ item.userText }}</p>
            </div>
          </div>

          <button class="restart-btn" @click="restartStory">
            <Icon icon="solar:restart-bold" width="18" />
            Restart
          </button>
        </div>
      </div>
    </transition>

    <!-- Game Screen -->
    <div v-if="!storyComplete" class="game-container">
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: `${(currentSparkIndex / (sparks.length - 1)) * 100}%` }"></div>
      </div>

      <div class="scene-card">
        <div class="scene-number">Scene {{ currentSparkIndex + 1 }}/{{ sparks.length }}</div>

        <p class="scene-text">{{ currentSpark.narration }}</p>

        <div class="words-list">
          <span
            v-for="word in currentSpark.words"
            :key="word"
            class="word-chip"
            :class="{ active: currentInput.toLowerCase().includes(word.toLowerCase()) }"
          >
            {{ word }}
          </span>
        </div>

        <textarea
          v-model="currentInput"
          class="story-input"
          placeholder="Write your continuation..."
          @keydown="handleKeydown"
          rows="3"
        ></textarea>

        <div v-if="showError" class="error-msg">
          Use at least one word above
        </div>

        <button class="continue-btn" @click="validateAndContinue" :disabled="!currentInput.trim()">
          {{ currentSparkIndex === sparks.length - 1 ? 'Finish' : 'Next' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.game-story-view {
  max-width: 700px;
  margin: 0 auto;
  padding: 40px 20px;
  color: #e2e0e8;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  min-height: 100vh;
  display: flex;
  align-items: center;
}

.progress-bar {
  width: 100%;
  height: 4px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  overflow: hidden;
  margin-bottom: 40px;
}

.progress-fill {
  height: 100%;
  background: #7c3aed;
  transition: width 0.3s ease;
}

.scene-number {
  font-size: 12px;
  color: #9c99ab;
  margin-bottom: 20px;
}

.scene-card {
  width: 100%;
}

.scene-text {
  font-size: 18px;
  line-height: 1.8;
  color: #b8b5c8;
  margin: 0 0 32px 0;
}

.words-list {
  display: flex;
  gap: 8px;
  margin-bottom: 32px;
  flex-wrap: wrap;
}

.word-chip {
  padding: 6px 12px;
  border-radius: 8px;
  background: rgba(124, 58, 237, 0.15);
  color: #c4b5fd;
  font-size: 13px;
  font-weight: 600;
  border: 1px solid rgba(124, 58, 237, 0.25);
  transition: all 0.2s ease;
  cursor: default;
}

.word-chip.active {
  background: rgba(124, 58, 237, 0.4);
  border-color: rgba(124, 58, 237, 0.6);
  color: #e0e7ff;
}

.story-input {
  width: 100%;
  padding: 14px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #e2e0e8;
  font-size: 15px;
  outline: none;
  font-family: inherit;
  resize: none;
  box-sizing: border-box;
  margin-bottom: 14px;
  transition: all 0.2s ease;
}

.story-input:focus {
  border-color: rgba(124, 58, 237, 0.4);
  background: rgba(255, 255, 255, 0.06);
}

.story-input::placeholder {
  color: #9c99ab;
}

.error-msg {
  font-size: 12px;
  color: #f87171;
  margin-bottom: 12px;
}

.continue-btn {
  width: 100%;
  padding: 12px;
  border-radius: 10px;
  border: none;
  background: #7c3aed;
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.continue-btn:hover:not(:disabled) {
  background: #6d28d9;
}

.continue-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ─── Story Complete ─── */
.story-complete {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
}

.complete-card {
  width: 100%;
  text-align: center;
}

.complete-icon {
  margin-bottom: 16px;
  color: #fbbf24;
}

.complete-title {
  font-size: 28px;
  font-weight: 700;
  color: #e2e0e8;
  margin: 0 0 28px 0;
}

.story-summary {
  margin-bottom: 32px;
  text-align: left;
}

.summary-item {
  padding: 12px;
  background: rgba(124, 58, 237, 0.08);
  border-radius: 8px;
  margin-bottom: 12px;
}

.summary-text {
  font-size: 14px;
  color: #b8b5c8;
  margin: 0;
  line-height: 1.6;
}

.restart-btn {
  width: 100%;
  padding: 12px;
  border-radius: 10px;
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

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 768px) {
  .game-story-view {
    padding: 32px 16px;
  }

  .scene-text {
    font-size: 16px;
  }

  .complete-title {
    font-size: 24px;
  }
}
</style>
