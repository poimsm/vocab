<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { Icon } from '@iconify/vue'

// ===================== TYPES =====================
interface WordItem {
    id: number
    main: string
    meaning: string
    type: string
    frequency: string
    level: string
    context: string
    is_favorite: boolean
    is_learned: boolean
    total_examples: number
}

interface Meta {
    total_items: number
    total_pages: number
    current_page: number
    limit: number
    has_next: boolean
    has_prev: boolean
}

interface ApiResponse {
    items: WordItem[]
    meta: Meta
}

// ===================== STATE =====================
const API_BASE = 'http://localhost:8000'

const search = ref('')
const filterTab = ref('all')
const sortBy = ref('newest')
const currentPage = ref(1)
const limit = ref(10)

// Data from API
const words = ref<WordItem[]>([])
const meta = ref<Meta | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

// Add form state
const showAddForm = ref(false)
const newWord = ref('')
const newNote = ref('')
const wordError = ref('')
const adding = ref(false)

// Actions loading states
const actionLoading = ref<Record<number, { fav?: boolean; active?: boolean; examples?: boolean }>>({})

// Toast notification
const toast = ref<{ show: boolean; message: string; type: 'success' | 'error' }>({
    show: false,
    message: '',
    type: 'success'
})

// ===================== COMPUTED =====================
const filteredWords = computed(() => {
    // Client-side search filter (API already filters by page, but we can filter visible)
    if (!search.value) return words.value
    return words.value.filter(w =>
        w.main.toLowerCase().includes(search.value.toLowerCase()) ||
        w.meaning.toLowerCase().includes(search.value.toLowerCase())
    )
})

// ===================== API CALLS =====================
async function fetchWords() {
    loading.value = true
    error.value = null
    try {
        const params = new URLSearchParams({
            limit: String(limit.value),
            sort: sortBy.value,
            page: String(currentPage.value)
        })
        if (search.value) params.append('search', search.value)

        const res = await fetch(`${API_BASE}/words/words?${params}`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data: ApiResponse = await res.json()
        words.value = data.items
        meta.value = data.meta
    } catch (err) {
        error.value = err instanceof Error ? err.message : 'Failed to load words'
        showToast(error.value, 'error')
    } finally {
        loading.value = false
    }
}

async function addWord() {
    const trimmedWord = newWord.value.trim()
    if (!trimmedWord) {
        wordError.value = 'Gotta type something!'
        return
    }
    if (trimmedWord.length > 50) {
        wordError.value = 'Too long! Keep it under 50 chars.'
        return
    }

    adding.value = true
    wordError.value = ''
    try {
        const res = await fetch(`${API_BASE}/words`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: trimmedWord })
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        showToast('Word added successfully!', 'success')
        newWord.value = ''
        newNote.value = ''
        // Refresh list
        await fetchWords()
    } catch (err) {
        wordError.value = err instanceof Error ? err.message : 'Failed to add word'
        showToast(wordError.value, 'error')
    } finally {
        adding.value = false
    }
}

