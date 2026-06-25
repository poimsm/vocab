import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useNavigationStore = defineStore('navigation', () => {
  // State
  const activeModule = ref('words')
  
  // Getters
  const currentModule = computed(() => activeModule.value)
  
  // Actions
  function setActiveModule(id: string) {
    activeModule.value = id
  }

  return {
    activeModule,
    currentModule,
    setActiveModule
  }
})