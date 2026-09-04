<script setup>
import { computed, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { supportApi } from "../api/notifications";

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

// Pulsante globale "Richiedi assistenza": invia un'email con contesto
// precompilato (pagina corrente, utente) all'indirizzo configurato in
// Amministrazione -> Notifiche, cosi' l'operatore non deve spiegare da capo
// dov'era e cosa stava facendo.
const showSupport = ref(false);
const supportForm = reactive({ subject: "", message: "" });
const supportSending = ref(false);
const supportFeedback = ref("");
const supportFeedbackIsError = ref(false);

function openSupport() {
  showSupport.value = true;
  supportForm.subject = "";
  supportForm.message = "";
  supportFeedback.value = "";
}
function closeSupport() {
  showSupport.value = false;
}
async function sendSupport() {
  if (!supportForm.message) return;
  supportSending.value = true;
  supportFeedback.value = "";
  try {
    await supportApi.send({
      subject: supportForm.subject || "Richiesta generica",
      message: supportForm.message,
      context: `Pagina: ${title.value} (${route.fullPath})`,
    });
    supportFeedbackIsError.value = false;
    supportFeedback.value = "Richiesta inviata.";
    setTimeout(closeSupport, 1500);
  } catch (e) {
    supportFeedbackIsError.value = true;
    supportFeedback.value = e.message || "Invio fallito.";
  } finally {
    supportSending.value = false;
  }
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
        <button @click="openSupport">Richiedi assistenza</button>
      </div>
      <div class="content">
        <slot />
      </div>
    </div>

    <div v-if="showSupport" style="position: fixed; inset: 0; background: rgba(0, 0, 0, 0.4); display: flex; align-items: center; justify-content: center; z-index: 100">
      <div class="panel" style="width: 420px; max-width: 90vw">
        <div class="panel-head"><h3>Richiedi assistenza</h3></div>
        <p class="hint" style="margin-top: -6px">Invia una segnalazione con il contesto della pagina attuale già incluso.</p>
        <div v-if="supportFeedback" :class="supportFeedbackIsError ? 'error-box' : 'badge ok'" :style="supportFeedbackIsError ? '' : 'display:block;padding:8px 12px;margin-bottom:8px;width:fit-content'">{{ supportFeedback }}</div>
        <div class="field">
          <label>Oggetto</label>
          <input v-model="supportForm.subject" placeholder="es. Problema con la Raccolta Dati" />
        </div>
        <div class="field">
          <label>Messaggio<span class="required-mark">*</span></label>
          <textarea v-model="supportForm.message" rows="4" style="width: 100%" :class="{ invalid: !supportForm.message }"></textarea>
        </div>
        <div style="margin-top: 10px; display: flex; gap: 8px; justify-content: flex-end">
          <button @click="closeSupport">Annulla</button>
          <button class="primary" :disabled="!supportForm.message || supportSending" @click="sendSupport">
            {{ supportSending ? "Invio..." : "Invia" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
