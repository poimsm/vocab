<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { useNavigationStore } from '@/stores/navigation'

const nav = useNavigationStore()

const modules = [
  { id: 'words', label: 'My Words', icon: 'solar:book-bookmark-linear' },
  { id: 'search', label: 'Search', icon: 'iconamoon:search-light' },
  { id: 'examples', label: 'Examples', icon: 'solar:chat-round-line-linear' },
  { id: 'clusters', label: 'Clusters', icon: 'solar:widget-3-linear' },
  { id: 'roleplay', label: 'Roleplay', icon: 'solar:users-group-rounded-linear' },
  { id: 'monsters', label: 'Monsters', icon: 'solar:ghost-linear' }
]
</script>

<template>
  <div class="layout">
    <!-- Desktop Sidebar -->
    <aside class="sidebar">
      <div class="logo">
        <div class="logo-square"></div>
        <span>Lexio</span>
      </div>

      <button
        v-for="module in modules"
        :key="module.id"
        class="nav-item"
        :class="{ active: nav.activeModule === module.id }"
        @click="nav.setActiveModule(module.id)"
      >
        <Icon :icon="module.icon" width="20" />
        <span>{{ module.label }}</span>
      </button>
    </aside>

    <div class="main">
      <!-- Mobile Navigation -->
      <div class="mobile-nav">
        <button
          v-for="module in modules"
          :key="module.id"
          class="mobile-tab"
          :class="{ active: nav.activeModule === module.id }"
          @click="nav.setActiveModule(module.id)"
        >
          <Icon :icon="module.icon" width="18" />
          <span>{{ module.label }}</span>
        </button>
      </div>

      <!-- Ya no necesitamos slot scope, el contenido se maneja en App.vue -->
      <div class="content">
        <slot />
      </div>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
  background: #fafafa;
}

.sidebar {
  width: 240px;
  flex-shrink: 0;
  padding: 24px 12px;
  border-right: 1px solid #ececec;
  background: white;

  display: flex;
  flex-direction: column;
  gap: 6px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;

  margin-bottom: 24px;
  padding: 0 12px;

  font-size: 20px;
  font-weight: 700;
}

.logo-square {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: #8b5cf6;
}

.nav-item {
  border: 0;
  background: transparent;

  display: flex;
  align-items: center;
  gap: 12px;

  padding: 12px;
  border-radius: 12px;

  cursor: pointer;
  color: #666;

  font-size: 14px;
}

.nav-item:hover {
  background: #f5f5f5;
}

.nav-item.active {
  background: #f2ebff;
  color: #7c3aed;
}

.main {
  flex: 1;
  min-width: 0;
}

.mobile-nav {
  display: none;
}

.content {
  padding: 24px;
}

@media (max-width: 768px) {
  .layout {
    display: block;
  }

  .sidebar {
    display: none;
  }

  .mobile-nav {
    display: flex;
    gap: 10px;

    overflow-x: auto;
    padding: 12px;

    position: sticky;
    top: 0;

    background: white;
    border-bottom: 1px solid #ececec;

    scrollbar-width: none;
    z-index: 100;
  }

  .mobile-nav::-webkit-scrollbar {
    display: none;
  }

  .mobile-tab {
    border: 0;
    background: #f5f5f5;

    display: flex;
    align-items: center;
    gap: 8px;

    white-space: nowrap;

    padding: 10px 14px;
    border-radius: 999px;

    cursor: pointer;
  }

  .mobile-tab.active {
    background: #f2ebff;
    color: #7c3aed;
  }

  .content {
    padding: 16px;
  }
}
</style>