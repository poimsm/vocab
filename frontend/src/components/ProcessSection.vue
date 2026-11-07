<script setup lang="ts">
import { Icon } from '@iconify/vue';
</script>

<template>
  <div class="process-section">
    <!-- Step 1 -->
    <div class="process-step step-1">
      <div class="step-number">1</div>
      <h3 class="step-title">Add words you find</h3>
      <p class="step-subtitle">Type any word you encounter in your daily life.</p>

      <div class="step-content">
        <div class="input-demo">
          <input type="text" value="serendipity" disabled class="demo-input" />
          <button class="demo-btn">+</button>
        </div>
        <div class="tags-demo">
          <span class="tag">books</span>
          <span class="tag">movies</span>
          <span class="tag">podcasts</span>
          <span class="tag">conversations</span>
          <span class="tag">websites</span>
          <span class="tag">etc.</span>
        </div>
      </div>
    </div>

    <div class="process-arrow-horizontal">→</div>

    <!-- Step 2 -->
    <div class="process-step step-2">
      <div class="step-number">2</div>
      <h3 class="step-title">We create content for you</h3>
      <p class="step-subtitle">Get example sentences, real-life contexts and more, all generated from your word.</p>

      <div class="step-content content-examples">
        <div class="example-item">
          <Icon icon="mdi:chat-outline" width="18" height="18" class="example-icon" />
          <span class="example-text">It was a moment of pure <span class="highlight">serendipity.</span></span>
          <Icon icon="mdi:volume-high" width="18" height="18" class="example-sound" />
        </div>
      </div>
    </div>

    <div class="process-arrow-horizontal">→</div>

    <!-- Step 3 -->
    <div class="process-step step-3">
      <div class="step-number">3</div>
      <h3 class="step-title">Explore and enjoy</h3>
      <p class="step-subtitle">Come back anytime to explore your words in a simple and relaxing way.</p>

      <div class="step-content content-menu">
        <div class="menu-item">
          <Icon icon="mdi:puzzle" width="18" height="18" />
          <span>Word clustering</span>
          <Icon icon="mdi:chevron-right" width="18" height="18" class="chevron" />
        </div>
        <div class="menu-item">
          <Icon icon="mdi:theater-masks" width="18" height="18" />
          <span>Role-play scenarios</span>
          <Icon icon="mdi:chevron-right" width="18" height="18" class="chevron" />
        </div>
        <div class="menu-item">
          <Icon icon="mdi:lightbulb-question" width="18" height="18" />
          <span>Tricky questions</span>
          <Icon icon="mdi:chevron-right" width="18" height="18" class="chevron" />
        </div>
        <div class="menu-item">
          <Icon icon="mdi:link" width="18" height="18" />
          <span>Collocations & combos</span>
          <Icon icon="mdi:chevron-right" width="18" height="18" class="chevron" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@400;500;600;700&family=Nunito:wght@300;400;500;600;700&display=swap');

.process-section {
  width: 100%;
  margin-top: 50px;
  padding-top: 50px;
  border-top: 1px solid rgba(196, 181, 253, 0.15);
  display: flex;
  align-items: stretch;
  gap: 20px;
  justify-content: center;
}

