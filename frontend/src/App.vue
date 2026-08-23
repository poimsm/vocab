<script setup lang="ts">
import { useNavigationStore } from '@/stores/navigation'
import MainLayout from './layouts/MainLayout.vue'

const nav = useNavigationStore()
</script>

<template>
  <MainLayout />
</template>

<style>
.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  color: #9c99ab;
  font-size: 18px;
}

@media (max-width: 768px) {
  .placeholder {
    font-size: 21px;
  }
}
</style>