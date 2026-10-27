<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { Icon } from '@iconify/vue'
import api from '@/utils/api'
import { wordApi } from '@/services/wordApi'
import { useActivityTracking } from '@/composables/useActivityTracking'

const { trackButtonClick } = useActivityTracking()

// ─── Throttle helper for infinite scroll ───
let scrollTimeout: ReturnType<typeof setTimeout> | null = null
function throttledScroll() {
  if (scrollTimeout) return
  scrollTimeout = setTimeout(() => {
    scrollTimeout = null
    onWindowScroll()
  }, 300) // 300ms throttle prevents infinite scroll loop
}

// ─── Types ───
type WordLevel = 'Beginner' | 'Intermediate' | 'Advanced'
type WordFrequency = 'rare' | 'uncommon' | 'common'
type FilterMode = 'all' | 'favorites'
type LearningStateFilter = 'all' | 'new' | 'learning' | 'mastered'

interface Word {
  id: number
  word: string
  definition: string
  level: WordLevel | number
  category: string
  frequency: WordFrequency
  isFavorite: boolean
  is_boosted: boolean
  isLearned: boolean
  addedAt: string
  totalExamples: number
  type: string
  examples: string[]
  synonyms: string[]
  sourceText?: string
  status?: 'pending' | 'ready'
  isExisting?: boolean
  explanation?: string
  targetWord?: string
  targetSynonym?: string
  targetExplanation?: string
}

