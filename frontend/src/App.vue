<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useNavigationStore } from '@/stores/navigation'

import MainLayout from '@/layouts/MainLayout.vue'
import MyWords from '@/components/MyWords.vue'
import Examples from '@/components/Examples.vue'
import Clusters from '@/components/Clusters.vue'
import Roleplay from '@/components/Roleplay.vue'
import Monsters from '@/components/Monsters.vue'
import SearchWord from './components/SearchWord.vue'

const nav = useNavigationStore()
const { activeModule } = storeToRefs(nav)

type ModuleId = 'words' | 'search' | 'examples' | 'clusters' | 'roleplay' | 'monsters'

const components: Record<ModuleId, any> = {
  words: MyWords,
  search: SearchWord,
  examples: Examples,
  clusters: Clusters,
  roleplay: Roleplay,
  monsters: Monsters
}

const currentComponent = computed(() => components[activeModule.value as ModuleId])
</script>

<template>
  <MainLayout>
    <component :is="currentComponent" />
  </MainLayout>
</template>

<style>
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
</style>