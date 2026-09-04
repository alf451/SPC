<script setup>
import { reactive, ref, watch } from "vue";
import { partsApi } from "../api/parts";
import { routinesApi } from "../api/routines";
import { featuresApi } from "../api/features";
import { daqSourcesApi, featureDaqBindingsApi } from "../api/daq";

const parts = ref([]);
const routines = ref([]);
const selectedPartId = ref(null);
const features = ref([]);
const daqSources = ref([]);
const error = ref("");
const bindOk = ref(""); // messaggio di conferma transitorio dopo un collegamento riuscito

const newPart = reactive({ name: "", description: "" });
const newRoutine = reactive({ name: "" });
const newFeature = reactive({ name: "", feature_type: "variable", target: "", lower_tolerance_limit: "", upper_tolerance_limit: "" });
const bindForm = reactive({ routine_id: "", feature_id: "", order_no: 0 });
const daqBindForm = reactive({ routine_id: "", feature_id: "", daq_source_id: "" });
const editVersion = reactive({}); // { [featureId]: { target, lower_tolerance_limit, upper_tolerance_limit } }

async function loadParts() {
  parts.value = await partsApi.list();
}
async function loadRoutines() {
  routines.value = await routinesApi.list();
}
async function loadDaqSources() {
  daqSources.value = await daqSourcesApi.list();
}

async function createPart() {
  error.value = "";
  try {
    const created = await partsApi.create({ name: newPart.name, description: newPart.description || null });
    newPart.name = "";
    newPart.description = "";
    await loadParts();
    selectedPartId.value = created.id;
  } catch (e) {
    error.value = e.message || "Impossibile creare il Part.";
  }
}

async function createRoutine() {
  error.value = "";
  try {
    await routinesApi.create({ name: newRoutine.name });
    newRoutine.name = "";
    await loadRoutines();
  } catch (e) {
    error.value = e.message || "Impossibile creare la Routine.";
  }
}

async function createFeature() {
  if (!selectedPartId.value) return;
  error.value = "";
  try {
    const properties =
      newFeature.target !== "" || newFeature.lower_tolerance_limit !== "" || newFeature.upper_tolerance_limit !== ""
        ? {
            target: newFeature.target === "" ? null : Number(newFeature.target),
            lower_tolerance_limit: newFeature.lower_tolerance_limit === "" ? null : Number(newFeature.lower_tolerance_limit),
            upper_tolerance_limit: newFeature.upper_tolerance_limit === "" ? null : Number(newFeature.upper_tolerance_limit),
          }
        : null;
    await featuresApi.create({
      part_id: selectedPartId.value,
      feature_type: newFeature.feature_type,
      name: newFeature.name,
      properties,
    });
    newFeature.name = "";
    newFeature.target = "";
    newFeature.lower_tolerance_limit = "";
    newFeature.upper_tolerance_limit = "";
    await loadFeatures();
  } catch (e) {
    error.value = e.message || "Impossibile creare la Feature.";
  }
}

async function loadFeatures() {
  if (!selectedPartId.value) {
    features.value = [];
    return;
  }
  features.value = await featuresApi.listByPart(selectedPartId.value);
}
watch(selectedPartId, loadFeatures);

function startEditVersion(feature) {
  const p = feature.current_properties;
  editVersion[feature.id] = {
    target: p?.target ?? "",
    lower_tolerance_limit: p?.lower_tolerance_limit ?? "",
    upper_tolerance_limit: p?.upper_tolerance_limit ?? "",
  };
}

async function saveNewVersion(feature) {
  const form = editVersion[feature.id];
  error.value = "";
  try {
    await featuresApi.addPropertyVersion(feature.id, {
      target: form.target === "" ? null : Number(form.target),
      lower_tolerance_limit: form.lower_tolerance_limit === "" ? null : Number(form.lower_tolerance_limit),
      upper_tolerance_limit: form.upper_tolerance_limit === "" ? null : Number(form.upper_tolerance_limit),
    });
    delete editVersion[feature.id];
    await loadFeatures();
  } catch (e) {
    error.value = e.message || "Impossibile salvare la nuova versione.";
  }
}