.process-step {
  flex: 0 0 calc(33.333% - 14px);
  min-height: 520px;
  padding: 32px 28px;
  background: rgba(124, 58, 237, 0.03);
  border: 1px solid rgba(196, 181, 253, 0.15);
  border-radius: 18px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.step-number {
  width: 56px;
  height: 56px;
  background: linear-gradient(135deg, #7c3aed 0%, #5b21b6 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Fredoka', sans-serif;
  font-weight: 700;
  font-size: 26px;
  color: #ffffff;
  margin: 0 auto;
}

.step-title {
  margin: 0;
  font-family: 'Fredoka', sans-serif;
  font-weight: 700;
  font-size: 22px;
  color: #f0ecff;
  text-align: center;
}

.step-subtitle {
  margin: 0;
  font-family: 'Nunito', sans-serif;
  font-weight: 400;
  font-size: 14px;
  color: #a5a0b8;
  text-align: center;
  line-height: 1.5;
  min-height: 42px;
}

.step-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
}

/* Step 1 */
.input-demo {
  display: flex;
  gap: 10px;
}

.demo-input {
  flex: 1;
  padding: 12px 16px;
  background: rgba(124, 58, 237, 0.08);
  border: 1.5px solid rgba(196, 181, 253, 0.25);
  border-radius: 10px;
  font-family: 'Nunito', sans-serif;
  font-size: 14px;
  color: #c4b5fd;
  cursor: not-allowed;
  font-weight: 500;
}

.demo-btn {
  width: 42px;
  height: 42px;
  background: linear-gradient(135deg, #7c3aed 0%, #5b21b6 100%);
  border: none;
  border-radius: 10px;
  color: #ffffff;
  font-weight: 700;
  font-size: 20px;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.demo-btn:hover {
  transform: scale(1.08);
}

.tags-demo {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.tag {
  padding: 8px 14px;
  background: rgba(196, 181, 253, 0.1);
  border: 1px solid rgba(196, 181, 253, 0.25);
  border-radius: 8px;
  font-family: 'Nunito', sans-serif;
  font-size: 12px;
  color: #a5a0b8;
  font-weight: 500;
}

/* Step 2 */
.content-examples {
  gap: 18px;
  justify-content: center;
}

.example-item {
  padding: 16px;
  background: rgba(124, 58, 237, 0.06);
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: 'Nunito', sans-serif;
  font-size: 14px;
  color: #a5a0b8;
  line-height: 1.5;
  text-align: center;
  justify-content: center;
  min-height: 64px;
}

.example-icon {
  color: #a5a0b8;
  flex-shrink: 0;
}

.example-sound {
  color: #a5a0b8;
  flex-shrink: 0;
}

.highlight {
  color: #c4b5fd;
  font-weight: 700;
}

.content-cards {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
}

.content-card {
  padding: 16px 12px;
  background: rgba(124, 58, 237, 0.06);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  font-family: 'Nunito', sans-serif;
  font-size: 12px;
  color: #a5a0b8;
  text-align: center;
}

.content-label {
  display: block;
  line-height: 1.3;
}

/* Step 3 */
.content-menu {
  gap: 12px;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: rgba(124, 58, 237, 0.06);
  border-radius: 10px;
  font-family: 'Nunito', sans-serif;
  font-size: 14px;
  color: #a5a0b8;
  cursor: pointer;
  transition: all 0.2s ease;
}

.menu-item:hover {
  background: rgba(124, 58, 237, 0.12);
  color: #c4b5fd;
}

.menu-item span {
  flex: 1;
  text-align: left;
  font-weight: 500;
}

.chevron {
  flex-shrink: 0;
  opacity: 0.5;
}

.process-arrow-horizontal {
  align-self: center;
  font-size: 22px;
  color: #8b7f9f;
  opacity: 0.6;
  margin-top: 40px;
}

/* Responsive */
@media (max-width: 768px) {
  .process-section {
    margin-top: 40px;
    padding-top: 40px;
    flex-direction: column;
    gap: 20px;
  }

  .process-step {
    flex: 0 0 100%;
    max-width: 100%;
    min-height: auto;
    padding: 32px 24px;
    gap: 20px;
  }

  .step-number {
    width: 50px;
    height: 50px;
    font-size: 24px;
  }

  .step-title {
    font-size: 18px;
  }

  .step-subtitle {
    font-size: 13px;
    min-height: auto;
  }

  .demo-input {
    font-size: 13px;
    padding: 11px 14px;
  }

  .demo-btn {
    width: 38px;
    height: 38px;
    font-size: 18px;
  }

  .tag {
    font-size: 11px;
    padding: 7px 12px;
  }

  .example-item {
    font-size: 13px;
    padding: 14px;
    min-height: auto;
  }

  .menu-item {
    font-size: 13px;
    padding: 12px 14px;
  }

  .content-card {
    font-size: 11px;
    padding: 14px 10px;
  }

  .process-arrow-horizontal {
    display: none;
  }
}
</style>