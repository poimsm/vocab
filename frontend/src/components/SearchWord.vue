<!-- SearchModule.vue -->
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Icon } from '@iconify/vue'

// ── State ───────────────────────────────────────────────
const search = ref('')
const hasSearched = ref(false)
const isSaved = ref(false)
const showHistory = ref(false)

const searchHistory = ref([
  'Ephemeral',
  'Pragmatic',
  'Resilient',
  'Ambiguous',
  'Meticulous',
])

// ── Mock Data ───────────────────────────────────────────
const mockResults: Record<string, {
  word: string
  phonetic: string
  partOfSpeech: string
  definition: string
  synonyms: string[]
  examples: string[]
}> = {
  ephemeral: {
    word: 'Ephemeral',
    phonetic: '/əˈfem(ə)rəl/',
    partOfSpeech: 'adjective',
    definition: 'Lasting for a very short time. Fleeting, transitory, or evanescent.',
    synonyms: ['fleeting', 'transitory', 'transient', 'evanescent', 'momentary', 'brief'],
    examples: [
      'The beauty of cherry blossoms is ephemeral, lasting only a few weeks each spring.',
      'Fame in the age of social media is often ephemeral.',
    ],
  },
  pragmatic: {
    word: 'Pragmatic',
    phonetic: '/praɡˈmadɪk/',
    partOfSpeech: 'adjective',
    definition: 'Dealing with things sensibly and realistically in a way that is based on practical rather than theoretical considerations.',
    synonyms: ['practical', 'realistic', 'sensible', 'rational', 'down-to-earth'],
    examples: [
      'We need a pragmatic solution that works within our budget constraints.',
      'Her pragmatic approach to problem-solving made her an invaluable team member.',
    ],
  },
  resilient: {
    word: 'Resilient',
    phonetic: '/rɪˈzɪlɪənt/',
    partOfSpeech: 'adjective',
    definition: 'Able to withstand or recover quickly from difficult conditions. Springing back into shape.',
    synonyms: ['flexible', 'tough', 'strong', 'adaptable', 'robust'],
    examples: [
      'Children are often more resilient than adults give them credit for.',
      'The resilient material returned to its original form after being compressed.',
    ],
  },
  ambiguous: {
    word: 'Ambiguous',
    phonetic: '/amˈbɪɡjuəs/',
    partOfSpeech: 'adjective',
    definition: 'Open to more than one interpretation; having a double meaning. Unclear or inexact.',
    synonyms: ['equivocal', 'vague', 'unclear', 'cryptic', 'enigmatic'],
    examples: [
      'His ambiguous statement left everyone confused about his true intentions.',
      'The ending of the novel was deliberately ambiguous.',
    ],
  },
  meticulous: {
    word: 'Meticulous',
    phonetic: '/məˈtɪkjʊləs/',
    partOfSpeech: 'adjective',
    definition: 'Showing great attention to detail; very careful and precise.',
    synonyms: ['careful', 'precise', 'scrupulous', 'thorough', 'punctilious'],
    examples: [
      'She was meticulous in her research, checking every source twice.',
      'The meticulous craftsmanship of the watch was evident in every detail.',
    ],
  },
}

// ── Computed ────────────────────────────────────────────
const result = computed(() => {
  if (!search.value.trim()) return null
  const key = search.value.toLowerCase().trim()
  return mockResults[key] || null
})

// ── Methods ─────────────────────────────────────────────
function doSearch() {
  if (!search.value.trim()) return
  hasSearched.value = true
  isSaved.value = false
  // Add to history if not already there
  const term = search.value.trim()
  const idx = searchHistory.value.indexOf(term)
  if (idx > -1) searchHistory.value.splice(idx, 1)
  searchHistory.value.unshift(term)
  if (searchHistory.value.length > 10) searchHistory.value.pop()
}

function playAudio(text: string) {
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'en-US'
  utterance.rate = 0.9
  speechSynthesis.speak(utterance)
}

function saveWord() {
  isSaved.value = !isSaved.value
}

function clearSearch() {
  search.value = ''
  hasSearched.value = false
  isSaved.value = false
}

function selectFromHistory(term: string) {
  search.value = term
  showHistory.value = false
  doSearch()
}

function clearHistory() {
  searchHistory.value = []
}

// Close history on click outside
function onDocClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.search-area')) {
    showHistory.value = false
  }
}

// Add/remove document click listener
watch(showHistory, (val) => {
  if (val) document.addEventListener('click', onDocClick)
  else document.removeEventListener('click', onDocClick)
})
</script>

