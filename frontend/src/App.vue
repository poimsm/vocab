<script setup lang="ts">
import { useNavigationStore } from '@/stores/navigation'
import MainLayout from './layouts/MainLayout.vue'
import ExamplesView from './components/ExamplesView.vue'
import MyWordsView from './components/MyWordsView.vue'

const nav = useNavigationStore()
</script>

<template>
  <MainLayout>
    <ExamplesView v-if="nav.activeModule === 'examples'" />
    <!-- Placeholders para otros módulos -->
     <MyWordsView v-if="nav.activeModule === 'words'" />
    <!-- <div v-else-if="nav.activeModule === 'words'" class="placeholder">
      My Words (coming soon)
    </div> -->
    <div v-else-if="nav.activeModule === 'search'" class="placeholder">
      Search (coming soon)
    </div>
    <div v-else-if="nav.activeModule === 'clusters'" class="placeholder">
      Clusters (coming soon)
    </div>
    <div v-else-if="nav.activeModule === 'roleplay'" class="placeholder">
      Roleplay (coming soon)
    </div>
    <div v-else-if="nav.activeModule === 'monsters'" class="placeholder">
      Monsters (coming soon)
    </div>
  </MainLayout>
</template>

<style>
.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  color: #9c99ab;
  font-size: 18px;
}
</style>