<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import api from '@/utils/api'
import { useBestOptionsStore } from '@/stores/bestOptions'
import { useActivityTracking } from '@/composables/useActivityTracking'
import LoadingCard from '@/components/LoadingCard.vue'

const bestOptionsStore = useBestOptionsStore()
const { trackButtonClick } = useActivityTracking()

// ─── Local State ───
const isComponentMounted = ref(false)
const pollTimer = ref<ReturnType<typeof setTimeout> | null>(null)

const BATCH_SIZE = 4
const POLL_INTERVAL = 3000
const MAX_CONSECUTIVE_GENERATING = 6

let pollAbortController: AbortController | null = null
let pollActive = ref(false)
let consecutiveGeneratingCount = ref(0)

// ─── Polling ───
function startPolling() {
  console.log('[startPolling] Starting poll loop')

  if (pollAbortController) {
    pollAbortController.abort()
  }

  consecutiveGeneratingCount.value = 0
  pollActive.value = true
  pollAbortController = new AbortController()

  const poll = () => {
    if (!pollActive.value) return

    pollTimer.value = setTimeout(async () => {
      if (!pollActive.value) return

      try {
        const response = await api.post('/best-options/explore', {
          actions: ['next'],
          limit: BATCH_SIZE,
          buffer_delivery_ids: bestOptionsStore.bufferIds,
          buffer_position: bestOptionsStore.currentIndex,
        }, {
          signal: pollAbortController?.signal
        })

        if (!pollActive.value) return

        if (response.data.status === 'generating') {
          consecutiveGeneratingCount.value++

          if (consecutiveGeneratingCount.value >= MAX_CONSECUTIVE_GENERATING) {
            bestOptionsStore.setIsPolling(false)
            bestOptionsStore.setGenerating(false)
            bestOptionsStore.setError('Content generation timeout - please try again')
            pollActive.value = false
            return
          }

          if (pollActive.value) poll()
          return
        }

        consecutiveGeneratingCount.value = 0

        if (response.data.status === 'no_words') {
          bestOptionsStore.setIsPolling(false)
          bestOptionsStore.setGenerating(false)
          bestOptionsStore.setNoWords(true)
          pollActive.value = false
          return
        }

        bestOptionsStore.setIsPolling(false)
        bestOptionsStore.setGenerating(false)
        bestOptionsStore.loadBestOptions(
          response.data.items || [],
          response.data.buffer_delivery_ids || [],
          response.data.buffer_position ?? 0
        )
        pollActive.value = false
      } catch (e: any) {
        if (e.name === 'AbortError') {
          pollActive.value = false
          return
        }
        bestOptionsStore.setIsPolling(false)
        bestOptionsStore.setGenerating(false)
        bestOptionsStore.setError(e.response?.data?.message || e.message || 'Failed to load')
        pollActive.value = false
      }
    }, POLL_INTERVAL)
  }
  poll()
}

function stopPolling() {
  pollActive.value = false

  if (pollAbortController) {
    pollAbortController.abort()
    pollAbortController = null
  }

  if (pollTimer.value) {
    clearTimeout(pollTimer.value)
    pollTimer.value = null
  }

  consecutiveGeneratingCount.value = 0
  bestOptionsStore.setIsPolling(false)
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

  if (bestOptionsStore.isPolling || bestOptionsStore.generating) {
    startPolling()
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

// ─── Mounted ───
onMounted(async () => {
  isComponentMounted.value = true

  try {
    const exploreResponse = await api.post('/best-options/explore', {
      actions: ['resume'],
      limit: BATCH_SIZE,
      buffer_delivery_ids: [],
      buffer_position: 0,
    })

    if (!isComponentMounted.value) return

    const { items, buffer_delivery_ids: bufferIds, buffer_position: bufferPos, status: exploreStatus } = exploreResponse.data

    bestOptionsStore.setBufferData(bufferIds, bufferPos)

    if (items && items.length > 0) {
      bestOptionsStore.loadBestOptions(items, bufferIds, bufferPos)
      bestOptionsStore.setCurrentIndex(bufferPos)
    } else if (exploreStatus === 'generating') {
      bestOptionsStore.setGenerating(true)
      startPolling()
    } else if (exploreStatus === 'no_words') {
      bestOptionsStore.setNoWords(true)
    }
  } catch (e) {
    if (isComponentMounted.value) {
      bestOptionsStore.resetBuffer()
      await bestOptionsStore.fetchBestOptions(BATCH_SIZE)
      if (bestOptionsStore.isPolling || bestOptionsStore.generating) {
        startPolling()
      }
    }
  }
})

onUnmounted(() => {
  isComponentMounted.value = false
  stopPolling()
})
</script>

<template>
  <div class="best-options-view">
    <LoadingCard v-if="bestOptionsStore.generating && bestOptionsStore.bestOptions.length === 0" message="Generating..." />

    <div v-else-if="bestOptionsStore.noWords" class="center-state">
      <p>No more words to review</p>
      <button class="retry" @click="bestOptionsStore.fetchBestOptions(BATCH_SIZE)">Try Again</button>
    </div>

    <div v-else-if="bestOptionsStore.error" class="center-state">
      <p class="err">{{ bestOptionsStore.error }}</p>
      <button class="retry" @click="bestOptionsStore.fetchBestOptions(BATCH_SIZE)">Retry</button>
    </div>

    <div v-else-if="!bestOptionsStore.currentBestOption" class="center-state">
      <p>No questions available</p>
      <button class="retry" @click="bestOptionsStore.fetchBestOptions(BATCH_SIZE)">Load</button>
    </div>

    <div v-else class="quiz">
      <button class="word">{{ bestOptionsStore.currentBestOption.word.main }}</button>

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
  transition: all 0.2s ease;
  text-transform: capitalize;
}

.word:hover {
  background: rgba(124, 58, 237, 0.2);
  border-color: rgba(124, 58, 237, 0.4);
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
  font-size: 14px;
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
}
</style>
