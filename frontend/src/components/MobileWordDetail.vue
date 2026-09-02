<script setup lang="ts">
import { Icon } from '@iconify/vue'

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
}

interface Props {
  modelValue: boolean
  word: WordDetail | null
}

interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'speak-word'): void
  (e: 'speak', text: string): void
  (e: 'toggle-favorite'): void
  (e: 'toggle-known'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

function handleClose() {
  emit('update:modelValue', false)
}
</script>

<template>
  <transition name="slide-up">
    <div v-if="modelValue" class="mobile-detail-overlay">
      <div class="mobile-detail-header">
        <button class="mobile-back-btn" @click="handleClose">
          <Icon icon="solar:arrow-left-linear" width="24" />
        </button>
        <div class="mobile-header-actions">
          <button class="mobile-sound-btn" @click="emit('speak-word')" title="Play pronunciation">
            <Icon icon="solar:volume-loud-linear" width="22" />
          </button>
          <button class="mobile-heart-btn" @click="emit('toggle-favorite')" title="Add to favorites">
            <Icon v-if="word?.is_favorite" icon="solar:heart-bold" width="22" />
            <Icon v-else icon="solar:heart-linear" width="22" />
          </button>
        </div>
      </div>

      <div class="mobile-detail-content">
        <div class="mobile-word-header">
          <h2 class="mobile-word">{{ word?.word }}</h2>
        </div>

        <div class="mobile-section">
          <p class="mobile-definition">{{ word?.definition }}</p>
        </div>

        <!-- Synonyms Section (Mobile) -->
        <div class="mobile-section" v-if="word?.synonyms && word.synonyms.length">
          <h3 class="mobile-section-title">Synonyms</h3>
          <div class="synonyms-tags">
            <span v-for="syn in word.synonyms" :key="syn" class="synonym-tag" @click="emit('speak', syn)"
              title="Tap to hear">
              {{ syn }}
            </span>
          </div>
        </div>

        <div class="mobile-section">
          <h3 class="mobile-section-title">Examples</h3>
          <ul class="mobile-examples-list">
            <li v-for="(ex, i) in word?.examples" :key="i">{{ ex }}</li>
          </ul>
        </div>

        <div class="known-toggle">
          <span>Already know this word?</span>
          <label class="toggle-switch">
            <input type="checkbox" @change="emit('toggle-known')" />
            <span class="toggle-slider"></span>
          </label>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
/* ─── Mobile Detail Overlay ─── */
.mobile-detail-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: #2d2a3e;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.mobile-detail-header {
  display: flex;
  align-items: center;
  padding: 16px;
  gap: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.mobile-back-btn {
  margin-right: auto;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mobile-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mobile-heart-btn,
.mobile-sound-btn {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #f472b6;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mobile-sound-btn {
  color: #a78bfa;
}

.mobile-sound-btn:hover {
  background: rgba(167, 139, 250, 0.1);
  color: #c4b5fd;
}

.mobile-heart-btn:hover {
  background: rgba(244, 114, 182, 0.1);
}

.mobile-detail-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.mobile-word-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 4px;
}

.mobile-word {
  font-size: 28px;
  font-weight: 600;
  color: #e2e0e8;
  margin: 0;
}

.mobile-section {
  margin-bottom: 24px;
}

.mobile-section-title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1px;
  color: #9c99ab;
  margin-bottom: 10px;
  text-transform: uppercase;
}

.mobile-definition {
  font-size: 15px;
  line-height: 1.6;
  color: #b8b5c8;
  margin: 0;
}

.mobile-examples-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.mobile-examples-list li {
  position: relative;
  padding-left: 16px;
  margin-bottom: 10px;
  font-size: 15px;
  line-height: 1.5;
  color: #b8b5c8;
}

.mobile-examples-list li::before {
  content: '•';
  position: absolute;
  left: 0;
  color: #c4b5fd;
  font-weight: 700;
}

.synonyms-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.synonym-tag {
  padding: 6px 14px;
  border-radius: 999px;
  background: rgba(124, 58, 237, 0.12);
  color: #a78bfa;
  font-size: 13px;
  font-weight: 600;
  border: 1px solid rgba(124, 58, 237, 0.2);
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
}

.synonym-tag:hover {
  background: rgba(124, 58, 237, 0.2);
  border-color: rgba(124, 58, 237, 0.35);
  color: #c4b5fd;
}

.known-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 14px;
  margin-top: 8px;
  font-size: 14px;
  color: #b8b5c8;
}

.toggle-switch {
  position: relative;
  width: 48px;
  height: 26px;
  cursor: pointer;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: #3d3a52;
  border-radius: 26px;
  transition: 0.3s;
}

.toggle-slider::before {
  content: '';
  position: absolute;
  height: 20px;
  width: 20px;
  left: 3px;
  bottom: 3px;
  background: #9c99ab;
  border-radius: 50%;
  transition: 0.3s;
}

.toggle-switch input:checked+.toggle-slider {
  background: #7c3aed;
}

.toggle-switch input:checked+.toggle-slider::before {
  transform: translateX(22px);
  background: white;
}

/* ─── Transitions ─── */
.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 0.3s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100%);
}

@media (min-width: 769px) {
  .mobile-detail-overlay {
    display: none;
  }
}
</style>
