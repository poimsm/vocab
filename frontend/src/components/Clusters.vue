<!-- ClustersModule.vue -->
<script setup lang="ts">
import { ref, computed } from 'vue'
import { Icon } from '@iconify/vue'

// ── State ───────────────────────────────────────────────
const search = ref('')
const category = ref('all')
const difficulty = ref('all')
const sortBy = ref('newest')
const itemsPerPage = ref(8)
const currentPage = ref(1)

const showGenerateModal = ref(false)
const showNewClusterModal = ref(false)
const generateMode = ref<'auto' | 'custom'>('auto')
const selectedWords = ref<string[]>([])
const newClusterTitle = ref('')
const newClusterCategory = ref('')

// ── Data ────────────────────────────────────────────────
const allWords = [
  'Haunting', 'Terrifying', 'Chilling', 'Spine-tingling', 'Eerie',
  'Stretch', 'Bend', 'Twist', 'Gesture', 'Shrug',
  'Galaxy', 'Nebula', 'Orbit', 'Comet', 'Gravity',
  'Forest', 'Valley', 'Breeze', 'Wilderness', 'Flora',
  'Anxiety', 'Joy', 'Nostalgia', 'Frustration', 'Serenity',
  'Understand', 'Analyze', 'Research', 'Memorize', 'Insight',
  'Journey', 'Explore', 'Discover', 'Trek', 'Wander',
  'Chop', 'Stir', 'Bake', 'Boil', 'Season'
]

interface Cluster {
  id: number
  title: string
  subtitle: string
  words: string[]
  totalWords: number
  level: 'Beginner' | 'Intermediate' | 'Advanced'
  icon: string
  is_favorite: boolean
}

const clusters = ref<Cluster[]>([
  {
    id: 1,
    title: 'Things That Make You Shiver',
    subtitle: 'Emotions / Fear',
    words: ['Haunting', 'Terrifying', 'Chilling', 'Spine-tingling', 'Eerie'],
    totalWords: 12,
    level: 'Advanced',
    icon: '👻',
    is_favorite: false,
  },
  {
    id: 2,
    title: 'Body Movements',
    subtitle: 'Body',
    words: ['Stretch', 'Bend', 'Twist', 'Gesture', 'Shrug'],
    totalWords: 15,
    level: 'Intermediate',
    icon: '💪',
    is_favorite: false,
  },
  {
    id: 3,
    title: 'Space and Beyond',
    subtitle: 'Science / Universe',
    words: ['Galaxy', 'Nebula', 'Comet', 'Planet', 'Gravity'],
    totalWords: 14,
    level: 'Intermediate',
    icon: '🪐',
    is_favorite: false,
  },
  {
    id: 4,
    title: 'Nature & Environment',
    subtitle: 'Nature',
    words: ['Forest', 'Valley', 'Breeze', 'Wilderness', 'Flora'],
    totalWords: 18,
    level: 'Beginner',
    icon: '🌿',
    is_favorite: false,
  },
  {
    id: 5,
    title: 'Emotions & Feelings',
    subtitle: 'Emotions',
    words: ['Anxiety', 'Joy', 'Nostalgia', 'Frustration', 'Serenity'],
    totalWords: 16,
    level: 'Intermediate',
    icon: '🧠',
    is_favorite: false,
  },
  {
    id: 6,
    title: 'Learning & Knowledge',
    subtitle: 'Education',
    words: ['Understand', 'Analyze', 'Research', 'Memorize', 'Insight'],
    totalWords: 13,
    level: 'Beginner',
    icon: '📚',
    is_favorite: false,
  },
  {
    id: 7,
    title: 'Travel & Adventure',
    subtitle: 'Travel',
    words: ['Journey', 'Explore', 'Discover', 'Trek', 'Wander'],
    totalWords: 17,
    level: 'Intermediate',
    icon: '🧳',
    is_favorite: false,
  },
  {
    id: 8,
    title: 'In the Kitchen',
    subtitle: 'Food',
    words: ['Chop', 'Stir', 'Bake', 'Boil', 'Season'],
    totalWords: 11,
    level: 'Beginner',
    icon: '🥣',
    is_favorite: false,
  }
])

