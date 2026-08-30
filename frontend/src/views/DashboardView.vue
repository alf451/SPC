<script setup>
import { computed, onMounted, ref } from "vue";
import { stationsApi } from "../api/stations";
import { runsApi } from "../api/runs";

const stations = ref([]);
const activeRuns = ref([]);
const loading = ref(true);
const error = ref("");

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [stationList, runList] = await Promise.all([
      stationsApi.list(),
      runsApi.list({ status_filter: "in_progress" }),
    ]);
    stations.value = stationList;
    activeRuns.value = runList;
  } catch (e) {
    error.value = e.message || "Errore nel caricamento del cruscotto.";
  } finally {
    loading.value = false;
  }
}

onMounted(load);

const runsByStation = computed(() => {
  const map = {};
  for (const run of activeRuns.value) {
    (map[run.station_id] ||= []).push(run);
  }
  return map;
});
</script>

<template>
  <div v-if="error" class="error-box">{{ error }}</div>

  <div class="grid grid-3" style="margin-bottom: 20px">
    <div class="panel kpi">
      <div class="label">Stazioni</div>
      <div class="value">{{ stations.length }}</div>
      <div class="sub">registrate nel sistema</div>
    </div>
    <div class="panel kpi">
      <div class="label">Run attivi</div>
      <div class="value">{{ activeRuns.length }}</div>
      <div class="sub">in raccolta dati ora</div>
    </div>
    <div class="panel kpi">
      <div class="label">Avvisi</div>
      <div class="value">0</div>
      <div class="sub">nessun avviso configurato ancora</div>
    </div>
  </div>

  <div class="panel">
    <div class="panel-head">
      <h3>Stazioni</h3>
      <span class="hint">{{ loading ? "caricamento..." : "aggiornato ora" }}</span>
    </div>
    <table>
      <thead>
        <tr>
          <th>Nome</th>
          <th>Sede</th>
          <th>Stato</th>
          <th>Run attivi</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="s in stations" :key="s.id">
          <td>{{ s.name }}</td>
          <td class="hint">{{ s.site_id }}</td>
          <td><span class="badge" :class="s.status === 'active' ? 'ok' : 'neutral'">{{ s.status }}</span></td>
          <td>{{ (runsByStation[s.id] || []).map((r) => r.name).join(", ") || "-" }}</td>
        </tr>
        <tr v-if="!loading && stations.length === 0">
          <td colspan="4" class="hint">Nessuna stazione configurata - vai su "Amministrazione" per crearne una.</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
