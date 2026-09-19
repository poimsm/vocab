<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { Icon } from '@iconify/vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import UserProfile from '@/components/UserProfile.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const hideLayout = computed(() => route.meta.hideLayout as boolean)
const mobileNavRef = ref<HTMLElement>()

// Scroll to active tab when route changes
watch(() => route.name, async () => {
  await nextTick()
  scrollToActiveTab()
}, { immediate: true })

function scrollToActiveTab() {
  if (!mobileNavRef.value) return

  const activeTab = mobileNavRef.value.querySelector('.mobile-tab.active')
  if (!activeTab) return

  // Calculate scroll position to center the active tab
  const navWidth = mobileNavRef.value.clientWidth
  const tabLeft = (activeTab as HTMLElement).offsetLeft
  const tabWidth = (activeTab as HTMLElement).offsetWidth

  const scrollPosition = tabLeft - (navWidth - tabWidth) / 2

  mobileNavRef.value.scrollTo({
    left: scrollPosition,
    behavior: 'smooth'
  })
}

const sidebarCollapsed = ref(false)
const drawerOpen = ref(false)
const logoutMenuOpen = ref(false)

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

function toggleDrawer() {
  drawerOpen.value = !drawerOpen.value
}

function closeDrawer() {
  drawerOpen.value = false
}

function toggleLogoutMenu() {
  logoutMenuOpen.value = !logoutMenuOpen.value
}

function closeLogoutMenu() {
  logoutMenuOpen.value = false
}

function handleLogout() {
  closeLogoutMenu()
  authStore.logout()
  router.push({ name: 'login' })
}

// Mapeamos los módulos a las propiedades "to" usando el "name" de tus rutas
const modules = [
  { id: 'words', label: 'My Words', icon: 'solar:book-bookmark-linear', to: { name: 'my-words' } },
  { id: 'examples', label: 'Examples', icon: 'solar:chat-round-line-linear', to: { name: 'examples' } },
  { id: 'best-options', label: 'Best Options', icon: 'akar-icons:chat-question', to: { name: 'best-options' } },
  { id: 'randomizer', label: 'Randomizer', icon: 'bi:dice-5', to: { name: 'randomizer' } },
  // { id: 'game-story', label: 'Game Story', icon: 'fluent:game-20-filled', to: { name: 'game-story' } },
  { id: 'quick-write', label: 'Quick Write', icon: 'solar:pen-bold', to: { name: 'quick-write' } },
  { id: 'collocations', label: 'Word Combos', icon: 'boxicons:burger-filled', to: { name: 'collocations' } },
  // { id: 'search', label: 'Search', icon: 'iconamoon:search-light', to: { name: 'home' } },
  // { id: 'explore', label: 'Explore', icon: 'material-symbols-light:explore-outline', to: { name: 'home' } },
  // { id: 'clusters', label: 'Clusters', icon: 'solar:widget-3-linear', to: { name: 'home' } },
  // { id: 'roleplay', label: 'Roleplay', icon: 'solar:users-group-rounded-linear', to: { name: 'home' } },
  // { id: 'monsters', label: 'Monsters', icon: 'solar:ghost-linear', to: { name: 'home' } }
  // { id: 'monsters', label: 'Monsters', icon: 'iconoir:wolf', to: { name: 'home' } }
]
</script>

