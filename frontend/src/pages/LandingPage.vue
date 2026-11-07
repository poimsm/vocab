<script setup lang="ts">
import { ref } from 'vue';
import { Icon } from '@iconify/vue';
import { useAuthStore } from '@/stores/auth';
import { useRouter } from 'vue-router';
import { useAssetUrl } from '@/composables/useAssetUrl';
import { landingCards } from '@/data/landing';

const { buildAssetUrl } = useAssetUrl();

const authStore = useAuthStore();
const router = useRouter();

const mode = ref<'landing' | 'login' | 'signup'>('landing');
const email = ref('');
const password = ref('');
const confirmPassword = ref('');
const isLoading = ref(false);
const errorMessage = ref('');
const successMessage = ref('');

async function handleLogin() {
  isLoading.value = true;
  errorMessage.value = '';
  successMessage.value = '';

  try {
    const success = await authStore.login({
      email: email.value,
      password: password.value,
    });
    if (success) {
      router.push({ name: 'my-words' });
    }
  } catch (error: any) {
    errorMessage.value = 'Invalid email or password. Please try again.';
  } finally {
    isLoading.value = false;
  }
}

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
  if (mode.value === 'login') {
    handleLogin();
  } else if (mode.value === 'signup') {
    handleRegister();
  }
}

function reset() {
  email.value = '';
  password.value = '';
  confirmPassword.value = '';
  errorMessage.value = '';
  successMessage.value = '';
}

function goBack() {
  mode.value = 'landing';
  reset();
}

function toSignUp() {
  mode.value = 'signup';
  reset();
}

function toLogin() {
  mode.value = 'login';
  reset();
}
</script>