// ─── State ───
const words = ref<Word[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const searchQuery = ref('')
const filterMode = ref<FilterMode>('all')
const learningStateFilter = ref<LearningStateFilter>('all')
const showBoostedOnly = ref(false)
const selectedWord = ref<Word | null>(null)
const showMobileDetail = ref(false)
const showFilterMenu = ref(false)
const showFilterDropdown = ref(false)
const showMoreControls = ref(false)
const showSearchMobile = ref(false)
const showSimpleBanner = ref(false)
const showVariantBanner = ref(false)
const showTipBanner = ref(true)

// ─── Infinite Scroll State ───
const currentPage = ref(1)
const totalPages = ref(1)
const totalWords = ref(0)
const totalFavorites = ref(0)
const hasMore = ref(false)
const loadingMore = ref(false)

// ─── Add Word State ───
const showAddDesktop = ref(false)
const showAddMobile = ref(false)
const newWordText = ref('')
const addMode = ref<'simple' | 'context' | null>('simple')
const adding = ref(false)
const addError = ref<string | null>(null)
const addSuccess = ref<string | null>(null)
const isSelectingTarget = ref(false)
const selectedTarget = ref<string | null>(null)

// ─── Command System State ───
interface CommandField {
  name: string
  label: string
  placeholder: string
}

interface Command {
  id: string
  name: string
  description: string
  icon: string
  fields: CommandField[]
  hint: string
}

const commands: Command[] = [
  {
    id: 'target',
    name: 'Understand Word in Context',
    description: 'Explain a word using your sentence',
    icon: '🎯',
    fields: [
      { name: 'sentence', label: 'sentence', placeholder: 'He hit the ball with the baseball bat' },
      { name: 'word', label: 'word to explain', placeholder: 'bat' }
    ],
    hint: `Understand Word in Context - Explains a word based on how it's used in YOUR sentence
This is the most powerful tool: instead of generic definitions, you get meaning specific to your context

How it works:
1. Paste a sentence or phrase
2. Select the word you want to understand
3. System explains that word in relation to your sentence

Example:
Sentence: "I need to book a flight"
Target word: "book"
Result: Explains the VERB meaning (to reserve), not the noun

Why this works:
✓ Learns words in real context (how native speakers use them)
✓ Avoids confusion from multiple meanings
✓ Helps with phrasal verbs, collocations, and idioms naturally
✓ Perfect for words from articles, movies, or conversations you're studying`
  },
]

const showCommandMenu = ref(false)
const selectedCommand = ref<Command | null>(null)
const filteredCommands = ref<Command[]>(commands)
const commandFieldValues = ref<Record<string, string>>({})
const showCommandHint = ref(false)

// ─── Explanation State ───
const showExplanation = ref(false)
const isExplaining = ref(false)

// ─── Relearn State ───
const showRelearnDialog = ref(false)
const relearnCount = ref(5)
const isRelearnProcessing = ref(false)
const relearnProgress = ref(0)
const relearnSuccess = ref(false)

// ─── View Mode State ───
const viewMode = ref<'list' | 'grid'>('list')

// ─── Boost State ───
const boostedWords = ref<Set<number>>(new Set())
const totalBoosted = ref(0)

// ─── Helpers ───
const levelColor = (level: WordLevel | number) => {
  const s = typeof level === 'number' ? String(level) : (level || '').toString().toLowerCase()
  if (s === '1' || s === 'beginner') return '#4ade80'
  if (s === '2' || s === 'intermediate') return '#60a5fa'
  if (s === '3' || s === 'advanced') return '#f472b6'
  return '#9c99ab'
}

const levelLabel = (level: WordLevel | number) => {
  if (level === 1) return 'Beginner'
  if (level === 2) return 'Intermediate'
  if (level === 3) return 'Advanced'
  const s = (level || '').toString().toLowerCase()
  if (s === 'beginner') return 'Beginner'
  if (s === 'intermediate') return 'Intermediate'
  if (s === 'advanced') return 'Advanced'
  return level?.toString() || '—'
}

const frequencyColor = (freq: WordFrequency) => {
  switch (freq) {
    case 'rare': return '#4ade80'
    case 'uncommon': return '#60a5fa'
    case 'common': return '#a78bfa'
    default: return '#9c99ab'
  }
}

const frequencyLabel = (freq: WordFrequency) => {
  if (!freq) return ''
  return freq.charAt(0).toUpperCase() + freq.slice(1)
}

// ─── Filtered Words ───
// Nota: El backend ya filtra por is_boosted cuando showBoostedOnly=true,
// así que simplemente devolvemos words.value
const filteredWords = computed(() => {
  return words.value
})

// ─── Text-to-Speech ───
function speak(text: string) {
  trackButtonClick('speak_word', { word: text })
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

// ─── API ───
async function fetchWords(reset = false) {
  if (reset) {
    currentPage.value = 1
    words.value = []
  }
  if (loading.value || loadingMore.value) return

  const isFirstLoad = currentPage.value === 1 && words.value.length === 0
  if (isFirstLoad) {
    loading.value = true
  } else {
    loadingMore.value = true
  }
  error.value = null

  try {
    const params: any = {
      page: currentPage.value,
      limit: 20
    }

    if (learningStateFilter.value !== 'all') {
      params.learning_state = learningStateFilter.value
    }

    if (filterMode.value === 'favorites') {
      params.is_favorite = true
    }

    if (showBoostedOnly.value) {
      params.is_boosted = true
    }

    if (searchQuery.value.trim()) {
      params.search = searchQuery.value.trim()
    }

    const response = await api.get('/words/words', { params })
const data = response.data

    const newItems = (data.items || []).map((item: any) => ({
      id: item.id,
      word: item.main,
      definition: item.meaning,
      level: item.level,
      category: item.context || item.type || 'General',
      frequency: item.frequency,
      isFavorite: item.is_favorite,
      is_boosted: item.is_boosted,
      isLearned: item.is_learned,
      addedAt: item.created_at ? item.created_at.split('T')[0] : '—',
      totalExamples: item.total_examples,
      type: item.type,
      examples: [],
      synonyms: item.synonyms || [],
      sourceText: item.source_text
    }))

    // Actualizar Set de palabras boosteadas
    if (reset) {
      boostedWords.value.clear()
      words.value = newItems
    } else {
      words.value.push(...newItems)
    }

    // Llenar el Set con palabras boosteadas
    newItems.forEach((item: any) => {
      if (item.is_boosted) {
        boostedWords.value.add(item.id)
      }
    })

    totalPages.value = data.pages || 1
    totalWords.value = data.total || 0
    totalFavorites.value = data.total_favorites || 0
    totalBoosted.value = data.total_boosted || 0
    hasMore.value = data.page < data.pages
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

async function loadMore() {
  if (!hasMore.value || loadingMore.value) return
  currentPage.value++
  await fetchWords()
}

// Global scroll listener for infinite scroll (single scroll, no nested containers)
function onWindowScroll() {
  if (!hasMore.value || loadingMore.value) return
  const scrollTop = window.scrollY || document.documentElement.scrollTop
  const scrollHeight = document.documentElement.scrollHeight
  const clientHeight = window.innerHeight
  // Trigger when within 200px of bottom
  if (scrollTop + clientHeight >= scrollHeight - 200) {
    loadMore()
  }
}

async function fetchWordDetail(id: number) {
  try {
    const response = await api.get(`/words/words/${id}`)
const data = response.data
    selectedWord.value = {
      id: data.id,
      word: data.main,
      definition: data.meaning,
      level: data.level,
      category: data.context || data.type || 'General',
      frequency: data.frequency,
      isFavorite: data.is_favorite,
      is_boosted: data.is_boosted,
      isLearned: data.is_learned,
      addedAt: data.created_at ? data.created_at.split('T')[0] : '—',
      totalExamples: data.total_examples,
      type: data.type,
      sourceText: data.source_text,
      examples: data.examples || [],
      synonyms: data.synonyms || [],
      targetWord: data.target_word,
      targetSynonym: data.target_synonym,
      targetExplanation: data.target_explanation
    }
    // Scroll detail panel to top after selecting
    await nextTick()
    const detailPanel = document.querySelector('.detail-panel')
    if (detailPanel) {
      detailPanel.scrollTop = 0
    }
  } catch (e) {
    alert('Could not load word detail')
  }
}

async function toggleFavoriteApi(word: Word) {
  try {
    const wasFavorite = word.isFavorite
    const response = await api.patch(`words/words/${word.id}/favorite`)
    const data = response.data
    word.isFavorite = data.is_favorite ?? !word.isFavorite

    // Actualizar contador reactivamente
    if (wasFavorite && !word.isFavorite) {
      totalFavorites.value--
    } else if (!wasFavorite && word.isFavorite) {
      totalFavorites.value++
    }

    if (selectedWord.value?.id === word.id) {
      selectedWord.value.isFavorite = word.isFavorite
    }
  } catch (e) {
    alert('Failed to toggle favorite')
  }
}

async function addWordApi() {
  let text = ''
  let targetWord = null

  // Build text based on mode
  if (addMode.value === 'simple') {
    text = newWordText.value.trim()
    targetWord = selectedTarget.value || null
  } else if (addMode.value === 'context' && selectedCommand.value) {
    // For context mode, build formatted text: "sentence <- word"
    const sentence = commandFieldValues.value['sentence'] || ''
    const word = commandFieldValues.value['word'] || ''
    text = `${sentence} <- ${word}`.trim()
  }

  if (!text) return
  adding.value = true
  addError.value = null
  addSuccess.value = null

  try {
    const payload = { text }
    if (targetWord) {
      payload.target_word = targetWord
    }
    const response = await api.post('/words/single', payload)
    const data = response.data

    // Handle error
    if (data.status === 'error') {
      addError.value = data.message
      return
    }

    // Handle existing word
    if (data.status === 'existing') {
      const existingWord = data.word
      const newWord: Word = {
        id: existingWord.id,
        word: existingWord.main,
        definition: existingWord.meaning || 'N/A',
        level: existingWord.level,
        category: existingWord.context || existingWord.type,
        frequency: existingWord.frequency || 'common',
        isFavorite: existingWord.is_favorite,
        is_boosted: existingWord.is_boosted || false,
        isLearned: existingWord.is_learned,
        addedAt: new Date(existingWord.created_at).toISOString().split('T')[0] ?? '',
        totalExamples: existingWord.total_examples || 0,
        type: existingWord.type,
        examples: existingWord.examples || [],
        synonyms: existingWord.synonyms || [],
        sourceText: existingWord.source_text,
        status: 'ready',
        isExisting: true
      }

      // Add to the beginning of the list
      words.value.unshift(newWord)
      totalWords.value++

      addSuccess.value = 'Esta palabra ya está en tu lista.'
      newWordText.value = ''
      closeAdd()
      return
    }

    // Handle successful queue
    if (data.status === 'queued') {
      // Add word optimistically with pending status
      const tempId = -Date.now() // Temporary ID
      const newWord: Word = {
        id: tempId,
        word: text.charAt(0).toUpperCase() + text.slice(1).toLowerCase(),
        definition: 'Loading...',
        level: 2,
        category: 'Pending',
        frequency: 'common',
        isFavorite: false,
        is_boosted: false,
        isLearned: false,
        addedAt: new Date().toISOString().split('T')[0] ?? '',
        totalExamples: 0,
        type: 'pending',
        examples: [],
        synonyms: [],
        status: 'pending',
        isExisting: false
      }

      // Add to the beginning of the list
      words.value.unshift(newWord)
      totalWords.value++

      addSuccess.value = 'Word added! It will be processed shortly.'
      newWordText.value = ''
      closeAdd()

      // Reload after a delay to get the real word data
      setTimeout(() => {
        fetchWords(true)
      }, 4000)
    }
  } catch (error: any) {
    const detail = error.response?.data?.detail || error.response?.data?.message || error.message
    addError.value = detail
  } finally {
    adding.value = false
  }
}

async function deleteWordApi(id: number) {
  if (!confirm('Delete this word?')) return
  try {
    await api.delete(`/words/words/${id}`)
    words.value = words.value.filter(w => w.id !== id)

    if (selectedWord.value?.id === id) {
      selectedWord.value = null
      showMobileDetail.value = false
    }
  } catch (e) {
    alert('Failed to delete word')
  }
}

async function getAIExplanation() {
  if (!selectedWord.value) return

  isExplaining.value = true
  try {
    const result = await wordApi.getWordExplanation(selectedWord.value.id)
    if (selectedWord.value) {
      selectedWord.value.explanation = result.explanation
    }
  } catch (err) {
    console.error('Error getting explanation:', err)
    alert('Failed to generate explanation')
  } finally {
    isExplaining.value = false
  }
}

function toggleExplanation() {
  trackButtonClick('toggle_explanation', { word_id: selectedWord.value?.id })
  if (!showExplanation.value && !selectedWord.value?.explanation) {
    getAIExplanation()
  }
  showExplanation.value = !showExplanation.value
}

// ─── Filter & View Mode Handlers ───
function setFilterModeAll() {
  trackButtonClick('filter_mode_all')
  filterMode.value = 'all'
  showBoostedOnly.value = false
  showFilterDropdown.value = false
  fetchWords(true)
}

function setFilterModeFavorites() {
  trackButtonClick('filter_mode_favorites')
  filterMode.value = 'favorites'
  showBoostedOnly.value = false
  learningStateFilter.value = 'all'
  showFilterDropdown.value = false
  fetchWords(true)
}

function setFilterBoosted() {
  trackButtonClick('filter_mode_boosted')
  showBoostedOnly.value = !showBoostedOnly.value
  filterMode.value = 'all'
  showFilterDropdown.value = false
  fetchWords(true)
}

function setLearningStateAll() {
  trackButtonClick('learning_state_filter_all')
  learningStateFilter.value = 'all'
}

function setLearningStateNew() {
  trackButtonClick('learning_state_filter_new')
  learningStateFilter.value = 'new'
}

function setLearningStateLearning() {
  trackButtonClick('learning_state_filter_learning')
  learningStateFilter.value = 'learning'
}

function setLearningStateMastered() {
  trackButtonClick('learning_state_filter_mastered')
  learningStateFilter.value = 'mastered'
}

function setViewModeList() {
  trackButtonClick('view_mode_list')
  viewMode.value = 'list'
}

function setViewModeGrid() {
  trackButtonClick('view_mode_grid')
  viewMode.value = 'grid'
}

function toggleSearchMobile() {
  trackButtonClick('toggle_mobile_search')
  showSearchMobile.value = !showSearchMobile.value
}

function clearSearch() {
  trackButtonClick('clear_search')
  searchQuery.value = ''
  showSearchMobile.value = false
}

function toggleFilterMenu() {
  trackButtonClick('toggle_filter_menu')
  showFilterMenu.value = !showFilterMenu.value
}

function closeFilterMenu() {
  showFilterMenu.value = false
}

function retryFetchWords() {
  trackButtonClick('retry_fetch_words')
  fetchWords(true)
}

function openRelearnDialog() {
  trackButtonClick('open_relearn_dialog')
  relearnCount.value = 5
  relearnProgress.value = 0
  relearnSuccess.value = false
  showRelearnDialog.value = true
}

function closeRelearnDialog() {
  showRelearnDialog.value = false
  relearnSuccess.value = false
  relearnProgress.value = 0
}

function selectRelearnCount(count: number) {
  relearnCount.value = count
  trackButtonClick('relearn_count_selected', { count })
}

async function simulateRelearn() {
  trackButtonClick('relearn_start', { count: relearnCount.value })
  isRelearnProcessing.value = true
  relearnProgress.value = 0
  relearnSuccess.value = false

  try {
    // Simulate progress animation while fetching
    const interval = setInterval(() => {
      relearnProgress.value += Math.random() * 20
      if (relearnProgress.value > 70) {
        relearnProgress.value = 70
      }
    }, 200)

    // Call the relearn endpoint
    const response = await api.post('/words/relearn', { count: relearnCount.value })

    clearInterval(interval)
    relearnProgress.value = 100

    if (response.data.status === 'ok') {
      setTimeout(() => {
        isRelearnProcessing.value = false
        relearnSuccess.value = true
        trackButtonClick('relearn_success', { count: relearnCount.value })
        // Refresh words list to show updated learning states
        fetchWords(true)
      }, 300)
    } else {
      clearInterval(interval)
      isRelearnProcessing.value = false
      error.value = response.data.message || 'Error relearning words'
      trackButtonClick('relearn_error', { message: error.value })
    }
  } catch (err: any) {
    isRelearnProcessing.value = false
    error.value = err.response?.data?.message || 'Error relearning words'
    trackButtonClick('relearn_error', { message: error.value })
    console.error('Error relearning words:', err)
  }
}


// ─── Computed ───
// (totalFavorites removed - now using totalFavorites from API)

// ─── Methods ───
function toggleFavoritesFilter() {
  trackButtonClick('toggle_favorites_filter', { current_mode: filterMode.value })
  if (filterMode.value === 'favorites') {
    filterMode.value = 'all'
  } else {
    filterMode.value = 'favorites'
    learningStateFilter.value = 'all'
  }
}

function toggleBoostedFilter() {
  trackButtonClick('toggle_boosted_filter', { show_boosted_only: showBoostedOnly.value })
  showBoostedOnly.value = !showBoostedOnly.value
  fetchWords(true) // Recargar palabras con el nuevo filtro
}

function toggleFavorite(word: Word) {
  trackButtonClick('toggle_favorite', { word_id: word.id, is_favorite: word.isFavorite })
  toggleFavoriteApi(word)
}

async function toggleBoostApi(word: Word) {
  try {
    const wasBoosted = word.is_boosted
    const response = await api.patch(`words/words/${word.id}/boost`)

    // Actualizar el estado del word
    word.is_boosted = response.data.is_boosted

    // Actualizar el Set local
    if (response.data.is_boosted) {
      boostedWords.value.add(word.id)
    } else {
      boostedWords.value.delete(word.id)
    }

    // Actualizar contador
    if (response.data.is_boosted && !wasBoosted) {
      totalBoosted.value++
    } else if (!response.data.is_boosted && wasBoosted) {
      totalBoosted.value--
    }

  } catch (err) {
    error.value = "Error toggling boost"
  }
}

function toggleBoost(word: Word) {
  trackButtonClick('toggle_boost', { word_id: word.id, is_boosted: word.is_boosted })
  toggleBoostApi(word)
}

function deleteWord(id: number) {
  trackButtonClick('delete_word', { word_id: id })
  deleteWordApi(id)
}

function openDetail(word: Word) {
  trackButtonClick('open_word_detail', { word_id: word.id })
  fetchWordDetail(word.id)
  showExplanation.value = false
  if (window.innerWidth <= 768) {
    showMobileDetail.value = true
  }
}

function closeDetail() {
  selectedWord.value = null
  showMobileDetail.value = false
  showExplanation.value = false
}

function openAdd() {
  trackButtonClick('open_add_word_modal')
  newWordText.value = ''
  isSelectingTarget.value = false
  selectedTarget.value = null
  if (window.innerWidth <= 768) {
    showAddMobile.value = true
  } else {
    showAddDesktop.value = true
  }
}

function closeAdd() {
  showAddDesktop.value = false
  showAddMobile.value = false
  newWordText.value = ''
  addMode.value = 'simple'
  selectedCommand.value = null
  commandFieldValues.value = {}
  addError.value = null
  addSuccess.value = null
  isSelectingTarget.value = false
  selectedTarget.value = null
}

function addWord() {
  trackButtonClick('add_word')
  addWordApi()
}

function handleAddKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') addWord()
  if (e.key === 'Escape') closeAdd()
}

function toggleSelectTarget() {
  isSelectingTarget.value = !isSelectingTarget.value
}

function selectWordAsTarget(word: string) {
  selectedTarget.value = word
  isSelectingTarget.value = false
}

// ─── Command System Functions ───
function handleInputChange(text: string) {
  // Si el texto comienza con "/" y no hay comando seleccionado, mostrar menú
  if (text.startsWith('/') && !selectedCommand.value) {
    const query = text.slice(1).toLowerCase()
    if (query === '') {
      filteredCommands.value = commands
    } else {
      filteredCommands.value = commands.filter(cmd =>
        cmd.name.toLowerCase().includes(query) ||
        cmd.id.toLowerCase().includes(query)
      )
    }
    showCommandMenu.value = true
  } else {
    showCommandMenu.value = false
  }
}

function selectCommand(command: Command | undefined) {
  if (!command) return
  selectedCommand.value = command
  newWordText.value = ''
  showCommandMenu.value = false
  showCommandHint.value = false
  // Inicializar los valores de los campos
  commandFieldValues.value = {}
  command.fields.forEach(field => {
    commandFieldValues.value[field.name] = ''
  })
  trackButtonClick('select_command', { command_id: command.id })
}

function cancelCommandSelection() {
  selectedCommand.value = null
  showCommandMenu.value = false
  showCommandHint.value = false
  newWordText.value = ''
  commandFieldValues.value = {}
}

function submitCommand() {
  if (!selectedCommand.value) return

  // Obtener los valores (permitir vacíos)
  const values = Object.values(commandFieldValues.value)

  // Construir el texto según el tipo de comando
  let finalText = ''
  switch (selectedCommand.value.id) {
    case 'search':
      finalText = values[0] || ''
      break
    case 'pattern':
      finalText = values[0] || ''
      break
    case 'slang':
      finalText = values[0] || ''
      break
    case 'target':
      finalText = `${values[0] || ''} <- ${values[1] || ''}`.trim()
      break
    case 'pos':
      finalText = `${values[0] || ''} : ${values[1] || ''}`.trim()
      break
    case 'compare':
      finalText = `${values[0] || ''} vs ${values[1] || ''}`.trim()
      break
  }

  // Solo si hay algo que buscar
  if (!finalText.trim()) {
    return
  }

  newWordText.value = finalText
  selectedCommand.value = null
  commandFieldValues.value = {}
  adding.value = true
  addError.value = null
  addSuccess.value = null

  // Ejecutar directamente
  addWordApi()
}

// ─── Watchers ───
import { watch } from 'vue'

watch([filterMode, learningStateFilter, searchQuery], () => {
  fetchWords(true)
})

onMounted(() => {
  fetchWords()
  window.addEventListener('scroll', throttledScroll)
})

onUnmounted(() => {
  window.removeEventListener('scroll', throttledScroll)
})
</script>

<template>
  <div class="my-words-view">
    <!-- Slogan Banner -->
    <!-- <div class="slogan-banner">
      <img src="/banner.png" alt="Add words from books, movies, and beyond" class="banner-image" />
      <div class="banner-overlay">
        <div class="banner-content" style="display:none">
          <h2 class="banner-title">add words from <span class="title-highlight">your books</span></h2>
          <p class="banner-subtitle">Turn the words you find in books into learning experience</p>
        </div>
      </div>
    </div> -->

    <!-- Simple Banner -->
    <transition name="slide-down">
      <div v-if="showSimpleBanner" class="simple-banner">
        <div class="banner-message">
          <p>Add words from your books, movies, and real life to build your vocabulary</p>
        </div>
        <button class="banner-close" @click="showSimpleBanner = false" title="Dismiss">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
    </transition>

    <!-- Variant Banner (Alternative) -->
    <transition name="slide-down">
      <div v-if="showVariantBanner" class="variant-banner">
        <div class="variant-banner-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
          </svg>
        </div>
        <div class="variant-banner-content">
          <h3 class="variant-banner-title">Expand Your Vocabulary</h3>
          <p class="variant-banner-text">Add words from your favorite books, movies, and real-life conversations</p>
        </div>
        <div class="variant-banner-actions">
          <button class="variant-banner-btn-action" @click="showVariantBanner = false">
            Add Now
          </button>
          <button class="variant-banner-btn-close" @click="showVariantBanner = false">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>
    </transition>

    <!-- Tip Banner (Completely Different) -->
    <transition name="slide-down">
      <div v-if="showTipBanner" class="tip-banner">
        <div class="tip-banner-left">
          <div class="tip-badge">Word Collector</div>
          <p class="tip-banner-message">Hear a fun word in a movie or book? Put it in your list so you don't forget to practice it later!</p>
        </div>
        <button class="tip-banner-dismiss" @click="showTipBanner = false">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
    </transition>

    <!-- Header -->
    <header class="words-header">
      <div class="header-left">
        <h1 class="words-title">My Words</h1>
        <p class="words-subtitle">{{ totalWords }} words saved</p>
      </div>
      <div class="header-actions">
        <button class="relearn-btn" @click="openRelearnDialog" :disabled="loading" title="Randomly relearn some words">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0114.85-4.95M20.49 15a9 9 0 01-14.85 4.95"/>
          </svg>
          <span>Relearn</span>
        </button>
        <button class="add-btn" @click="openAdd" :disabled="loading">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/>
          </svg>
          <span>Add Word</span>
        </button>
      </div>
    </header>

    <!-- Search & Filter Toolbar -->
    <div class="words-toolbar">
      <div class="search-box">
        <svg class="search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search your words..."
          class="search-input"
        />
      </div>

      <!-- Toolbar Controls (Right side) -->
      <div class="toolbar-controls">
        <!-- Filter Dropdown -->
        <div class="filter-dropdown-wrap">
          <button class="filter-dropdown-toggle" @click="showFilterDropdown = !showFilterDropdown">
            {{ filterMode === 'favorites' ? 'Favorites' : showBoostedOnly ? 'Boosted' : 'All Words' }}
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>
          <transition name="fade">
            <div v-if="showFilterDropdown" class="filter-dropdown-content" @click="showFilterDropdown = false">
              <button class="dropdown-item" :class="{ active: filterMode === 'all' && !showBoostedOnly }" @click="setFilterModeAll()">
                All Words
              </button>
              <button class="dropdown-item" :class="{ active: filterMode === 'favorites' }" @click="setFilterModeFavorites()">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                </svg>
                Favorites <span v-if="totalFavorites > 0" class="badge">{{ totalFavorites }}</span>
              </button>
              <button class="dropdown-item" :class="{ active: showBoostedOnly }" @click="setFilterBoosted()">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                </svg>
                Boosted <span v-if="totalBoosted > 0" class="badge">{{ totalBoosted }}</span>
              </button>
            </div>
          </transition>
        </div>
        <!-- View Mode Buttons (Desktop) -->
        <div class="view-mode-desktop">
          <button class="view-mode-btn" :class="{ active: viewMode === 'list' }" @click="setViewModeList" title="List view">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
            </svg>
          </button>
          <button class="view-mode-btn" :class="{ active: viewMode === 'grid' }" @click="setViewModeGrid" title="Grid view">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
            </svg>
          </button>
        </div>

        <!-- More Controls Dropdown -->
        <div class="more-controls-wrap">
        <button class="more-controls-toggle" @click="showMoreControls = !showMoreControls" title="More options">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/>
          </svg>
        </button>
        <transition name="fade">
          <div v-if="showMoreControls" class="more-controls-content">
            <div class="controls-section">
              <div class="section-label">Learning State</div>
              <button class="control-btn" :class="{ active: learningStateFilter === 'all' }" @click="setLearningStateAll(); showMoreControls = false">
                All
              </button>
              <button class="control-btn" :class="{ active: learningStateFilter === 'new' }" @click="setLearningStateNew(); showMoreControls = false">
                New
              </button>
              <button class="control-btn" :class="{ active: learningStateFilter === 'learning' }" @click="setLearningStateLearning(); showMoreControls = false">
                In Progress
              </button>
              <button class="control-btn" :class="{ active: learningStateFilter === 'mastered' }" @click="setLearningStateMastered(); showMoreControls = false">
                Learned
              </button>
            </div>
            <div class="controls-divider"></div>
            <button class="control-btn relearn-option" @click="openRelearnDialog(); showMoreControls = false" :disabled="loading">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0114.85-4.95M20.49 15a9 9 0 01-14.85 4.95"/>
              </svg>
              Relearn
            </button>
          </div>
        </transition>
      </div>
      </div>

      <!-- Mobile Search Button -->
      <button class="mobile-search-btn" @click="toggleSearchMobile">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
      </button>
      <!-- Mobile Favorites Button -->
      <button class="mobile-favorites-btn" :class="{ active: filterMode === 'favorites' }" @click="toggleFavoritesFilter">
        <svg v-if="filterMode === 'favorites'" width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
        </svg>
        <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
        </svg>
        <span v-if="totalFavorites > 0" class="mobile-fav-badge">{{ totalFavorites }}</span>
      </button>
      <!-- Mobile Boosted Button -->
      <button class="mobile-boosted-btn" :class="{ active: showBoostedOnly }" @click="toggleBoostedFilter" title="Show only boosted words">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
          <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
        </svg>
        <span v-if="totalBoosted > 0" class="boosted-count">{{ totalBoosted }}</span>
      </button>
      <!-- Mobile Filter Button -->
      <button class="mobile-filter-btn" :class="{ active: learningStateFilter !== 'all' }" @click="toggleFilterMenu">
        <Icon icon="solar:filter-outline" width="18" />
      </button>
    </div>

    <!-- Active Filter Banner -->
    <transition name="slide-down">
      <div v-if="showBoostedOnly" class="active-filter-banner">
        <div class="banner-content">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
          </svg>
          <span class="banner-text">
            Filtering <strong>{{ words.length }}</strong> of <strong>{{ totalBoosted }}</strong> boosted word{{ totalBoosted !== 1 ? 's' : '' }}
          </span>
          <button class="banner-close" @click="toggleBoostedFilter" title="Clear filter">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
            </svg>
          </button>
        </div>
      </div>
    </transition>

    <!-- Learning State Filter -->
    <div class="learning-state-filter" :class="{ disabled: filterMode === 'favorites' }">
      <button
        class="state-tab"
        :class="{ active: learningStateFilter === 'all' }"
        :disabled="filterMode === 'favorites'"
        @click="setLearningStateAll"
      >
        All
      </button>
      <button
        class="state-tab"
        :class="{ active: learningStateFilter === 'new' }"
        :disabled="filterMode === 'favorites'"
        @click="setLearningStateNew"
      >
        New
      </button>
      <button
        class="state-tab"
        :class="{ active: learningStateFilter === 'learning' }"
        :disabled="filterMode === 'favorites'"
        @click="setLearningStateLearning"
      >
        In Progress
      </button>
      <button
        class="state-tab"
        :class="{ active: learningStateFilter === 'mastered' }"
        :disabled="filterMode === 'favorites'"
        @click="setLearningStateMastered"
      >
        Learned
      </button>

      <!-- View Mode Toggle -->
      <div class="view-mode-toggle">
        <button
          class="view-mode-btn"
          :class="{ active: viewMode === 'list' }"
          @click="setViewModeList"
          title="List view"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
          </svg>
        </button>
        <button
          class="view-mode-btn"
          :class="{ active: viewMode === 'grid' }"
          @click="setViewModeGrid"
          title="Grid view"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Mobile Search Panel -->
    <transition name="slide-down">
      <div v-if="showSearchMobile" class="mobile-search-panel">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search your words..."
          class="mobile-search-input"
          autofocus
          @keydown.escape="showSearchMobile = false"
        />
        <button class="mobile-search-close" @click="clearSearch">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
        </button>
      </div>
    </transition>

    <!-- Mobile Filter Menu -->
    <transition name="fade">
      <div v-if="showFilterMenu" class="mobile-filter-backdrop" @click="closeFilterMenu"></div>
    </transition>
    <transition name="slide-down">
      <div v-if="showFilterMenu" class="mobile-filter-menu">
        <button
          class="filter-menu-item"
          :class="{ active: learningStateFilter === 'all' }"
          @click="setLearningStateAll(); closeFilterMenu()"
        >
          <span>All</span>
          <svg v-if="learningStateFilter === 'all'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
        </button>
        <button
          class="filter-menu-item"
          :class="{ active: learningStateFilter === 'new' }"
          @click="setLearningStateNew(); closeFilterMenu()"
        >
          <span>New</span>
          <svg v-if="learningStateFilter === 'new'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
        </button>
        <button
          class="filter-menu-item"
          :class="{ active: learningStateFilter === 'learning' }"
          @click="setLearningStateLearning(); closeFilterMenu()"
        >
          <span>In Progress</span>
          <svg v-if="learningStateFilter === 'learning'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
        </button>
        <button
          class="filter-menu-item"
          :class="{ active: learningStateFilter === 'mastered' }"
          @click="setLearningStateMastered(); closeFilterMenu()"
        >
          <span>Learned</span>
          <svg v-if="learningStateFilter === 'mastered'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
        </button>
      </div>
    </transition>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading words...</p>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <button @click="retryFetchWords" class="retry-btn">Retry</button>
    </div>

    <!-- Desktop: Split View -->
    <div v-else class="words-content" :class="{ 'detail-open': selectedWord && !showMobileDetail }">
      <!-- Word List — NO internal scroll, flows naturally with the page -->
      <div class="word-list" :class="{ 'grid-view': viewMode === 'grid' }">
        <div
          v-for="word in filteredWords"
          :key="word.id"
          class="word-card"
          :class="{ active: selectedWord?.id === word.id, pending: word.status === 'pending' }"
          @click="openDetail(word)"
        >
          <div class="word-card-main">
            <div class="word-info">
              <div class="word-name-row">
                <h4 class="word-name">{{ word.word }}</h4>
                <span v-if="word.isFavorite" class="word-fav-indicator">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                  </svg>
                </span>
                <span v-if="word.status === 'pending'" class="word-pending-badge">
                  Pending
                </span>
                <span v-if="word.isExisting" class="word-existing-badge">
                  Already Added
                </span>
              </div>
              <p class="word-definition">{{ word.definition }}</p>
            </div>
            <div class="word-card-actions">
              <button
                class="boost-btn"
                :class="{ active: word.is_boosted }"
                @click.stop="toggleBoost(word)"
                title="Boost this word for super priority"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                </svg>
              </button>
              <button
                class="fav-btn"
                :class="{ active: word.isFavorite }"
                @click.stop="toggleFavorite(word)"
              >
                <svg v-if="word.isFavorite" width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                </svg>
                <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
                </svg>
              </button>
            </div>
          </div>
          <div class="word-meta">
            <span class="meta-tag level" :style="{ color: levelColor(word.level) }">
              {{ levelLabel(word.level) }}
            </span>
            <span class="meta-dot">·</span>
            <span class="meta-tag category">{{ word.category }}</span>
            <span class="meta-dot">·</span>
            <span class="meta-tag frequency" :style="{ color: frequencyColor(word.frequency) }">
              {{ frequencyLabel(word.frequency) }}
            </span>
          </div>
        </div>

        <!-- Loading More Indicator -->
        <div v-if="loadingMore" class="loading-more">
          <div class="spinner-small"></div>
          <span>Loading more...</span>
        </div>

        <!-- Empty State -->
        <div v-if="words.length === 0 && !loadingMore" class="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
          </svg>
          <p class="empty-text">
            {{ filterMode === 'favorites' ? 'No favorite words yet' : 'No words found' }}
          </p>
          <button class="empty-add-btn" @click="openAdd">Add your first word</button>
        </div>
      </div>

      <!-- Desktop Detail Panel — sticky, scrolls independently ONLY if taller than viewport -->
      <transition name="slide-panel">
        <aside v-if="selectedWord && !showMobileDetail" class="detail-panel" style="position:fixed;right:0">
          <div class="detail-header">
            <button class="detail-close" @click="trackButtonClick('close_word_detail_panel'); selectedWord = null">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
              </svg>
            </button>
          </div>

          <div class="detail-body">
            <div class="detail-word-header">
              <div class="detail-word-left">
                <h2 class="detail-word">{{ selectedWord.word }}</h2>
                <button class="detail-speak-btn" @click="speak(selectedWord.word)" title="Play pronunciation">
                  <Icon icon="solar:volume-loud-linear" width="20" />
                </button>
              </div>
              <div class="detail-actions">
                <button
                  class="detail-boost-btn"
                  :class="{ active: selectedWord && selectedWord.is_boosted }"
                  @click="toggleBoost(selectedWord)"
                  title="Boost this word for super priority"
                >
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                  </svg>
                </button>
                <button
                  class="detail-fav-btn"
                  :class="{ active: selectedWord.isFavorite }"
                  @click="toggleFavorite(selectedWord)"
                >
                  <svg v-if="selectedWord.isFavorite" width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                  </svg>
                  <svg v-else width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
                  </svg>
                </button>
              </div>
            </div>

            <p class="detail-definition">{{ selectedWord.definition }}</p>

            <!-- Target Info Section - Prominent -->
            <div v-if="selectedWord.targetWord" class="detail-target-info-v2">
              <div v-if="selectedWord.sourceText" class="target-context-box">
                <div class="context-icon">💬</div>
                <p class="context-text">{{ selectedWord.sourceText }}</p>
              </div>

              <div class="target-analysis">
                <div class="analysis-row">
                  <div class="analysis-label">Target word</div>
                  <div class="analysis-value target-word-highlight">{{ selectedWord.targetWord }}</div>
                </div>

                <div v-if="selectedWord.targetSynonym" class="analysis-row">
                  <div class="analysis-label">Synonym</div>
                  <div class="analysis-value">{{ selectedWord.targetSynonym }}</div>
                </div>

                <div v-if="selectedWord.targetExplanation" class="analysis-row">
                  <div class="analysis-label">Meaning</div>
                  <div class="analysis-value explanation-text">{{ selectedWord.targetExplanation }}</div>
                </div>
              </div>
            </div>

            <!-- Synonyms Section -->
            <div v-if="selectedWord.synonyms && selectedWord.synonyms.length" class="detail-synonyms">
              <h4 class="synonyms-title">Synonyms</h4>
              <div class="synonyms-list">
                <span
                  v-for="syn in selectedWord.synonyms"
                  :key="syn"
                  class="synonym-tag"
                >
                  {{ syn }}
                </span>
              </div>
            </div>

            <div class="detail-meta-grid">
              <div class="detail-meta-item">
                <span class="meta-label">Level</span>
                <span class="meta-value" :style="{ color: levelColor(selectedWord.level) }">
                  {{ levelLabel(selectedWord.level) }}
                </span>
              </div>
              <div class="detail-meta-item">
                <span class="meta-label">Category</span>
                <span class="meta-value">{{ selectedWord.category }}</span>
              </div>
              <div class="detail-meta-item">
                <span class="meta-label">Frequency</span>
                <span class="meta-value" :style="{ color: frequencyColor(selectedWord.frequency) }">
                  {{ frequencyLabel(selectedWord.frequency) }}
                </span>
              </div>
              <div class="detail-meta-item">
                <span class="meta-label">Added</span>
                <span class="meta-value">{{ selectedWord.addedAt }}</span>
              </div>
              <div class="detail-meta-item">
                <span class="meta-label">Type</span>
                <span class="meta-value">{{ selectedWord.type || '—' }}</span>
              </div>
              <div class="detail-meta-item">
                <span class="meta-label">Examples</span>
                <span class="meta-value">{{ selectedWord.totalExamples || 0 }}</span>
              </div>
            </div>

            <div v-if="selectedWord.examples && selectedWord.examples.length" class="detail-examples">
              <h4 class="examples-title">Examples</h4>
              <ul class="examples-list">
                <li v-for="(ex, i) in selectedWord.examples" :key="i">{{ ex }}</li>
              </ul>
            </div>

            <div class="detail-actions">
              <button
                class="detail-action-btn explain"
                @click="toggleExplanation"
                :disabled="isExplaining"
              >
                <Icon
                  :icon="isExplaining ? 'solar:spinner-linear' : 'solar:lightbulb-linear'"
                  width="16"
                  :class="{ 'spinner-icon': isExplaining }"
                />
                <span>{{ isExplaining ? 'Explaining...' : 'Explain' }}</span>
              </button>
              <button class="detail-action-btn danger" @click="deleteWord(selectedWord.id)">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
                <span>Delete</span>
              </button>
            </div>

            <!-- Explanation Section -->
            <div v-if="showExplanation" class="detail-explanation">
              <h4 class="explanation-title">AI Explanation</h4>
              <div v-if="isExplaining" class="explanation-loading">
                <div class="spinner-small"></div>
                <p>Generating explanation...</p>
              </div>
              <div v-else-if="selectedWord?.explanation" class="explanation-content">
                {{ selectedWord.explanation }}
              </div>
              <div v-else class="explanation-empty">
                <p>No explanation available.</p>
              </div>
            </div>
          </div>
        </aside>
      </transition>
    </div>

    <!-- Mobile Detail Overlay -->
    <transition name="slide-up">
      <div v-if="showMobileDetail && selectedWord" class="mobile-detail-overlay">
        <div class="mobile-detail-header">
          <button class="mobile-back-btn" @click="trackButtonClick('close_mobile_detail'); closeDetail()">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
            </svg>
          </button>
          <h3 class="mobile-detail-title">Word Detail</h3>
          <div class="mobile-detail-actions">
            <button
              class="mobile-boost-btn"
              :class="{ active: boostedWords.has(selectedWord.id) }"
              @click="toggleBoost(selectedWord)"
              title="Boost this word for super priority"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
              </svg>
            </button>
            <button
              class="mobile-fav-btn"
              :class="{ active: selectedWord.isFavorite }"
              @click="toggleFavorite(selectedWord)"
            >
              <svg v-if="selectedWord.isFavorite" width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
              </svg>
              <svg v-else width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
              </svg>
            </button>
          </div>
        </div>

        <div class="mobile-detail-content">
          <div class="mobile-word-header">
            <h2 class="mobile-word">{{ selectedWord.word }}</h2>
            <button class="mobile-speak-btn" @click="speak(selectedWord.word)" title="Play pronunciation">
              <Icon icon="solar:volume-loud-linear" width="20" />
            </button>
          </div>
          <p class="mobile-definition">{{ selectedWord.definition }}</p>

          <!-- Mobile Target Info Section - Prominent -->
          <div v-if="selectedWord.targetWord" class="detail-target-info-v2">
            <div v-if="selectedWord.sourceText" class="target-context-box">
              <div class="context-icon">💬</div>
              <p class="context-text">{{ selectedWord.sourceText }}</p>
            </div>

            <div class="target-analysis">
              <div class="analysis-row">
                <div class="analysis-label">Target word</div>
                <div class="analysis-value target-word-highlight">{{ selectedWord.targetWord }}</div>
              </div>

              <div v-if="selectedWord.targetSynonym" class="analysis-row">
                <div class="analysis-label">Synonym</div>
                <div class="analysis-value">{{ selectedWord.targetSynonym }}</div>
              </div>

              <div v-if="selectedWord.targetExplanation" class="analysis-row">
                <div class="analysis-label">Meaning</div>
                <div class="analysis-value explanation-text">{{ selectedWord.targetExplanation }}</div>
              </div>
            </div>
          </div>

          <!-- Mobile Synonyms -->
          <div v-if="selectedWord.synonyms && selectedWord.synonyms.length" class="mobile-synonyms">
            <h4 class="synonyms-title">Synonyms</h4>
            <div class="synonyms-list">
              <span
                v-for="syn in selectedWord.synonyms"
                :key="syn"
                class="synonym-tag"
              >
                {{ syn }}
              </span>
            </div>
          </div>

          <div class="mobile-meta-list">
            <div class="mobile-meta-row">
              <span class="mobile-meta-label">Level</span>
              <span class="mobile-meta-value" :style="{ color: levelColor(selectedWord.level) }">
                {{ levelLabel(selectedWord.level) }}
              </span>
            </div>
            <div class="mobile-meta-row">
              <span class="mobile-meta-label">Category</span>
              <span class="mobile-meta-value">{{ selectedWord.category }}</span>
            </div>
            <div class="mobile-meta-row">
              <span class="mobile-meta-label">Frequency</span>
              <span class="mobile-meta-value" :style="{ color: frequencyColor(selectedWord.frequency) }">
                {{ frequencyLabel(selectedWord.frequency) }}
              </span>
            </div>
            <div class="mobile-meta-row">
              <span class="mobile-meta-label">Added</span>
              <span class="mobile-meta-value">{{ selectedWord.addedAt }}</span>
            </div>
            <div class="mobile-meta-row">
              <span class="mobile-meta-label">Type</span>
              <span class="mobile-meta-value">{{ selectedWord.type || '—' }}</span>
            </div>
            <div class="mobile-meta-row">
              <span class="mobile-meta-label">Examples</span>
              <span class="mobile-meta-value">{{ selectedWord.totalExamples || 0 }}</span>
            </div>
          </div>

          <div v-if="selectedWord.examples && selectedWord.examples.length" class="mobile-examples">
            <h4 class="examples-title">Examples</h4>
            <ul class="examples-list">
              <li v-for="(ex, i) in selectedWord.examples" :key="i">{{ ex }}</li>
            </ul>
          </div>

          <button
            class="mobile-explanation-btn"
            @click="toggleExplanation"
            :disabled="isExplaining"
          >
            <Icon
              :icon="isExplaining ? 'solar:spinner-linear' : 'solar:lightbulb-linear'"
              width="20"
              :class="{ 'spinner-icon': isExplaining }"
            />
            <span>{{ isExplaining ? 'Explaining...' : showExplanation ? 'Hide' : 'AI Explanation' }}</span>
          </button>

          <div v-if="showExplanation" class="mobile-explanation-content">
            <div v-if="isExplaining" class="explanation-loading">
              <div class="spinner-small"></div>
              <p>Generating explanation...</p>
            </div>
            <div v-else-if="selectedWord?.explanation">
              {{ selectedWord.explanation }}
            </div>
            <div v-else class="explanation-empty">
              <p>No explanation available.</p>
            </div>
          </div>

          <button class="mobile-delete-btn" @click="deleteWord(selectedWord.id)">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
            <span>Delete Word</span>
          </button>
        </div>
      </div>
    </transition>

    <!-- Desktop: Add Word Modal -->
    <transition name="fade">
      <div v-if="showAddDesktop" class="modal-overlay" @click.self="trackButtonClick('close_add_modal_overlay'); closeAdd()">
        <div class="modal-card">
          <div class="modal-header">
            <h3 class="modal-title">Add New Word</h3>
            <button class="modal-close" @click="trackButtonClick('close_add_modal_button'); closeAdd()">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
              </svg>
            </button>
          </div>
          <div class="modal-body">
            <!-- ERROR MESSAGE -->
            <div v-if="addError" class="add-error">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <circle cx="12" cy="12" r="10"/>
                <path fill="white" d="M12 5c-3.9 0-7 3.1-7 7s3.1 7 7 7 7-3.1 7-7-3.1-7-7-7zm3.5 7c0 .8-.7 1.5-1.5 1.5S12.5 12.8 12.5 12 13.2 10.5 14 10.5s1.5.7 1.5 1.5zm-7 0c0 .8-.7 1.5-1.5 1.5S4.5 12.8 4.5 12 5.2 10.5 6 10.5 7.5 11.2 7.5 12z"/>
              </svg>
              {{ addError }}
            </div>

            <!-- SUCCESS MESSAGE -->
            <div v-if="addSuccess" class="add-success">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/>
              </svg>
              {{ addSuccess }}
            </div>

            <!-- SIMPLE MODE INPUT -->
            <div v-if="addMode === 'simple'" class="simple-mode-input">
              <div class="input-wrapper">
                <input
                  ref="desktopInput"
                  v-model="newWordText"
                  type="text"
                  placeholder="Type a word or paste text..."
                  class="form-input form-input-large"
                  @keydown="handleAddKeydown"
                  autofocus
                />
              </div>

              <!-- TARGET SELECTION SECTION -->
              <div v-if="newWordText.trim()" class="target-selector-wrapper">
                <div v-if="!isSelectingTarget" class="target-display">
                  <div class="target-label-container">
                    <Icon icon="mdi:target" width="18" height="18" class="target-icon" />
                    <div class="target-text-info">
                      <span v-if="!selectedTarget" class="target-hint">Select a target word (optional)</span>
                      <span v-else class="target-selected">
                        Target: <span class="target-word-badge">{{ selectedTarget }}</span>
                      </span>
                    </div>
                  </div>
                  <button
                    class="target-toggle-btn"
                    @click="toggleSelectTarget"
                    :title="selectedTarget ? 'Change target' : 'Add target'"
                  >
                    <Icon :icon="selectedTarget ? 'mdi:pencil' : 'mdi:plus'" width="18" height="18" />
                  </button>
                </div>

                <!-- WORD SELECTION MODE -->
                <div v-else class="word-selection-expanded">
                  <div class="selection-header">
                    <span class="selection-title">Select Target Word</span>
                    <button
                      class="close-selection-btn"
                      @click="toggleSelectTarget"
                      title="Close"
                    >
                      <Icon icon="mdi:close" width="16" height="16" />
                    </button>
                  </div>
                  <div class="words-grid">
                    <button
                      v-for="(word, idx) in newWordText.trim().split(/\s+/)"
                      :key="idx"
                      class="word-button"
                      :class="{ 'word-button-active': selectedTarget === word }"
                      @click="selectWordAsTarget(word)"
                    >
                      {{ word }}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <!-- CONTEXT MODE FIELDS -->
            <div v-if="addMode === 'context' && selectedCommand" class="command-input-section">
              <div class="command-fields">
                <div v-for="field in selectedCommand.fields" :key="field.name" class="command-field">
                  <label class="field-label">{{ field.label }}</label>
                  <textarea v-if="field.name === 'sentence'" v-model="commandFieldValues[field.name]" :placeholder="field.placeholder" class="field-textarea" rows="3"></textarea>
                  <input v-else v-model="commandFieldValues[field.name]" type="text" :placeholder="field.placeholder" class="field-input" @keydown.enter="addWord"/>
                </div>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="modal-footer">
            <button class="modal-btn secondary" @click="trackButtonClick('cancel_add_word'); closeAdd()">Cancel</button>
            <button class="modal-btn primary" @click="addWord" :disabled="adding || (addMode === 'simple' ? !newWordText.trim() : !selectedCommand || !commandFieldValues['sentence']?.trim() || !commandFieldValues['word']?.trim())">
              <span v-if="adding">Adding...</span>
              <span v-else>Add Word</span>
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- Desktop: Commands Modal (Top Sheet) -->
    <transition name="slide-down">
      <div v-if="showCommandMenu && !selectedCommand && showAddDesktop" class="desktop-commands-modal">
        <div class="desktop-commands-overlay" @click="handleInputChange('')"></div>
        <div class="desktop-commands-sheet">
          <div class="desktop-commands-header">
            <h3 class="desktop-commands-title">Available Commands</h3>
            <button class="desktop-commands-close" @click="handleInputChange('')">✕</button>
          </div>
          <div class="desktop-commands-grid">
            <button
              v-for="cmd in filteredCommands"
              :key="cmd.id"
              class="desktop-command-card"
              @click="selectCommand(cmd)"
            >
              <span class="card-icon">{{ cmd.icon }}</span>
              <div class="card-content">
                <div class="card-title">{{ cmd.name }}</div>
                <div class="card-desc">{{ cmd.description }}</div>
              </div>
            </button>
            <div v-if="filteredCommands.length === 0" class="desktop-commands-empty">
              No commands found
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- Mobile: Add Word Inline Panel -->
    <transition name="slide-up">
      <div v-if="showAddMobile" class="mobile-add-panel">
        <div class="mobile-add-handle" @click="trackButtonClick('close_mobile_add_panel_handle'); closeAdd()">
          <div class="handle-bar"></div>
        </div>
        <div class="mobile-add-content">
          <h3 v-if="addMode !== null" class="mobile-add-title">Add New Word</h3>

          <!-- ERROR -->
          <div v-if="addError" class="add-error">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <circle cx="12" cy="12" r="10"/>
              <path fill="white" d="M12 5c-3.9 0-7 3.1-7 7s3.1 7 7 7 7-3.1 7-7-3.1-7-7-7zm3.5 7c0 .8-.7 1.5-1.5 1.5S12.5 12.8 12.5 12 13.2 10.5 14 10.5s1.5.7 1.5 1.5zm-7 0c0 .8-.7 1.5-1.5 1.5S4.5 12.8 4.5 12 5.2 10.5 6 10.5 7.5 11.2 7.5 12z"/>
            </svg>
            {{ addError }}
          </div>

          <!-- SUCCESS -->
          <div v-if="addSuccess" class="add-success">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/>
            </svg>
            {{ addSuccess }}
          </div>

          <!-- SIMPLE INPUT -->
          <div v-if="addMode === 'simple'">
            <div class="input-wrapper mobile-input-wrapper">
              <input v-model="newWordText" type="text" placeholder="Type a word or paste text..." class="mobile-add-input mobile-add-input-large" @keydown="handleAddKeydown" autofocus/>
            </div>

            <!-- TARGET SELECTION SECTION - MOBILE -->
            <div v-if="newWordText.trim()" class="target-selector-wrapper">
              <div v-if="!isSelectingTarget" class="target-display">
                <div class="target-label-container">
                  <Icon icon="mdi:target" width="18" height="18" class="target-icon" />
                  <div class="target-text-info">
                    <span v-if="!selectedTarget" class="target-hint">Select a target word (optional)</span>
                    <span v-else class="target-selected">
                      Target: <span class="target-word-badge">{{ selectedTarget }}</span>
                    </span>
                  </div>
                </div>
                <button
                  class="target-toggle-btn"
                  @click="toggleSelectTarget"
                  :title="selectedTarget ? 'Change target' : 'Add target'"
                >
                  <Icon :icon="selectedTarget ? 'mdi:pencil' : 'mdi:plus'" width="18" height="18" />
                </button>
              </div>

              <!-- WORD SELECTION MODE - MOBILE -->
              <div v-else class="word-selection-expanded">
                <div class="selection-header">
                  <span class="selection-title">Select Target Word</span>
                  <button
                    class="close-selection-btn"
                    @click="toggleSelectTarget"
                    title="Close"
                  >
                    <Icon icon="mdi:close" width="16" height="16" />
                  </button>
                </div>
                <div class="words-grid">
                  <button
                    v-for="(word, idx) in newWordText.trim().split(/\s+/)"
                    :key="idx"
                    class="word-button"
                    :class="{ 'word-button-active': selectedTarget === word }"
                    @click="selectWordAsTarget(word)"
                  >
                    {{ word }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- CONTEXT FIELDS -->
          <div v-if="addMode === 'context' && selectedCommand" class="command-input-section mobile-command-section">
            <div class="command-fields mobile-fields">
              <div v-for="field in selectedCommand.fields" :key="field.name" class="command-field">
                <label class="field-label">{{ field.label }}</label>
                <textarea v-if="field.name === 'sentence'" v-model="commandFieldValues[field.name]" :placeholder="field.placeholder" class="field-textarea" rows="2"></textarea>
                <input v-else v-model="commandFieldValues[field.name]" type="text" :placeholder="field.placeholder" class="field-input" @keydown.enter="addWord"/>
              </div>
            </div>
          </div>

          <!-- Actions - Mobile -->
          <div class="mobile-add-actions">
            <button class="mobile-add-btn secondary" @click="trackButtonClick('cancel_mobile_add_word'); closeAdd()">Cancel</button>
            <button class="mobile-add-btn primary" @click="addWord" :disabled="adding || (addMode === 'simple' ? !newWordText.trim() : !selectedCommand || !commandFieldValues['sentence']?.trim() || !commandFieldValues['word']?.trim())">
              <span v-if="adding">Adding...</span>
              <span v-else>Add</span>
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- Mobile: Backdrop for add panel -->
    <transition name="fade">
      <div v-if="showAddMobile" class="mobile-backdrop" @click="trackButtonClick('close_mobile_add_backdrop'); closeAdd()"></div>
    </transition>

    <!-- Mobile: Commands Modal (Bottom Sheet) -->
    <transition name="slide-up">
      <div v-if="showCommandMenu && !selectedCommand && showAddMobile" class="mobile-commands-modal">
        <div class="mobile-commands-overlay" @click="handleInputChange('')"></div>
        <div class="mobile-commands-sheet">
          <div class="mobile-commands-header">
            <h3 class="mobile-commands-title">Choose a Command</h3>
            <button class="mobile-commands-close" @click="handleInputChange('')">✕</button>
          </div>
          <div class="mobile-commands-list">
            <button
              v-for="cmd in filteredCommands"
              :key="cmd.id"
              class="mobile-command-btn"
              @click="selectCommand(cmd)"
            >
              <span class="cmd-icon">{{ cmd.icon }}</span>
              <div class="cmd-text">
                <div class="cmd-title">{{ cmd.name }}</div>
                <div class="cmd-desc">{{ cmd.description }}</div>
              </div>
            </button>
            <div v-if="filteredCommands.length === 0" class="mobile-commands-empty">
              No commands found
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- Relearn Dialog -->
    <transition name="fade">
      <div v-if="showRelearnDialog" class="modal-overlay" @click.self="closeRelearnDialog">
        <div class="modal-card relearn-modal">
          <div class="modal-header">
            <h3 class="modal-title">Relearn Words</h3>
            <button class="modal-close" @click="closeRelearnDialog" :disabled="isRelearnProcessing">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
              </svg>
            </button>
          </div>
          <div class="modal-body">
            <!-- Success State -->
            <div v-if="relearnSuccess" class="relearn-success-state">
              <div class="success-icon-container">
                <svg class="success-icon" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
              </div>
              <h4 class="success-title">Relearning Started!</h4>
              <p class="success-message">
                {{ relearnCount }} words are back in your LEARNING list to help reinforce your memory.
              </p>
              <button class="modal-btn primary" @click="closeRelearnDialog">Done</button>
            </div>

            <!-- Input State -->
            <div v-else>
              <p class="modal-hint">
                Select the number of learned words you want to review again.
              </p>

              <!-- Processing State -->
              <div v-if="isRelearnProcessing" class="processing-state">
                <div class="progress-container">
                  <div class="progress-bar">
                    <div class="progress-fill" :style="{ width: relearnProgress + '%' }"></div>
                  </div>
                  <p class="progress-text">Processing... {{ Math.floor(relearnProgress) }}%</p>
                </div>
              </div>

              <!-- Count Selection -->
              <div v-else class="count-selection">
                <p class="selection-label">How many words?</p>
                <div class="count-buttons">
                  <button
                    v-for="count in [5, 10, 15]"
                    :key="count"
                    class="count-btn"
                    :class="{ active: relearnCount === count }"
                    @click="selectRelearnCount(count)"
                  >
                    {{ count }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div v-if="!relearnSuccess && !isRelearnProcessing" class="modal-footer">
            <button class="modal-btn secondary" @click="closeRelearnDialog" :disabled="isRelearnProcessing">Cancel</button>
            <button class="modal-btn primary" @click="simulateRelearn" :disabled="isRelearnProcessing || relearnCount < 1">
              Relearn {{ relearnCount }} Words
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
/* ════════════════════════════════════════
   LAYOUT PRINCIPAL — Un solo scroll fluido
   ════════════════════════════════════════ */

/* El contenedor raíz fluye naturalmente con el documento.
   NO tiene max-height ni overflow. El único scroll es el de la página. */
.my-words-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px;
  color: #e2e0e8;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* ─── Slogan Banner ─── */
.slogan-banner {
  position: relative;
  margin-bottom: 24px;
  border-radius: 8px;
  overflow: hidden;
  margin-top: -15px;
}

.banner-image {
  width: 100%;
  height: auto;
  display: block;
}

.banner-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  padding: 48px 60px;
}

.banner-content {
  max-width: 450px;
  display: flex;
  flex-direction: column;
  gap: 16px;  
}

.banner-title {
  margin: 0;
  font-size: 42px;
  font-weight: 700;
  color: #f0ede9;
  letter-spacing: -1px;
  line-height: 1.15;
}

.title-highlight {
  color: #c4aaf1ff;
}

.banner-subtitle {
  margin: 0;
  font-size: 15px;
  color: #d0ccc7;
  line-height: 1.6;
  font-weight: 400;
}

/* ─── Simple Banner ─── */
.simple-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  margin-bottom: 20px;
  border-radius: 10px;
  background: rgba(124, 58, 237, 0.08);
  border: 1px solid rgba(124, 58, 237, 0.2);
  animation: slideDown 0.3s ease-out;
}

.banner-message {
  flex: 1;
}

.banner-message p {
  margin: 0;
  font-size: 14px;
  color: #d0ccc7;
  line-height: 1.5;
  font-weight: 500;
}

.banner-close {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
  margin-left: 12px;
  border-radius: 6px;
}

.banner-close:hover {
  background: rgba(124, 58, 237, 0.1);
  color: #c4aaf1;
}

/* ─── Variant Banner ─── */
.variant-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  margin-bottom: 20px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(124, 58, 237, 0.12) 0%, rgba(167, 139, 250, 0.06) 100%);
  border: 1px solid rgba(167, 139, 250, 0.25);
  animation: slideDown 0.3s ease-out;
  box-shadow: 0 4px 12px rgba(124, 58, 237, 0.08);
}

.variant-banner-icon {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(167, 139, 250, 0.15);
  border-radius: 10px;
  color: #a78bfa;
}

.variant-banner-content {
  flex: 1;
}

.variant-banner-title {
  margin: 0 0 4px 0;
  font-size: 15px;
  font-weight: 700;
  color: #e2e0e8;
}

.variant-banner-text {
  margin: 0;
  font-size: 13px;
  color: #b0aac0;
  line-height: 1.5;
}

.variant-banner-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.variant-banner-btn-action {
  padding: 8px 16px;
  border-radius: 8px;
  border: none;
  background: linear-gradient(135deg, #a78bfa 0%, #c4aaf1 100%);
  color: white;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.variant-banner-btn-action:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(167, 139, 250, 0.3);
}

.variant-banner-btn-close {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  border-radius: 6px;
}

.variant-banner-btn-close:hover {
  background: rgba(167, 139, 250, 0.1);
  color: #c4aaf1;
}

/* ─── Tip Banner (Completely Different Style) ─── */
.tip-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px;
  margin-bottom: 20px;
  border-radius: 12px;
  background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%);
  border-left: 4px solid #06b6d4;
  animation: slideDown 0.3s ease-out;
  box-shadow: 0 2px 8px rgba(13, 148, 136, 0.15);
}