// ── Computed ────────────────────────────────────────────
const filteredClusters = computed(() => {
  let result = clusters.value
  if (search.value.trim()) {
    const q = search.value.toLowerCase()
    result = result.filter(c =>
      c.title.toLowerCase().includes(q) ||
      c.words.some(w => w.toLowerCase().includes(q))
    )
  }
  return result
})

const paginatedClusters = computed(() => {
  const start = (currentPage.value - 1) * itemsPerPage.value
  return filteredClusters.value.slice(start, start + itemsPerPage.value)
})

const totalPages = computed(() =>
  Math.ceil(filteredClusters.value.length / itemsPerPage.value)
)

const displayedRange = computed(() => {
  const start = (currentPage.value - 1) * itemsPerPage.value + 1
  const end = Math.min(currentPage.value * itemsPerPage.value, filteredClusters.value.length)
  return { start, end }
})

// ── Methods ─────────────────────────────────────────────
function toggleFavorite(id: number) {
  const c = clusters.value.find(x => x.id === id)
  if (c) c.is_favorite = !c.is_favorite
}

function levelClass(level: string) {
  return {
    Beginner: 'beginner',
    Intermediate: 'intermediate',
    Advanced: 'advanced'
  }[level] || ''
}

function levelLabel(level: string) {
  return level
}

function goToPage(page: number) {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page
  }
}

function generateClusters() {
  const themes: { title: string; subtitle: string; icon: string; level: 'Beginner' | 'Intermediate' | 'Advanced' }[] = [
    { title: 'Ocean & Water', subtitle: 'Nature', icon: '🌊', level: 'Beginner' },
    { title: 'Light & Shadow', subtitle: 'Physics', icon: '💡', level: 'Intermediate' },
    { title: 'Sound & Silence', subtitle: 'Music', icon: '🎵', level: 'Advanced' },
    { title: 'Mind & Thought', subtitle: 'Psychology', icon: '💭', level: 'Intermediate' },
  ]
  
  const randomIdx = Math.floor(Math.random() * themes.length)
  const chosenTheme = themes[randomIdx] // Guardamos la referencia

  // Si por alguna razón extraña fuera undefined, salimos (así TS se queda tranquilo)
  if (!chosenTheme) return

  const shuffled = [...allWords].sort(() => 0.5 - Math.random())
  const picked = shuffled.slice(0, 5)

  clusters.value.unshift({
    id: Date.now(),
    title: chosenTheme.title,
    subtitle: chosenTheme.subtitle,
    words: picked,
    totalWords: picked.length + Math.floor(Math.random() * 10),
    level: chosenTheme.level,
    icon: chosenTheme.icon,
    is_favorite: false,
  })

  showGenerateModal.value = false
  selectedWords.value = []
  currentPage.value = 1
}

function createCluster() {
  if (!newClusterTitle.value.trim()) return
  const words = selectedWords.value.length ? [...selectedWords.value] : ['Custom']
  clusters.value.unshift({
    id: Date.now(),
    title: newClusterTitle.value,
    subtitle: newClusterCategory.value || 'Custom',
    words: words,
    totalWords: words.length,
    level: 'Beginner',
    icon: '📦',
    is_favorite: false,
  })
  newClusterTitle.value = ''
  newClusterCategory.value = ''
  selectedWords.value = []
  showNewClusterModal.value = false
  currentPage.value = 1
}

function toggleWordSelection(word: string) {
  const idx = selectedWords.value.indexOf(word)
  if (idx > -1) selectedWords.value.splice(idx, 1)
  else selectedWords.value.push(word)
}
</script>