async function bindFeature() {
  if (!bindForm.routine_id || !bindForm.feature_id) return;
  error.value = "";
  bindOk.value = "";
  try {
    await routinesApi.setFeatureBinding(Number(bindForm.routine_id), Number(bindForm.feature_id), {
      order_no: Number(bindForm.order_no) || 0,
    });
    bindOk.value = "Feature aggiunta alla Routine.";
  } catch (e) {
    error.value = e.message || "Impossibile collegare la Feature alla Routine.";
  }
}

function daqSourceLabel(s) {
  return `${s.name} (${s.port || "?"}${s.channel_no != null ? " / ch" + s.channel_no : ""})`;
}

async function bindFeatureDaq() {
  if (!daqBindForm.routine_id || !daqBindForm.feature_id || !daqBindForm.daq_source_id) return;
  error.value = "";
  bindOk.value = "";
  try {
    await featureDaqBindingsApi.set({
      routine_id: Number(daqBindForm.routine_id),
      feature_id: Number(daqBindForm.feature_id),
      daq_source_id: Number(daqBindForm.daq_source_id),
    });
    bindOk.value = "Sorgente DAQ collegata: le misure in arrivo da quella porta verranno assegnate a questa Feature per questa Routine.";
  } catch (e) {
    error.value = e.message || "Impossibile collegare la sorgente DAQ alla Feature.";
  }
}

loadParts();
loadRoutines();
loadDaqSources();
</script>

