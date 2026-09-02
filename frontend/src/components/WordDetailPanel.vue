<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import api from '@/utils/api'

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
  word: WordDetail | null
}

interface Emits {
  (e: 'close'): void
  (e: 'speak'): void
  (e: 'toggle-favorite'): void
  (e: 'toggle-known'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const frequencySegments = computed(() => {
  if (!props.word) return []
  const freq = props.word.frequency
  return [
    { label: 'RARE', active: freq === 'rare', color: '#4ade80' },
    { label: 'UNCOMMON', active: freq === 'uncommon' || freq === 'common', color: '#60a5fa' },
    { label: 'COMMON', active: freq === 'common', color: '#a78bfa' }
  ]
})

function handleToggleKnown() {
  emit('toggle-known')
}

function handleToggleFavorite() {
  emit('toggle-favorite')
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

function handleSpeak() {
  if (props.word) {
    speak(props.word.word)
  }
}
</script>

<template>
  <transition name="slide-panel">
    <aside v-if="word" class="word-panel">
      <div class="panel-header">
        <button class="back-btn" @click="emit('close')">
          <Icon icon="solar:arrow-left-linear" width="20" />
        </button>
        <div class="panel-header-actions">
          <button class="sound-btn" @click="handleSpeak" title="Play pronunciation">
            <Icon icon="solar:volume-loud-linear" width="20" />
          </button>
          <button class="heart-btn" @click="handleToggleFavorite" title="Add to favorites">
            <Icon v-if="word?.is_favorite" icon="solar:heart-bold" width="20" />
            <Icon v-else icon="solar:heart-linear" width="20" />
          </button>
        </div>
      </div>

      <h2 class="panel-word">{{ word.word }}</h2>
      <p class="panel-definition">{{ word.definition }}</p>

      <!-- Synonyms Section (Desktop) -->
      <div v-if="word.synonyms && word.synonyms.length" class="panel-section">
        <h3 class="section-title">SYNONYMS</h3>
        <div class="synonyms-list">
          <span v-for="syn in word.synonyms" :key="syn" class="synonym-tag" @click="speak(syn)"
            title="Click to hear">
            {{ syn }}
          </span>
        </div>
      </div>

      <div class="panel-section">
        <h3 class="section-title">EXAMPLES</h3>
        <ul class="examples-list">
          <li v-for="(ex, i) in word.examples" :key="i">{{ ex }}</li>
        </ul>
      </div>

      <div class="badges-row">
        <div class="badge">
          <span class="badge-label">{{ word.level }}</span>
          <span class="badge-sublabel">Level</span>
        </div>
        <div class="badge-divider">/</div>
        <div class="badge">
          <span class="badge-label">{{ word.context }}</span>
          <span class="badge-sublabel">Context</span>
        </div>
      </div>

      <div class="frequency-section">
        <span class="frequency-label">FREQUENCY</span>
        <div class="frequency-bar">
          <div v-for="(seg, i) in frequencySegments" :key="i" class="frequency-segment"
            :class="{ active: seg.active }" :style="{ background: seg.active ? seg.color : '#3d3a52' }">
            <div v-if="seg.active && word.frequency === 'common' && i === 2" class="frequency-star">
              <Icon icon="solar:star-bold" width="12" />
            </div>
          </div>
        </div>
        <div class="frequency-labels">
          <span>RARE</span>
          <span>UNCOMMON</span>
          <span>COMMON</span>
        </div>
      </div>
    </aside>
  </transition>
</template>

<style scoped>
/* ─── Word Panel (Desktop) ─── */
.word-panel {
  width: 380px;
  flex-shrink: 0;
  background: #36324a;
  border-left: 1px solid rgba(255, 255, 255, 0.06);
  padding: 24px;
  overflow-y: auto;
  z-index: 999;
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;
  height: 100vh;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.panel-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.back-btn {
  width: 36px;
  height: 36px;
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

.back-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
}

.heart-btn,
.sound-btn {
  width: 36px;
  height: 36px;
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

.heart-btn:hover,
.sound-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
}

.heart-btn {
  color: #f472b6;
}

.sound-btn {
  color: #a78bfa;
}

.sound-btn:hover {
  color: #c4b5fd;
  background: rgba(167, 139, 250, 0.1);
}

.panel-word {
  font-size: 32px;
  font-weight: 600;
  color: #9c99ab;
  margin-bottom: 16px;
  letter-spacing: -0.5px;
}

.panel-definition {
  font-size: 15px;
  line-height: 1.6;
  color: #b8b5c8;
  margin-bottom: 28px;
}

.panel-section {
  margin-bottom: 24px;
}

.section-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.5px;
  color: #9c99ab;
  margin-bottom: 12px;
}

.examples-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.examples-list li {
  position: relative;
  padding-left: 16px;
  margin-bottom: 10px;
  font-size: 14px;
  line-height: 1.5;
  color: #b8b5c8;
}

.examples-list li::before {
  content: '•';
  position: absolute;
  left: 0;
  color: #c4b5fd;
  font-weight: 700;
}

/* ─── Synonyms ─── */
.synonyms-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
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

/* ─── Badges ─── */
.badges-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: rgba(0, 0, 0, 0.15);
  border-radius: 14px;
  margin-bottom: 24px;
}

.badge {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.badge-label {
  font-size: 15px;
  font-weight: 600;
  color: #e2e0e8;
}

.badge-sublabel {
  font-size: 12px;
  color: #9c99ab;
}

.badge-divider {
  font-size: 18px;
  color: #9c99ab;
  font-weight: 300;
}

/* ─── Frequency Bar ─── */
.frequency-section {
  margin-top: 8px;
}

.frequency-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.5px;
  color: #9c99ab;
  margin-bottom: 10px;
  display: block;
}

.frequency-bar {
  display: flex;
  gap: 4px;
  height: 28px;
  margin-bottom: 8px;
}

.frequency-segment {
  flex: 1;
  border-radius: 6px;
  position: relative;
  transition: all 0.3s ease;
}

.frequency-segment.active {
  box-shadow: 0 0 12px rgba(167, 139, 250, 0.3);
}

.frequency-star {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: rgba(255, 255, 255, 0.6);
}

.frequency-labels {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1px;
  color: #9c99ab;
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

@media (max-width: 768px) {
  .word-panel {
    display: none;
  }
}
</style>
