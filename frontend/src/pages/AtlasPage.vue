<script setup lang="ts">
import { ref, computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useActivityTracking } from '@/composables/useActivityTracking'
import { spaceThemes } from '@/data/space'
import type { AtlasItem, AtlasTheme } from '@/types/atlas'

const { trackButtonClick } = useActivityTracking()

// Import themes from data files
const themes: Record<string, AtlasTheme> = {
  ...spaceThemes
  // Future: import castleThemes, hospitalThemes, etc. and merge here
}

// Build themes list from imported data
const themesList = Object.values(themes)

const currentThemeIndex = ref(0)
const currentTheme = computed<AtlasTheme | undefined>(() => themesList[currentThemeIndex.value])

const selectedItem = ref<AtlasItem | null>(null)
const hoveredItemId = ref<string | null>(null)

const canGoPrev = computed(() => currentThemeIndex.value > 0)
const canGoNext = computed(() => currentThemeIndex.value < themesList.length - 1)

function goToPrev() {
  if (canGoPrev.value) {
    currentThemeIndex.value--
    deselectItem()
    trackButtonClick('atlas_nav_prev')
  }
}

function goToNext() {
  if (canGoNext.value) {
    currentThemeIndex.value++
    deselectItem()
    trackButtonClick('atlas_nav_next')
  }
}

function selectItem(item: AtlasItem) {
  selectedItem.value = item
  if (currentTheme.value) {
    trackButtonClick(`atlas_${currentTheme.value.id}_item_${item.id}`)
  }
}

function deselectItem() {
  selectedItem.value = null
}

const containerRef = ref<HTMLDivElement>()
</script>

<template>
  <div class="atlas-page">
    <div class="atlas-main">
      <!-- Navigation Buttons -->
      <button
        class="nav-btn nav-btn-prev"
        @click="goToPrev"
        :disabled="!canGoPrev"
        title="Previous"
      >
        <Icon icon="solar:alt-arrow-left-linear" width="24" />
      </button>

      <button
        class="nav-btn nav-btn-next"
        @click="goToNext"
        :disabled="!canGoNext"
        title="Next"
      >
        <Icon icon="solar:alt-arrow-right-linear" width="24" />
      </button>

      <!-- Image Viewer with Scroll -->
      <div class="atlas-viewer" v-if="currentTheme">
        <!-- Fixed Container for Image + Hotspots -->
        <div class="atlas-container" ref="containerRef">
          <img
            :src="currentTheme.image"
            :alt="currentTheme.title"
            class="atlas-image"
          />

          <!-- Title Overlay -->
          <div class="atlas-title">
            <h1>{{ currentTheme.title }}</h1>
          </div>

          <!-- Interactive Hotspots -->
          <div class="hotspots">
            <button
              v-for="item in currentTheme.items"
              :key="item.id"
              class="hotspot"
              :class="{
                'is-selected': selectedItem?.id === item.id,
                'is-hovered': hoveredItemId === item.id
              }"
              :style="{ left: item.x + '%', top: item.y + '%' }"
              @click="selectItem(item)"
              @mouseenter="hoveredItemId = item.id"
              @mouseleave="hoveredItemId = null"
              :title="item.label"
            >
              <span class="hotspot-dot"></span>
              <span class="hotspot-label">{{ item.label }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Info Panel -->
      <transition name="slide-in-right">
        <div v-if="selectedItem" class="info-panel">
          <div class="panel-header">
            <h2>{{ selectedItem.label }}</h2>
            <button class="close-btn" @click="deselectItem">
              <Icon icon="solar:close-circle-linear" width="24" />
            </button>
          </div>

          <div class="panel-content">
            <div class="section">
              <h3>Definition</h3>
              <p>{{ selectedItem.definition }}</p>
            </div>

            <div class="section">
              <h3>Example</h3>
              <p class="example">{{ selectedItem.example }}</p>
            </div>

            <div class="actions">
              <button class="action-btn">
                <Icon icon="solar:star-linear" width="18" />
                <span>Add to Favorites</span>
              </button>
              <button class="action-btn">
                <Icon icon="solar:book-bookmark-linear" width="18" />
                <span>View More Examples</span>
              </button>
            </div>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<style scoped>
.atlas-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #2d2a3e;
  color: #e2e0e8;
  overflow: hidden;
  position: relative;
}

.nav-btn {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: rgba(45, 42, 62, 0.85);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(155, 143, 181, 0.3);
  color: #9b8fb5;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  z-index: 15;
}

.nav-btn:hover:not(:disabled) {
  background: rgba(155, 143, 181, 0.2);
  border-color: rgba(155, 143, 181, 0.5);
  color: #e2e0e8;
}

.nav-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.nav-btn-prev {
  left: 20px;
}

.nav-btn-next {
  right: 20px;
}

.atlas-main {
  display: flex;
  flex: 1;
  min-width: 0;
  gap: 0;
  overflow: hidden;
  background: #2d2a3e;
  position: relative;
  width: 100%;
}

