<script setup lang="ts">
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
import api from '@/utils/api'

interface Props {
  modelValue: boolean
  words: string[]
}

interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'word-added', word: string): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const addedWords = ref<Set<string>>(new Set())
const addingWord = ref<string | null>(null)

async function addWordToList(word: string) {
  if (addedWords.value.has(word)) {
    return
  }

  addingWord.value = word

  try {
    const response = await api.post('/words/single', {
      text: word
    })

    if (response.status === 202 || response.data.status === 'queued') {
      addedWords.value.add(word)
      emit('word-added', word)
    } else {
      alert('Failed to add word')
    }
  } catch (e: any) {
    alert('Failed to add word: ' + (e.response?.data?.message || e.message))
  } finally {
    addingWord.value = null
  }
}

function handleClose() {
  emit('update:modelValue', false)
  addedWords.value.clear()
}
</script>

<template>
  <!-- Extracted Words Modal (Desktop) -->
  <transition name="fade">
    <div v-if="modelValue" class="modal-overlay extracted-words-overlay" @click="handleClose">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add words from this example</h3>
          <button class="modal-close-btn" @click="handleClose">
            <Icon icon="solar:close-circle-linear" width="24" />
          </button>
        </div>

        <div class="modal-body">
          <div v-if="words && words.length > 0" class="words-grid">
            <button
              v-for="word in words"
              :key="word"
              class="word-chip"
              :class="{ added: addedWords.has(word), loading: addingWord === word }"
              @click="addWordToList(word)"
              :disabled="addedWords.has(word) || addingWord === word"
            >
              <span class="word-text">{{ word }}</span>
              <Icon v-if="!addedWords.has(word) && addingWord !== word" icon="solar:add-circle-linear" width="18" />
              <Icon v-else-if="addedWords.has(word)" icon="solar:check-circle-bold" width="18" class="check-icon" />
              <Icon v-else icon="solar:refresh-circle-linear" width="18" class="spinning" />
            </button>
          </div>
          <div v-else class="empty-words">
            <p>No words to add</p>
          </div>
        </div>
      </div>
    </div>
  </transition>

  <!-- Extracted Words Action Sheet (Mobile) -->
  <transition name="slide-up">
    <div v-if="modelValue" class="mobile-extracted-words-sheet">
      <div class="action-sheet-header">
        <h3>Add words from this example</h3>
        <button class="action-sheet-close" @click="handleClose">
          <Icon icon="solar:close-linear" width="24" />
        </button>
      </div>

      <div class="action-sheet-content">
        <div v-if="words && words.length > 0" class="action-sheet-words">
          <button
            v-for="word in words"
            :key="word"
            class="action-sheet-word-item"
            :class="{ added: addedWords.has(word), loading: addingWord === word }"
            @click="addWordToList(word)"
            :disabled="addedWords.has(word) || addingWord === word"
          >
            <span class="action-sheet-word-text">{{ word }}</span>
            <Icon v-if="!addedWords.has(word) && addingWord !== word" icon="solar:add-circle-linear" width="26" />
            <Icon v-else-if="addedWords.has(word)" icon="solar:check-circle-bold" width="26" class="check-icon" />
            <Icon v-else icon="solar:refresh-circle-linear" width="26" class="spinning" />
          </button>
        </div>
        <div v-else class="action-sheet-empty">
          <p>No words to add</p>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
/* ─── Modal (Desktop) ─── */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-content {
  background: #36324a;
  border-radius: 16px;
  width: 90%;
  max-width: 500px;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #e2e0e8;
}

.modal-close-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.modal-close-btn:hover {
  color: #e2e0e8;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 10px;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.words-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.word-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: transparent;
  color: #b8b5c8;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.word-chip:hover:not(:disabled) {
  border-color: rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.05);
  color: #e2e0e8;
}

.word-chip.added {
  border-color: rgba(74, 222, 128, 0.3);
  background: rgba(74, 222, 128, 0.05);
  color: #4ade80;
}

.word-chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.word-chip .check-icon {
  color: #4ade80;
}

.empty-words {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  color: #9c99ab;
  font-size: 14px;
}

.empty-words p {
  margin: 0;
}

/* ─── Action Sheet (Mobile) ─── */
.mobile-extracted-words-sheet {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: #2d2a3e;
  z-index: 1000;
  display: none;
  flex-direction: column;
  overflow: hidden;
}

.action-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.action-sheet-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #e2e0e8;
}

.action-sheet-close {
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-sheet-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px 0;
}

.action-sheet-words {
  display: flex;
  flex-direction: column;
}

.action-sheet-word-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border: none;
  background: transparent;
  color: #b8b5c8;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  text-transform: capitalize;
}

.action-sheet-word-item:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.04);
  color: #e2e0e8;
}

.action-sheet-word-item.added {
  color: #4ade80;
}

.action-sheet-word-item:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-sheet-word-text {
  flex: 1;
  text-align: left;
}

.action-sheet-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  color: #9c99ab;
  font-size: 14px;
}

.action-sheet-empty p {
  margin: 0;
}

/* ─── Transitions ─── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 0.3s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100%);
}

.spinning {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* ─── Hide Modal on Mobile ─── */
@media (max-width: 768px) {
  .modal-overlay {
    display: none;
  }

  .mobile-extracted-words-sheet {
    display: flex;
  }
}
</style>