.tip-banner-left {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.tip-badge {
  display: inline-block;
  width: fit-content;
  padding: 4px 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.15);
  font-size: 11px;
  font-weight: 700;
  color: #cffafe;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tip-banner-message {
  margin: 0;
  font-size: 14px;
  color: #f0fdfa;
  line-height: 1.5;
  font-weight: 500;
  max-width: 90%;
}

.tip-banner-dismiss {
  width: 32px;
  height: 32px;
  border: none;
  background: rgba(255, 255, 255, 0.15);
  color: #cffafe;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  border-radius: 6px;
  flex-shrink: 0;
  margin-left: 12px;
}

.tip-banner-dismiss:hover {
  background: rgba(255, 255, 255, 0.25);
  transform: scale(1.1);
}

/* ─── Header ─── */
.words-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 28px;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.words-title {
  font-size: 28px;
  font-weight: 700;
  color: #e2e0e8;
  margin: 0;
  letter-spacing: -0.5px;
}

@media (max-width: 768px) {
  .words-title {
    font-size: 32px;
  }
}

.words-subtitle {
  font-size: 14px;
  color: #9c99ab;
  margin: 0;
}

@media (max-width: 768px) {
  .words-subtitle {
    font-size: 17px;
  }
  .selection-label {
    font-size: 15px !important;
  }

  .count-btn {
    font-size: 17px !important;
  }

  .success-message {
    font-size: 17px !important;
  }

  .success-title{
    font-size: 22px !important;
  }
}