<template>
  <div class="clusters-page">

    <!-- Header -->
    <header class="header">
      <div>
        <h1>Clusters</h1>
        <p>Explore groups of words that share a common theme.</p>
      </div>

      <div class="header-actions">
        <button class="ai-btn" @click="showGenerateModal = true">
          <Icon icon="solar:magic-stick-3-linear" width="18" />
          Generate with AI
        </button>

        <button class="new-btn" @click="showNewClusterModal = true">
          <Icon icon="solar:add-circle-linear" width="18" />
          New cluster
        </button>
      </div>
    </header>

    <!-- Toolbar -->
    <div class="toolbar">
      <div class="search">
        <Icon icon="solar:magnifer-linear" width="20" color="#aaa" />
        <input
          v-model="search"
          placeholder="Search clusters..."
        >
      </div>

      <div class="select-wrapper">
        <select v-model="category">
          <option value="all">Category: All</option>
        </select>
        <Icon icon="solar:alt-arrow-down-linear" width="16" class="select-arrow" />
      </div>

      <div class="select-wrapper">
        <select v-model="difficulty">
          <option value="all">Difficulty: All</option>
        </select>
        <Icon icon="solar:alt-arrow-down-linear" width="16" class="select-arrow" />
      </div>

      <div class="select-wrapper sort-wrapper">
        <select v-model="sortBy">
          <option value="newest">Sort by: Newest</option>
        </select>
        <Icon icon="solar:sort-vertical-linear" width="16" class="select-arrow" />
      </div>

      <button class="filter-btn">
        <Icon icon="solar:tuning-2-linear" width="18" />
        Filters
      </button>
    </div>

    <!-- Featured Section -->
    <div class="featured-section">
      <h2 class="featured-title">
        <Icon icon="solar:stars-bold" width="18" color="#8b5cf6" />
        Featured Clusters
      </h2>
    </div>

    <!-- Grid -->
    <div class="grid">
      <article
        v-for="cluster in paginatedClusters"
        :key="cluster.id"
        class="card"
      >
        <button
          class="favorite-btn"
          :class="{ active: cluster.is_favorite }"
          @click="toggleFavorite(cluster.id)"
        >
          <Icon
            :icon="cluster.is_favorite ? 'solar:star-bold' : 'solar:star-linear'"
            width="20"
            :color="cluster.is_favorite ? '#f59e0b' : '#ccc'"
          />
        </button>

        <div class="card-header">
          <div class="card-icon">{{ cluster.icon }}</div>
          <div class="card-info">
            <h3 class="card-title">{{ cluster.title }}</h3>
            <span class="card-subtitle">{{ cluster.subtitle }}</span>
          </div>
        </div>

        <div class="card-words">
          <span
            v-for="word in cluster.words.slice(0, 5)"
            :key="word"
            class="word-chip"
          >
            {{ word }}
          </span>
          <span v-if="cluster.totalWords > cluster.words.length" class="word-chip more">
            +{{ cluster.totalWords - cluster.words.length }} more
          </span>
        </div>

        <div class="card-footer">
          <span class="word-count">{{ cluster.totalWords }} words</span>
          <span class="level" :class="levelClass(cluster.level)">
            <Icon icon="solar:chart-linear" width="14" />
            {{ levelLabel(cluster.level) }}
          </span>
          <button class="more-btn">
            <Icon icon="solar:menu-dots-bold" width="18" color="#999" />
          </button>
        </div>
      </article>
    </div>

    <!-- Footer -->
    <footer class="footer">
      <span class="results-text">
        Showing {{ displayedRange.start }}–{{ displayedRange.end }} of {{ filteredClusters.length }} clusters
      </span>

      <div class="pagination">
        <button
          class="page-btn"
          :disabled="currentPage === 1"
          @click="goToPage(currentPage - 1)"
        >
          <Icon icon="solar:alt-arrow-left-linear" width="16" />
        </button>

        <button
          v-for="page in totalPages"
          :key="page"
          class="page-btn"
          :class="{ active: currentPage === page }"
          @click="goToPage(page)"
        >
          {{ page }}
        </button>

        <button
          class="page-btn"
          :disabled="currentPage === totalPages"
          @click="goToPage(currentPage + 1)"
        >
          <Icon icon="solar:alt-arrow-right-linear" width="16" />
        </button>
      </div>

      <div class="select-wrapper per-page">
        <select v-model="itemsPerPage">
          <option :value="8">Per page: 8</option>
          <option :value="12">Per page: 12</option>
          <option :value="16">Per page: 16</option>
        </select>
        <Icon icon="solar:alt-arrow-down-linear" width="14" class="select-arrow" />
      </div>
    </footer>

    <!-- Generate Modal -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="showGenerateModal" class="modal-overlay" @click.self="showGenerateModal = false">
          <div class="modal">
            <div class="modal-header">
              <h3>
                <Icon icon="solar:magic-stick-3-linear" width="20" color="#8b5cf6" />
                Generate Clusters
              </h3>
              <button class="modal-close" @click="showGenerateModal = false">
                <Icon icon="solar:close-circle-linear" width="24" color="#aaa" />
              </button>
            </div>
            <div class="modal-body">
              <p class="modal-desc">AI will analyze your vocabulary and create thematic groupings.</p>
              <div class="generate-options">
                <label class="option-card" :class="{ selected: generateMode === 'auto' }">
                  <input type="radio" v-model="generateMode" value="auto">
                  <div class="option-icon" style="background: #f4edff;">
                    <Icon icon="solar:stars-linear" width="24" color="#8b5cf6" />
                  </div>
                  <div class="option-info">
                    <strong>Auto-discover</strong>
                    <span>Let AI find patterns in all your words</span>
                  </div>
                </label>
                <label class="option-card" :class="{ selected: generateMode === 'custom' }">
                  <input type="radio" v-model="generateMode" value="custom">
                  <div class="option-icon" style="background: #f0fdf4;">
                    <Icon icon="solar:pen-new-square-linear" width="24" color="#22c55e" />
                  </div>
                  <div class="option-info">
                    <strong>From selection</strong>
                    <span>Pick words to group together</span>
                  </div>
                </label>
              </div>
              <div v-if="generateMode === 'custom'" class="word-selector">
                <p class="selector-label">Select words to cluster:</p>
                <div class="word-chips">
                  <button
                    v-for="word in allWords"
                    :key="word"
                    class="word-chip-modal"
                    :class="{ selected: selectedWords.includes(word) }"
                    @click="toggleWordSelection(word)"
                  >
                    {{ word }}
                    <Icon v-if="selectedWords.includes(word)" icon="solar:check-circle-bold" width="14" color="#22c55e" />
                  </button>
                </div>
              </div>
            </div>
            <div class="modal-footer">
              <button class="btn-secondary" @click="showGenerateModal = false">Cancel</button>
              <button
                class="btn-primary"
                :disabled="generateMode === 'custom' && selectedWords.length < 2"
                @click="generateClusters"
              >
                <Icon icon="solar:magic-stick-3-linear" width="18" />
                Generate
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- New Cluster Modal -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="showNewClusterModal" class="modal-overlay" @click.self="showNewClusterModal = false">
          <div class="modal">
            <div class="modal-header">
              <h3>
                <Icon icon="solar:add-circle-linear" width="20" color="#8b5cf6" />
                New Cluster
              </h3>
              <button class="modal-close" @click="showNewClusterModal = false">
                <Icon icon="solar:close-circle-linear" width="24" color="#aaa" />
              </button>
            </div>
            <div class="modal-body">
              <div class="form-group">
                <label>Cluster title</label>
                <input v-model="newClusterTitle" placeholder="e.g., Ocean & Water" class="form-input">
              </div>
              <div class="form-group">
                <label>Category</label>
                <input v-model="newClusterCategory" placeholder="e.g., Nature" class="form-input">
              </div>
              <div class="form-group">
                <label>Add words</label>
                <div class="word-chips">
                  <button
                    v-for="word in allWords"
                    :key="word"
                    class="word-chip-modal"
                    :class="{ selected: selectedWords.includes(word) }"
                    @click="toggleWordSelection(word)"
                  >
                    {{ word }}
                    <Icon v-if="selectedWords.includes(word)" icon="solar:check-circle-bold" width="14" color="#22c55e" />
                  </button>
                </div>
              </div>
            </div>
            <div class="modal-footer">
              <button class="btn-secondary" @click="showNewClusterModal = false">Cancel</button>
              <button class="btn-primary" :disabled="!newClusterTitle.trim()" @click="createCluster">
                <Icon icon="solar:add-circle-linear" width="18" />
                Create cluster
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

  </div>
