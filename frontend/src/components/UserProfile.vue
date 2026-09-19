<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

interface Props {
  compact?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  compact: false
})

const authStore = useAuthStore()

const userInitials = computed(() => {
  if (!authStore.userEmail) return '?'
  return authStore.userEmail
    .split('@')[0]
    .substring(0, 2)
    .toUpperCase()
})

const displayEmail = computed(() => {
  if (!authStore.userEmail) return 'User'
  return authStore.userEmail.split('@')[0]
})
</script>

<template>
  <div class="user-profile" :class="{ compact }" :title="compact ? authStore.userEmail : ''">
    <div class="avatar" :title="compact ? authStore.userEmail : ''">
      {{ userInitials }}
    </div>
    <div v-if="!compact" class="user-info">
      <div class="user-name">{{ displayEmail }}</div>
      <div class="user-email">{{ authStore.userEmail }}</div>
    </div>
  </div>
</template>

<style scoped>
.user-profile {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  flex: 1;
  min-width: 0;
}

.user-profile.compact {
  padding: 0;
  gap: 0;
  background: transparent;
  border: none;
  justify-content: flex-start;
  cursor: pointer;
}

.user-profile.compact:hover .avatar {
  transform: scale(1.08);
  box-shadow: 0 0 8px rgba(155, 143, 181, 0.4);
}

.avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: linear-gradient(135deg, #9b8fb5 0%, #7c6fa8 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #f5f0e8;
  font-weight: 600;
  font-size: 14px;
  flex-shrink: 0;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.user-profile.compact .avatar {
  width: 36px;
  height: 36px;
  font-size: 13px;
}

.user-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.user-name {
  color: #e2e0e8;
  font-size: 13px;
  font-weight: 600;
  text-transform: capitalize;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-email {
  color: #9c99ab;
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.2;
}

/* Mobile version - compact */
@media (max-width: 768px) {
  .user-profile {
    padding: 8px;
    gap: 8px;
  }

  .avatar {
    width: 36px;
    height: 36px;
    font-size: 13px;
  }

  .user-name {
    font-size: 13px;
  }

  .user-email {
    font-size: 11px;
  }
}
</style>