.add-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-radius: 12px;
  border: none;
  background: #7c3aed;
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

@media (max-width: 768px) {
  .add-btn {
    font-size: 17px;
  }
}

.add-btn:hover:not(:disabled) {
  background: #6d28d9;
  transform: translateY(-1px);
}

.add-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ─── Header Actions Container ─── */
.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

/* ─── Relearn Button ─── */
.relearn-btn {
  display: none;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-radius: 12px;
  border: none;
  background: #0891b2;
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

@media (max-width: 768px) {
  .relearn-btn {
    display: flex;
    font-size: 17px;
  }
}

.relearn-btn:hover:not(:disabled) {
  background: #0e7490;
  transform: translateY(-1px);
}

.relearn-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ─── Toolbar ─── */
.words-toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
  align-items: center;
}

.toolbar-controls {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-left: auto;
}

.search-box {
  flex: 1;
  position: relative;
  max-width: 400px;
}

.search-icon {
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: #9c99ab;
  pointer-events: none;
}

.search-input {
  width: 80%;
  padding: 12px 14px 12px 42px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #e2e0e8;
  font-size: 14px;
  outline: none;
  transition: all 0.2s ease;
}

@media (max-width: 768px) {
  .search-input {
    font-size: 17px;
  }
}

.search-input::placeholder {
  color: #9c99ab;
}