async function toggleFavorite(id: number) {
    setActionLoading(id, 'fav', true)
    try {
        const res = await fetch(`${API_BASE}/words/${id}/toggle-fav`, {
            method: 'PATCH'
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        // Update local state
        const word = words.value.find(w => w.id === id)
        if (word) word.is_favorite = !word.is_favorite
        showToast(word?.is_favorite ? 'Added to favorites' : 'Removed from favorites', 'success')
    } catch (err) {
        showToast('Failed to toggle favorite', 'error')
    } finally {
        setActionLoading(id, 'fav', false)
    }
}

async function toggleActive(id: number) {
    setActionLoading(id, 'active', true)
    try {
        const res = await fetch(`${API_BASE}/words/${id}/toggle-active`, {
            method: 'PATCH'
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        // Remove from list (deactivated)
        words.value = words.value.filter(w => w.id !== id)
        showToast('Word deactivated', 'success')
    } catch (err) {
        showToast('Failed to deactivate word', 'error')
    } finally {
        setActionLoading(id, 'active', false)
    }
}

async function generateExamples(id: number) {
    setActionLoading(id, 'examples', true)
    try {
        const res = await fetch(`${API_BASE}/examples/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ word_id: id })
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        // Update local count
        const word = words.value.find(w => w.id === id)
        if (word) word.total_examples += 1
        showToast('Examples generated!', 'success')
    } catch (err) {
        showToast('Failed to generate examples', 'error')
    } finally {
        setActionLoading(id, 'examples', false)
    }
}

// ===================== HELPERS =====================
function setActionLoading(id: number, action: 'fav' | 'active' | 'examples', value: boolean) {
    if (!actionLoading.value[id]) actionLoading.value[id] = {}
    actionLoading.value[id][action] = value
}

function isActionLoading(id: number, action: 'fav' | 'active' | 'examples') {
    return actionLoading.value[id]?.[action] || false
}

function showToast(message: string, type: 'success' | 'error') {
    toast.value = { show: true, message, type }
    setTimeout(() => { toast.value.show = false }, 3000)
}

function toggleAddForm() {
    showAddForm.value = !showAddForm.value
    if (!showAddForm.value) {
        newWord.value = ''
        newNote.value = ''
        wordError.value = ''
    }
}

function goToPage(page: number) {
    if (meta.value && page >= 1 && page <= meta.value.total_pages) {
        currentPage.value = page
        fetchWords()
    }
}

function levelClass(level: string) {
    return {
        beginner: 'level-beginner',
        intermediate: 'level-intermediate',
        advanced: 'level-advanced'
    }[level.toLowerCase()] || ''
}

function frequencyColor(frequency: string) {
    return {
        'high': '#111',
        'medium': '#555',
        'low': '#999'
    }[frequency.toLowerCase()] || '#999'
}

function difficultyColor(level: string) {
    // Map level to difficulty color
    return {
        'beginner': '#22c55e',
        'intermediate': '#f59e0b',
        'advanced': '#ef4444'
    }[level.toLowerCase()] || '#999'
}

function capitalize(str: string) {
    return str.charAt(0).toUpperCase() + str.slice(1)
}

// ===================== WATCHERS =====================
watch([sortBy, limit], () => {
    currentPage.value = 1
    fetchWords()
})

// Debounce search
let searchTimeout: ReturnType<typeof setTimeout>
watch(search, () => {
    clearTimeout(searchTimeout)
    searchTimeout = setTimeout(() => {
        currentPage.value = 1
        fetchWords()
    }, 400)
})

// ===================== LIFECYCLE =====================
onMounted(() => {
    fetchWords()
})
</script>

<template>
    <div class="module">
        <!-- Toast Notification -->
        <Transition name="toast">
            <div v-if="toast.show" class="toast" :class="toast.type">
                <Icon :icon="toast.type === 'success' ? 'solar:check-circle-bold' : 'solar:danger-circle-bold'" width="18" />
                {{ toast.message }}
            </div>
        </Transition>

        <header class="header">
            <div>
                <h1>My words</h1>
                <p>Your personal word stash. Add anything cool you come across.</p>
            </div>

            <button class="add-btn" @click="toggleAddForm" :disabled="adding">
                <Icon :icon="showAddForm ? 'solar:close-circle-bold' : 'material-symbols:add'" width="20" />
                {{ showAddForm ? 'Close' : 'Add word' }}
            </button>
        </header>

        <!-- Inline Add Form -->
        <div v-if="showAddForm" class="add-form">
            <div class="form-row">
                <div class="form-group word-group">
                    <label>Word or phrase <span class="required">*</span></label>
                    <input v-model="newWord" type="text" placeholder="e.g. 'serendipity' or 'hit the sack'"
                        maxlength="50" @keydown.enter="addWord" :disabled="adding" />
                    <span class="char-count" :class="{ 'over': newWord.length > 50 }">
                        {{ newWord.length }}/50
                    </span>
                    <p v-if="wordError" class="error-msg">{{ wordError }}</p>
                </div>
                <div class="form-group note-group">
                    <label>Note <span class="optional">(optional)</span></label>
                    <input v-model="newNote" type="text" placeholder="What does it mean?" @keydown.enter="addWord" :disabled="adding" />
                </div>
            </div>
            <button class="form-submit" @click="addWord" :disabled="adding">
                <Icon :icon="adding ? 'solar:spinner-bold' : 'material-symbols:add'" width="18" :class="{ 'spin': adding }" />
                {{ adding ? 'Saving...' : 'Save it' }}
            </button>
        </div>

        <!-- Filters toolbar -->
        <div class="toolbar">
            <div class="search">
                <Icon icon="solar:magnifer-linear" width="20" color="#aaa" />
                <input v-model="search" placeholder="Find a word..." :disabled="loading">
            </div>

            <div class="toolbar-right">
                <div class="limit-dropdown">
                    <select v-model="limit">
                        <option :value="5">5 / page</option>
                        <option :value="10">10 / page</option>
                        <option :value="20">20 / page</option>
                        <option :value="50">50 / page</option>
                    </select>
                    <Icon icon="solar:alt-arrow-down-linear" width="16" class="sort-icon" />
                </div>

                <div class="sort-dropdown">
                    <select v-model="sortBy">
                        <option value="newest">Newest first</option>
                        <option value="oldest">Oldest first</option>
                        <option value="relevance">Most relevant</option>
                        <option value="difficulty">Hardest first</option>
                    </select>
                    <Icon icon="solar:alt-arrow-down-linear" width="16" class="sort-icon" />
                </div>
            </div>
        </div>

        <!-- Loading State -->
        <div v-if="loading && words.length === 0" class="loading-state">
            <Icon icon="solar:spinner-bold" width="32" color="#8b5cf6" class="spin" />
            <p>Loading words...</p>
        </div>

        <!-- Error State -->
        <div v-else-if="error && words.length === 0" class="empty-state error">
            <Icon icon="solar:danger-circle-bold-duotone" width="48" color="#ef4444" />
            <p>{{ error }}</p>
            <button class="retry-btn" @click="fetchWords">Try again</button>
        </div>

        <!-- Table -->
        <div v-else class="table-wrapper">
            <div v-if="loading" class="table-loading-overlay">
                <Icon icon="solar:spinner-bold" width="24" color="#8b5cf6" class="spin" />
            </div>

            <table>
                <thead>
                    <tr>
                        <th>Word</th>
                        <th>Level</th>
                        <th>Context</th>
                        <th>Frequency</th>
                        <th>Examples</th>
                        <th>Actions</th>
                    </tr>
                </thead>

                <tbody>
                    <tr v-for="word in filteredWords" :key="word.id">
                        <td class="text">
                            <div class="word-cell">
                                <span class="word-name">{{ word.main }}</span>
                                <span v-if="word.meaning" class="word-note">{{ word.meaning }}</span>
                            </div>
                        </td>                       

                        <td>
                            <span class="badge" :class="levelClass(word.level)">
                                {{ capitalize(word.level) }}
                            </span>
                        </td>

                        <td>
                            <span class="category-badge">{{ capitalize(word.context) }}</span>
                        </td>

                        <td :style="{ color: frequencyColor(word.frequency), fontWeight: word.frequency === 'high' ? '600' : '400' }">
                            {{ capitalize(word.frequency) }}
                        </td>

                        <td class="text-muted">
                            <div class="examples-cell">
                                <Icon icon="solar:document-text-linear" width="14" color="#aaa" />
                                {{ word.total_examples }}
                            </div>
                        </td>

                        <td>
                            <div class="actions">
                                <!-- Generate Examples -->
                                <button
                                    class="action-btn"
                                    :class="{ 'loading': isActionLoading(word.id, 'examples') }"
                                    @click="generateExamples(word.id)"
                                    :disabled="isActionLoading(word.id, 'examples')"
                                    title="Generate examples"
                                >
                                    <Icon :icon="isActionLoading(word.id, 'examples') ? 'solar:spinner-bold' : 'solar:magic-stick-3-linear'" width="16" :class="{ 'spin': isActionLoading(word.id, 'examples') }" />
                                </button>

                                <!-- Toggle Favorite -->
                                <button
                                    class="action-btn fav"
                                    :class="{ 'active': word.is_favorite, 'loading': isActionLoading(word.id, 'fav') }"
                                    @click="toggleFavorite(word.id)"
                                    :disabled="isActionLoading(word.id, 'fav')"
                                    title="Toggle favorite"
                                >
                                    <Icon :icon="isActionLoading(word.id, 'fav') ? 'solar:spinner-bold' : (word.is_favorite ? 'solar:heart-bold' : 'solar:heart-linear')" width="16" :class="{ 'spin': isActionLoading(word.id, 'fav') }" />
                                </button>

                                <!-- Deactivate / Delete -->
                                <button
                                    class="action-btn delete"
                                    :class="{ 'loading': isActionLoading(word.id, 'active') }"
                                    @click="toggleActive(word.id)"
                                    :disabled="isActionLoading(word.id, 'active')"
                                    title="Deactivate"
                                >
                                    <Icon :icon="isActionLoading(word.id, 'active') ? 'solar:spinner-bold' : 'solar:trash-bin-trash-linear'" width="16" :class="{ 'spin': isActionLoading(word.id, 'active') }" />
                                </button>
                            </div>
                        </td>
                    </tr>
                </tbody>
            </table>

            <div v-if="filteredWords.length === 0 && !loading" class="empty-state">
                <Icon icon="solar:document-text-bold-duotone" width="48" color="#ddd" />
                <p>No words found. Try a different search or add something new!</p>
            </div>

            <!-- Footer with Pagination -->
            <div class="footer">
                <span>
                    Showing {{ filteredWords.length }} of {{ meta?.total_items || 0 }} word{{ (meta?.total_items || 0) !== 1 ? 's' : '' }}
                    <span v-if="meta"> · Page {{ meta.current_page }} of {{ meta.total_pages }}</span>
                </span>

                <div class="pagination" v-if="meta && meta.total_pages > 1">
                    <button @click="goToPage(currentPage - 1)" :disabled="!meta.has_prev || loading">
                        <Icon icon="solar:alt-arrow-left-linear" />
                    </button>

                    <button
                        v-for="page in meta.total_pages"
                        :key="page"
                        :class="{ 'active': page === currentPage }"
                        @click="goToPage(page)"
                        :disabled="loading"
                    >
                        {{ page }}
                    </button>

                    <button @click="goToPage(currentPage + 1)" :disabled="!meta.has_next || loading">
                        <Icon icon="solar:alt-arrow-right-linear" />
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.module {
    display: flex;
    flex-direction: column;
    gap: 20px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    position: relative;
}

/* ===== TOAST ===== */
.toast {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 1000;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 20px;
    border-radius: 12px;
    font-size: 14px;
    font-weight: 500;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    animation: slideInRight 0.3s ease;
}

.toast.success {
    background: #eaf8ef;
    color: #28a745;
    border: 1px solid #c3e6cb;
}

.toast.error {
    background: #fdeaea;
    color: #ef4444;
    border: 1px solid #f5c6cb;
}

.toast-enter-active,
.toast-leave-active {
    transition: all 0.3s ease;
}

.toast-enter-from,
.toast-leave-to {
    opacity: 0;
    transform: translateX(100%);
}

@keyframes slideInRight {
    from { opacity: 0; transform: translateX(100%); }
    to { opacity: 1; transform: translateX(0); }
}

/* ===== HEADER ===== */
.header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    flex-wrap: wrap;
}

.header h1 {
    margin: 0;
    font-size: 1.75rem;
    font-weight: 700;
    color: #1a1a2e;
    letter-spacing: -0.5px;
}

.header p {
    margin: 4px 0 0 0;
    color: #888;
    font-size: 14px;
}

.add-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    border: 0;
    color: white;
    background: #8b5cf6;
    padding: 12px 20px;
    border-radius: 12px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
    box-shadow: 0 2px 8px rgba(139, 92, 246, 0.25);
}

.add-btn:hover:not(:disabled) {
    background: #7c3aed;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(139, 92, 246, 0.35);
}

.add-btn:active:not(:disabled) {
    transform: translateY(0);
}

.add-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

/* ===== INLINE ADD FORM ===== */
.add-form {
    background: #faf8ff;
    border: 1.5px solid #e8e0f7;
    border-radius: 16px;
    padding: 20px 24px;
    animation: slideDown 0.25s ease;
}

@keyframes slideDown {
    from { opacity: 0; transform: translateY(-10px); max-height: 0; }
    to { opacity: 1; transform: translateY(0); max-height: 300px; }
}

.form-row {
    display: flex;
    gap: 16px;
    margin-bottom: 14px;
}

.form-group {
    display: flex;
    flex-direction: column;
    gap: 5px;
}

.word-group { flex: 1.2; min-width: 200px; }
.note-group { flex: 1; min-width: 180px; }

.form-group label {
    font-size: 12px;
    font-weight: 600;
    color: #555;
}

.required { color: #ef4444; }
.optional { color: #aaa; font-weight: 400; }

.form-group input {
    border: 1.5px solid #e0d8f0;
    border-radius: 10px;
    padding: 11px 14px;
    font-size: 14px;
    color: #333;
    outline: none;
    transition: all 0.2s;
    background: white;
    font-family: inherit;
}

.form-group input:focus {
    border-color: #8b5cf6;
    box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.1);
}

.form-group input:disabled {
    background: #f5f5f5;
    cursor: not-allowed;
}

.form-group input::placeholder { color: #bbb; }

.char-count {
    font-size: 11px;
    color: #bbb;
    text-align: right;
}

.char-count.over { color: #ef4444; font-weight: 600; }

.error-msg {
    font-size: 12px;
    color: #ef4444;
    margin: 0;
    animation: shake 0.3s ease;
}

@keyframes shake {
    0%, 100% { transform: translateX(0); }
    25% { transform: translateX(-4px); }
    75% { transform: translateX(4px); }
}

.form-submit {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 10px 20px;
    border: 0;
    border-radius: 10px;
    background: #8b5cf6;
    color: white;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
}

.form-submit:hover:not(:disabled) { background: #7c3aed; }

.form-submit:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

/* ===== TOOLBAR ===== */
.toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
}

.toolbar-right {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-left: auto;
}

.search {
    flex: 1;
    min-width: 200px;
    max-width: 320px;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 16px;
    border: 1.5px solid #e5e5e5;
    border-radius: 12px;
    background: white;
    height: 44px;
    transition: border-color 0.2s;
}

.search:focus-within { border-color: #8b5cf6; }

.search input {
    border: 0;
    outline: none;
    width: 100%;
    height: 100%;
    font-size: 14px;
    color: #333;
    background: transparent;
}

.search input::placeholder { color: #bbb; }

.limit-dropdown, .sort-dropdown {
    position: relative;
}

.limit-dropdown select, .sort-dropdown select {
    appearance: none;
    -webkit-appearance: none;
    height: 44px;
    padding: 0 36px 0 16px;
    border: 1.5px solid #e5e5e5;
    border-radius: 12px;
    background: white;
    font-size: 13px;
    font-weight: 500;
    color: #555;
    cursor: pointer;
    outline: none;
    transition: border-color 0.2s;
}

.limit-dropdown select { min-width: 100px; }
.sort-dropdown select { min-width: 140px; }

.limit-dropdown select:focus, .sort-dropdown select:focus { border-color: #8b5cf6; }

.sort-icon {
    position: absolute;
    right: 14px;
    top: 50%;
    transform: translateY(-50%);
    pointer-events: none;
    color: #999;
}

/* ===== LOADING STATES ===== */
.loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 60px 20px;
    color: #999;
}

.loading-state p { margin: 0; font-size: 14px; }

.table-loading-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(255,255,255,0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10;
    border-radius: 16px;
}

.spin { animation: spin 1s linear infinite; }

@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.retry-btn {
    margin-top: 12px;
    padding: 8px 20px;
    border: 0;
    border-radius: 10px;
    background: #8b5cf6;
    color: white;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
}

.retry-btn:hover { background: #7c3aed; }

/* ===== TABLE ===== */
.table-wrapper {
    background: white;
    border: 1px solid #ececec;
    border-radius: 16px;
    overflow: hidden;
    position: relative;
}

table { width: 100%; border-collapse: collapse; }

th, td {
    text-align: left;
    padding: 14px 18px;
}

th {
    font-size: 11px;
    font-weight: 600;
    color: #aaa;
    text-transform: none;
    letter-spacing: 0.3px;
    background: #fafafa;
}

tbody tr {
    border-top: 1px solid #f0f0f0;
    transition: background 0.15s;
}

tbody tr:hover { background: #fafafa; }

/* Word cell */
.word-cell {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.word-name {
    font-weight: 600;
    color: #333;
    font-size: 14px;
}

.word-note {
    font-size: 12px;
    color: #999;
    max-width: 240px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* Type badge */
.type-badge {
    display: inline-block;
    padding: 3px 10px;
    background: #f0f0ff;
    color: #6366f1;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    text-transform: capitalize;
}

/* Level badges */
.badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
}

.level-beginner { background: #eaf8ef; color: #28a745; }
.level-intermediate { background: #eef5ff; color: #3b82f6; }
.level-advanced { background: #f4edff; color: #8b5cf6; }

/* Category */
.category-badge {
    display: inline-block;
    padding: 3px 10px;
    background: #f5f5f5;
    border-radius: 6px;
    font-size: 11px;
    color: #777;
    font-weight: 500;
    text-transform: capitalize;
}

/* Examples cell */
.examples-cell {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: #999;
}

/* Actions */
.actions {
    display: flex;
    gap: 6px;
    align-items: center;
}

.action-btn {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid #e5e5e5;
    border-radius: 8px;
    background: white;
    color: #777;
    cursor: pointer;
    transition: all 0.15s;
    padding: 0;
}

.action-btn:hover:not(:disabled) {
    background: #f5f5f5;
    border-color: #ddd;
    transform: translateY(-1px);
}

.action-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.action-btn.fav.active {
    background: #fef2f2;
    border-color: #fecaca;
    color: #ef4444;
}

.action-btn.delete:hover:not(:disabled) {
    background: #fef2f2;
    border-color: #fecaca;
    color: #ef4444;
}

/* Text styles */
.text-muted { color: #aaa; font-size: 13px; }
.text { color: #555; font-size: 14px; }

/* Empty state */
.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 48px 20px;
    color: #bbb;
    text-align: center;
}

.empty-state.error { color: #ef4444; }

.empty-state p { margin: 0; font-size: 14px; }

/* Footer */
.footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 18px;
    border-top: 1px solid #f0f0f0;
    color: #999;
    font-size: 13px;
    flex-wrap: wrap;
    gap: 10px;
}

.pagination {
    display: flex;
    gap: 6px;
}

.pagination button {
    width: 34px;
    height: 34px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid #ececec;
    border-radius: 10px;
    background: white;
    color: #777;
    cursor: pointer;
    transition: all 0.15s;
    font-size: 13px;
}

.pagination button:hover:not(:disabled) {
    background: #f5f5f5;
    border-color: #ddd;
}

.pagination button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}

.pagination .active {
    border-color: #8b5cf6;
    color: #8b5cf6;
    font-weight: 600;
    background: #f4edff;
}

/* ===== RESPONSIVE ===== */
@media (max-width: 768px) {
    .module { gap: 16px; }

    .header {
        flex-direction: column;
        gap: 12px;
    }

    .header h1 { font-size: 1.5rem; }

    .add-btn {
        width: 100%;
        justify-content: center;
        padding: 14px;
        font-size: 15px;
    }

    .add-form {
        padding: 16px;
        border-radius: 14px;
    }

    .form-row {
        flex-direction: column;
        gap: 12px;
        margin-bottom: 12px;
    }

    .word-group, .note-group {
        min-width: auto;
        width: 100%;
    }

    .form-submit {
        width: 100%;
        justify-content: center;
        padding: 12px;
    }

    .toolbar {
        flex-direction: column;
        align-items: stretch;
        gap: 10px;
    }

    .toolbar-right {
        margin-left: 0;
        justify-content: space-between;
    }

    .search {
        max-width: none;
        width: 100%;
    }

    .table-wrapper {
        overflow-x: auto;
        border-radius: 14px;
    }

    table { min-width: 800px; }

    th, td { padding: 12px 14px; }

    .word-note { max-width: 140px; }
}
</style>