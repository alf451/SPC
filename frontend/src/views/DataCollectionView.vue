<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { runsApi } from "../api/runs";
import { routinesApi } from "../api/routines";
import { stationsApi } from "../api/stations";
import { measurementsApi } from "../api/measurements";
import { connectDashboardSocket } from "../ws/dashboardSocket";

const activeRuns = ref([]);
const routines = ref([]);
const stations = ref([]);
const selectedRunId = ref(null);
const run = ref(null);
const features = ref([]);
const observations = ref([]);
const error = ref("");
const loadingRun = ref(false);

const newRun = reactive({ routine_id: "", station_id: "", name: "" });
const entry = reactive({ feature_id: "", value: "" });

let socket = null;

async function loadOptions() {
  const [runList, routineList, stationList] = await Promise.all([
    runsApi.list({ status_filter: "active" }),
    routinesApi.list(),
    stationsApi.list(),
  ]);
  activeRuns.value = runList;
  routines.value = routineList;
  stations.value = stationList;
}

async function startRun() {
  error.value = "";
  try {
    const created = await runsApi.create({
      routine_id: Number(newRun.routine_id),
      station_id: Number(newRun.station_id),
      name: newRun.name || `Run ${new Date().toLocaleString("it-IT")}`,
    });
    await loadOptions();
    selectedRunId.value = created.id;
    newRun.routine_id = "";
    newRun.station_id = "";
    newRun.name = "";
  } catch (e) {
    error.value = e.message || "Impossibile avviare il Run.";
  }
}

async function completeRun() {
  if (!run.value) return;
  await runsApi.complete(run.value.id);
  await loadOptions();
  selectedRunId.value = null;
}

function nextObsNo(featureId) {
  const count = observations.value.filter((o) => o.feature_id === featureId).length;
  return count + 1;
}

async function submitManualEntry() {
  if (!run.value || !entry.feature_id || entry.value === "") return;
  error.value = "";
  try {
    const featureId = Number(entry.feature_id);
    await measurementsApi.create(run.value.id, {
      feature_id: featureId,
      obs_no: nextObsNo(featureId),
      value: Number(entry.value),
      captured_at: new Date().toISOString(),
      source: "manual",
    });
    entry.value = "";
    // il proprio evento "measurement" arrivera' anche via WebSocket (broadcast
    // a tutti i client sul Run, incluso questo), quindi non serve aggiungerlo
    // due volte qui manualmente.
  } catch (e) {
    error.value = e.message || "Impossibile registrare la misura.";
  }
}

function featureLabel(id) {
  return features.value.find((f) => f.id === id)?.name || `#${id}`;
}

function toleranceRange(feature) {
  const p = feature.current_properties;
  if (!p) return "-";
  const parts = [];
  if (p.lower_tolerance_limit != null) parts.push(p.lower_tolerance_limit);
  if (p.target != null) parts.push(`[${p.target}]`);
  if (p.upper_tolerance_limit != null) parts.push(p.upper_tolerance_limit);
  return parts.length ? parts.join(" / ") : "-";
}

function outOfTolerance(obs) {
  const feature = features.value.find((f) => f.id === obs.feature_id);
  const p = feature?.current_properties;
  if (!p || obs.value == null) return false;
  if (p.lower_tolerance_limit != null && obs.value < p.lower_tolerance_limit) return true;
  if (p.upper_tolerance_limit != null && obs.value > p.upper_tolerance_limit) return true;
  return false;
}

watch(selectedRunId, async (id) => {
  socket?.close();
  socket = null;
  run.value = null;
  features.value = [];
  observations.value = [];
  error.value = "";
  if (!id) return;

  loadingRun.value = true;
  try {
    run.value = await runsApi.get(id);
    const [featureList, measurementList] = await Promise.all([
      routinesApi.features(run.value.routine_id),
      measurementsApi.list(id, { limit: 200 }),
    ]);
    features.value = featureList;
    observations.value = measurementList.slice().reverse(); // piu' recente in cima

    socket = connectDashboardSocket(id, (msg) => {
      if (msg.type === "measurement") {
        observations.value.unshift(msg);
      }
    });
  } catch (e) {
    error.value = e.message || "Impossibile caricare il Run selezionato.";
  } finally {
    loadingRun.value = false;
  }
});

onMounted(loadOptions);
onBeforeUnmount(() => socket?.close());