.search-input:focus {
  border-color: rgba(124, 58, 237, 0.4);
  background: rgba(255, 255, 255, 0.06);
}

/* ─── Filter Tabs ─── */
.filter-tabs {
  display: flex;
  gap: 6px;
  background: rgba(255, 255, 255, 0.04);
  padding: 4px;
  border-radius: 12px;
}

.filter-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #9c99ab;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

@media (max-width: 768px) {
  .filter-tab {
    font-size: 16px;
  }
}

.filter-tab:hover {
  color: #e2e0e8;
}

.filter-tab.active {
  background: rgba(124, 58, 237, 0.2);
  color: #a78bfa;
}

.fav-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: rgba(244, 114, 182, 0.2);
  color: #f472b6;
  font-size: 10px;
  font-weight: 700;
}

@media (max-width: 768px) {
  .fav-count {
    font-size: 14px;
  }
}

.boosted-count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: rgba(255, 193, 7, 0.2);
  color: #ffc107;
  font-size: 10px;
  font-weight: 700;
}

@media (max-width: 768px) {
  .boosted-count-badge {
    font-size: 14px;
  }
}

/* ─── Active Filter Banner ─── */
.active-filter-banner {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  margin-bottom: 16px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(255, 193, 7, 0.15) 0%, rgba(255, 193, 7, 0.08) 100%);
  border: 1px solid rgba(255, 193, 7, 0.3);
  animation: slideDown 0.3s ease-out;
}

.banner-content {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  color: #ffc107;
  font-size: 13px;
  font-weight: 600;
}

.banner-content svg {
  flex-shrink: 0;
  color: #ffc107;
}

.banner-text {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
}

.banner-text strong {
  color: #fff;
  font-weight: 700;
}

.banner-close {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: #ffc107;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.banner-close:hover {
  color: #fff;
  background: rgba(255, 193, 7, 0.15);
  border-radius: 6px;
}

@media (max-width: 768px) {
  .active-filter-banner {
    padding: 10px 12px;
  }

  .banner-content {
    font-size: 12px;
  }

  .banner-content svg {
    width: 14px;
    height: 14px;
  }

  .banner-close {
    width: 20px;
    height: 20px;
  }
}

/* ─── Filter Dropdown ─── */
.filter-dropdown-wrap {
  position: relative;
}

.filter-dropdown-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.05);
  /* color: #e2e0e8; */
  color: #bbb;
  font-size: 13px;
  /* font-weight: 600; */
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.filter-dropdown-toggle:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
}

.filter-dropdown-content {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 6px;
  min-width: 160px;
  background: #2a2635;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  z-index: 1000;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 14px;
  border: none;
  background: transparent;
  color: #9c99ab;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;
}

.dropdown-item:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
}

.dropdown-item.active {
  background: rgba(124, 58, 237, 0.2);
  color: #a78bfa;
}

.dropdown-item svg {
  flex-shrink: 0;
  width: 14px;
  height: 14px;
}

.badge {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 999px;
  background: rgba(124, 58, 237, 0.2);
  color: #a78bfa;
  font-size: 9px;
  font-weight: 700;
}

/* ─── View Mode Desktop ─── */
.view-mode-desktop {
  display: none;
  gap: 4px;
}

@media (min-width: 769px) {
  .view-mode-desktop {
    display: flex;
  }
}

.view-mode-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #9c99ab;
  cursor: pointer;
  transition: all 0.2s ease;
}

.view-mode-btn:hover {
  border-color: rgba(255, 255, 255, 0.15);
  color: #e2e0e8;
}

.view-mode-btn.active {
  background: rgba(124, 58, 237, 0.15);
  border-color: rgba(124, 58, 237, 0.3);
  color: #a78bfa;
}

/* ─── More Controls Dropdown ─── */
.more-controls-wrap {
  position: relative;
  display: none;
}

@media (min-width: 769px) {
  .more-controls-wrap {
    display: block;
  }
}

.more-controls-toggle {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.more-controls-toggle:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
}

.more-controls-content {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 6px;
  width: 200px;
  background: #2a2635;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  z-index: 1000;
  overflow: hidden;
}

.controls-section {
  padding: 10px;
}

.section-label {
  font-size: 10px;
  font-weight: 700;
  color: #6b6876;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 0 6px 8px;
  display: block;
}

.control-btn {
  display: block;
  width: 100%;
  padding: 8px 10px;
  border: none;
  background: transparent;
  color: #9c99ab;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;
  border-radius: 6px;
  margin-bottom: 4px;
}

.control-btn:last-child {
  margin-bottom: 0;
}

.control-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
}

.control-btn.active {
  background: rgba(124, 58, 237, 0.2);
  color: #a78bfa;
}

.control-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.controls-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
  margin: 4px 0;
}

.relearn-option {
  display: flex;
  align-items: center;
  gap: 6px;
  justify-content: flex-start;
}

.relearn-option svg {
  flex-shrink: 0;
}

