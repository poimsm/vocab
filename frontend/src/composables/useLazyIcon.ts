import { defineAsyncComponent, ref, type Ref } from 'vue'

// Lazy load Icon component only when needed
// This removes ~50KB from the initial bundle
let IconComponent: any = null
let isLoading = ref(false)

export function useLazyIcon(): { Icon: Ref<any>; isLoading: Ref<boolean> } {
  const Icon = ref<any>(null)

  if (!IconComponent && !isLoading.value) {
    isLoading.value = true
    IconComponent = defineAsyncComponent(() =>
      import('@iconify/vue').then((module) => {
        isLoading.value = false
        return module
      })
    )
  }

  Icon.value = IconComponent

  return { Icon, isLoading }
}
