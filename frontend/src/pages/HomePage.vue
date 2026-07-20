<script setup lang="ts">
import { Icon } from '@iconify/vue';
</script>

<template>
  <div class="lexio-desktop">
    <!-- Top Navigation Bar -->
    <nav class="top-nav">
      <div class="nav-left">
        <div class="logo">
          <div class="logo-icon">
            <Icon icon="fluent-emoji:bear" width="28" height="28" />
          </div>
          <span class="logo-text">LEXIO</span>
        </div>
      </div>
      <div class="nav-right">
        <div class="nav-links">
          <a href="#" class="nav-link">
            <Icon icon="mdi:account" width="16" height="16" />
            ProfileX
          </a>
          <a href="#" class="nav-link">
            <Icon icon="mdi:cog" width="16" height="16" />
            Settings
          </a>
        </div>
        <div class="search-box">
          <Icon icon="mdi:magnify" width="16" height="16" class="search-icon" />
          <span>Search</span>
        </div>
      </div>
    </nav>

    <!-- Main Content Area -->
    <main class="main-content">
      <!-- Left Panel -->
      <div class="left-panel">
        <h1 class="title">
          <span class="line">BRING YOUR</span>
          <span class="line">FICTION TO LIFE</span>
        </h1>
        <p class="subtitle">
          Capture interesting words from your<br />
          favorite stories and watch them play.
        </p>

        <div class="actions">
          <button class="btn-primary">
            <span>CREATE ACCOUNT - START CAPTURING</span>
          </button>
          <a href="/login" class="btn-text">LOG IN</a>
        </div>
      </div>

      <!-- Right Panel - Book Illustration -->
      <div class="right-panel">
        <div class="book-scene">
          <img src="/book_desktop.png" alt="Magic Book" class="book-image" />
        </div>
      </div>
    </main>

    <!-- Bottom Feature Bar -->
    <div class="bottom-bar">
      <div class="feature-item">
        <span class="feature-text">Discover the words that matter</span>
      </div>
      <div class="feature-item">
        <span class="feature-text">Analyze Character Vocabulary</span>
      </div>
      <div class="feature-item">
        <span class="feature-text">Build Your Own Fiction Codex</span>
      </div>
    </div>
  </div>
</template>



<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@400;500;600;700&family=Nunito:wght@300;400;500;600;700&display=swap');

.lexio-desktop {
  min-height: 100vh;
  width: 100%;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  padding: 0;
  box-sizing: border-box;
}

/* Top Navigation */
.top-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 40px;
  z-index: 10;
  position: relative;
}

.nav-left {
  display: flex;
  align-items: center;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-icon {
  width: 36px;
  height: 36px;
  background: #f5e6d3;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.logo-text {
  font-family: 'Fredoka', sans-serif;
  font-weight: 700;
  font-size: 20px;
  color: #e8e4f0;
  letter-spacing: 2px;
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 24px;
}

.nav-links {
  display: flex;
  gap: 20px;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #a5a0b8;
  font-family: 'Nunito', sans-serif;
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  transition: color 0.2s ease;
}

.nav-link:hover {
  color: #c4b5fd;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 8px 16px;
  color: #6b7280;
  font-family: 'Nunito', sans-serif;
  font-size: 13px;
  cursor: text;
}

.search-icon {
  color: #6b7280;
}

/* Main Content */
.main-content {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 60px 40px;
  gap: 60px;
  z-index: 1;
  position: relative;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

/* Left Panel */
.left-panel {
  flex: 0 0 42%;
  max-width: 520px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.title {
  margin: 0;
  font-family: 'Fredoka', sans-serif;
  font-weight: 700;
}

.title .line {
  display: block;
  font-size: clamp(36px, 4.5vw, 56px);
  line-height: 1.05;
  color: #c4b5fd;
}

.subtitle {
  font-family: 'Nunito', sans-serif;
  font-weight: 400;
  font-size: clamp(15px, 1.5vw, 18px);
  line-height: 1.6;
  color: #a5a0b8;
  margin: 0;
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 16px;
  align-items: flex-start;
  margin-top: 8px;
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 28px;
  background: linear-gradient(135deg, #7c3aed 0%, #5b21b6 50%, #4c1d95 100%);
  border: none;
  border-radius: 12px;
  color: #ffffff;
  font-family: 'Nunito', sans-serif;
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 0.5px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.btn-primary:hover {
  transform: translateY(-2px);
}

.btn-text {
  color: #a5a0b8;
  font-family: 'Nunito', sans-serif;
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
  letter-spacing: 1px;
  transition: color 0.2s ease;
  padding: 4px 0;
}

.btn-text:hover {
  color: #c4b5fd;
}

/* Right Panel - Book */
.right-panel {
  flex: 0 0 55%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.book-scene {
  position: relative;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.book-image {
  width: 100%;
  max-width: 520px;
  height: auto;
  position: relative;
}

/* Bottom Feature Bar */
.bottom-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 20px 40px 32px;
  z-index: 1;
  position: relative;
  flex-wrap: wrap;
}

.feature-item {
  padding: 12px 24px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
}

.feature-text {
  font-family: 'Nunito', sans-serif;
  font-size: 13px;
  font-weight: 500;
  color: #8b8799;
  white-space: nowrap;
}

/* Responsive */
@media (max-width: 1000px) {
  .main-content {
    flex-direction: column;
    padding: 30px 40px;
    gap: 40px;
  }

  .left-panel {
    flex: none;
    max-width: 100%;
    text-align: center;
    align-items: center;
  }

  .actions {
    align-items: center;
  }

  .right-panel {
    flex: none;
    width: 100%;
  }

  .book-image {
    max-width: 400px;
  }
}

@media (max-width: 768px) {
  .top-nav {
    padding: 16px 20px;
  }

  .nav-right {
    gap: 12px;
  }

  .nav-links {
    display: none;
  }

  .main-content {
    padding: 20px 24px;
  }

  .title .line {
    font-size: 32px;
  }

  .book-image {
    max-width: 320px;
  }

  .bottom-bar {
    padding: 16px 20px 24px;
    gap: 10px;
  }

  .feature-item {
    padding: 10px 16px;
  }

  .feature-text {
    font-size: 12px;
  }
}

@media (max-width: 480px) {
  .title .line {
    font-size: 28px;
  }

  .subtitle {
    font-size: 14px;
  }

  .btn-primary {
    font-size: 13px;
    padding: 12px 20px;
  }

  .book-image {
    max-width: 280px;
  }
}
</style>