<template>
  <div class="module">

    <!-- Hero Search -->
    <div class="hero">
      <h1>Search</h1>
      <p>Look up any word in your vocabulary.</p>

      <div class="search-area">
        <div class="search-box" :class="{ focused: showHistory }">
          <Icon icon="solar:magnifer-linear" width="22" color="#aaa" />
          <input
            v-model="search"
            placeholder="Type a word..."
            @keyup.enter="doSearch"
            @focus="showHistory = true"
          >
          <button v-if="search" class="clear-btn" @click="clearSearch">
            <Icon icon="solar:close-circle-linear" width="18" color="#ccc" />
          </button>
          <button class="history-toggle" @click="showHistory = !showHistory">
            <Icon icon="solar:history-linear" width="20" color="#aaa" />
          </button>
        </div>

        <!-- History Dropdown -->
        <Transition name="slide">
          <div v-if="showHistory && searchHistory.length" class="history-dropdown">
            <div class="history-header">
              <span>Recent searches</span>
              <button class="clear-history" @click="clearHistory">Clear</button>
            </div>
            <button
              v-for="term in searchHistory"
              :key="term"
              class="history-item"
              @click="selectFromHistory(term)"
            >
              <Icon icon="solar:clock-circle-linear" width="16" color="#aaa" />
              {{ term }}
            </button>
          </div>
        </Transition>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="!hasSearched" class="empty">
      <Icon icon="solar:document-search-linear" width="64" color="#e5e5e5" />
      <p>Type a word above to see its definition, synonyms, and examples.</p>
    </div>

    <!-- Results -->
    <div v-else-if="result" class="result">

      <!-- Word Header -->
      <div class="word-header">
        <div class="word-main">
          <h2>{{ result.word }}</h2>
          <span class="phonetic">{{ result.phonetic }}</span>
          <span class="pos">{{ result.partOfSpeech }}</span>
        </div>
        <div class="word-actions">
          <button class="icon-btn" @click="playAudio(result.word)" title="Listen">
            <Icon icon="solar:volume-loud-linear" width="20" color="#666" />
          </button>
          <button
            class="icon-btn"
            :class="{ saved: isSaved }"
            @click="saveWord"
            :title="isSaved ? 'Saved' : 'Save word'"
          >
            <Icon
              :icon="isSaved ? 'solar:bookmark-bold' : 'solar:bookmark-linear'"
              width="20"
              :color="isSaved ? '#8b5cf6' : '#666'"
            />
          </button>
        </div>
      </div>

      <!-- Definition -->
      <div class="section">
        <h3>Definition</h3>
        <p class="definition">{{ result.definition }}</p>
      </div>

      <!-- Synonyms -->
      <div class="section">
        <h3>Synonyms</h3>
        <div class="synonyms">
          <span v-for="syn in result.synonyms" :key="syn" class="synonym-chip">
            {{ syn }}
          </span>
        </div>
      </div>

      <!-- Examples -->
      <div class="section">
        <h3>Examples</h3>
        <div class="examples">
          <div
            v-for="(ex, i) in result.examples"
            :key="i"
            class="example"
          >
            <span class="example-num">{{ i + 1 }}</span>
            <p>{{ ex }}</p>
            <button class="play-example" @click="playAudio(ex)" title="Listen">
              <Icon icon="solar:play-bold" width="14" color="#8b5cf6" />
            </button>
          </div>
        </div>
      </div>

    </div>

    <!-- Not Found -->
    <div v-else class="not-found">
      <Icon icon="solar:confounded-square-linear" width="48" color="#ddd" />
      <p>No results for "<strong>{{ search }}</strong>"</p>
      <span>Try searching: Ephemeral, Pragmatic, Resilient...</span>
    </div>

  </div>
</template>

<style scoped>
/* ── Layout ────────────────────────────────────────────── */
.module {
  max-width: 680px;
  margin: 0 auto;
  padding: 40px 24px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  min-height: 100vh;
}

/* ── Hero ──────────────────────────────────────────────── */
.hero {
  text-align: center;
  margin-bottom: 48px;
}

.hero h1 {
  margin: 0 0 8px;
  font-size: 2rem;
  font-weight: 700;
  color: #111;
}

.hero p {
  margin: 0 0 28px;
  color: #888;
  font-size: 15px;
}

