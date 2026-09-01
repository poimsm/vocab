<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Icon } from '@iconify/vue'

interface Collocation {
  id: number
  phrase: string
}

const original = [
  { id: 1, phrase: 'quivering hands' },
  { id: 2, phrase: 'flushed cheeks' },
  { id: 3, phrase: 'flung stone' },
  { id: 4, phrase: 'grimacing face' },
  { id: 5, phrase: 'sledgehammer blow' },
  { id: 6, phrase: 'blowlamp flame' },
  { id: 7, phrase: 'deep hatred' },
  { id: 8, phrase: 'religious heretic' },
  { id: 9, phrase: 'neat goatee' }
]

const shuffled = ref<Collocation[]>([...original])
const isShuffled = ref(false)
const completed = ref<Set<number>>(new Set())

const collocations = computed(() => shuffled.value)

const completedCount = computed(() => completed.value.size)
const totalCount = computed(() => original.length)
const progressPercent = computed(() => Math.round((completedCount.value / totalCount.value) * 100))

const shuffle = () => {
  const arr = [...original]
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i]!, arr[j]!] = [arr[j]!, arr[i]!]
  }
  shuffled.value = arr
  isShuffled.value = true
}

const reset = () => {
  shuffled.value = [...original]
  isShuffled.value = false
}

const toggleCompleted = (id: number) => {
  if (completed.value.has(id)) {
    completed.value.delete(id)
  } else {
    completed.value.add(id)
  }
  saveProgress()
}

const isCompleted = (id: number) => {
  return completed.value.has(id)
}

const saveProgress = () => {
  const ids = Array.from(completed.value)
  localStorage.setItem('collocations-completed', JSON.stringify(ids))
}

const loadProgress = () => {
  const saved = localStorage.getItem('collocations-completed')
  if (saved) {
    try {
      const ids = JSON.parse(saved)
      completed.value = new Set(ids)
    } catch {
      completed.value = new Set()
    }
  }
}

const clearProgress = () => {
  completed.value.clear()
  localStorage.removeItem('collocations-completed')
}

onMounted(() => {
  loadProgress()
})
</script>

<template>
  <div class="collocations-view">
    <div class="page">
      <!-- Header -->
      <div class="page-header">
        <div class="title-section">
          <h1 class="title">Cozy Collocations</h1>
          <Icon icon="fluent-emoji:relaxed-face" width="32" class="emoji" />
        </div>
        <div class="date-section">
          <span class="label">Date:</span>
          <span class="date">{{ new Date().toISOString().split('T')[0] }}</span>
          <Icon icon="solar:calendar-outline" width="16" class="date-icon" />
        </div>
      </div>

      <!-- Progress Bar -->
      <div class="progress-section">
        <div class="progress-bar-container">
          <div class="progress-bar" :style="{ width: progressPercent + '%' }"></div>
        </div>
        <span class="progress-text">{{ completedCount }} / {{ totalCount }}</span>
      </div>

      <!-- List -->
      <div class="items-list">
        <div
          v-for="(collocation, index) in collocations"
          :key="collocation.id"
          class="list-item"
          :class="{ completed: isCompleted(collocation.id) }"
          @click="toggleCompleted(collocation.id)"
        >
          <div
            class="number-badge"
            :class="{ checked: isCompleted(collocation.id) }"
          >
            {{ isCompleted(collocation.id) ? '✓' : index + 1 }}
          </div>
          <span class="phrase">{{ collocation.phrase }}</span>
        </div>
      </div>

      <!-- Footer -->
      <div class="page-footer">
        <div class="footer-content">
          <span class="next-pack">
            <Icon icon="noto:ball-of-yarn" width="16" />
            Next Pack
          </span>
          <p class="footer-text">A cozy study companion</p>
        </div>
      </div>
    </div>

    <!-- Controls -->
    <div class="controls">
      <button
        class="clear-btn"
        @click="clearProgress"
        title="Clear all progress"
        v-if="completedCount > 0"
      >
        <Icon icon="solar:trash-bin-trash-linear" width="16" />
      </button>
      <button
        class="shuffle-btn"
        :class="{ active: isShuffled }"
        @click="isShuffled ? reset() : shuffle()"
        :title="isShuffled ? 'Reset to original' : 'Shuffle'"
      >
        <Icon :icon="isShuffled ? 'solar:undo-left-linear' : 'solar:shuffle-linear'" width="18" />
        <span>{{ isShuffled ? 'Reset' : 'Shuffle' }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.collocations-view {
  min-height: 100vh;
  padding: 32px 16px;
  background: #2d2a3e;
  color: #e2e0e8;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.page {
  max-width: 700px;
  margin: 0 auto 24px;
  padding: 40px 36px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 32px;
  gap: 24px;
}

.title-section {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.title {
  font-size: 32px;
  font-weight: 700;
  margin: 0;
  color: #e2e0e8;
  letter-spacing: -0.5px;
}

.emoji {
  flex-shrink: 0;
}

.date-section {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #9c99ab;
  white-space: nowrap;
}

.label {
  font-weight: 600;
}

.date {
  font-family: 'Courier New', monospace;
  color: #a8a5b8;
}

.date-icon {
  color: #7c7a8a;
}

.progress-section {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 28px;
}

.progress-bar-container {
  flex: 1;
  height: 5px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 2.5px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: #a78bfa;
  border-radius: 2.5px;
  transition: width 0.4s ease;
}

.progress-text {
  font-size: 12px;
  color: #9c99ab;
  font-weight: 600;
  min-width: 45px;
  text-align: right;
}

.items-list {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-bottom: 32px;
}

.list-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  transition: opacity 0.2s ease, background 0.15s ease;
  cursor: pointer;
  user-select: none;
}

.list-item:hover {
  background: rgba(255, 255, 255, 0.02);
}

.list-item.completed {
  opacity: 0.5;
}

.list-item.completed .phrase {
  text-decoration: line-through;
  color: #7c7a8a;
}

.number-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 2px solid rgba(167, 139, 250, 0.4);
  background: rgba(167, 139, 250, 0.1);
  color: #a78bfa;
  font-weight: 700;
  font-size: 13px;
  flex-shrink: 0;
  transition: all 0.2s ease;
  font-family: 'Segoe UI', sans-serif;
  pointer-events: none;
}