/* ─── Learning State Filter ─── */
.learning-state-filter {
  display: none;
  gap: 6px;
  margin-bottom: 24px;
  flex-wrap: wrap;
  align-items: center;
}

@media (max-width: 768px) {
  .learning-state-filter {
    display: flex;
  }
}

/* ─── Mobile Search Button ─── */
.mobile-search-btn {
  display: none;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #9c99ab;
  cursor: pointer;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.mobile-search-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
}

/* ─── Mobile Favorites Button ─── */
.mobile-favorites-btn {
  display: none;
  position: relative;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #9c99ab;
  cursor: pointer;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.mobile-favorites-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
}

.mobile-favorites-btn.active {
  color: #f472b6;
  background: rgba(244, 114, 182, 0.1);
  border-color: rgba(244, 114, 182, 0.2);
}

.mobile-fav-badge {
  position: absolute;
  top: -8px;
  right: -8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: #f472b6;
  color: white;
  font-size: 10px;
  font-weight: 700;
}

.mobile-boosted-btn {
  display: none;
  position: relative;
  width: 44px;
  height: 44px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #9c99ab;
  cursor: pointer;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.mobile-boosted-btn:hover {
  background: rgba(255, 193, 7, 0.1);
  color: #ffc107;
}

.mobile-boosted-btn.active {
  color: #ffc107;
  background: rgba(255, 193, 7, 0.15);
  border-color: rgba(255, 193, 7, 0.2);
}

.boosted-count {
  position: absolute;
  top: -8px;
  right: -8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: #ffc107;
  color: #1a1625;
  font-size: 10px;
  font-weight: 700;
}

/* ─── Mobile Search Panel ─── */
.mobile-search-panel {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  background: #36324a;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  z-index: 1501;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
}

.mobile-search-input {
  flex: 1;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #e2e0e8;
  font-size: 15px;
  outline: none;
  transition: all 0.2s ease;
  font-family: inherit;
}

.mobile-search-input:focus {
  border-color: rgba(124, 58, 237, 0.4);
  background: rgba(255, 255, 255, 0.06);
}

.mobile-search-input::placeholder {
  color: #9c99ab;
}

.mobile-search-close {
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
  flex-shrink: 0;
}

.mobile-search-close:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
}

/* ─── Mobile Filter Button ─── */
.mobile-filter-btn {
  display: none;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #9c99ab;
  cursor: pointer;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.mobile-filter-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
}

.mobile-filter-btn.active {
  color: #a78bfa;
  background: rgba(124, 58, 237, 0.1);
  border-color: rgba(124, 58, 237, 0.2);
}

/* ─── Mobile Filter Menu ─── */
.mobile-filter-backdrop {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1500;
}

.mobile-filter-menu {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  background: #36324a;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  z-index: 1501;
  flex-direction: column;
}

.filter-menu-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border: none;
  background: transparent;
  color: #9c99ab;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.filter-menu-item:hover {
  background: rgba(255, 255, 255, 0.03);
  color: #e2e0e8;
}

.filter-menu-item.active {
  color: #a78bfa;
  background: rgba(124, 58, 237, 0.1);
}

.filter-menu-item:last-child {
  border-bottom: none;
}

.state-tab {
  padding: 8px 14px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #9c99ab;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

@media (max-width: 768px) {
  .state-tab {
    font-size: 15px;
  }
}

.state-tab:hover {
  border-color: rgba(255, 255, 255, 0.15);
  color: #e2e0e8;
}

.state-tab.active {
  background: rgba(124, 58, 237, 0.2);
  border-color: rgba(124, 58, 237, 0.4);
  color: #a78bfa;
}

.state-tab:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  background: rgba(255, 255, 255, 0.02);
  color: #6b6876;
  border-color: rgba(255, 255, 255, 0.04);
}

.state-tab:disabled:hover {
  background: rgba(255, 255, 255, 0.02);
  border-color: rgba(255, 255, 255, 0.04);
  color: #6b6876;
}

/* ─── View Mode Toggle ─── */
.view-mode-toggle {
  display: flex;
  gap: 6px;
  margin-left: auto;
}

.view-mode-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #9c99ab;
  cursor: pointer;
  transition: all 0.2s ease;
}

.view-mode-btn:hover {
  border-color: rgba(255, 255, 255, 0.15);
  color: #e2e0e8;
}

.view-mode-btn.active {
  background: rgba(155, 143, 181, 0.12);
  border-color: rgba(155, 143, 181, 0.25);
  color: #9b8fb5;
}

/* ─── Loading / Error ─── */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  gap: 16px;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(124, 58, 237, 0.2);
  border-top-color: #7c3aed;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-state p {
  color: #9c99ab;
  font-size: 14px;
  margin: 0;
}

@media (max-width: 768px) {
  .loading-state p {
    font-size: 17px;
  }
}

.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  gap: 16px;
  text-align: center;
}

.error-state p {
  color: #f87171;
  font-size: 14px;
  margin: 0;
}

@media (max-width: 768px) {
  .error-state p {
    font-size: 17px;
  }
}

.retry-btn {
  padding: 10px 20px;
  border-radius: 10px;
  border: none;
  background: rgba(124, 58, 237, 0.2);
  color: #a78bfa;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

@media (max-width: 768px) {
  .retry-btn {
    font-size: 17px;
  }
}

.retry-btn:hover {
  background: rgba(124, 58, 237, 0.3);
}

/* ════════════════════════════════════════
   SPLIT VIEW — Desktop
   ════════════════════════════════════════ */

.words-content {
  display: flex;
  gap: 0;
  align-items: flex-start;
}

/* Cuando hay detail abierto, la lista ocupa ~55% */
.words-content.detail-open .word-list {
  flex: 0 0 55%;
  max-width: 55%;
}

/* ─── Word List — NO internal scroll!
   Fluye con el documento. Ocupa todo el ancho disponible. ─── */
.word-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: all 0.3s ease;
  /* SIN max-height, SIN overflow-y — fluye naturalmente */
}

/* ─── Grid View ─── */
.word-list.grid-view {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.word-list.grid-view.detail-open {
  grid-template-columns: repeat(3, 1fr);
}

/* ─── Loading More ─── */
.loading-more {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 24px;
  color: #9c99ab;
  font-size: 13px;
}

@media (max-width: 768px) {
  .loading-more {
    font-size: 16px;
  }
}

.spinner-small {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(124, 58, 237, 0.2);
  border-top-color: #7c3aed;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* ─── Word Card ─── */
.word-card {
  padding: 16px 18px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  cursor: pointer;
  transition: all 0.2s ease;
}

.word-card:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.1);
}

.word-card.active {
  background: rgba(124, 58, 237, 0.1);
  border-color: rgba(124, 58, 237, 0.25);
}

.word-card-main {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 10px;
}

.word-info {
  min-width: 0;
  flex: 1;
}

.word-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.word-name {
  font-size: 16px;
  font-weight: 600;
  color: #e2e0e8;
  margin: 0;
}

@media (max-width: 768px) {
  .word-name {
    font-size: 19px;
  }
}

.word-fav-indicator {
  color: #f472b6;
  display: flex;
  align-items: center;
}

.word-pending-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(96, 165, 250, 0.15);
  color: #60a5fa;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.3px;
  text-transform: uppercase;
}

.word-existing-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(168, 85, 247, 0.15);
  color: #a855f7;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.3px;
  text-transform: uppercase;
}

@media (max-width: 768px) {
  .word-pending-badge,
  .word-existing-badge {
    font-size: 12px;
  }
}

.word-card.pending {
  opacity: 0.85;
  border-color: rgba(96, 165, 250, 0.2);
  background: rgba(96, 165, 250, 0.05);
}

.word-card.pending:hover {
  background: rgba(96, 165, 250, 0.08);
}

.word-definition {
  font-size: 13px;
  color: #9c99ab;
  margin: 0;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

@media (max-width: 768px) {
  .word-definition {
    font-size: 16px;
  }
}

.fav-btn {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s ease;
}

.fav-btn:hover {
  background: rgba(255, 255, 255, 0.06);
}

.fav-btn.active {
  color: #f472b6;
}

/* ─── Boost Button ─── */
.word-card-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.boost-btn {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s ease;
}

.boost-btn:hover {
  background: rgba(255, 193, 7, 0.1);
  color: #ffc107;
}

.boost-btn.active {
  color: #ffc107;
  background: rgba(255, 193, 7, 0.15);
  box-shadow: 0 0 12px rgba(255, 193, 7, 0.3);
}

/* ─── Meta Tags ─── */
.word-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.meta-tag {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

@media (max-width: 768px) {
  .meta-tag {
    font-size: 14px;
  }
}

.meta-tag.level {
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
}

.meta-tag.category {
  color: #9c99ab;
}

.meta-tag.frequency {
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
}

.meta-dot {
  color: #9c99ab;
  font-size: 11px;
}

/* ════════════════════════════════════════
   DETAIL PANEL — Sticky, scrolls solo si es más alto que viewport
   ════════════════════════════════════════ */

.detail-panel {
  width: 380px;
  flex-shrink: 0;
  background: #36324a;
  border-left: 1px solid rgba(255, 255, 255, 0.06);
  padding: 24px;
  border-radius: 16px 0 0 16px;

  /* Sticky: se queda pegado arriba mientras scrolleas la lista */
  position: sticky;
  top: 24px;

  /* Solo scrollea internamente si el contenido es más alto que la ventana */
  max-height: calc(100vh - 48px);
  overflow-y: auto;
}

.detail-panel::-webkit-scrollbar {
  width: 5px;
}

.detail-panel::-webkit-scrollbar-track {
  background: transparent;
}

.detail-panel::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
}

.detail-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.detail-close {
  width: 32px;
  height: 32px;
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

.detail-close:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
}

.detail-word-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.detail-word-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.detail-word {
  font-size: 32px;
  font-weight: 700;
  color: #e2e0e8;
  margin: 0;
  letter-spacing: -0.5px;
}

@media (max-width: 768px) {
  .detail-word {
    font-size: 36px;
  }
}

.detail-speak-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: none;
  background: rgba(167, 139, 250, 0.1);
  color: #a78bfa;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.detail-speak-btn:hover {
  background: rgba(167, 139, 250, 0.2);
  color: #c4b5fd;
}

.detail-fav-btn {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  border: none;
  background: rgba(255, 255, 255, 0.06);
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.detail-fav-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.detail-fav-btn.active {
  color: #f472b6;
  background: rgba(244, 114, 182, 0.1);
}

.detail-actions {
  display: flex;
  gap: 10px;
}

.detail-boost-btn {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  border: none;
  background: rgba(255, 255, 255, 0.06);
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.detail-boost-btn:hover {
  background: rgba(255, 193, 7, 0.15);
  color: #ffc107;
}

.detail-boost-btn.active {
  color: #ffc107;
  background: rgba(255, 193, 7, 0.2);
  box-shadow: 0 0 16px rgba(255, 193, 7, 0.4);
}

.detail-definition {
  font-size: 15px;
  line-height: 1.6;
  color: #b8b5c8;
  margin-bottom: 28px;
}

@media (max-width: 768px) {
  .detail-definition {
    font-size: 18px;
  }
}

/* ─── Synonyms ─── */
.detail-synonyms {
  margin-bottom: 28px;
}

.synonyms-title {
  font-size: 13px;
  font-weight: 600;
  color: #9c99ab;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0 0 12px 0;
}

@media (max-width: 768px) {
  .synonyms-title {
    font-size: 16px;
  }
}

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
  transition: all 0.2s ease;
}

@media (max-width: 768px) {
  .synonym-tag {
    font-size: 16px;
  }
}

.synonym-tag:hover {
  background: rgba(124, 58, 237, 0.2);
  border-color: rgba(124, 58, 237, 0.35);
}

.detail-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 28px;
}

.detail-meta-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px;
  background: rgba(0, 0, 0, 0.15);
  border-radius: 12px;
}

.meta-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: #9c99ab;
  text-transform: uppercase;
}

@media (max-width: 768px) {
  .meta-label {
    font-size: 14px;
  }
}

.meta-value {
  font-size: 14px;
  font-weight: 600;
  color: #e2e0e8;
}

@media (max-width: 768px) {
  .meta-value {
    font-size: 17px;
  }
}

.detail-examples {
  margin-bottom: 28px;
}

.examples-title {
  font-size: 13px;
  font-weight: 600;
  color: #9c99ab;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0 0 12px 0;
}

@media (max-width: 768px) {
  .examples-title {
    font-size: 16px;
  }
}

.examples-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.examples-list li {
  font-size: 14px;
  color: #b8b5c8;
  padding: 10px 14px;
  background: rgba(0, 0, 0, 0.12);
  border-radius: 10px;
  line-height: 1.5;
}

@media (max-width: 768px) {
  .examples-list li {
    font-size: 17px;
  }
}

/* ─── Target Info Section V2 ─── */
.detail-target-info-v2 {
  margin-bottom: 28px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.target-context-box {
  display: flex;
  gap: 12px;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  align-items: flex-start;
}

.context-icon {
  font-size: 18px;
  flex-shrink: 0;
  line-height: 1.4;
}

.context-text {
  margin: 0;
  font-size: 14px;
  color: #b8b5c8;
  line-height: 1.6;
  font-style: italic;
}

.target-analysis {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.05) 0%, rgba(139, 92, 246, 0.03) 100%);
  border: 1px solid rgba(59, 130, 246, 0.1);
  border-radius: 10px;
}

.analysis-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding: 8px 0;
}

.analysis-label {
  font-size: 12px;
  font-weight: 700;
  color: #9c99ab;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  min-width: 90px;
  flex-shrink: 0;
}

.analysis-value {
  font-size: 14px;
  color: #e2e0e8;
  line-height: 1.5;
  flex: 1;
}

.target-word-highlight {
  font-weight: 600;
  color: #60a5fa;
}

.explanation-text {
  color: #b8b5c8;
  font-style: italic;
}

@media (max-width: 768px) {
  .detail-target-info-v2 {
    margin-bottom: 24px;
    gap: 14px;
  }

  .target-context-box {
    padding: 14px 16px;
    gap: 12px;
  }

  .context-icon {
    font-size: 20px;
  }

  .context-text {
    font-size: 15px;
  }

  .target-analysis {
    padding: 14px 16px;
    gap: 12px;
  }

  .analysis-row {
    gap: 12px;
    padding: 6px 0;
  }

  .analysis-label {
    font-size: 12px;
    min-width: 85px;
  }

  .analysis-value {
    font-size: 15px;
  }
}