.atlas-viewer {
  flex: 1;
  position: relative;
  overflow-y: auto;
  overflow-x: hidden;
  min-width: 0;
  width: 100%;
  height: 100%;
}

.atlas-viewer::-webkit-scrollbar {
  /* width: 5px; */
  width: 8px;
}

.atlas-viewer::-webkit-scrollbar-track {
  background: transparent;
}

.atlas-viewer::-webkit-scrollbar-thumb {
  /* border-radius: 3px; */
  /* background: rgba(255, 255, 255, 0.08); */
  background: #9f9f9f;
  border-radius: 3px;
}

.atlas-container {
  width: 100%;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  box-sizing: border-box;
  min-height: 100vh;
}

.atlas-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  user-select: none;
  z-index: 1;
}

.atlas-title {
  position: absolute;
  top: 20px;
  left: 20px;
  z-index: 5;
  background: rgba(45, 42, 62, 0.85);
  backdrop-filter: blur(8px);
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid rgba(155, 143, 181, 0.2);
}

.atlas-title h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #e2e0e8;
  white-space: nowrap;
}

.hotspots {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  padding: 20px;
  box-sizing: border-box;
  z-index: 2;
}

.hotspot {
  position: absolute;
  transform: translate(-50%, -50%);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  transition: all 0.2s ease;
}

.hotspot-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: rgba(155, 143, 181, 0.3);
  border: 2px solid #9b8fb5;
  transition: all 0.2s ease;
  box-shadow: 0 0 8px rgba(155, 143, 181, 0.2);
}

.hotspot-label {
  position: absolute;
  background: #3d3a52;
  color: #e2e0e8;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 13px;
  white-space: nowrap;
  border: 1px solid rgba(255, 255, 255, 0.1);
  opacity: 0;
  pointer-events: none;
  transform: translateY(-10px);
  transition: all 0.2s ease;
  bottom: 100%;
  margin-bottom: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.hotspot:hover .hotspot-dot {
  background: rgba(155, 143, 181, 0.5);
  width: 16px;
  height: 16px;
  box-shadow: 0 0 16px rgba(155, 143, 181, 0.4);
}

.hotspot:hover .hotspot-label {
  opacity: 1;
  transform: translateY(0);
}

.hotspot.is-hovered .hotspot-dot {
  background: rgba(155, 143, 181, 0.7);
  width: 18px;
  height: 18px;
  box-shadow: 0 0 20px rgba(155, 143, 181, 0.5);
}

.hotspot.is-selected .hotspot-dot {
  background: #9b8fb5;
  width: 20px;
  height: 20px;
  box-shadow: 0 0 24px rgba(155, 143, 181, 0.6);
}

.info-panel {
  width: 340px;
  flex-shrink: 0;
  background: #3d3a52;
  border-left: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  z-index: 25;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  gap: 12px;
  flex-shrink: 0;
}

.panel-header h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: #e2e0e8;
}

.close-btn {
  background: transparent;
  border: none;
  color: #9c99ab;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s ease;
  flex-shrink: 0;
}

.close-btn:hover {
  color: #e2e0e8;
}

.panel-content {
  padding: 20px;
  flex: 1;
  overflow-y: auto;
}

.panel-content::-webkit-scrollbar {
  width: 5px;
}

.panel-content::-webkit-scrollbar-track {
  background: transparent;
}

.panel-content::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
}

.section {
  margin-bottom: 20px;
}

.section h3 {
  margin: 0 0 8px 0;
  font-size: 13px;
  font-weight: 600;
  color: #9b8fb5;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.section p {
  margin: 0;
  font-size: 16px;
  line-height: 1.6;
  color: #c9c7d4;
}

.example {
  font-style: italic;
  color: #9c99ab;
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: rgba(155, 143, 181, 0.12);
  border: 1px solid rgba(155, 143, 181, 0.2);
  border-radius: 8px;
  color: #9b8fb5;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.action-btn:hover {
  background: rgba(155, 143, 181, 0.2);
  border-color: rgba(155, 143, 181, 0.4);
  color: #e2e0e8;
}

.slide-in-right-enter-active,
.slide-in-right-leave-active {
  transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

.slide-in-right-enter-from,
.slide-in-right-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

.slide-in-right-enter-to,
.slide-in-right-leave-from {
  transform: translateX(0);
  opacity: 1;
}

/* Mobile Responsive */
@media (max-width: 768px) {
  .atlas-viewer {
    flex: 1;
  }

  .info-panel {
    position: fixed;
    inset: 0;
    width: 100%;
    height: 100%;
    z-index: 50;
    border-left: none;
  }

  .atlas-container {
    min-height: auto;
  }

  .hotspot-label {
    font-size: 12px;
    padding: 4px 8px;
  }

  .panel-content {
    padding: 16px;
  }

  .panel-header {
    padding: 16px;
  }
}
</style>
