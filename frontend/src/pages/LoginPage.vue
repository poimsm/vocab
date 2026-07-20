<template>
    <div class="login-container">
        <h2>Welcome back to Vocab!</h2>
        <form @submit.prevent="handleLogin">
            <div class="form-group">
                <label>Email:</label>
                <input type="email" v-model="email" required placeholder="you@example.com" style="padding: 7px 10px" />
            </div>

            <div class="form-group">
                <label>Password:</label>
                <input type="password" v-model="password" required placeholder="********" style="padding: 7px 10px" />
            </div>

            <p v-if="errorMessage" class="error">{{ errorMessage }}</p>

            <button type="submit" :disabled="isLoading">
                {{ isLoading ? 'Signing you in...' : 'Sign In' }}
            </button>
        </form>
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
const isLoading = ref(false)
const errorMessage = ref('')

async function handleLogin() {
    isLoading.value = true
    errorMessage.value = ''

    // Preparar datos en formato Form URL Encoded exigido por FastAPI
    const formData = new FormData()
    formData.append('username', email.value)
    formData.append('password', password.value)

    try {
        const success = await authStore.login(formData)
        if (success) {
            router.push({ name: 'my-words' }) // Redirigir a la zona protegida
        }
    } catch (error: any) {
        errorMessage.value = error.response?.data?.detail || 'Oops! Something went wrong. Please check your credentials and try again.'
    } finally {
        isLoading.value = false
    }
}
</script>

<style scoped>
.login-container {
    max-width: 400px;
    margin: 50px auto;
    padding: 20px;
    /* border: 1px solid #ccc; */
    border-radius: 8px;
}

.form-group {
    margin-bottom: 15px;
    display: flex;
    flex-direction: column;
    width: 300px;
}

.error {
    color: red;
    font-size: 0.9em;
}

button {
    padding: 10px;
    cursor: pointer;
    background-color: #42b983;
    color: white;
    border: none;
    border-radius: 4px;
}

button:disabled {
    background-color: #a8d8b9;
}
</style>