.detail-actions {
  display: flex;
  gap: 10px;
  margin-bottom: 30px;
}

.detail-action-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  border-radius: 12px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

@media (max-width: 768px) {
  .detail-action-btn {
    font-size: 17px;
  }
}

.detail-action-btn.danger {
  background: rgba(239, 68, 68, 0.1);
  color: #f87171;
}

.detail-action-btn.danger:hover {
  background: rgba(239, 68, 68, 0.2);
}

.detail-action-btn.explain {
  background: rgba(167, 139, 250, 0.1);
  color: #a78bfa;
}

.detail-action-btn.explain:hover:not(:disabled) {
  background: rgba(167, 139, 250, 0.2);
}

.detail-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spinner-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ─── Explanation Section ─── */
.detail-explanation {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 20px;
  animation: slideDown 0.3s ease;
}

.explanation-title {
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  color: #a78bfa;
  margin: 0 0 12px 0;
  letter-spacing: 0.5px;
}

.explanation-content {
  font-size: 15px;
  line-height: 1.6;
  color: #b4b1c6;
}

.explanation-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 16px;
  min-height: 60px;
}

.spinner-small {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(167, 139, 250, 0.2);
  border-top-color: #a78bfa;
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}

.explanation-loading p {
  color: #9c99ab;
  font-size: 13px;
  margin: 0;
}

.explanation-empty {
  text-align: center;
  padding: 12px;
  color: #9c99ab;
  font-size: 13px;
}

.explanation-empty p {
  margin: 0;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ─── Empty State ─── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.empty-state svg {
  color: #9c99ab;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-text {
  font-size: 16px;
  color: #9c99ab;
  margin: 0 0 16px 0;
}

@media (max-width: 768px) {
  .empty-text {
    font-size: 19px;
  }
}

.empty-add-btn {
  padding: 12px 24px;
  border-radius: 12px;
  border: none;
  background: #7c3aed;
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

@media (max-width: 768px) {
  .empty-add-btn {
    font-size: 17px;
  }
}

.empty-add-btn:hover {
  background: #6d28d9;
}

/* ─── Desktop Modal ─── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 20px;
}

.modal-card {
  width: 100%;
  max-width: 420px;
  background: #36324a;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  overflow: visible;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.modal-title {
  font-size: 18px;
  font-weight: 700;
  color: #e2e0e8;
  margin: 0;
}

@media (max-width: 768px) {
  .modal-title {
    font-size: 21px;
  }
}

.modal-close {
  width: 32px;
  height: 32px;
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

.modal-close:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
}

.modal-body {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.modal-hint {
  font-size: 15.5px;
  color: #9c99ab;
  line-height: 1.5;
  margin: 0;
}

@media (max-width: 768px) {
  .modal-hint {
    font-size: 18px !important;
  }
}

/* ─── Mode Selection Screen ─── */
.mode-selection-screen {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  align-items: center;
  justify-content: center;
  min-height: 300px;
}

.content-screen {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* ─── Mode Selector Cards ─── */
.mode-cards-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin: 0 0 24px 0;
}

.mode-card {
  padding: 20px;
  border-radius: 16px;
  border: 2px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  text-align: center;
}

.mode-card:hover {
  border-color: rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  transform: translateY(-2px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.3);
}

.mode-card.selected {
  border-color: rgba(124, 58, 237, 0.6);
  background: rgba(124, 58, 237, 0.15);
  box-shadow: 0 8px 24px rgba(124, 58, 237, 0.2);
}

.card-icon {
  font-size: 32px;
  line-height: 1;
}

.card-title {
  font-size: 14px;
  font-weight: 700;
  color: #e2e0e8;
}

@media (max-width: 768px) {
  .mode-cards-grid {
    gap: 10px;
    margin: 0 0 18px 0;
  }

  .mode-card {
    padding: 16px;
    gap: 10px;
  }

  .card-icon {
    font-size: 28px;
  }

  .card-title {
    font-size: 13px;
  }

  .card-description {
    font-size: 11px;
  }
}

.mobile-cards-grid {
  margin: 0 -16px 0 -16px;
  padding: 0 16px;
}

.mobile-mode-selection {
  padding: 16px;
  min-height: 320px;
}

.mobile-content-screen {
  padding: 16px;
}

.simple-mode-input {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  position: relative;
}

.form-label {
  font-size: 12px;
  font-weight: 600;
  color: #9c99ab;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

@media (max-width: 768px) {
  .form-label {
    font-size: 15px;
  }
}

.form-input {
  width: 100%;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #e2e0e8;
  font-size: 15px;
  outline: none;
  transition: all 0.2s ease;
  font-family: inherit;
  box-sizing: border-box;
}

@media (max-width: 768px) {
  .form-input {
    font-size: 18px;
  }
}

.form-input:focus {
  border-color: rgba(124, 58, 237, 0.25);
  background: rgba(255, 255, 255, 0.05);
}

/* Large Input for Command Input */
.form-input-large {
  padding: 18px 18px;
  /* min-height: 120px; */
  font-size: 15px;
}

@media (max-width: 768px) {
  .form-input-large {
    min-height: 100px;
  }
}

/* Textarea for Command Input */
.form-textarea-large {
  width: 100%;
  padding: 16px 18px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #e2e0e8;
  font-size: 15px;
  outline: none;
  transition: all 0.2s ease;
  font-family: inherit;
  resize: vertical;
  min-height: 120px;
  line-height: 1.5;
  box-sizing: border-box;
}

@media (max-width: 768px) {
  .form-textarea-large {
    font-size: 16px;
    min-height: 100px;
  }
}

.form-textarea-large:focus {
  border-color: rgba(124, 58, 237, 0.4);
  background: rgba(255, 255, 255, 0.06);
}

.form-input::placeholder {
  color: #9c99ab;
}

.add-error {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: #f87171;
  font-size: 13px;
  line-height: 1.4;
}

@media (max-width: 768px) {
  .add-error {
    font-size: 15px;
  }
}

.add-error svg {
  flex-shrink: 0;
  margin-top: 2px;
}

.add-success {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.2);
  color: #22c55e;
  font-size: 13px;
  line-height: 1.4;
}

@media (max-width: 768px) {
  .add-success {
    font-size: 15px;
  }
}

.add-success svg {
  flex-shrink: 0;
  margin-top: 2px;
}

/* ─── Target Selector Styles ─── */
.target-selector-wrapper {
  margin-top: 12px;
  background: transparent;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.target-display {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.03);
}

.target-label-container {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.target-icon {
  color: #9c99ab;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.target-text-info {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.target-hint {
  font-size: 13px;
  color: #9c99ab;
}

.target-selected {
  font-size: 13px;
  color: #9c99ab;
}

.target-word-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.1);
  color: #e2e0e8;
  font-weight: 600;
  font-size: 12px;
}

.target-toggle-btn {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.05);
  color: #9c99ab;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.target-toggle-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #e2e0e8;
}

.target-toggle-btn:active {
  transform: scale(0.95);
}

/* Word Selection Expanded */
.word-selection-expanded {
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.02);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.selection-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.selection-title {
  font-size: 12px;
  font-weight: 600;
  color: #9c99ab;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.close-selection-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: transparent;
  color: #9c99ab;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-selection-btn:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #e2e0e8;
}

.words-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.word-button {
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.04);
  color: #9c99ab;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.word-button:hover {
  border-color: rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.08);
  color: #e2e0e8;
}

.word-button-active {
  border-color: rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.12);
  color: #e2e0e8;
  font-weight: 600;
}

.word-button-active:hover {
  border-color: rgba(255, 255, 255, 0.4);
  background: rgba(255, 255, 255, 0.15);
}

@media (max-width: 768px) {
  .target-selector-wrapper {
    margin-top: 16px;
    margin-left: -16px;
    margin-right: -16px;
    border-radius: 0;
    border-left: none;
    border-right: none;
  }

  .target-display {
    padding: 16px;
  }

  .target-hint,
  .target-selected {
    font-size: 15px;
  }

  .target-word-badge {
    padding: 6px 12px;
    font-size: 13px;
  }

  .target-toggle-btn {
    width: 40px;
    height: 40px;
    font-size: 18px;
  }

  .word-selection-expanded {
    padding: 16px;
  }

  .selection-title {
    font-size: 13px;
  }

  .word-button {
    padding: 12px 16px;
    font-size: 14px;
  }

  .words-grid {
    gap: 10px;
  }
}

.modal-footer {
  display: flex;
  gap: 10px;
  padding: 0 24px 24px;
}

.modal-btn {
  flex: 1;
  padding: 12px;
  border-radius: 12px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

@media (max-width: 768px) {
  .modal-btn {
    font-size: 17px;
  }
}

.modal-btn.secondary {
  background: rgba(255, 255, 255, 0.06);
  color: #9c99ab;
}

.modal-btn.secondary:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #e2e0e8;
}

.modal-btn.primary {
  background: #7c3aed;
  color: white;
}

.modal-btn.primary:hover:not(:disabled) {
  background: #6d28d9;
}

.modal-btn.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ─── Relearn Modal ─── */
.relearn-modal {
  max-width: 500px;
}

.relearn-success-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 20px 0;
}

.success-icon-container {
  margin-bottom: 20px;
}

.success-icon {
  stroke: #22c55e;
  animation: successPulse 0.6s ease-out;
}

@keyframes successPulse {
  0% {
    transform: scale(0);
    opacity: 0;
  }
  50% {
    transform: scale(1.1);
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

.success-title {
  font-size: 18px;
  font-weight: 700;
  color: #e2e0e8;
  margin: 0 0 12px 0;
}

.success-message {
  font-size: 15.5px;
  color: #b8b5c8;
  margin-bottom: 24px;
  line-height: 1.6;
}

.processing-state {
  padding: 20px 0;
}

.progress-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.progress-bar {
  width: 100%;
  height: 8px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #0891b2, #06b6d4);
  transition: width 0.3s ease;
  border-radius: 4px;
}

.progress-text {
  font-size: 14px;
  color: #9c99ab;
  text-align: center;
  margin: 0;
}

.count-selection {
  padding: 20px 0;
}

.selection-label {
  font-size: 14px;
  color: #9c99ab;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0 0 16px 0;
  font-weight: 600;
}

.count-buttons {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.count-btn {
  flex: 1;
  padding: 10px;
  border-radius: 10px;
  border: 2px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: #b8b5c8;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.count-btn:hover {
  border-color: rgba(8, 145, 178, 0.3);
  background: rgba(8, 145, 178, 0.1);
  color: #06b6d4;
}

.count-btn.active {
  background: #0891b2;
  color: white;
  border-color: #0891b2;
}

/* ─── Mobile Add Panel (Bottom Sheet) ─── */
.mobile-add-panel {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  background: #36324a;
  border-radius: 24px 24px 0 0;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding: 8px 20px 28px;
  z-index: 2001;
  max-height: 80vh;
  overflow-y: auto;
  /* Prevenir que el teclado se superponga */
  -webkit-user-select: none;
  user-select: none;
}

/* Asegurar que el input sea accesible cuando el teclado abre */
.mobile-add-input {
  -webkit-user-select: text;
  user-select: text;
}

@supports (padding: max(0px)) {
  .mobile-add-panel {
    padding-bottom: max(28px, env(safe-area-inset-bottom));
  }
}

.mobile-add-handle {
  display: flex;
  justify-content: center;
  padding: 8px 0 12px;
  cursor: pointer;
}

.handle-bar {
  width: 40px;
  height: 4px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.15);
}

.mobile-add-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.mobile-add-title {
  font-size: 20px;
  font-weight: 700;
  color: #e2e0e8;
  margin: 0;
}

@media (max-width: 768px) {
  .mobile-add-title {
    font-size: 23px;
  }
}

.mobile-add-hint {
  font-size: 13px;
  color: #9c99ab;
  line-height: 1.5;
  margin: 0;
}

@media (max-width: 768px) {
  .mobile-add-hint {
    font-size: 16px;
  }
}

.mobile-add-input {
  width: 100%;
  padding: 16px 18px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #e2e0e8;
  font-size: 16px;
  outline: none;
  transition: all 0.2s ease;
  font-family: inherit;
  box-sizing: border-box;
}

@media (max-width: 768px) {
  .mobile-add-input {
    font-size: 19px;
  }
}

.mobile-add-input:focus {
  border-color: rgba(124, 58, 237, 0.4);
  background: rgba(255, 255, 255, 0.06);
}

.mobile-add-input::placeholder {
  color: #9c99ab;
}

.mobile-add-actions {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}

.mobile-add-btn {
  flex: 1;
  padding: 14px;
  border-radius: 14px;
  border: none;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

@media (max-width: 768px) {
  .mobile-add-btn {
    font-size: 18px;
  }
}

.mobile-add-btn.secondary {
  background: rgba(255, 255, 255, 0.06);
  color: #9c99ab;
}

.mobile-add-btn.primary {
  background: #7c3aed;
  color: white;
}

.mobile-add-btn.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mobile-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 2000;
}

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
  padding: 16px 20px;
  gap: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.mobile-back-btn {
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

.mobile-detail-title {
  flex: 1;
  font-size: 16px;
  font-weight: 600;
  color: #e2e0e8;
  margin: 0;
  text-align: center;
}

@media (max-width: 768px) {
  .mobile-detail-title {
    font-size: 19px;
  }
}

.mobile-fav-btn {
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

.mobile-fav-btn.active {
  color: #f472b6;
}

.mobile-detail-actions {
  display: flex;
  gap: 10px;
}

.mobile-boost-btn {
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
  transition: all 0.2s ease;
}

.mobile-boost-btn:hover {
  background: rgba(255, 193, 7, 0.1);
  color: #ffc107;
}

.mobile-boost-btn.active {
  color: #ffc107;
  background: rgba(255, 193, 7, 0.15);
  box-shadow: 0 0 12px rgba(255, 193, 7, 0.3);
}

.mobile-detail-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px 20px;
}

.mobile-word-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 4px;
}

.mobile-word {
  font-size: 32px;
  font-weight: 700;
  color: #e2e0e8;
  margin: 0;
  letter-spacing: -0.5px;
}

@media (max-width: 768px) {
  .mobile-word {
    font-size: 36px;
  }
}

.mobile-speak-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: none;
  background: rgba(167, 139, 250, 0.1);
  color: #a78bfa;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.mobile-speak-btn:hover {
  background: rgba(167, 139, 250, 0.2);
  color: #c4b5fd;
}

.mobile-definition {
  font-size: 15px;
  line-height: 1.6;
  color: #b8b5c8;
  margin: 0 0 28px 0;
}

@media (max-width: 768px) {
  .mobile-definition {
    font-size: 18px;
  }
}

/* Mobile Synonyms */
.mobile-synonyms {
  margin-bottom: 28px;
}

.mobile-meta-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 28px;
}