<template>
  <div v-if="error" class="error-box">{{ error }}</div>
  <div v-if="bindOk" class="badge ok" style="display: block; padding: 8px 12px; margin-bottom: 12px; width: fit-content">{{ bindOk }}</div>

  <div class="config-grid grid grid-2">
    <div class="panel">
      <div class="panel-head"><h3>Part</h3></div>
      <table>
        <tbody>
          <tr v-for="p in parts" :key="p.id" class="tree-item" :class="{ sel: p.id === selectedPartId }" style="cursor: pointer" @click="selectedPartId = p.id">
            <td>{{ p.name }}</td>
          </tr>
          <tr v-if="parts.length === 0"><td class="hint">Nessun Part ancora.</td></tr>
        </tbody>
      </table>
      <details style="margin-top: 12px">
        <summary class="hint" style="cursor: pointer">Nuovo Part</summary>
        <div class="field"><label>Nome</label><input v-model="newPart.name" style="width: 100%" /></div>
        <div class="field"><label>Descrizione</label><input v-model="newPart.description" style="width: 100%" /></div>
        <button class="primary" :disabled="!newPart.name" @click="createPart">Crea</button>
      </details>

      <div class="panel-head" style="margin-top: 18px"><h3>Routine</h3></div>
      <table>
        <tbody>
          <tr v-for="r in routines" :key="r.id"><td>{{ r.name }}</td></tr>
          <tr v-if="routines.length === 0"><td class="hint">Nessuna Routine ancora.</td></tr>
        </tbody>
      </table>
      <details style="margin-top: 12px">
        <summary class="hint" style="cursor: pointer">Nuova Routine</summary>
        <div class="field"><label>Nome</label><input v-model="newRoutine.name" style="width: 100%" /></div>
        <button class="primary" :disabled="!newRoutine.name" @click="createRoutine">Crea</button>
      </details>

      <div class="panel-head" style="margin-top: 18px"><h3>Aggiungi Feature alla Routine</h3></div>
      <p class="hint" style="margin: -6px 0 8px">Solo l'ordine di collaudo delle Feature in questa Routine — non collega ancora nessuno strumento (per quello vedi sotto).</p>
      <div class="grid grid-3">
        <select v-model="bindForm.routine_id"><option value="">Routine</option><option v-for="r in routines" :key="r.id" :value="r.id">{{ r.name }}</option></select>
        <select v-model="bindForm.feature_id"><option value="">Feature</option><option v-for="f in features" :key="f.id" :value="f.id">{{ f.name }}</option></select>
        <input v-model="bindForm.order_no" type="number" placeholder="Ordine" />
      </div>
      <button class="primary" style="margin-top: 8px" @click="bindFeature">Aggiungi</button>

      <div class="panel-head" style="margin-top: 18px"><h3>Collega Feature &rarr; Sorgente DAQ</h3></div>
      <p class="hint" style="margin: -6px 0 8px">Questo e' il collegamento che serve perche' le misure di uno strumento arrivino alla Feature giusta durante un Run. Senza questo, l'Edge Agent invia le letture ma il backend non sa a quale Feature assegnarle.</p>
      <div class="grid grid-3">
        <select v-model="daqBindForm.routine_id"><option value="">Routine</option><option v-for="r in routines" :key="r.id" :value="r.id">{{ r.name }}</option></select>
        <select v-model="daqBindForm.feature_id"><option value="">Feature</option><option v-for="f in features" :key="f.id" :value="f.id">{{ f.name }}</option></select>
        <select v-model="daqBindForm.daq_source_id"><option value="">Sorgente DAQ</option><option v-for="s in daqSources" :key="s.id" :value="s.id">{{ daqSourceLabel(s) }}</option></select>
      </div>
      <button class="primary" style="margin-top: 8px" :disabled="!daqBindForm.routine_id || !daqBindForm.feature_id || !daqBindForm.daq_source_id" @click="bindFeatureDaq">Collega</button>
    </div>

    <div class="panel">
      <div class="panel-head">
        <h3>Feature{{ selectedPartId ? "" : " (seleziona un Part)" }}</h3>
        <span class="hint">quote/tolleranze versionate</span>
      </div>
      <table v-if="selectedPartId">
        <thead><tr><th>Nome</th><th>Tipo</th><th>Versione corrente</th><th></th></tr></thead>
        <tbody>
          <template v-for="f in features" :key="f.id">
            <tr>
              <td>{{ f.name }}</td>
              <td class="hint">{{ f.feature_type }}</td>
              <td class="mono">
                <template v-if="f.current_properties">
                  {{ f.current_properties.lower_tolerance_limit ?? "-" }} / [{{ f.current_properties.target ?? "-" }}] / {{ f.current_properties.upper_tolerance_limit ?? "-" }}
                  <span class="hint">(v{{ f.current_properties.version_no }})</span>
                </template>
                <span v-else class="hint">nessuna versione</span>
              </td>
              <td><button @click="startEditVersion(f)">Nuova versione</button></td>
            </tr>
            <tr v-if="editVersion[f.id]">
              <td colspan="4">
                <div class="grid grid-3">
                  <input v-model="editVersion[f.id].lower_tolerance_limit" placeholder="Limite inf." type="number" step="any" />
                  <input v-model="editVersion[f.id].target" placeholder="Target" type="number" step="any" />
                  <input v-model="editVersion[f.id].upper_tolerance_limit" placeholder="Limite sup." type="number" step="any" />
                </div>
                <button class="primary" style="margin-top: 6px" @click="saveNewVersion(f)">Salva nuova versione</button>
                <button style="margin-top: 6px" @click="delete editVersion[f.id]">Annulla</button>
              </td>
            </tr>
          </template>
          <tr v-if="features.length === 0"><td colspan="4" class="hint">Nessuna Feature per questo Part.</td></tr>
        </tbody>
      </table>

      <details v-if="selectedPartId" style="margin-top: 14px">
        <summary class="hint" style="cursor: pointer">Nuova Feature</summary>
        <div class="grid grid-2" style="margin-top: 8px">
          <input v-model="newFeature.name" placeholder="Nome" />
          <select v-model="newFeature.feature_type">
            <option value="variable">Variabile</option>
            <option value="attribute">Attributiva</option>
          </select>
        </div>
        <div class="grid grid-3" style="margin-top: 8px">
          <input v-model="newFeature.lower_tolerance_limit" placeholder="Limite inf. (opz.)" type="number" step="any" />
          <input v-model="newFeature.target" placeholder="Target (opz.)" type="number" step="any" />
          <input v-model="newFeature.upper_tolerance_limit" placeholder="Limite sup. (opz.)" type="number" step="any" />
        </div>
        <button class="primary" style="margin-top: 8px" :disabled="!newFeature.name" @click="createFeature">Crea Feature</button>
      </details>
    </div>
  </div>
</template>