</template>

<style scoped>
/* ── Layout ────────────────────────────────────────────── */
.clusters-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
  background: #fafafa;
  min-height: 100vh;
}

/* ── Header ────────────────────────────────────────────── */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.header h1 {
  margin: 0;
  font-size: 2rem;
  font-weight: 700;
  color: #111;
}

.header p {
  margin: 6px 0 0;
  color: #777;
  font-size: 0.95rem;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.ai-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 18px;
  border: 0;
  border-radius: 10px;
  background: #8b5cf6;
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.ai-btn:hover {
  background: #7c3aed;
}

.new-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 18px;
  border: 1px solid #e5e5e5;
  border-radius: 10px;
  background: white;
  color: #555;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.new-btn:hover {
  border-color: #c0c0c0;
  background: #fafafa;
}

/* ── Toolbar ───────────────────────────────────────────── */
.toolbar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.search {
  flex: 1;
  min-width: 280px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 14px;
  border: 1px solid #e5e5e5;
  border-radius: 12px;
  background: white;
  height: 44px;
}

.search input {
  width: 100%;
  height: 100%;
  border: none;
  outline: none;
  font-size: 14px;
  color: #333;
  background: transparent;
}

.search input::placeholder {
  color: #bbb;
}

.select-wrapper {
  position: relative;
}

