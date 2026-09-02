<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import { collocationApi } from '@/services/collocationApi'

interface Collocation {
  id: number
  phrase: string
  is_marked: boolean
}

const original = ref<Collocation[]>([])
const isLoading = ref(true)
const error = ref<string | null>(null)
const filterStatus = ref<'all' | 'marked' | 'not_marked'>('all')
const isSavingStatus = ref<number | null>(null)

const collocations = computed(() => {
  if (filterStatus.value === 'all') {
    return original.value
  } else if (filterStatus.value === 'marked') {
    return original.value.filter(c => c.is_marked)
  } else {
    return original.value.filter(c => !c.is_marked)
  }
})

const toggleMarked = async (collocation: Collocation) => {
  const newStatus = !collocation.is_marked
  isSavingStatus.value = collocation.id

  try {
    const updated = await collocationApi.toggleMarked(collocation.id, newStatus)

    // Update local state
    const item = original.value.find(c => c.id === collocation.id)
    if (item) {
      item.is_marked = updated.is_marked
    }
  } catch (err) {
    console.error('Error updating collocation status:', err)
    error.value = 'Failed to update status'
  } finally {
    isSavingStatus.value = null
  }
}

const clearProgress = async () => {
  try {
    // Clear all marked items by setting them back to unmarked
    const markedItems = original.value.filter(c => c.is_marked)
    for (const item of markedItems) {
      await collocationApi.toggleMarked(item.id, false)
      item.is_marked = false
    }
  } catch (err) {
    console.error('Error clearing progress:', err)
    error.value = 'Failed to clear progress'
  }
}

const loadCollocations = async () => {
  try {
    isLoading.value = true
    error.value = null
    let response = await collocationApi.getCollocations('all')

    // Generate initial collocations if empty
    if (response.items.length === 0) {
      const initResult = await collocationApi.generateInitial()
      if (initResult.status === 'created' && initResult.items) {
        response.items = initResult.items
      }
    }

    original.value = response.items
  } catch (err: any) {
    error.value = err.message || 'Failed to load collocations'
    console.error('Error loading collocations:', err)
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  loadCollocations()
})
</script>

<template>
  <div class="collocations-view">
    <div class="page">
      <!-- Loading State -->
      <div v-if="isLoading" class="loading-state">
        <p>Loading collocations...</p>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="error-state">
        <p>{{ error }}</p>
        <button @click="loadCollocations" class="retry-btn">Retry</button>
      </div>

      <!-- Empty State -->
      <div v-else-if="original.length === 0" class="empty-state">
        <p>No collocations yet. Create some to get started!</p>
      </div>

      <!-- Content -->
      <template v-else>
        <!-- Header -->
        <div class="page-header">
          <div class="title-section">
            <h1 class="title">Cozy Collocations</h1>
            <Icon icon="fluent-emoji:relaxed-face" width="32" class="emoji" />
          </div>
        </div>

        <!-- Filter -->
        <div class="filter-section">
          <div class="filter-group">
            <button
              v-for="option in ['all', 'marked', 'not_marked']"
              :key="option"
              class="filter-btn"
              :class="{ active: filterStatus === option }"
              @click="filterStatus = option as any"
            >
              {{ option === 'all' ? 'All' : option === 'marked' ? 'Marked' : 'Not Marked' }}
            </button>
          </div>
        </div>

        <!-- List -->
        <div class="items-list">
          <div
            v-for="(collocation, index) in collocations"
            :key="collocation.id"
            class="list-item"
            :class="{ completed: collocation.is_marked, saving: isSavingStatus === collocation.id }"
            @click="toggleMarked(collocation)"
          >
            <div
              class="number-badge"
              :class="{ checked: collocation.is_marked }"
            >
              {{ collocation.is_marked ? '✓' : index + 1 }}
            </div>
            <span class="phrase">{{ collocation.phrase }}</span>
            <div v-if="isSavingStatus === collocation.id" class="saving-spinner"></div>
          </div>
        </div>
      </template>

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

.loading-state,
.error-state,
.empty-state {
  max-width: 700px;
  margin: 0 auto;
  padding: 40px 36px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  text-align: center;
}

.loading-state p,
.error-state p,
.empty-state p {
  font-size: 16px;
  color: #9c99ab;
  margin: 0;
}

.error-state {
  border-color: rgba(255, 100, 100, 0.2);
}

.error-state p {
  color: #ff6464;
  margin-bottom: 16px;
}

.retry-btn {
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid rgba(167, 139, 250, 0.4);
  background: rgba(167, 139, 250, 0.1);
  color: #a78bfa;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.retry-btn:hover {
  background: rgba(167, 139, 250, 0.2);
  border-color: rgba(167, 139, 250, 0.6);
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
  align-items: center;
  margin-bottom: 32px;
  gap: 12px;
}

.title-section {
  display: flex;
  align-items: center;
  gap: 12px;
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

.items-list {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-bottom: 32px;
}

.filter-section {
  margin-bottom: 24px;
}

.filter-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-btn {
  padding: 6px 12px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.05);
  color: #9c99ab;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.filter-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
}

.filter-btn.active {
  background: rgba(167, 139, 250, 0.15);
  border-color: rgba(167, 139, 250, 0.4);
  color: #a78bfa;
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
  position: relative;
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

.list-item.saving {
  opacity: 0.7;
  pointer-events: none;
}

.saving-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(167, 139, 250, 0.3);
  border-top-color: #a78bfa;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
}

@keyframes spin {
  to {
    transform: translateY(-50%) rotate(360deg);
  }
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

  .emoji {
    width: 24px;
    height: 24px;
  }

  .filter-section {
    margin-bottom: 16px;
  }

  .filter-group {
    gap: 6px;
  }

  .filter-btn {
    padding: 5px 10px;
    font-size: 11px;
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
}
</style>