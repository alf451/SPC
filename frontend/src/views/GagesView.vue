<script setup>
import { reactive, ref, watch } from "vue";
import { gagesApi } from "../api/gages";
import { calibrationsApi } from "../api/calibrations";

const gages = ref([]);
const selectedGageId = ref(null);
const calibrations = ref([]);
const error = ref("");

const newGage = reactive({ name: "", classification: "", model: "", serial_number: "" });
const resultForm = reactive({}); // { [calibrationId]: { point_no, nominal, found } }

async function loadGages() {
  gages.value = await gagesApi.list();
}

async function createGage() {
  error.value = "";
  try {
    await gagesApi.create({ ...newGage, classification: newGage.classification || null, model: newGage.model || null, serial_number: newGage.serial_number || null });
    Object.assign(newGage, { name: "", classification: "", model: "", serial_number: "" });
    await loadGages();
  } catch (e) {
    error.value = e.message || "Impossibile creare lo strumento.";
  }
}

async function loadCalibrations() {
  if (!selectedGageId.value) {
    calibrations.value = [];
    return;
  }
  calibrations.value = await calibrationsApi.list({ gage_id: selectedGageId.value });
}
watch(selectedGageId, loadCalibrations);

async function startCalibration() {
  if (!selectedGageId.value) return;
  error.value = "";
  try {
    await calibrationsApi.create({ gage_id: selectedGageId.value });
    await loadCalibrations();
  } catch (e) {
    error.value = e.message || "Impossibile avviare la calibrazione.";
  }
}

function initResultForm(calId) {
  const existingCount = 0; // il backend non espone ancora GET dei singoli risultati, si numera in sequenza da qui
  resultForm[calId] = { point_no: existingCount + 1, nominal: "", found: "" };
}

async function submitResult(calId) {
  const form = resultForm[calId];
  error.value = "";
  try {
    await calibrationsApi.addResult(calId, {
      point_no: Number(form.point_no),
      nominal: form.nominal === "" ? null : Number(form.nominal),
      found: form.found === "" ? null : Number(form.found),
    });
    form.point_no += 1;
    form.nominal = "";
    form.found = "";
  } catch (e) {
    error.value = e.message || "Impossibile registrare il punto di calibrazione.";
  }
}

async function completeCalibration(calId, passed) {
  error.value = "";
  try {
    await calibrationsApi.complete(calId, passed);
    await loadCalibrations();
  } catch (e) {
    error.value = e.message || "Impossibile completare la calibrazione.";
  }
}

const statusLabel = { in_progress: "in corso", passed: "superata", failed: "non superata" };

loadGages();
</script>

<template>
  <div v-if="error" class="error-box">{{ error }}</div>

  <div class="grid grid-2">
    <div class="panel">
      <div class="panel-head"><h3>Strumenti di misura</h3><span class="hint">{{ gages.length }} registrati</span></div>
      <table>
        <thead><tr><th>Nome</th><th>Modello</th><th>Matricola</th><th>Stato</th></tr></thead>
        <tbody>
          <tr v-for="g in gages" :key="g.id" style="cursor: pointer" :class="{ sel: g.id === selectedGageId }" @click="selectedGageId = g.id">
            <td>{{ g.name }}</td>
            <td class="hint">{{ g.model || "-" }}</td>
            <td class="mono">{{ g.serial_number || "-" }}</td>
            <td><span class="badge" :class="g.status === 'in_service' ? 'ok' : 'neutral'">{{ g.status }}</span></td>
          </tr>
          <tr v-if="gages.length === 0"><td colspan="4" class="hint">Nessuno strumento registrato ancora.</td></tr>
        </tbody>
      </table>

      <details style="margin-top: 12px">
        <summary class="hint" style="cursor: pointer">Nuovo strumento</summary>
        <div class="grid grid-2" style="margin-top: 8px">
          <input v-model="newGage.name" placeholder="Nome" />
          <input v-model="newGage.classification" placeholder="Classificazione" />
          <input v-model="newGage.model" placeholder="Modello" />
          <input v-model="newGage.serial_number" placeholder="Matricola" />
        </div>
        <button class="primary" style="margin-top: 8px" :disabled="!newGage.name" @click="createGage">Crea</button>
      </details>
    </div>

    <div class="panel">
      <div class="panel-head">
        <h3>Calibrazioni{{ selectedGageId ? "" : " (seleziona uno strumento)" }}</h3>
      </div>
      <template v-if="selectedGageId">
        <button class="primary" style="margin-bottom: 12px" @click="startCalibration">Avvia nuova calibrazione</button>
        <div v-for="c in calibrations" :key="c.id" class="panel" style="margin-bottom: 10px">
          <div class="panel-head" style="margin-bottom: 8px; padding-bottom: 8px">
            <span>Calibrazione #{{ c.id }} - <span class="badge" :class="c.status === 'passed' ? 'ok' : c.status === 'failed' ? 'danger' : 'neutral'">{{ statusLabel[c.status] || c.status }}</span></span>
            <span class="hint">{{ new Date(c.started_at).toLocaleString("it-IT") }}</span>
          </div>
          <template v-if="c.status === 'in_progress'">
            <div v-if="!resultForm[c.id]"><button @click="initResultForm(c.id)">Aggiungi punto di misura</button></div>
            <div v-else class="grid grid-3">
              <input v-model="resultForm[c.id].point_no" type="number" placeholder="Punto n." />
              <input v-model="resultForm[c.id].nominal" type="number" step="any" placeholder="Nominale" />
              <input v-model="resultForm[c.id].found" type="number" step="any" placeholder="Rilevato" />
            </div>
            <div style="margin-top: 8px">
              <button v-if="resultForm[c.id]" class="primary" @click="submitResult(c.id)">Registra punto</button>
              <button style="margin-left: 6px" @click="completeCalibration(c.id, true)">Completa: superata</button>
              <button class="danger" style="margin-left: 6px" @click="completeCalibration(c.id, false)">Completa: non superata</button>
            </div>
          </template>
        </div>
        <div v-if="calibrations.length === 0" class="hint">Nessuna calibrazione ancora per questo strumento.</div>
      </template>
    </div>
  </div>
</template>
