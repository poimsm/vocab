<script setup lang="ts">
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

// ─── Local State ───
const userWordSlots = ref(25) // Mock: word slots actuales
const userCredits = ref(100) // Mock: créditos del usuario

// ─── Product Categories ───
const categories = ref([
  { id: 'storage', label: 'Storage', emoji: '📦' },
  { id: 'credits', label: 'Credits', emoji: '⚡' },
  { id: 'content', label: 'Content', emoji: '🎮' }
])
const activeCategory = ref('storage')

// ─── Product Data ───
const products = ref({
  storage: [
    { id: 's1', slots: '50', price: '$2.99', image_url: '/e01_no_bg.png', popular: false },
    { id: 's2', slots: '200', price: '$7.99', image_url: '/e02_no_bg.png', popular: true },
    { id: 's3', slots: '500', price: '$16.99', image_url: '/e03_no_bg.png', popular: false },
    { id: 's4', slots: '1000', price: '$29.99', image_url: '/e04_no_bg.png', popular: false }
  ],
  credits: [
    { id: 'c1', amount: '100', price: '$0.99', image_url: '/diamons01.png', popular: false },
    { id: 'c2', amount: '500', price: '$3.49', image_url: '/diamons01.png', popular: true },
    { id: 'c3', amount: '1500', price: '$8.99', image_url: '/diamons01.png', popular: false },
    { id: 'c4', amount: 'Unlimited', price: '$9.99/mo', image_url: '/diamons01.png', popular: false }
  ],
  content: [
    { id: 'ct1', name: 'Business', price: '$7.99', emoji: '💼', popular: false },
    { id: 'ct2', name: 'Travel', price: '$7.99', emoji: '✈️', popular: true },
    { id: 'ct3', name: 'Academic', price: '$9.99', emoji: '🎓', popular: false },
    { id: 'ct4', name: 'Movies', price: '$6.99', emoji: '🎬', popular: false }
  ]
})

// ─── Methods ───
function buyProduct(product: any) {
  console.log(`✅ Purchased:`, product)
}
</script>

<template>
  <div class="store-container">
    <!-- Header -->
    <div class="store-header">
      <div class="header-title">
        <span class="logo-w">W</span>
        <h1>WORDWIZ STORE</h1>
      </div>
      <div class="header-stats">
        <div class="stat">
          <span class="stat-label">SLOTS</span>
          <span class="stat-value">{{ userWordSlots }}/100</span>
        </div>
        <div class="stat">
          <span class="stat-label">CREDITS</span>
          <span class="stat-value">{{ userCredits }}</span>
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button
        v-for="cat in categories"
        :key="cat.id"
        @click="activeCategory = cat.id"
        class="tab"
        :class="{ active: activeCategory === cat.id }"
      >
        <span class="tab-emoji">{{ cat.emoji }}</span>
        <span class="tab-label">{{ cat.label }}</span>
      </button>
    </div>

    <!-- Products Grid -->
    <div class="products-grid">
      <!-- Storage Section -->
      <template v-if="activeCategory === 'storage'">
        <div
          v-for="product in products.storage"
          :key="product.id"
          class="product-card"
          :class="{ popular: product.popular }"
        >
          <div v-if="product.popular" class="badge">⭐ POPULAR</div>
          <div class="product-image-box">
            <img :src="product.image_url" alt="Storage" class="product-image" />
          </div>
          <div class="product-label">{{ product.slots }} SLOTS</div>
          <div class="product-price">{{ product.price }}</div>
          <button class="btn-buy" @click="buyProduct(product)">BUY NOW</button>
        </div>
      </template>

      <!-- Credits Section -->
      <template v-if="activeCategory === 'credits'">
        <div
          v-for="product in products.credits"
          :key="product.id"
          class="product-card credits-card"
          :class="{ popular: product.popular }"
        >
          <div v-if="product.popular" class="badge">⭐ POPULAR</div>
          <div class="product-image-box">
            <img :src="product.image_url" alt="Credits" class="product-image" />
          </div>
          <div class="product-label">{{ product.amount }}</div>
          <div class="product-label-small">CREDITS</div>
          <div class="product-price">{{ product.price }}</div>
          <button class="btn-buy" @click="buyProduct(product)">BUY NOW</button>
        </div>
      </template>

      <!-- Content Section -->
      <template v-if="activeCategory === 'content'">
        <div
          v-for="product in products.content"
          :key="product.id"
          class="product-card content-card"
          :class="{ popular: product.popular }"
        >
          <div v-if="product.popular" class="badge">⭐ POPULAR</div>
          <div class="product-image-box">
            <div class="product-emoji">{{ product.emoji }}</div>
          </div>
          <div class="product-label">{{ product.name }}</div>
          <div class="product-price">{{ product.price }}</div>
          <button class="btn-buy" @click="buyProduct(product)">BUY NOW</button>
        </div>
      </template>
    </div>

    <!-- Bottom Message -->
    <div class="bottom-message">
      <p>✨ Unlock the next tier!</p>
    </div>
  </div>
