<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const titles = {
  dashboard: "Cruscotto",
  "data-collection": "Raccolta Dati",
  config: "Routine & Quote",
  gages: "Strumenti",
  admin: "Amministrazione",
};
const title = computed(() => titles[route.name] || "");

function logout() {
  auth.logout();
  router.push({ name: "login" });
}
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">leank<small>spc</small></div>

      <RouterLink to="/" class="nav-item" active-class="active">
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="2.5" y="2.5" width="6" height="6" rx="1"/><rect x="11.5" y="2.5" width="6" height="6" rx="1"/><rect x="2.5" y="11.5" width="6" height="6" rx="1"/><rect x="11.5" y="11.5" width="6" height="6" rx="1"/></svg>
        Cruscotto
      </RouterLink>
      <RouterLink to="/raccolta-dati" class="nav-item" active-class="active">
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"><path d="M2 11h3.5l2-6 3 11 2-8 1.5 3H18"/></svg>
        Raccolta Dati
      </RouterLink>
      <RouterLink to="/routine-quote" class="nav-item" active-class="active">
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M3 5h14M3 10h14M3 15h9"/><circle cx="16" cy="15" r="1.4" fill="currentColor" stroke="none"/></svg>
        Routine &amp; Quote
      </RouterLink>
      <RouterLink to="/strumenti" class="nav-item" active-class="active">
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 4.5v11M2.5 4.5h3M2.5 8h2M2.5 11h2M2.5 15.5h3M17.5 4.5v11M6 10h9"/><path d="M17.5 4.5l-2.2 2.2M17.5 15.5l-2.2-2.2"/></svg>
        Strumenti
      </RouterLink>
      <RouterLink to="/amministrazione" class="nav-item" active-class="active">
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="7" r="3"/><path d="M3.5 17c1-3.5 3.8-5.5 6.5-5.5s5.5 2 6.5 5.5"/></svg>
        Amministrazione
      </RouterLink>

      <div class="sidebar-foot">
        <div class="user-chip">
          <div class="avatar">{{ auth.initials }}</div>
          <div class="who">
            {{ auth.username }}
            <span><a href="#" @click.prevent="logout">Esci</a></span>
          </div>
        </div>
      </div>
    </aside>

    <div class="main">
      <div class="topbar">
        <div>
          <h1>{{ title }}</h1>
        </div>
      </div>
      <div class="content">
        <slot />
      </div>
    </div>
  </div>
</template>