.mobile-meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.mobile-meta-label {
  font-size: 13px;
  color: #9c99ab;
}

@media (max-width: 768px) {
  .mobile-meta-label {
    font-size: 16px;
  }
}

.mobile-meta-value {
  font-size: 14px;
  font-weight: 600;
  color: #e2e0e8;
}

@media (max-width: 768px) {
  .mobile-meta-value {
    font-size: 17px;
  }
}

.mobile-examples {
  margin-bottom: 28px;
}

.mobile-delete-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px;
  border-radius: 14px;
  border: none;
  background: rgba(239, 68, 68, 0.1);
  color: #f87171;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

@media (max-width: 768px) {
  .mobile-delete-btn {
    font-size: 18px;
  }
}

.mobile-delete-btn:hover {
  background: rgba(239, 68, 68, 0.2);
}

.mobile-explanation-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px 16px;
  border: none;
  background: rgba(167, 139, 250, 0.1);
  color: #a78bfa;
  font-size: 17px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
  border-bottom: 1px solid rgba(167, 139, 250, 0.1);
  margin-bottom: 12px;
  border-radius: 15px;
}

.mobile-explanation-btn:hover:not(:disabled) {
  background: rgba(167, 139, 250, 0.15);
}

.mobile-explanation-btn:active:not(:disabled) {
  background: rgba(167, 139, 250, 0.1);
}

.mobile-explanation-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mobile-explanation-content {
  background: rgba(167, 139, 250, 0.05);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  font-size: 17px;
  line-height: 1.6;
  color: #b4b1c6;
  animation: slideDown 0.3s ease;
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
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100%);
}

.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.2s ease;
}

.slide-down-enter-from,
.slide-down-leave-to {
  transform: translateY(-100%);
  opacity: 0;
}

/* ════════════════════════════════════════
   Responsive
   ════════════════════════════════════════ */

@media (max-width: 768px) {
  .my-words-view {
    padding: 16px;
  }

  .words-header {
    flex-direction: row;
    align-items: center;
    gap: 12px;
  }

  .words-title {
    font-size: 22px;
  }

  .add-btn span {
    display: none;
  }

  .add-btn {
    padding: 10px;
    border-radius: 12px;
  }

  .relearn-btn span {
    display: none;
  }

  .relearn-btn {
    padding: 10px;
    border-radius: 12px;
  }

  .words-toolbar {
    flex-direction: row;
    align-items: center;
    gap: 8px;
  }

  .search-box {
    display: none;
  }

  .filter-tabs {
    display: none;
  }

  .mobile-search-btn {
    display: flex;
  }

  .mobile-favorites-btn {
    display: flex;
  }

  .mobile-filter-btn {
    display: flex;
  }

  .mobile-search-panel {
    display: flex;
  }

  .learning-state-filter {
    display: none;
  }

  .mobile-filter-backdrop {
    display: block;
  }

  .mobile-filter-menu {
    display: flex;
  }

  .words-content.detail-open .word-list {
    flex: 1;
    max-width: none;
  }

  .detail-panel {
    display: none;
  }

  .word-card {
    padding: 14px 16px;
  }

  .word-definition {
    -webkit-line-clamp: 1;
  }

  /* Relearn Modal - Mobile */
  .relearn-modal {
    max-width: 95vw;
  }

  .modal-hint {
    font-size: 15px;
    line-height: 1.5;
  }

  .success-title {
    font-size: 16px;
  }

  .success-message {
    font-size: 13px;
  }

  .selection-label {
    font-size: 13px;
  }

  .count-buttons {
    gap: 10px;
  }

  .count-btn {
    font-size: 13px;
    padding: 8px;
  }

  .progress-text {
    font-size: 13px;
  }
}

@media (min-width: 769px) {
  .mobile-detail-overlay,
  .mobile-add-panel,
  .mobile-backdrop {
    display: none;
  }
}

/* ════════════════════════════════════════
   COMMAND SYSTEM — Slash Commands
   ════════════════════════════════════════ */

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
}

.input-slash-btn {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 32px;
  height: 32px;
  background: rgba(124, 58, 237, 0.2);
  border: 1px solid rgba(124, 58, 237, 0.4);
  border-radius: 8px;
  color: #a78bfa;
  cursor: pointer;
  font-size: 16px;
  font-weight: 700;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.input-slash-btn:hover {
  background: rgba(124, 58, 237, 0.3);
  border-color: rgba(124, 58, 237, 0.6);
  color: #d8b4fe;
}

/* Quick Commands Section */
.quick-commands-section {
  margin-top: 12px;
  padding: 12px;
  background: rgba(124, 58, 237, 0.08);
  border: 1px solid rgba(124, 58, 237, 0.15);
  border-radius: 10px;
}

.quick-commands-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  color: #7c99ab;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.quick-commands-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.quick-command-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(124, 58, 237, 0.15);
  border: 1px solid rgba(124, 58, 237, 0.3);
  border-radius: 16px;
  color: #a78bfa;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.quick-command-chip:hover {
  background: rgba(124, 58, 237, 0.25);
  border-color: rgba(124, 58, 237, 0.5);
  color: #d8b4fe;
}

.quick-command-chip span:first-child {
  font-size: 13px;
}

.mobile-input-wrapper {
  width: 100%;
  position: relative;
}

.mobile-add-input-large {
  /* min-height: 100px; */
  padding: 14px 14px;
  font-size: 16px;
}

.mobile-slash-btn {
  position: absolute;
  right: 10px;
  bottom: 10px;
  width: 28px;
  height: 28px;
  background: rgba(124, 58, 237, 0.2);
  border: 1px solid rgba(124, 58, 237, 0.4);
  border-radius: 6px;
  color: #a78bfa;
  font-size: 14px;
  font-weight: 700;
}

.mobile-quick-commands {
  margin-top: 10px;
}

.mobile-commands-list {
  gap: 4px;
}

.mobile-command-chip {
  padding: 5px 8px;
  font-size: 11px;
  gap: 3px;
}

.mobile-command-chip span:first-child {
  font-size: 12px;
}

/* Command Input Section */
.command-input-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.mobile-command-section {
  gap: 12px;
  padding: 12px;
}

/* Command Header Actions */
.command-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cmd-help-btn {
  background: rgba(124, 58, 237, 0.15);
  border: 1px solid rgba(124, 58, 237, 0.3);
  color: #a78bfa;
  cursor: pointer;
  font-size: 11px;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.cmd-help-btn:hover {
  background: rgba(124, 58, 237, 0.25);
  border-color: rgba(124, 58, 237, 0.5);
  color: #d8b4fe;
}

/* Command Hint Tooltip */
.command-hint-tooltip {
  font-size: 12px;
  color: #9c99ab;
  line-height: 1.6;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 8px;
  border-left: 3px solid rgba(124, 58, 237, 0.5);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
  overflow-y: auto;
}

.mobile-hint-tooltip {
  font-size: 11px;
  padding: 10px 12px;
  line-height: 1.5;
}

/* Command Header */
.command-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.mobile-cmd-header {
  gap: 10px;
}

.command-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.command-title-icon {
  font-size: 20px;
}

.command-title-text {
  font-size: 14px;
  font-weight: 700;
  color: #a78bfa;
}

.cmd-close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  color: #9c99ab;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s ease;
}

.cmd-close-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #e2e0e8;
}

/* Dynamic Fields */
.command-fields {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mobile-fields {
  gap: 10px;
}

.command-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  color: #9c99ab;
  letter-spacing: 0.5px;
}

.field-input {
  width: 100%;
  padding: 12px 14px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.05);
  color: #e2e0e8;
  font-size: 14.7px;
  outline: none;
  transition: all 0.2s ease;
  font-family: inherit;
  box-sizing: border-box;
}

.field-input::placeholder {
  color: #9c99ab;
}

.field-input:focus {
  border-color: rgba(124, 58, 237, 0.25);
  background: rgba(255, 255, 255, 0.06);
}

/* Textarea for sentence fields */
.field-textarea {
  width: 100%;
  padding: 12px 14px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.05);
  color: #e2e0e8;
  font-size: 14.7px;
  outline: none;
  transition: all 0.2s ease;
  font-family: inherit;
  box-sizing: border-box;
  resize: vertical;
  line-height: 1.5;
  min-height: 100px;
}

.field-textarea::placeholder {
  color: #9c99ab;
}

.field-textarea:focus {
  border-color: rgba(124, 58, 237, 0.25);
  background: rgba(255, 255, 255, 0.06);
}

/* Parts of Speech Chips */

.hint-text {
  font-size: 12px;
  line-height: 1.5;
  color: #9c99ab;
  margin: 0;
}


/* Command Menu Dropdown */
.command-menu {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  background: rgba(20, 18, 30, 0.98);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 12px;
  backdrop-filter: blur(15px);
  max-height: 80vh;
  overflow-y: scroll;
  overflow-x: hidden;
  z-index: 10000;
  box-shadow: 0 15px 50px rgba(0, 0, 0, 0.6);
  min-width: 100%;
  scroll-behavior: smooth;
  overscroll-behavior: contain;
}

/* En pantallas pequeñas, usar menos altura */
@media (max-height: 800px) {
  .command-menu {
    max-height: 60vh;
  }
}

/* Custom scrollbar for command menu */
.command-menu::-webkit-scrollbar {
  width: 6px;
}

.command-menu::-webkit-scrollbar-track {
  background: transparent;
}

.command-menu::-webkit-scrollbar-thumb {
  background: rgba(124, 58, 237, 0.4);
  border-radius: 3px;
}

.command-menu::-webkit-scrollbar-thumb:hover {
  background: rgba(124, 58, 237, 0.6);
}

.command-menu-header {
  padding: 10px 14px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  color: #7c7a8a;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  letter-spacing: 0.5px;
}

.command-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  padding: 12px 14px;
  border: none;
  background: none;
  color: inherit;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s ease;
  border-bottom: 1px solid rgba(255, 255, 255, 0.02);
}

.command-item:hover {
  background: rgba(124, 58, 237, 0.15);
}

.command-item:last-child {
  border-bottom: none;
}

.command-icon {
  font-size: 20px;
  min-width: 24px;
  text-align: center;
}

.command-info {
  flex: 1;
  min-width: 0;
}

.command-name {
  font-size: 14px;
  font-weight: 600;
  color: #e2e0e8;
  margin-bottom: 2px;
}

.command-desc {
  font-size: 12px;
  color: #9c99ab;
}

.command-empty {
  padding: 20px 14px;
  text-align: center;
  color: #9c99ab;
  font-size: 13px;
}

/* Mobile Specific */

/* Mobile Commands Modal (Bottom Sheet) */
.mobile-commands-modal {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  flex-direction: column;
  pointer-events: none;
}

.mobile-commands-overlay {
  flex: 1;
  background: rgba(0, 0, 0, 0.4);
  pointer-events: auto;
}

.mobile-commands-sheet {
  background: #36324a;
  border-radius: 16px 16px 0 0;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
  pointer-events: auto;
  box-shadow: 0 -5px 30px rgba(0, 0, 0, 0.3);
}

.mobile-commands-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.mobile-commands-title {
  font-size: 16px;
  font-weight: 700;
  color: #e2e0e8;
  margin: 0;
}

.mobile-commands-close {
  background: none;
  border: none;
  color: #9c99ab;
  cursor: pointer;
  font-size: 20px;
  padding: 0;
  transition: color 0.2s ease;
}

.mobile-commands-close:active {
  color: #e2e0e8;
}

.mobile-commands-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mobile-command-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 14px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 10px;
  color: inherit;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s ease;
}

.mobile-command-btn:active {
  background: rgba(124, 58, 237, 0.2);
  border-color: rgba(124, 58, 237, 0.4);
}

.cmd-icon {
  font-size: 22px;
  min-width: 24px;
}

.cmd-text {
  flex: 1;
  min-width: 0;
}

.cmd-title {
  font-size: 14px;
  font-weight: 600;
  color: #e2e0e8;
  margin-bottom: 2px;
}

.cmd-desc {
  font-size: 12px;
  color: #9c99ab;
}

.mobile-commands-empty {
  padding: 32px 16px;
  text-align: center;
  color: #9c99ab;
  font-size: 13px;
}

/* Desktop Commands Modal (Top Sheet) */
.desktop-commands-modal {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  flex-direction: column;
  pointer-events: none;
}

.desktop-commands-overlay {
  flex: 1;
  background: rgba(0, 0, 0, 0.4);
  pointer-events: auto;
}

.desktop-commands-sheet {
  background: #36324a;
  border-radius: 0 0 16px 16px;
  max-height: 60vh;
  display: flex;
  flex-direction: column;
  pointer-events: auto;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4);
}

.desktop-commands-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.desktop-commands-title {
  font-size: 18px;
  font-weight: 700;
  color: #e2e0e8;
  margin: 0;
}

.desktop-commands-close {
  background: none;
  border: none;
  color: #9c99ab;
  cursor: pointer;
  font-size: 22px;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s ease;
}

.desktop-commands-close:hover {
  color: #e2e0e8;
}

.desktop-commands-grid {
  flex: 1;
  overflow-y: auto;
  padding: 16px 24px;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.desktop-command-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  color: inherit;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s ease;
}

.desktop-command-card:hover {
  background: rgba(124, 58, 237, 0.15);
  border-color: rgba(124, 58, 237, 0.3);
}

.card-icon {
  font-size: 28px;
  min-width: 28px;
  min-height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-content {
  flex: 1;
  min-width: 0;
}

.card-title {
  font-size: 14px;
  font-weight: 700;
  color: #e2e0e8;
  margin-bottom: 4px;
}

.card-desc {
  font-size: 12px;
  color: #9c99ab;
  line-height: 1.4;
}

.desktop-commands-empty {
  padding: 40px 24px;
  text-align: center;
  color: #9c99ab;
  font-size: 14px;
  grid-column: 1 / -1;
}

</style>