<template>
  <div class="landing-container">
    <!-- Back Button (Fixed in mobile) -->
    <button v-if="mode !== 'landing'" class="back-btn" @click="goBack">
      <Icon icon="mdi:arrow-left" width="20" height="20" />
      Back
    </button>

    <!-- Landing Mode -->
    <div v-if="mode === 'landing'" class="content landing-content">
      <div class="icon-section">
        <div class="icon-circle">
          <Icon icon="fluent-color:book-16" width="48" height="48" />
        </div>
      </div>

      <h1 class="heading">
        Collect Words,
        <br>Make Them Stick
        <!-- Catch your words. -->
        <!-- <br>Make them stick. -->
      </h1>

      <div class="divider">
        <img :src="buildAssetUrl('media/landing/sparkles.svg')" alt="divider" class="divider-icon" />
      </div>

      <p class="subtitle">
        See words from every angle. Understand them deeply.<br>
        Watch them become part of you.
      </p>

      <div class="explanation-section">
        <h2 class="explanation-title">How it works</h2>

        <div class="explanation-steps">
          <div class="step">
            <div class="step-icon">
              <Icon icon="fluent-emoji:books" width="40" height="40" />
            </div>
            <div class="step-content">
              <h3 class="step-title">Capture</h3>
              <p class="step-text">
                <!-- Found an incredible word in a book? Heard a fun expression in a movie? Save it! -->
                <!-- Found an incredible word in a book? Heard a fun expression in a movie? Add it to your list! -->
                 Spotted a unreal word in a book or a movie? Add it to your list!
              </p>
            </div>
          </div>

          <div class="step">
            <div class="step-icon">
              <Icon icon="fluent-emoji:sparkles" width="40" height="40" />
            </div>
            <div class="step-content">
              <h3 class="step-title">Immerse</h3>
              <p class="step-text">
                <!-- We create all sorts of experiences around the words you choose to collect. -->
                <!-- We design fun, engaging experiences around everything you save. -->
                We create all sorts of experiences around the words you save. 🤗
                <!-- 🤗 -->
                
                <!-- We craft stories, dialogues, and games around your personal collection. Learning that feels like entertainment, not homework. -->

                <!-- We craft ... Stories, unexpected encounters, curious combinations, and situations built around the words you've collected.  -->
                <!-- <span style="font-weight: bold; color:#bbb">There's always another way to discover them.</span>  -->
                

                <!-- Our app generates engaging content around your words.<br>
                Examples. Conversations. Challenges.<br>
                <strong>Master them all.</strong> -->
              </p>
            </div>
          </div>

          <div class="step">
            <div class="step-icon">
              <Icon icon="fluent-emoji:brain" width="40" height="40" />
            </div>
            <div class="step-content">
              <h3 class="step-title">Remember Forever</h3>
              <p class="step-text">
                <!-- Experience your words from every angle. They'll stick with you for life. -->
                <!-- Make unfamiliar expressions feel familiar. And familiar words feel like your own. -->
                 <!-- Make rare words familiar, and familiar words locked in forever. -->

                 <!-- Revisit your saved words. Keep them for life. -->

                 <!-- Store them, revisit them, and keep rare words locked in forever. -->
                  <!-- A cozy spot to collect, review, and never forget a single word!! =) -->
                 <!-- keep all your "rares" into one single place! -->
                  <!-- in that way, youll view them from some many sides, that youll never forget! -->
                   That way, you’ll see every side of your words.. and they’ll be right here waiting!
              </p>
            </div>
          </div>
        </div>
      </div>

      <div class="hook-message" style="display:none">
        <!-- <p>Don't just know what a word means.<br>Know when to use it, how it feels, and how it fits.</p> -->
        Gather rare words in one spot and make them stick.
      </div>

      <div class="features" style="display:none">
        <div class="feature">
          <div class="feature-icon">
            <Icon icon="fluent-emoji:eyes" width="32" height="32" />
          </div>
          <p class="feature-text">Spot interesting words</p>
        </div>
        <div class="feature">
          <div class="feature-icon">
            <Icon icon="fluent-emoji:floppy-disk" width="32" height="32" />
          </div>
          <p class="feature-text">Save them instantly</p>
        </div>
        <div class="feature">
          <div class="feature-icon">
            <Icon icon="fluent-emoji:brain" width="32" height="32" />
          </div>
          <p class="feature-text">Make them yours</p>
        </div>
      </div>

      <div class="actions">
        <button class="btn btn-primary" @click="toSignUp">
          <Icon icon="fluent-emoji:sparkles" width="18" height="18" />
          Start Your Collection
        </button>
        <button class="btn btn-secondary" @click="toLogin">
          Already collecting? Log in
        </button>
      </div>

      <!-- Features Cards Grid -->
      <div class="cards-grid" style="display:none">
        <div v-for="card in landingCards" :key="card.id" class="feature-card">
          <div class="card-top">
            <div class="card-header">

              <div style="display:flex;align-items: center;justify-content: flex-start;">
                 <img :src="buildAssetUrl(card.icon)" :alt="card.title" class="card-icon" />
                <h3 class="card-title">{{ card.title }}</h3>
              </div>
              <Icon :icon="card.badge" width="24" height="24" class="card-badge" />
            </div>
          </div>
          <div class="card-image" :style="{ marginTop: card.image_margin_top }">
            <img
              :src="buildAssetUrl(card.image)"
              :alt="card.title"
              :style="{ height: card.image_height, width: card.image_width }"
            />
          </div>
          <button class="card-arrow">
            <Icon icon="mdi:arrow-right" width="24" height="24" />
          </button>
        </div>
      </div>

    </div>

    <!-- Form Mode (Login/Signup) -->
    <div v-else class="content form-content">
      <!-- Form -->
      <div class="form-wrapper">
        <h2 class="form-title">
          {{ mode === 'signup' ? 'Join the hunt' : 'Welcome back, collector' }}
        </h2>
        <p class="form-subtitle">
          {{ mode === 'signup' ? 'Start building your vocabulary collection.' : 'Continue collecting words.' }}
        </p>

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
              :placeholder="mode === 'signup' ? 'At least 6 characters' : '••••••••'"
              :autocomplete="mode === 'signup' ? 'new-password' : 'current-password'"
            />
          </label>

          <label v-if="mode === 'signup'" class="form-group">
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
                ? mode === 'signup'
                  ? 'Setting things up...'
                  : "Let's go..."
                : mode === 'signup'
                  ? 'Create my account ✨'
                  : 'Sign me in →'
            }}
          </button>
        </form>

        <p class="foot-note">
          {{ mode === 'signup' ? 'Let\'s start collecting.' : 'Welcome back to your collection.' }}
        </p>
      </div>
    </div>

    <!-- Footer -->
    <div class="footer">
      <a href="#terms" class="footer-link">Terms of Service</a>
      <span class="footer-separator">•</span>
      <a href="#privacy" class="footer-link">Privacy Policy</a>
      <span class="footer-separator">•</span>
      <a href="#contact" class="footer-link">Contact</a>
      <div class="footer-bottom">
        <p class="footer-text">&copy; 2024 Vocab. All rights reserved.</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@400;500;600;700&family=Nunito:wght@300;400;500;600;700&display=swap');

.landing-container {
  min-height: 100vh;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding: 40px 20px;
  box-sizing: border-box;
}

.content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 32px;
  /* max-width: 520px; */
  max-width: 70vw;
  text-align: center;
  animation: fadeIn 0.4s ease-out;
  flex-grow: 1;
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

/* ============ Landing Content ============ */
.icon-section {
  animation: float 3s ease-in-out infinite;
}

