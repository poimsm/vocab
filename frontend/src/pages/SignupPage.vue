<script setup lang="ts">
import { ref } from 'vue';
import { Icon } from '@iconify/vue';
import { useAuthStore } from '@/stores/auth';
import { useRouter } from 'vue-router';

const authStore = useAuthStore();
const router = useRouter();

const email = ref('');
const password = ref('');
const confirmPassword = ref('');
const isLoading = ref(false);
const errorMessage = ref('');
const successMessage = ref('');

async function handleRegister() {
  isLoading.value = true;
  errorMessage.value = '';
  successMessage.value = '';

  if (password.value.length < 6) {
    errorMessage.value = 'Password needs at least 6 characters 🙂';
    isLoading.value = false;
    return;
  }

  if (password.value !== confirmPassword.value) {
    errorMessage.value = "Passwords don't match. Try again.";
    isLoading.value = false;
    return;
  }

  try {
    await authStore.register({
      email: email.value,
      password: password.value,
    });
    successMessage.value = "Nice, you're in! Logging you in...";

    setTimeout(async () => {
      try {
        await authStore.login({
          email: email.value,
          password: password.value,
        });
        router.push({ name: 'my-words' });
      } catch (error: any) {
        errorMessage.value = 'Account created, but login failed. Try signing in manually.';
      }
    }, 1500);
  } catch (error: any) {
    errorMessage.value = error.response?.data?.detail || "Couldn't create your account. Mind trying again?";
  } finally {
    isLoading.value = false;
  }
}

function onSubmit() {
  handleRegister();
}

function reset() {
  email.value = '';
  password.value = '';
  confirmPassword.value = '';
  errorMessage.value = '';
  successMessage.value = '';
}

function goBack() {
  router.push({ name: 'home' });
}

function toLogin() {
  router.push({ name: 'login' });
}
</script>

<template>
  <div class="signup-container">
    <!-- Back Button -->
    <button class="back-btn" @click="goBack">
      <Icon icon="mdi:arrow-left" width="20" height="20" />
      Back
    </button>

    <!-- Form -->
    <div class="content form-content">
      <div class="form-wrapper">
        <h2 class="form-title">Join the hunt</h2>
        <p class="form-subtitle">Start building your vocabulary collection.</p>

        <form @submit.prevent="onSubmit">
          <label class="form-group">
            <span class="form-label">Email</span>
            <input
              type="email"
              v-model="email"
              required
              placeholder="you@example.com"
              autocomplete="email"
            />
          </label>

          <label class="form-group">
            <span class="form-label">Password</span>
            <input
              type="password"
              v-model="password"
              required
              placeholder="At least 6 characters"
              autocomplete="new-password"
            />
          </label>

          <label class="form-group">
            <span class="form-label">Confirm password</span>
            <input
              type="password"
              v-model="confirmPassword"
              required
              placeholder="One more time"
              autocomplete="new-password"
            />
          </label>

          <p v-if="successMessage" class="message success">{{ successMessage }}</p>
          <p v-if="errorMessage" class="message error">{{ errorMessage }}</p>

          <button type="submit" :disabled="isLoading" class="submit-btn">
            {{
              isLoading
                ? 'Setting things up...'
                : 'Create my account ✨'
            }}
          </button>
        </form>

        <p class="foot-note">Let's start collecting.</p>

        <p class="toggle-mode">
          Already have an account?
          <button type="button" @click="toLogin" class="toggle-btn">Sign in</button>
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@400;500;600;700&family=Nunito:wght@300;400;500;600;700&display=swap');

.signup-container {
  min-height: 100vh;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  box-sizing: border-box;
}

.content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
  text-align: center;
  animation: fadeIn 0.4s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.back-btn {
  position: fixed;
  top: 20px;
  left: 20px;
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: #a5a0b8;
  font-family: 'Nunito', sans-serif;
  font-weight: 600;
  font-size: 17px;
  cursor: pointer;
  transition: all 0.2s ease;
  padding: 8px 12px;
  z-index: 100;
}

.back-btn:hover {
  color: #c4b5fd;
}

.form-content {
  width: 100%;
  max-width: 480px;
  gap: 24px;
  position: relative;
}

.form-wrapper {
  width: 100%;
}

.form-title {
  margin: 0 0 8px 0;
  font-family: 'Fredoka', sans-serif;
  font-size: 31px;
  font-weight: 700;
  color: #c4b5fd;
  letter-spacing: -0.4px;
}

.form-subtitle {
  margin: 0 0 24px 0;
  font-family: 'Nunito', sans-serif;
  font-size: 18px;
  color: #a5a0b8;
  line-height: 1.5;
}

form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.form-label {
  font-family: 'Nunito', sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: #a5a0b8;
  margin-bottom: 8px;
  text-align: left;
}

.form-group input {
  padding: 12px 14px;
  font-family: 'Nunito', sans-serif;
  font-size: 17px;
  color: #e8e4f0;
  border: 1px solid rgba(196, 181, 253, 0.2);
  border-radius: 10px;
  background: rgba(124, 58, 237, 0.08);
  outline: none;
  transition: all 0.3s ease;
}

.form-group input:focus {
  border-color: rgba(196, 181, 253, 0.5);
  background: rgba(124, 58, 237, 0.12);
  box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.1);
}

.form-group input::placeholder {
  color: #8b7f9f;
}

.message {
  margin: 0;
  padding: 12px 14px;
  border-radius: 10px;
  font-family: 'Nunito', sans-serif;
  font-size: 16px;
  text-align: left;
}

.message.success {
  background: rgba(124, 58, 237, 0.15);
  color: #c4b5fd;
  border: 1px solid rgba(196, 181, 253, 0.3);
}

.message.error {
  background: rgba(239, 68, 68, 0.1);
  color: #fca5a5;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.submit-btn {
  padding: 13px 16px;
  margin-top: 8px;
  background: linear-gradient(135deg, #7c3aed 0%, #5b21b6 100%);
  color: #ffffff;
  border: none;
  border-radius: 10px;
  font-family: 'Nunito', sans-serif;
  font-size: 18px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s ease;
  letter-spacing: 0.3px;
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(124, 58, 237, 0.3);
}

.submit-btn:active:not(:disabled) {
  transform: translateY(0);
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.foot-note {
  margin: 20px 0 0 0;
  font-family: 'Nunito', sans-serif;
  text-align: center;
  font-size: 16px;
  color: #8b7f9f;
}

.toggle-mode {
  margin: 20px 0 0 0;
  font-family: 'Nunito', sans-serif;
  text-align: center;
  font-size: 14px;
  color: #8b7f9f;
}

.toggle-btn {
  background: none;
  border: none;
  color: #c4b5fd;
  font-family: 'Nunito', sans-serif;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: color 0.2s ease;
  padding: 0;
  margin-left: 4px;
}

.toggle-btn:hover {
  color: #e8e4f0;
}

@media (max-width: 768px) {
  .form-title {
    font-size: 27px;
  }

  .form-label {
    font-size: 16px;
  }

  .form-subtitle {
    font-size: 18px;
  }

  .form-group input {
    font-size: 19px;
    padding: 14px 16px;
  }

  .submit-btn {
    font-size: 19px;
    padding: 14px 16px;
  }

  .foot-note {
    font-size: 16px;
  }

  .toggle-mode {
    font-size: 13px;
  }
}
</style>