/* ── Search ────────────────────────────────────────────── */
.search-area {
  position: relative;
  max-width: 520px;
  margin: 0 auto;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
  height: 56px;
  border: 1.5px solid #e5e5e5;
  border-radius: 16px;
  background: white;
  transition: all 0.2s;
}

.search-box.focused,
.search-box:focus-within {
  border-color: #8b5cf6;
  box-shadow: 0 0 0 4px rgba(139, 92, 246, 0.08);
}

.search-box input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 16px;
  color: #333;
  background: transparent;
  height: 100%;
}

.search-box input::placeholder {
  color: #bbb;
}

.clear-btn,
.history-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  transition: background 0.2s;
}

.clear-btn:hover,
.history-toggle:hover {
  background: #f5f5f5;
}

/* ── History Dropdown ──────────────────────────────────── */
.history-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  background: white;
  border: 1px solid #eee;
  border-radius: 14px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.08);
  padding: 8px;
  z-index: 10;
  overflow: hidden;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px 4px;
  font-size: 12px;
  color: #999;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.clear-history {
  border: none;
  background: none;
  color: #8b5cf6;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}

.clear-history:hover {
  background: #f4edff;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border: none;
  background: none;
  border-radius: 10px;
  font-size: 14px;
  color: #444;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s;
}

.history-item:hover {
  background: #f9f9f9;
}

/* ── Empty State ───────────────────────────────────────── */
.empty {
  text-align: center;
  padding: 80px 20px;
  color: #bbb;
}

.empty p {
  margin-top: 16px;
  font-size: 15px;
  max-width: 320px;
  margin-left: auto;
  margin-right: auto;
  line-height: 1.5;
}

/* ── Result ────────────────────────────────────────────── */
.result {
  animation: fadeUp 0.3s ease;
}

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Word Header */
.word-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 32px;
  padding-bottom: 24px;
  border-bottom: 1px solid #f0f0f0;
}

.word-main {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.word-main h2 {
  margin: 0;
  font-size: 2.5rem;
  font-weight: 700;
  color: #111;
  letter-spacing: -0.02em;
}

.phonetic {
  font-size: 15px;
  color: #888;
  font-family: 'Georgia', serif;
}

.pos {
  display: inline-block;
  width: fit-content;
  padding: 3px 10px;
  background: #f5f3ff;
  color: #8b5cf6;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  text-transform: capitalize;
}

.word-actions {
  display: flex;
  gap: 8px;
}

.icon-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #eee;
  border-radius: 10px;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
}

.icon-btn:hover {
  background: #fafafa;
  border-color: #ddd;
}

.icon-btn.saved {
  border-color: #e0d4f7;
  background: #f5f3ff;
}

/* Sections */
.section {
  margin-bottom: 28px;
}

.section h3 {
  margin: 0 0 12px;
  font-size: 13px;
  font-weight: 600;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}

.definition {
  margin: 0;
  font-size: 17px;
  line-height: 1.7;
  color: #333;
}

/* Synonyms */
.synonyms {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.synonym-chip {
  padding: 6px 14px;
  background: #f5f5f5;
  border-radius: 8px;
  font-size: 14px;
  color: #555;
  font-weight: 500;
  transition: all 0.2s;
  cursor: default;
}

.synonym-chip:hover {
  background: #eee;
}

/* Examples */
.examples {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.example {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px 18px;
  background: #fafafa;
  border-radius: 12px;
  border: 1px solid #f0f0f0;
}

.example-num {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f0f0;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
  color: #999;
  flex-shrink: 0;
  margin-top: 2px;
}

.example p {
  margin: 0;
  font-size: 15px;
  line-height: 1.6;
  color: #444;
  flex: 1;
}

.play-example {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  background: #f5f3ff;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.2s;
}

.play-example:hover {
  background: #ede9fe;
}

/* ── Not Found ─────────────────────────────────────────── */
.not-found {
  text-align: center;
  padding: 80px 20px;
  color: #bbb;
}

.not-found p {
  margin: 16px 0 8px;
  font-size: 16px;
  color: #666;
}

.not-found span {
  font-size: 14px;
  color: #aaa;
}

/* ── Transitions ───────────────────────────────────────── */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.2s ease;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* ── Responsive ──────────────────────────────────────────── */
@media (max-width: 640px) {
  .module {
    padding: 24px 16px;
  }

  .hero h1 {
    font-size: 1.6rem;
  }

  .word-main h2 {
    font-size: 1.8rem;
  }

  .word-header {
    flex-direction: column;
    gap: 16px;
  }

  .word-actions {
    align-self: flex-start;
  }
}
</style>