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
        <div class="logo-bear">
          <Icon icon="fluent-emoji:bear" width="32" />
        </div>
        <span>Lexio</span>
      </div>

      <nav class="sidebar-nav">
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
      </nav>
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
  background: #2d2a3e;
  color: #e2e0e8;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* ─── Desktop Sidebar ─── */
.sidebar {
  width: 240px;
  flex-shrink: 0;
  padding: 24px 16px;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  background: #2d2a3e;

  display: flex;
  flex-direction: column;
  gap: 6px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 32px;
  padding: 0 8px;
  font-size: 20px;
  font-weight: 700;
  color: #e2e0e8;
}

.logo-bear {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #f5f0e8;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
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
  color: #9c99ab;
  font-size: 14px;
  transition: all 0.2s ease;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
}

.nav-item.active {
  background: rgba(124, 58, 237, 0.15);
  color: #a78bfa;
}

/* ─── Main Content Area ─── */
.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.mobile-nav {
  display: none;
}

.content {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

/* ─── Mobile Navigation ─── */
@media (max-width: 768px) {
  .layout {
    display: flex;
    flex-direction: column;
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
    background: #2d2a3e;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    scrollbar-width: none;
    z-index: 100;
  }

  .mobile-nav::-webkit-scrollbar {
    display: none;
  }

  .mobile-tab {
    border: 0;
    background: rgba(255, 255, 255, 0.06);
    display: flex;
    align-items: center;
    gap: 8px;
    white-space: nowrap;
    padding: 10px 14px;
    border-radius: 999px;
    cursor: pointer;
    color: #9c99ab;
    font-size: 13px;
    transition: all 0.2s ease;
  }

  .mobile-tab:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #e2e0e8;
  }

  .mobile-tab.active {
    background: rgba(124, 58, 237, 0.2);
    color: #a78bfa;
  }

  .content {
    flex: 1;
    overflow: auto;
  }
}
</style>