.number-badge.checked {
  background: rgba(167, 139, 250, 0.25);
  color: #c4b5fd;
  border-color: rgba(167, 139, 250, 0.6);
}

.phrase {
  font-size: 16px;
  font-weight: 600;
  color: #e2e0e8;
  letter-spacing: -0.3px;
  text-align: left;
}

.page-footer {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  text-align: center;
}

.footer-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.next-pack {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #a78bfa;
}

.footer-text {
  font-size: 12px;
  color: #7c7a8a;
  margin: 0;
  font-style: italic;
}

.controls {
  display: flex;
  justify-content: center;
  gap: 8px;
  max-width: 700px;
  margin: 0 auto;
}

.shuffle-btn,
.clear-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.05);
  color: #9c99ab;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.shuffle-btn:hover,
.clear-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
  color: #e2e0e8;
}

.shuffle-btn.active {
  background: rgba(167, 139, 250, 0.15);
  border-color: rgba(167, 139, 250, 0.4);
  color: #a78bfa;
}

@media (max-width: 900px) {
  .page {
    max-width: 100%;
  }

  .page-header {
    flex-direction: column;
    gap: 16px;
  }

  .title-section {
    width: 100%;
  }

  .date-section {
    justify-content: flex-start;
    width: 100%;
  }
}

@media (max-width: 768px) {
  .page {
    padding: 32px 24px;
  }

  .title {
    font-size: 28px;
  }

  .list-item {
    padding: 12px 0;
    gap: 12px;
  }

  .phrase {
    font-size: 15px;
  }
}

@media (max-width: 480px) {
  .collocations-view {
    padding: 16px 12px;
  }

  .page {
    padding: 20px 16px;
    border-radius: 12px;
    margin-bottom: 16px;
    max-width: 100%;
  }

  .page-header {
    gap: 10px;
    margin-bottom: 20px;
  }

  .title {
    font-size: 22px;
  }

  .date-section {
    font-size: 11px;
  }

  .emoji {
    width: 24px;
    height: 24px;
  }

  .progress-section {
    margin-bottom: 20px;
  }

  .number-badge {
    width: 26px;
    height: 26px;
    font-size: 11px;
    border-width: 1.5px;
  }

  .list-item {
    padding: 18px 0;
    gap: 10px;
    border-bottom-color: rgba(255, 255, 255, 0.04);
  }

  .phrase {
    font-size: 19px;
    font-weight: normal;
  }

  .page-footer {
    margin-top: 16px;
    padding-top: 16px;
  }

  .controls {
    gap: 6px;
    max-width: 100%;
  }

  .shuffle-btn,
  .clear-btn {
    padding: 6px 10px;
    font-size: 12px;
  }
}
</style>