.select-wrapper select {
  height: 44px;
  padding: 0 36px 0 14px;
  border: 1px solid #e5e5e5;
  border-radius: 10px;
  background: white;
  font-size: 14px;
  color: #333;
  cursor: pointer;
  outline: none;
  appearance: none;
  -webkit-appearance: none;
}

.select-arrow {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  color: #999;
}

.sort-wrapper .select-arrow {
  color: #666;
}

.filter-btn {
  height: 44px;
  padding: 0 16px;
  border: 1px solid #e5e5e5;
  border-radius: 10px;
  background: white;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #555;
  cursor: pointer;
  font-weight: 500;
}

/* ── Featured ──────────────────────────────────────────── */
.featured-section {
  margin-top: 4px;
}

.featured-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #333;
}

/* ── Grid ──────────────────────────────────────────────── */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

/* ── Card ──────────────────────────────────────────────── */
.card {
  position: relative;
  background: white;
  border-radius: 16px;
  padding: 20px;
  border: 1px solid #eee;
  transition: box-shadow 0.2s;
}

.card:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.06);
}

.favorite-btn {
  position: absolute;
  top: 16px;
  right: 16px;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.card-icon {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  flex-shrink: 0;
}

.card-info {
  min-width: 0;
}

.card-title {
  margin: 0 0 4px;
  font-size: 16px;
  font-weight: 600;
  color: #3A425D;
  line-height: 1.3;
}

.card-subtitle {
  font-size: 12px;
  color: #8b5cf6;
  font-weight: 500;
}

/* Words */
.card-words {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.word-chip {
  padding: 5px 12px;
  background: #f5f5f5;
  border-radius: 8px;
  font-size: 13px;
  color: #555;
  font-weight: 500;
}

.word-chip.more {
  background: transparent;
  color: #999;
  padding-left: 4px;
}

/* Footer */
.card-footer {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

.word-count {
  font-size: 13px;
  color: #888;
}

.level {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 6px;
}

.level.beginner {
  color: #22c55e;
}

.level.intermediate {
  color: #f59e0b;
}

.level.advanced {
  color: #8b5cf6;
}

.more-btn {
  margin-left: auto;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ── Footer / Pagination ─────────────────────────────────── */
.footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 8px;
}

.results-text {
  font-size: 14px;
  color: #888;
}

.pagination {
  display: flex;
  gap: 6px;
  align-items: center;
}

.page-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  background: white;
  color: #555;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.page-btn:hover:not(:disabled) {
  background: #f9f9f9;
}

.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-btn.active {
  background: #8b5cf6;
  border-color: #8b5cf6;
  color: white;
}

.per-page {
  margin-left: auto;
}

.per-page select {
  height: 36px;
  padding: 0 28px 0 12px;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  background: white;
  font-size: 13px;
  color: #555;
  cursor: pointer;
  outline: none;
  appearance: none;
  -webkit-appearance: none;
}

.per-page .select-arrow {
  right: 10px;
}

/* ── Modal ─────────────────────────────────────────────── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.35);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 20px;
}

.modal {
  background: white;
  border-radius: 18px;
  width: 100%;
  max-width: 480px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0,0,0,0.15);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #f0f0f0;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
  display: flex;
  align-items: center;
  gap: 10px;
  color: #111;
}

.modal-close {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  transition: background 0.2s;
}

.modal-close:hover {
  background: #f5f5f5;
}

.modal-body {
  padding: 24px;
}

.modal-desc {
  margin: 0 0 20px;
  color: #666;
  font-size: 14px;
}

/* Options */
.generate-options {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.option-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  border: 1.5px solid #ececec;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  background: white;
}

.option-card:hover {
  border-color: #d0d0d0;
}

.option-card.selected {
  border-color: #8b5cf6;
  background: #faf7ff;
}

.option-card input {
  display: none;
}

.option-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.option-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.option-info strong {
  font-size: 14px;
  color: #111;
}

.option-info span {
  font-size: 12px;
  color: #888;
}

/* Word selector */
.word-selector {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #f0f0f0;
}

.selector-label {
  margin: 0 0 12px;
  font-size: 13px;
  font-weight: 600;
  color: #555;
}

.word-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.word-chip-modal {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1.5px solid #e5e5e5;
  border-radius: 999px;
  background: white;
  font-size: 13px;
  color: #555;
  cursor: pointer;
  transition: all 0.2s;
}

.word-chip-modal:hover {
  border-color: #c0c0c0;
}

.word-chip-modal.selected {
  border-color: #8b5cf6;
  background: #f4edff;
  color: #8b5cf6;
  font-weight: 500;
}

/* Form */
.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #444;
}

.form-input {
  width: 100%;
  padding: 12px 14px;
  border: 1.5px solid #e5e5e5;
  border-radius: 10px;
  font-size: 14px;
  color: #333;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.form-input:focus {
  border-color: #8b5cf6;
}

.form-input::placeholder {
  color: #bbb;
}

/* Modal footer */
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 24px 20px;
  border-top: 1px solid #f0f0f0;
}

.btn-secondary {
  padding: 10px 18px;
  border: 1px solid #e5e5e5;
  border-radius: 10px;
  background: white;
  color: #555;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-secondary:hover {
  background: #f9f9f9;
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border: 0;
  border-radius: 10px;
  background: #8b5cf6;
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary:hover:not(:disabled) {
  background: #7c3aed;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ── Transitions ─────────────────────────────────────────── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* ── Responsive ──────────────────────────────────────────── */
@media (max-width: 900px) {
  .clusters-page {
    padding: 16px;
  }

  .header {
    flex-direction: column;
    align-items: flex-start;
  }

  .header-actions {
    width: 100%;
    flex-direction: column;
  }

  .ai-btn,
  .new-btn {
    width: 100%;
    justify-content: center;
  }

  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .search {
    min-width: auto;
    width: 100%;
  }

  .select-wrapper,
  .filter-btn {
    width: 100%;
  }

  .select-wrapper select,
  .filter-btn {
    width: 100%;
  }

  .footer {
    flex-direction: column;
    gap: 16px;
    align-items: center;
  }

  .per-page {
    margin-left: 0;
  }
}
</style>