const canStartRun = computed(() => newRun.routine_id && newRun.station_id);
</script>

<template>
  <div v-if="error" class="error-box">{{ error }}</div>

  <div class="panel" style="margin-bottom: 16px">
    <div class="panel-head">
      <h3>Run attivo</h3>
    </div>
    <div class="grid grid-2">
      <div class="field" style="margin: 0">
        <label>Seleziona un Run in corso</label>
        <select v-model="selectedRunId" style="width: 100%">
          <option :value="null">-- nessuno --</option>
          <option v-for="r in activeRuns" :key="r.id" :value="r.id">{{ r.name }} (stazione #{{ r.station_id }})</option>
        </select>
      </div>
      <div v-if="run" style="align-self: end">
        <button class="danger" @click="completeRun">Completa Run</button>
      </div>
    </div>

    <details style="margin-top: 14px">
      <summary class="hint" style="cursor: pointer">Avvia un nuovo Run</summary>
      <div class="grid grid-3" style="margin-top: 10px">
        <div class="field" style="margin: 0">
          <label>Routine</label>
          <select v-model="newRun.routine_id" style="width: 100%">
            <option value="">-- scegli --</option>
            <option v-for="r in routines" :key="r.id" :value="r.id">{{ r.name }}</option>
          </select>
        </div>
        <div class="field" style="margin: 0">
          <label>Stazione</label>
          <select v-model="newRun.station_id" style="width: 100%">
            <option value="">-- scegli --</option>
            <option v-for="s in stations" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </div>
        <div class="field" style="margin: 0">
          <label>Nome Run (opzionale)</label>
          <input v-model="newRun.name" style="width: 100%" placeholder="es. Collaudo lotto 123" />
        </div>
      </div>
      <button class="primary" style="margin-top: 10px" :disabled="!canStartRun" @click="startRun">Avvia Run</button>
    </details>
  </div>

  <template v-if="run">
    <div class="live-grid grid grid-2">
      <div class="panel">
        <div class="panel-head">
          <h3>Quote della routine</h3>
          <span class="hint">target / tolleranze correnti</span>
        </div>
        <table>
          <thead>
            <tr><th>Feature</th><th>Tipo</th><th>Tolleranza</th></tr>
          </thead>
          <tbody>
            <tr v-for="f in features" :key="f.id">
              <td>{{ f.name }}</td>
              <td class="hint">{{ f.feature_type }}</td>
              <td class="mono">{{ toleranceRange(f) }}</td>
            </tr>
            <tr v-if="features.length === 0"><td colspan="3" class="hint">Nessuna Feature associata a questa Routine.</td></tr>
          </tbody>
        </table>

        <div class="panel-head" style="margin-top: 18px">
          <h3>Inserimento manuale</h3>
          <span class="hint">se l'Edge Agent non e' collegato</span>
        </div>
        <div class="grid grid-2">
          <select v-model="entry.feature_id">
            <option value="">-- Feature --</option>
            <option v-for="f in features" :key="f.id" :value="f.id">{{ f.name }}</option>
          </select>
          <input v-model="entry.value" type="number" step="any" placeholder="Valore" />
        </div>
        <button class="primary" style="margin-top: 10px" @click="submitManualEntry">Registra misura</button>
      </div>

      <div class="panel">
        <div class="panel-head">
          <h3>Osservazioni recenti</h3>
          <span class="hint">in tempo reale via WebSocket</span>
        </div>
        <table>
          <thead>
            <tr><th>Feature</th><th>N.</th><th>Valore</th><th>Ora</th></tr>
          </thead>
          <tbody>
            <tr v-for="(o, i) in observations.slice(0, 30)" :key="i" :class="{ 'error-box': outOfTolerance(o) }">
              <td>{{ featureLabel(o.feature_id) }}</td>
              <td class="hint">{{ o.obs_no }}</td>
              <td class="mono" :style="outOfTolerance(o) ? 'color: var(--danger); font-weight:600' : ''">{{ o.value }}</td>
              <td class="hint">{{ new Date(o.captured_at).toLocaleTimeString("it-IT") }}</td>
            </tr>
            <tr v-if="observations.length === 0"><td colspan="4" class="hint">Nessuna misura ancora per questo Run.</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </template>
  <div v-else-if="!loadingRun" class="hint">Seleziona o avvia un Run per iniziare la raccolta dati.</div>
</template>
