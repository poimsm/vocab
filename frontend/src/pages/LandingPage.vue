<script setup lang="ts">
import { Icon } from '@iconify/vue';
import { useRouter } from 'vue-router';
import { useAssetUrl } from '@/composables/useAssetUrl';

const { buildAssetUrl } = useAssetUrl();
const router = useRouter();

function toSignUp() {
  router.push({ name: 'signup' });
}

function toLogin() {
  router.push({ name: 'login' });
}
</script>

<template>
  <div class="landing-container">
    <!-- Landing Content -->
    <div class="content landing-content">
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

      <div class="actions">
        <button class="btn btn-primary" @click="toSignUp">
          <Icon icon="fluent-emoji:sparkles" width="18" height="18" />
          Start Your Collection
        </button>
        <button class="btn btn-secondary" @click="toLogin">
          Already collecting? Log in
        </button>
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


.subtitle {
  margin: 0;
  font-family: 'Nunito', sans-serif;
  font-weight: 400;
  font-size: clamp(17px, 2vw, 19px);
  line-height: 1.7;
  color: #a5a0b8;
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


.actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 600px;
  margin: 16px auto 0;
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

}
</style>
