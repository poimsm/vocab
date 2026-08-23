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
  padding: 80px 20px;
  gap: 16px;
  min-height: 50vh;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(124, 58, 237, 0.2);
  border-top-color: #7c3aed;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.message {
  color: #9c99ab;
  font-size: 14px;
  margin: 0;
}

@media (max-width: 768px) {
  .message {
    font-size: 17px;
  }
}
</style>
