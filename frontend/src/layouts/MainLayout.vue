<script setup lang="ts">
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
import { useNavigationStore } from '@/stores/navigation'

const nav = useNavigationStore()
const sidebarCollapsed = ref(false)

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

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
  <div class="layout" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <!-- Desktop Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-top" :class="{ 'sidebar-top-expanded': !sidebarCollapsed }">
        <div class="logo">
          <div class="logo-bear">
            <Icon icon="fluent-emoji:bear" width="28" />
          </div>
          <span class="logo-text">Lexio</span>
        </div>

        <button
          class="collapse-btn"
          @click="toggleSidebar"
          :title="sidebarCollapsed ? 'Expand' : 'Collapse'"
        >
          <Icon
            :icon="sidebarCollapsed ? 'solar:alt-arrow-right-linear' : 'solar:alt-arrow-left-linear'"
            width="16"
          />
        </button>
      </div>

      <nav class="sidebar-nav">
        <button
          v-for="module in modules"
          :key="module.id"
          class="nav-item"
          :class="{ active: nav.activeModule === module.id }"
          @click="nav.setActiveModule(module.id)"
          :title="sidebarCollapsed ? module.label : ''"
        >
          <span class="nav-icon">
            <Icon :icon="module.icon" width="20" />
          </span>
          <span class="nav-label">{{ module.label }}</span>
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
/* ─── CSS Variables for sidebar widths ─── */
:root {
  --sidebar-width: 220px;
  --sidebar-collapsed: 56px;
}

.sidebar-top-expanded {
  width: 15vw;
}

.layout {
  display: flex;
  min-height: 100vh;
  background: #2d2a3e;
  color: #e2e0e8;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* ─── Desktop Sidebar ─── */
.sidebar {
  width: var(--sidebar-width);
  flex-shrink: 0;
  padding: 16px 12px;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  background: #2d2a3e;

  display: flex;
  flex-direction: column;
  gap: 4px;

  /* GPU-accelerated transition */
  transition: width 0.25s cubic-bezier(0.25, 0.46, 0.45, 0.94);
  will-change: width;
}

/* Collapsed: much narrower */
.layout.sidebar-collapsed .sidebar {
  width: var(--sidebar-collapsed);
  padding: 16px 8px;
}

.sidebar-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  padding: 0 4px;
  min-height: 36px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 700;
  color: #e2e0e8;
  overflow: hidden;
}

.logo-bear {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #f5f0e8;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
}

.logo-text {
  opacity: 1;
  transform: translateX(0);
  transition: opacity 0.15s ease, transform 0.15s ease;
}

/* Hide logo text when collapsed */
.layout.sidebar-collapsed .logo-text {
  opacity: 0;
  transform: translateX(-8px);
  pointer-events: none;
  position: absolute;
}

/* Collapse toggle button */
.collapse-btn {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  border: none;
  background: rgba(255, 255, 255, 0.06);
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
  margin-left: auto;
}

.collapse-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #e2e0e8;
}

/* When collapsed, center the collapse button under the logo */
.layout.sidebar-collapsed .sidebar-top {
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 0;
}

.layout.sidebar-collapsed .collapse-btn {
  margin-left: 0;
  transform: rotate(180deg);
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  border: 0;
  background: transparent;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  color: #9c99ab;
  font-size: 14px;
  transition: background 0.15s ease, color 0.15s ease;
  white-space: nowrap;
  position: relative;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
}

.nav-item.active {
  background: rgba(124, 58, 237, 0.15);
  color: #a78bfa;
}

.nav-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 20px;
}

.nav-label {
  opacity: 1;
  transform: translateX(0);
  transition: opacity 0.12s ease, transform 0.12s ease;
}

/* Hide nav labels when collapsed — faster, simpler transition */
.layout.sidebar-collapsed .nav-label {
  opacity: 0;
  transform: translateX(-4px);
  pointer-events: none;
  position: absolute;
  left: 48px;
}

/* Center icons when collapsed */
.layout.sidebar-collapsed .nav-item {
  justify-content: center;
  padding: 10px 0;
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