.icon-circle {
  width: 80px;
  height: 80px;
  background: rgba(124, 58, 237, 0.1);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid rgba(196, 181, 253, 0.3);
}

.heading {
  margin: 0;
  font-family: 'Fredoka', sans-serif;
  font-weight: 700;
  font-size: clamp(35px, 6vw, 51px);
  line-height: 1.2;
  color: #c4b5fd;
  /* letter-spacing: -0.5px; */
}

.divider {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  width: 100%;
  max-width: 300px;
  margin: 12px 0;
  color: #c4b5fd;
  display: none;
}

.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1.5px;
  background: rgba(196, 181, 253, 0.3);
}

.divider-icon {
  width: 32px;
  height: 32px;
  object-fit: contain;
  flex-shrink: 0;
  opacity: 0.8;
}

.subtitle {
  margin: 0;
  font-family: 'Nunito', sans-serif;
  font-weight: 400;
  font-size: clamp(17px, 2vw, 19px);
  line-height: 1.7;
  color: #a5a0b8;
}

.hook-message {
  margin: 8px 0 0 0;
  padding: 24px 32px;
  background: rgba(196, 181, 253, 0.08);
  border: 1.5px solid rgba(196, 181, 253, 0.25);
  border-radius: 14px;
  max-width: 600px;
}

.hook-message p {
  margin: 0;
  font-family: 'Fredoka', sans-serif;
  font-weight: 600;
  font-size: clamp(17px, 2.5vw, 21px);
  line-height: 1.6;
  color: #e8e4f0;
  letter-spacing: -0.2px;
}

.explanation-section {
  display: flex;
  flex-direction: column;
  gap: 32px;
  width: 100%;
  max-width: 900px;
  margin: 24px 0;
  padding: 40px;
  background: rgba(124, 58, 237, 0.05);
  border: 1.5px solid rgba(196, 181, 253, 0.15);
  border-radius: 20px;
}

.explanation-title {
  margin: 0 0 12px 0;
  font-family: 'Fredoka', sans-serif;
  font-weight: 700;
  font-size: clamp(24px, 4vw, 32px);
  color: #c4b5fd;
  letter-spacing: -0.3px;
}

.explanation-steps {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 28px;
  width: 100%;
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  text-align: center;
}

.step-icon {
  width: 72px;
  height: 72px;
  background: rgba(124, 58, 237, 0.1);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1.5px solid rgba(196, 181, 253, 0.2);
}

.step-title {
  margin: 0;
  font-family: 'Fredoka', sans-serif;
  font-weight: 700;
  font-size: 18px;
  color: #e8e4f0;
  /* letter-spacing: -0.2px; */
}

.step-text {
  margin: 0;
  font-family: 'Nunito', sans-serif;
  font-weight: 400;
  font-size: 16.7px;
  line-height: 1.7;
  color: #a5a0b8;
}

.features {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
  width: 100%;
  margin: 8px 0;
}

.feature {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.feature-icon {
  width: 56px;
  height: 56px;
  background: rgba(124, 58, 237, 0.08);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(196, 181, 253, 0.2);
}

.feature-text {
  margin: 0;
  font-family: 'Nunito', sans-serif;
  font-weight: 500;
  font-size: 13px;
  color: #a5a0b8;
  line-height: 1.4;
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 600px;
  margin: 16px auto 0;
}

.cards-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  width: 100%;
  margin-top: 50px;
}

.feature-card {
  padding: 28px 24px;
  background: #302b43;
  border: 1.5px solid #443d5f;
  border-radius: 18px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  transition: all 0.3s ease;
  cursor: pointer;
  position: relative;
  width: 250px;
  /* min-height: 380px; */
}

.feature-card:hover {
  background: #32265485;
  border-color: #6a5f8f78;
  transform: translateY(-6px);
}

.card-top {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card-icon {
  width: 55px;
  height: 55px;
  object-fit: contain;
  flex-shrink: 0;
}

.card-title {
  margin: 0;
  font-family: 'Fredoka', sans-serif;
  font-weight: 700;
  font-size: 18.5px;
  color: #e8e4f0;
  text-align: left;
  line-height: 1.3;
}

.card-badge {
  /* color: #fbbf24d4; */
  color: transparent;
  flex-shrink: 0;
}

.card-image {
  /* width: 180px; */
  /* height: 180px; */
  border-radius: 14px;
  overflow: hidden;
  /* background: #1f1535; */
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.98;
  /* padding: 12px; */
}

.card-image img {
  /* width: 100%; */
  height: 60px;
  /* width: 180px; */
  object-fit: contain;
}

.card-arrow {
  position: absolute;
  bottom: 20px;
  right: 20px;
  width: 48px;
  height: 48px;
  background: #493c74;
  border: 1px solid #5a4d7f6b;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
  color: #c4b5fd;
  padding: 0;
}

.card-arrow:hover {
  background: #4a3d7f;
  border-color: #7a6d9f;
  transform: translate(4px, -4px);
}


.btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px 32px;
  border: none;
  border-radius: 12px;
  font-family: 'Nunito', sans-serif;
  font-weight: 600;
  font-size: 18px;
  cursor: pointer;
  text-decoration: none;
  transition: all 0.3s ease;
  letter-spacing: 0.3px;
}