<template>
  <div class="layout" :class="{ 'sidebar-collapsed': sidebarCollapsed, 'hide-layout': hideLayout }">
    <!-- Desktop Sidebar (Solo visible si el usuario está autenticado y no en hideLayout) -->
    <aside v-if="authStore.isAuthenticated && !hideLayout" class="sidebar">
      <div class="sidebar-top" :class="{ 'sidebar-top-expanded': !sidebarCollapsed }">
        <img src="@/assets/logo.svg" alt="Logo" class="logo" />

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

      <!-- Navegación de Escritorio -->
      <nav class="sidebar-nav">
        <router-link
          v-for="module in modules"
          :key="module.id"
          :to="module.to"
          custom
          v-slot="{ navigate, href }"
        >
          <a
            :href="href"
            @click="navigate"
            class="nav-item"
            :class="{ active: route.name === module.to.name }"
            :title="sidebarCollapsed ? module.label : ''"
          >
            <span class="nav-icon">
              <Icon :icon="module.icon" width="20" />
            </span>
            <span class="nav-label">{{ module.label }}</span>
          </a>
        </router-link>
      </nav>

      <!-- User Info en Escritorio -->
      <div class="sidebar-footer">
        <button
          class="user-footer-btn"
          @click="toggleLogoutMenu"
          :title="sidebarCollapsed ? (authStore.userEmail ?? '') : ''"
        >
          <UserProfile :compact="sidebarCollapsed" />
        </button>

        <!-- Logout Menu Overlay (close on click outside) -->
        <transition name="fade">
          <div v-if="logoutMenuOpen" class="logout-overlay" @click="closeLogoutMenu"></div>
        </transition>

        <!-- Logout Menu Popup -->
        <transition name="fade">
          <div v-if="logoutMenuOpen" class="logout-menu">
            <button class="logout-menu-item" @click="handleLogout">
              <Icon icon="solar:logout-3-linear" width="18" />
              <span>Logout</span>
            </button>
          </div>
        </transition>
      </div>
    </aside>

    <div class="main">
      <!-- Mobile Navigation (Solo visible si el usuario está autenticado y no en hideLayout) -->
      <div v-if="authStore.isAuthenticated && !hideLayout" ref="mobileNavRef" class="mobile-nav">
        <button class="mobile-menu-btn" @click="toggleDrawer">
          <Icon :icon="drawerOpen ? 'solar:close-circle-linear' : 'solar:hamburger-menu-linear'" width="20" />
        </button>
        <router-link
          v-for="module in modules"
          :key="module.id"
          :to="module.to"
          custom
          v-slot="{ navigate, href }"
        >
          <a
            :href="href"
            @click="navigate"
            class="mobile-tab"
            :class="{ active: route.name === module.to.name }"
          >
            <Icon :icon="module.icon" width="18" />
            <span>{{ module.label }}</span>
          </a>
        </router-link>
      </div>

      <!-- Aquí renderizamos de forma dinámica las páginas inyectadas por el Router -->
      <div class="content">
        <router-view />
      </div>

      <!-- Mobile Drawer -->
      <transition name="drawer">
        <div v-if="drawerOpen" class="drawer-overlay" @click="closeDrawer"></div>
      </transition>
      <transition name="slide-in">
        <aside v-if="drawerOpen" class="mobile-drawer">
          <div class="drawer-header">
            <h2>Menu</h2>
            <button class="drawer-close" @click="closeDrawer">
              <Icon icon="solar:close-circle-linear" width="24" />
            </button>
          </div>

          <button class="drawer-user" @click="toggleLogoutMenu">
            <UserProfile class="drawer-profile" />
          </button>

          <nav class="drawer-nav">
            <router-link
              v-for="module in modules"
              :key="module.id"
              :to="module.to"
              custom
              v-slot="{ navigate, href, isActive }"
            >
              <a
                :href="href"
                @click="navigate; closeDrawer()"
                class="drawer-item"
                :class="{ active: route.name === module.to.name }"
              >
                <Icon :icon="module.icon" width="20" />
                <span>{{ module.label }}</span>
              </a>
            </router-link>
          </nav>

          <!-- Logout Menu Popup en Mobile -->
          <transition name="fade">
            <div v-if="logoutMenuOpen" class="logout-menu-mobile">
              <button class="logout-menu-item" @click="handleLogout">
                <Icon icon="solar:logout-3-linear" width="18" />
                <span>Logout</span>
              </button>
            </div>
          </transition>
        </aside>
      </transition>
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

  /* display: flex; */
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
  margin-bottom: 16px;
  padding: 0 4px;
  min-height: 52px;
  gap: 8px;
  width: 98%;
}

/* Hide UserProfile when sidebar collapsed */
.layout.sidebar-collapsed .sidebar-top :deep(.user-profile) {
  opacity: 0;
  transform: scale(0.8);
  pointer-events: none;
  position: absolute;
  transition: opacity 0.15s ease, transform 0.15s ease;
}

/* Desktop UserProfile styling */
.sidebar-top :deep(.user-profile) {
  padding: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
}

.user-profile {
  padding: 12px;
  background: transparent;
  border: 0;
  border-radius: 8px;
}

.sidebar-top :deep(.user-name) {
  font-size: 14px;
  font-weight: 600;
}

.sidebar-top :deep(.user-email) {
  font-size: 12px;
}

