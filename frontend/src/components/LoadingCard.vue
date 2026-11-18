<script setup lang="ts">
defineProps<{
  message?: string
}>()
</script>

<template>
  <div class="loading-card">
    <div class="spinner"></div>
    <p class="message">{{ message || 'Generating...' }}</p>
  </div>
</template>

<style scoped>
.loading-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  padding: 80px 20px;
  gap: 16px;
  min-height: 50vh;
}

.spinner {
  width: 48px;
  height: 48px;
  border: 2.5px solid rgba(255, 255, 255, 0.12);
  border-top-color: rgba(255, 255, 255, 0.5);
  border-right-color: rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.message {
  color: #b8b5c8;
  font-size: 14px;
  margin: 0;
  letter-spacing: 0.5px;
}

@media (max-width: 768px) {
  .message {
    font-size: 17px;
  }
}
</style>