</template>

<style scoped>
.store-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #2d2a3e 0%, #3d3a52 100%);
  padding: 16px;
  display: flex;
  flex-direction: column;
  color: #e2e0e8;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* ─── Header ─── */
.store-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  gap: 16px;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logo-w {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  border-radius: 8px;
  font-weight: 700;
  font-size: 20px;
  color: white;
}

.header-title h1 {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 2px;
  margin: 0;
  color: #ffffff;
}

.header-stats {
  display: flex;
  gap: 8px;
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(155, 143, 181, 0.2);
  border-radius: 8px;
  gap: 2px;
}

.stat-label {
  font-size: 10px;
  font-weight: 600;
  color: #9c99ab;
  letter-spacing: 1px;
}

.stat-value {
  font-size: 14px;
  font-weight: 700;
  color: #ffffff;
}

/* ─── Tabs ─── */
.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  overflow-x: auto;
  padding-bottom: 8px;
}

.tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  color: #9c99ab;
  cursor: pointer;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.2s ease;
}

.tab:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(155, 143, 181, 0.3);
}

.tab.active {
  background: linear-gradient(135deg, #7c3aed, #ec4899);
  border-color: transparent;
  color: white;
}

.tab-emoji {
  font-size: 16px;
}

.tab-label {
  letter-spacing: 0.5px;
}

/* ─── Products Grid ─── */
.products-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 24px;
  flex: 1;
}

@media (max-width: 1200px) {
  .products-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 768px) {
  .products-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 480px) {
  .products-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* ─── Product Card ─── */
.product-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: 2px;
  padding: 8px 6px;
  background: rgba(61, 58, 82, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  text-align: center;
  aspect-ratio: 1;
  overflow: hidden;
}

.product-card:hover {
  border-color: rgba(155, 143, 181, 0.3);
  background: rgba(61, 58, 82, 0.9);
  transform: translateY(-3px);
}

.product-card.popular {
  border: 2px solid rgba(245, 158, 11, 0.3);
  background: rgba(245, 158, 11, 0.08);
}

.product-card.popular:hover {
  border-color: rgba(245, 158, 11, 0.6);
  background: rgba(245, 158, 11, 0.12);
}

.badge {
  position: absolute;
  top: 6px;
  right: 6px;
  font-size: 10px;
  font-weight: 700;
  padding: 3px 6px;
  background: rgba(245, 158, 11, 0.2);
  color: #f59e0b;
  border-radius: 4px;
  letter-spacing: 0.5px;
}

.product-image-box {
  /* width: 150px; */
  height: 120px;
  /* background: rgba(255, 255, 255, 0.06); */
  /* border: 2px dashed rgba(155, 143, 181, 0.3); */
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s ease;
  margin-top: 14px;
}

.product-card:hover .product-image-box {
  /* border-color: rgba(155, 143, 181, 0.5); */
  /* background: rgba(255, 255, 255, 0.08); */
}

.product-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  padding: 4px;
}

.product-emoji {
  font-size: 40px;
  line-height: 1;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.product-label {
  font-size: 14px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 0.5px;
  flex-shrink: 0;
  line-height: 1.2;
}

.product-label-small {
  font-size: 8px;
  font-weight: 600;
  color: #9c99ab;
  letter-spacing: 0.5px;
  flex-shrink: 0;
  line-height: 1;
}

.product-price {
  font-size: 13px;
  font-weight: 700;
  color: #9b8fb5;
  flex-shrink: 0;
  line-height: 1.2;
}

.btn-buy {
  margin-top: auto;
  padding: 6px 8px;
  width: calc(100% - 4px);
  background: linear-gradient(135deg, #7c3aed, #ec4899);
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.btn-buy:active {
  transform: scale(0.95);
}

.btn-buy:hover {
  box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);
}

/* ─── Bottom Message ─── */
.bottom-message {
  text-align: center;
  padding: 16px;
  font-size: 13px;
  color: #9b8fb5;
  font-weight: 500;
}

/* ─── Mobile ─── */
@media (max-width: 480px) {
  .store-container {
    padding: 12px;
  }

  .header-title h1 {
    font-size: 14px;
  }

  .tabs {
    gap: 6px;
  }

  .tab {
    padding: 6px 12px;
    font-size: 12px;
  }
}
</style>
