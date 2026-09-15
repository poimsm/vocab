<template>
    <div class="login-container">
        <div class="form-card">
            <div class="mode-switch">
                <button
                    type="button"
                    class="mode-btn"
                    :class="{ active: !isSignUp }"
                    @click="isSignUp = false"
                >
                    Sign in
                </button>
                <button
                    type="button"
                    class="mode-btn"
                    :class="{ active: isSignUp }"
                    @click="isSignUp = true"
                >
                    Create account
                </button>
            </div>

            <h2 class="form-title">
                {{ isSignUp ? 'Join the fun 🎉' : 'Hey, welcome back 👋' }}
            </h2>
            <p class="form-subtitle">
                {{ isSignUp ? 'Takes like 10 seconds. No sweat.' : 'Pick up right where you left off.' }}
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
                        :placeholder="isSignUp ? 'At least 6 characters' : '••••••••'"
                        :autocomplete="isSignUp ? 'new-password' : 'current-password'"
                    />
                </label>

                <label v-if="isSignUp" class="form-group">
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
                    {{ isLoading
                        ? (isSignUp ? 'Setting things up...' : 'Let\'s go...')
                        : (isSignUp ? 'Create my account ✨' : 'Sign me in →') }}
                </button>
            </form>

            <p class="foot-note">
                {{ isSignUp ? 'By joining you agree to be awesome.' : 'Glad to see you again.' }}
            </p>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()

const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const isLoading = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const isSignUp = ref(false)

async function onSubmit() {
    return isSignUp.value ? handleRegister() : handleLogin()
}

async function handleLogin() {
    isLoading.value = true
    errorMessage.value = ''
    successMessage.value = ''

    const loginData = {
        email: email.value,
        password: password.value
    }

    try {
        const success = await authStore.login(loginData)
        if (success) {
            router.push({ name: 'my-words' })
        }
    } catch (error: any) {
        errorMessage.value = 'Invalid email or password. Please try again.'
    } finally {
        isLoading.value = false
    }
}

async function handleRegister() {
    isLoading.value = true
    errorMessage.value = ''
    successMessage.value = ''

    if (password.value.length < 6) {
        errorMessage.value = 'Password needs at least 6 characters 🙂'
        isLoading.value = false
        return
    }

    if (password.value !== confirmPassword.value) {
        errorMessage.value = 'Passwords don\'t match. Try again.'
        isLoading.value = false
        return
    }

    const registerData = {
        email: email.value,
        password: password.value
    }

    try {
        await authStore.register(registerData)
        successMessage.value = 'Nice, you\'re in! Logging you in...'

        setTimeout(async () => {
            try {
                await authStore.login(registerData)
                router.push({ name: 'my-words' })
            } catch (error: any) {
                errorMessage.value = 'Account created, but login failed. Try signing in manually.'
            }
        }, 1500)
    } catch (error: any) {
        errorMessage.value = error.response?.data?.detail || 'Couldn\'t create your account. Mind trying again?'
    } finally {
        isLoading.value = false
    }
}
</script>

<style scoped>
* {
    box-sizing: border-box;
}

/* Palette
   --bg:      #2d2a3e  app background
   --surface: #3a354c  inputs
   --accent:  #8b7fd4  buttons / active states
*/

.login-container {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #2d2a3e;
    padding: 24px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

.form-card {
    width: 100%;
    max-width: 440px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 22px;
    padding: 44px 42px 30px;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35);
}

/* ---- Mode switch: no overlay, just an active state per button ---- */
.mode-switch {
    display: flex;
    gap: 4px;
    background: #3a354c;
    border-radius: 13px;
    padding: 5px;
    margin-bottom: 32px;
}

.mode-btn {
    flex: 1;
    padding: 11px 0;
    border: none;
    border-radius: 9px;
    font-size: 14px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.55);
    background: transparent;
    cursor: pointer;
    transition: background 0.3s ease, color 0.3s ease;
}

.mode-btn.active {
    background: #8b7fd4;
    color: #fff;
}

.form-title {
    margin: 0 0 8px 0;
    font-size: 29px;
    font-weight: 700;
    color: #fff;
    letter-spacing: -0.4px;
}

.form-subtitle {
    margin: 0 0 30px 0;
    font-size: 15px;
    color: rgba(255, 255, 255, 0.55);
}

form {
    display: flex;
    flex-direction: column;
    gap: 18px;
}

.form-group {
    display: flex;
    flex-direction: column;
}

.form-label {
    font-size: 14px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.78);
    margin-bottom: 7px;
}

.form-group input {
    padding: 14px 16px;
    font-size: 15px;
    color: #fff;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    outline: none;
    background: #3a354c;
    transition: border-color 0.25s ease, box-shadow 0.25s ease, background 0.25s ease;
}

.form-group input:focus {
    border-color: #8b7fd4;
    background: #443e5a;
    box-shadow: 0 0 0 3px rgba(139, 127, 212, 0.22);
}

.form-group input::placeholder {
    color: rgba(255, 255, 255, 0.35);
}

.message {
    margin: 0;
    padding: 12px 16px;
    border-radius: 12px;
    font-size: 14px;
}

.message.success {
    background: rgba(139, 127, 212, 0.14);
    color: #c3baf0;
    border: 1px solid rgba(139, 127, 212, 0.35);
}

.message.error {
    background: rgba(239, 68, 68, 0.1);
    color: #fca5a5;
    border: 1px solid rgba(239, 68, 68, 0.3);
}

.submit-btn {
    padding: 15px 16px;
    background: #8b7fd4;
    color: #fff;
    border: none;
    border-radius: 12px;
    font-size: 16px;
    font-weight: 700;
    cursor: pointer;
    transition: background 0.25s ease, box-shadow 0.25s ease, transform 0.15s ease;
    margin-top: 6px;
}

.submit-btn:hover:not(:disabled) {
    background: #7d70c9;
    box-shadow: 0 8px 22px rgba(139, 127, 212, 0.4);
}

.submit-btn:active:not(:disabled) {
    transform: scale(0.98);
}

.submit-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.foot-note {
    margin: 28px 0 0 0;
    text-align: center;
    font-size: 13px;
    color: rgba(255, 255, 255, 0.4);
}

/* ---- Mobile: no card, bigger text, roomier inputs ---- */
@media (max-width: 480px) {
    .login-container {
        align-items: flex-start;
        padding: 26px 20px 20px;
    }

    .form-card {
        max-width: 100%;
        background: transparent;
        border: none;
        box-shadow: none;
        padding: 0;
    }

    .form-title {
        font-size: 27px;
        margin-top: 10px;
    }

    .form-subtitle {
        font-size: 16px;
        margin-bottom: 26px;
    }

    .mode-switch {
        margin-bottom: 24px;
    }

    .mode-btn {
        font-size: 15px;
        padding: 12px 0;
    }

    form {
        gap: 20px;
    }

    .form-label {
        font-size: 15px;
    }

    .form-group input {
        padding: 16px;
        font-size: 16px; /* prevents iOS auto-zoom on focus */
        border-radius: 13px;
    }

    .message {
        font-size: 15px;
    }

    .submit-btn {
        font-size: 17px;
        padding: 16px;
    }

    .foot-note {
        font-size: 14px;
    }
}
</style>