.btn-primary {
  background: linear-gradient(135deg, #7c3aed 0%, #5b21b6 100%);
  color: #ffffff;
}

.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(124, 58, 237, 0.3);
}

.btn-secondary {
  background: transparent;
  color: #a5a0b8;
  border: 1px solid rgba(196, 181, 253, 0.2);
}

.btn-secondary:hover {
  color: #c4b5fd;
  border-color: rgba(196, 181, 253, 0.4);
  background: rgba(124, 58, 237, 0.05);
}

/* ============ Form Content ============ */
.form-content {
  width: 100%;
  max-width: 480px;
  gap: 24px;
  position: relative;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  align-self: flex-start;
  background: none;
  border: none;
  color: #a5a0b8;
  font-family: 'Nunito', sans-serif;
  font-weight: 600;
  font-size: 17px;
  cursor: pointer;
  transition: all 0.2s ease;
  padding: 8px 12px;
  margin-left: -12px;
}

.back-btn:hover {
  color: #c4b5fd;
}

@media (max-width: 768px) {
  .back-btn {
    position: fixed;
    top: 20px;
    left: 16px;
    margin-left: 0;
    z-index: 100;
  }

  .landing-container {
    padding-top: 70px;
  }
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

@keyframes float {
  0%, 100% {
    transform: translateY(0px);
  }
  50% {
    transform: translateY(-10px);
  }
}

/* ============ Footer ============ */
.footer {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  padding: 40px 20px;
  margin-top: 60px;
  font-family: 'Nunito', sans-serif;
  font-size: 12px;
}

.footer-link {
  color: #6b6178;
  text-decoration: none;
  transition: color 0.3s ease;
  cursor: pointer;
}

.footer-link:hover {
  color: #8b7f9f;
}

.footer-separator {
  color: #5a4d7f;
  opacity: 0.5;
}

.footer-bottom {
  display: none;
}

.footer-text {
  margin: 0;
  color: #5a4d7f;
  font-size: 11px;
}

@media (max-width: 768px) {
  .footer {
    gap: 12px;
    padding: 30px 16px;
    margin-top: 40px;
  }

  .footer-text {
    font-size: 10px;
  }
}

/* ============ Responsive ============ */
@media (max-width: 768px) {
  .landing-container {
    padding: 32px 16px;
  }

  .content {
    gap: 24px;
  }

  .landing-content {
    gap: 20px;
  }

  .icon-circle {
    width: 64px;
    height: 64px;
  }

  .heading {
    font-size: 31px;
  }

  .subtitle {
    font-size: 17px;
  }

  .hook-message {
    padding: 20px 24px;
    margin: 8px 0 0 0;
  }

  .hook-message p {
    font-size: 16px;
  }

  .explanation-section {
    padding: 28px 20px;
    gap: 24px;
  }

  .explanation-title {
    font-size: 24px;
  }

  .explanation-steps {
    grid-template-columns: 1fr;
    gap: 20px;
  }

  .step-icon {
    width: 64px;
    height: 64px;
  }

  .step-title {
    font-size: 16px;
  }

  .step-text {
    font-size: 14px;
  }

  .actions {
    width: 100%;
  }

  .btn {
    padding: 12px 24px;
    font-size: 17px;
  }

  .features {
    grid-template-columns: 1fr;
    gap: 16px;
    margin: 16px 0;
  }

  .feature-icon {
    width: 48px;
    height: 48px;
  }

  .feature-text {
    font-size: 14px;
  }

  .cards-grid {
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-top: 40px;
  }

  .feature-card {
    padding: 24px 20px;
    gap: 18px;
    min-height: 360px;
  }

  .card-top {
    gap: 12px;
  }

  .card-icon {
    width: 32px;
    height: 32px;
  }

  .card-title {
    font-size: 16px;
  }

  .card-image {
    height: 160px;    
  }

  .card-arrow {
    width: 42px;
    height: 42px;
  }

  .form-content {
    max-width: 100%;
  }

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

  .back-btn {
    font-size: 17px;
  }

  .message {
    font-size: 16px;
  }

  .foot-note {
    font-size: 16px;
  }
}
</style>
