<script setup>
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const username = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

async function onSubmit() {
  error.value = "";
  loading.value = true;
  try {
    await auth.login(username.value, password.value);
    router.push(route.query.redirect || { name: "dashboard" });
  } catch (e) {
    error.value = e.message || "Errore di login.";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-screen">
    <form class="panel login-card" @submit.prevent="onSubmit">
      <div class="brand" style="padding: 0 0 18px">leank<small>spc</small></div>
      <div v-if="error" class="error-box">{{ error }}</div>
      <div class="field">
        <label for="username">Utente</label>
        <input id="username" v-model="username" autocomplete="username" required style="width: 100%" />
      </div>
      <div class="field">
        <label for="password">Password</label>
        <input id="password" v-model="password" type="password" autocomplete="current-password" required style="width: 100%" />
      </div>
      <button type="submit" class="primary" :disabled="loading" style="width: 100%">
        {{ loading ? "Accesso in corso..." : "Accedi" }}
      </button>
    </form>
  </div>
</template>