/* Collapse toggle button */
.collapse-btn {
  width: 28px;
  height: 28px;
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

/* When collapsed, center the collapse button */
.layout.sidebar-collapsed .sidebar-top {
  justify-content: center;
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

.nav-item, .logout-btn {
  border: 0;
  background: transparent;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  color: #9c99ab;
  font-size: 16px;
  transition: background 0.15s ease, color 0.15s ease;
  white-space: nowrap;
  position: relative;
  text-decoration: none;
}

@media (max-width: 768px) {
  .nav-item, .logout-btn {
    font-size: 15px;
  }
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e0e8;
}

.nav-item.active {
  background: rgba(155, 143, 181, 0.12);
  color: #9b8fb5;
}

.logo {
  height: 28px;
  width: auto;
  max-width: 28px;
  opacity: 0.9;
  flex-shrink: 0;
}

.logo:hover {
  opacity: 1;
}

/* Hide logo when sidebar collapsed */
.layout.sidebar-collapsed .logo {
  max-width: 0;
  opacity: 0;
}

.sidebar-footer {
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  position: relative;
}

.user-footer-btn {
  border: none;
  background: transparent;
  padding: 12px 0px;
  margin: 0;
  cursor: pointer;
  width: 100%;
  border-radius: 0;
  transition: background 0.2s ease;
  text-align: left;
}

.user-footer-btn:hover {
  background: rgba(255, 255, 255, 0.06);
}

/* UserProfile styling in footer */
.sidebar-footer :deep(.user-profile) {
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 0;
  gap: 12px;
}

.sidebar-footer :deep(.user-name) {
  font-size: 14px;
  font-weight: 600;
  text-align: left;
}

.sidebar-footer :deep(.user-email) {
  font-size: 12px;
  text-align: left;
}

/* When collapsed, show only compact version */
.layout.sidebar-collapsed .user-footer-btn {
  padding: 0;
}

.layout.sidebar-collapsed .sidebar-footer :deep(.user-profile) {
  padding: 0;
  background: transparent;
  border: none;
}

.layout.sidebar-collapsed .sidebar-footer :deep(.avatar) {
  width: 36px;
  height: 36px;
}

.logout-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 105;
}

.logout-menu {
  position: absolute;
  bottom: 60px;
  left: 12px;
  right: 12px;
  background: #3d3a52;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  overflow: hidden;
  z-index: 110;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.logout-menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px 16px;
  border: none;
  background: transparent;
  color: #f87171;
  cursor: pointer;
  font-size: 15px;
  transition: all 0.15s ease;
}

.logout-menu-item:hover {
  background: rgba(248, 113, 113, 0.1);
  color: #f87171;
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
.layout.sidebar-collapsed .nav-item,
.layout.sidebar-collapsed .logout-btn {
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

.mobile-user-header {
  display: none;
}

.content {
  flex: 1;
  min-height: 0;
  /* overflow: auto; */
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
    align-items: center;
    gap: 10px;
    overflow-x: auto;
    padding: 8px 12px;
    position: sticky;
    top: 0;
    background: #2d2a3e;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    scrollbar-width: none;
    z-index: 100;
  }

  .mobile-menu-btn {
    border: none;
    background: rgba(255, 255, 255, 0.06);
    color: #9c99ab;
    cursor: pointer;
    width: 36px;
    height: 36px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: all 0.2s ease;
  }

  .mobile-menu-btn:active {
    background: rgba(255, 255, 255, 0.12);
    color: #e2e0e8;
  }

  /* Drawer Overlay */
  .drawer-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 199;
  }

  /* Mobile Drawer */
  .mobile-drawer {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    width: 280px;
    background: #2d2a3e;
    border-right: 1px solid rgba(255, 255, 255, 0.06);
    display: flex;
    flex-direction: column;
    z-index: 200;
    overflow-y: auto;
  }

  .drawer-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  }

  .drawer-header h2 {
    margin: 0;
    font-size: 18px;
    color: #e2e0e8;
  }

  .drawer-close {
    border: none;
    background: transparent;
    color: #9c99ab;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 4px;
    transition: color 0.2s ease;
  }

  .drawer-close:active {
    color: #e2e0e8;
  }

  .drawer-user {
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    background: transparent;
    padding: 16px;
    margin: 0;
    width: 100%;
    cursor: pointer;
    text-align: left;
    transition: background 0.2s ease;
  }

  .drawer-user:hover {
    background: rgba(255, 255, 255, 0.06);
  }

  .drawer-profile :deep(.user-profile) {
    padding: 0;
    background: transparent;
    border: none;
    border-radius: 0;
    gap: 12px;
  }

  .drawer-profile :deep(.avatar) {
    width: 48px;
    height: 48px;
    font-size: 18px;
  }

  .drawer-profile :deep(.user-info) {
    gap: 4px;
  }

  .drawer-profile :deep(.user-name) {
    font-size: 16px;
    font-weight: 600;
    text-align: left;
  }

  .drawer-profile :deep(.user-email) {
    font-size: 13px;
    text-align: left;
  }

  .drawer-nav {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 12px 0;
    flex: 1;
  }

  .drawer-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    color: #9c99ab;
    text-decoration: none;
    transition: all 0.15s ease;
    border-left: 3px solid transparent;
  }

  .drawer-item:active {
    background: rgba(255, 255, 255, 0.06);
    color: #e2e0e8;
  }

  .drawer-item.active {
    background: rgba(155, 143, 181, 0.12);
    color: #9b8fb5;
    border-left-color: #9b8fb5;
  }

  .logout-menu-mobile {
    padding: 12px 0;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    margin-top: auto;
  }

  .logout-menu-mobile .logout-menu-item {
    width: 100%;
    padding-left: 16px;
    padding-right: 16px;
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
    font-size: 15px;
    transition: all 0.2s ease;
    text-decoration: none;
  }

  .mobile-tab:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #e2e0e8;
  }

  .mobile-tab.active {
    background: rgba(155, 143, 181, 0.18);
    color: #9b8fb5;
  }

  .content {
    flex: 1;
    overflow: auto;
  }
}

/* ─── Hide Layout Mode (for full-screen pages like WordDetailPage) ─── */
.layout.hide-layout {
  display: block;
}

.layout.hide-layout .main {
  width: 100%;
  margin: 0;
  padding: 0;
}

.layout.hide-layout .content {
  width: 100%;
  margin: 0;
  padding: 0;
}

/* ─── Drawer Transitions ─── */
.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.25s ease;
}

.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}

.slide-in-enter-active,
.slide-in-leave-active {
  transition: transform 0.25s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

.slide-in-enter-from,
.slide-in-leave-to {
  transform: translateX(-100%);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>