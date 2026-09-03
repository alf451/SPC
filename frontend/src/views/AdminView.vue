<script setup>
import { reactive, ref } from "vue";
import { usersApi } from "../api/users";
import { sitesApi, stationsApi } from "../api/stations";
import { daqDevicesApi, daqSourcesApi } from "../api/daq";

// Questa vista copre lo stesso ambito di admin/index.html (rimasto invariato,
// gia' collaudato) ma integrato nel frontend Vue principale, cosi' chi lavora
// gia' dentro l'app non deve aprire una pagina separata per configurare
// utenti/stazioni/dispositivi. admin/index.html resta disponibile come
// alternativa standalone (vedi docs/installazione.md).
const tab = ref("users");
const error = ref("");

// --- Utenti ---
const users = ref([]);
const newUser = reactive({ username: "", email: "", full_name: "", password: "" });
async function loadUsers() {
  users.value = await usersApi.list();
}
async function createUser() {
  error.value = "";
  try {
    await usersApi.create({ ...newUser, email: newUser.email || null, full_name: newUser.full_name || null });
    Object.assign(newUser, { username: "", email: "", full_name: "", password: "" });
    await loadUsers();
  } catch (e) {
    error.value = e.message || "Impossibile creare l'utente.";
  }
}

const editUser = reactive({}); // { [userId]: {email, full_name, status, password} }
function startEditUser(u) {
  editUser[u.id] = { email: u.email || "", full_name: u.full_name || "", status: u.status, password: "" };
}
async function saveUser(id) {
  error.value = "";
  try {
    const form = editUser[id];
    const payload = { email: form.email || null, full_name: form.full_name || null, status: form.status };
    if (form.password) payload.password = form.password;
    await usersApi.update(id, payload);
    delete editUser[id];
    await loadUsers();
  } catch (e) {
    error.value = e.message || "Impossibile salvare le modifiche.";
  }
}

// --- Sedi & Stazioni ---
const sites = ref([]);
const stations = ref([]);
const newSite = reactive({ name: "" });
const newStation = reactive({ site_id: "", name: "", computer_name: "" });
async function loadSitesAndStations() {
  [sites.value, stations.value] = await Promise.all([sitesApi.list(), stationsApi.list()]);
}
async function createSite() {
  error.value = "";
  try {
    await sitesApi.create({ name: newSite.name });
    newSite.name = "";
    await loadSitesAndStations();
  } catch (e) {
    error.value = e.message || "Impossibile creare la sede.";
  }
}

const editSite = reactive({}); // { [siteId]: {name} }
function startEditSite(s) {
  editSite[s.id] = { name: s.name };
}
async function saveSite(id) {
  error.value = "";
  try {
    await sitesApi.update(id, { name: editSite[id].name });
    delete editSite[id];
    await loadSitesAndStations();
  } catch (e) {
    error.value = e.message || "Impossibile salvare la sede.";
  }
}

const editStation = reactive({}); // { [stationId]: {site_id, name, computer_name} }
function startEditStation(s) {
  editStation[s.id] = { site_id: s.site_id, name: s.name, computer_name: s.computer_name || "" };
}
async function saveStation(id) {
  error.value = "";
  try {
    const form = editStation[id];
    await stationsApi.update(id, {
      site_id: Number(form.site_id),
      name: form.name,
      computer_name: form.computer_name || null,
    });
    delete editStation[id];
    await loadSitesAndStations();
  } catch (e) {
    error.value = e.message || "Impossibile salvare la stazione.";
  }
}

async function createStation() {
  error.value = "";
  try {
    await stationsApi.create({
      site_id: Number(newStation.site_id),
      name: newStation.name,
      computer_name: newStation.computer_name || null,
    });
    Object.assign(newStation, { site_id: "", name: "", computer_name: "" });
    await loadSitesAndStations();
  } catch (e) {
    error.value = e.message || "Impossibile creare la stazione.";
  }
}
async function removeStation(id) {
  if (!confirm("Eliminare questa stazione?")) return;
  await stationsApi.remove(id);
  await loadSitesAndStations();
}
function siteName(id) {
  return sites.value.find((s) => s.id === id)?.name || `#${id}`;
}

// --- Dispositivi DAQ ---
const devices = ref([]);
const sources = ref([]);
const newDevice = reactive({ name: "", connection_type: "rs232", terminator: "\\r\\n" });
const newSource = reactive({ station_id: "", device_id: "", name: "", port: "", channel_no: "" });
const portScan = reactive({ loading: false, agentConnected: null, ports: null, error: "" });

async function scanAvailablePorts() {
  if (!newSource.station_id) return;
  portScan.loading = true;
  portScan.error = "";
  portScan.ports = null;
  try {
    const res = await stationsApi.availablePorts(newSource.station_id);
    portScan.agentConnected = res.agent_connected;
    portScan.ports = res.ports;
  } catch (e) {
    portScan.error = e.message || "Impossibile interrogare la stazione.";
  } finally {
    portScan.loading = false;
  }
}

function usePort(device) {
  newSource.port = device;
}
const testResults = reactive({}); // { [sourceId]: {ok, message} }
async function loadDaq() {
  [devices.value, sources.value] = await Promise.all([daqDevicesApi.list(), daqSourcesApi.list()]);
}
async function createDevice() {
  error.value = "";
  try {
    await daqDevicesApi.create({ name: newDevice.name, connection_type: newDevice.connection_type, terminator: newDevice.terminator || null });
    Object.assign(newDevice, { name: "", connection_type: "rs232", terminator: "\\r\\n" });
    await loadDaq();
  } catch (e) {
    error.value = e.message || "Impossibile creare il dispositivo.";
  }
}

const editDevice = reactive({}); // { [deviceId]: {name, connection_type} }
function startEditDevice(d) {
  editDevice[d.id] = { name: d.name, connection_type: d.connection_type };
}
async function saveDevice(id) {
  error.value = "";
  try {
    await daqDevicesApi.update(id, editDevice[id]);
    delete editDevice[id];
    await loadDaq();
  } catch (e) {
    error.value = e.message || "Impossibile salvare il dispositivo.";
  }
}

const editSource = reactive({}); // { [sourceId]: {station_id, device_id, name, port, channel_no} }
function startEditSource(s) {
  editSource[s.id] = {
    station_id: s.station_id,
    device_id: s.device_id,
    name: s.name,
    port: s.port || "",
    channel_no: s.channel_no ?? "",
  };
}
async function saveSource(id) {
  error.value = "";
  try {
    const form = editSource[id];
    await daqSourcesApi.update(id, {
      station_id: Number(form.station_id),
      device_id: Number(form.device_id),
      name: form.name,
      port: form.port || null,
      channel_no: form.channel_no === "" ? null : Number(form.channel_no),
    });
    delete editSource[id];
    await loadDaq();
  } catch (e) {
    error.value = e.message || "Impossibile salvare la sorgente.";
  }
}

async function createSource() {
  error.value = "";
  try {
    await daqSourcesApi.create({
      station_id: Number(newSource.station_id),
      device_id: Number(newSource.device_id),
      name: newSource.name,
      port: newSource.port || null,
      channel_no: newSource.channel_no === "" ? null : Number(newSource.channel_no),
    });
    Object.assign(newSource, { station_id: "", device_id: "", name: "", port: "", channel_no: "" });
    await loadDaq();
  } catch (e) {
    error.value = e.message || "Impossibile creare la sorgente DAQ.";
  }
}
async function removeSource(id) {
  if (!confirm("Eliminare questa sorgente?")) return;
  await daqSourcesApi.remove(id);
  await loadDaq();
}
async function testSource(id) {
  testResults[id] = { ok: null, message: "Test in corso..." };
  try {
    testResults[id] = await daqSourcesApi.test(id);
  } catch (e) {
    testResults[id] = { ok: false, message: e.message || "Errore" };
  }
}
function deviceName(id) {
  return devices.value.find((d) => d.id === id)?.name || `#${id}`;
}

loadUsers();
loadSitesAndStations();
loadDaq();
</script>

<template>
  <div v-if="error" class="error-box">{{ error }}</div>

  <div style="margin-bottom: 16px; display: flex; gap: 8px">
    <button :class="{ primary: tab === 'users' }" @click="tab = 'users'">Utenti</button>
    <button :class="{ primary: tab === 'stations' }" @click="tab = 'stations'">Stazioni</button>
    <button :class="{ primary: tab === 'devices' }" @click="tab = 'devices'">Dispositivi</button>
  </div>

  <div v-if="tab === 'users'" class="panel">
    <div class="panel-head"><h3>Utenti</h3><span class="hint">{{ users.length }}</span></div>
    <table>
      <thead><tr><th>Utente</th><th>Nome</th><th>Email</th><th>Stato</th><th></th></tr></thead>
      <tbody>
        <template v-for="u in users" :key="u.id">
          <tr>
            <td class="mono">{{ u.username }}</td>
            <td>{{ u.full_name || "-" }}</td>
            <td class="hint">{{ u.email || "-" }}</td>
            <td><span class="badge" :class="u.status === 'active' ? 'ok' : 'neutral'">{{ u.status }}</span></td>
            <td><button @click="startEditUser(u)">Modifica</button></td>
          </tr>
          <tr v-if="editUser[u.id]">
            <td colspan="5">
              <div class="grid grid-2">
                <input v-model="editUser[u.id].full_name" placeholder="Nome completo" />
                <input v-model="editUser[u.id].email" placeholder="Email" />
                <select v-model="editUser[u.id].status">
                  <option value="active">active</option>
                  <option value="disabled">disabled</option>
                </select>
                <input v-model="editUser[u.id].password" type="password" placeholder="Nuova password (lascia vuoto per non cambiarla)" />
              </div>
              <button class="primary" style="margin-top: 6px" @click="saveUser(u.id)">Salva</button>
              <button style="margin-top: 6px" @click="delete editUser[u.id]">Annulla</button>
            </td>
          </tr>
        </template>
        <tr v-if="users.length === 0"><td colspan="5" class="hint">Nessun utente.</td></tr>
      </tbody>
    </table>
    <details style="margin-top: 12px">
      <summary class="hint" style="cursor: pointer">Nuovo utente</summary>
      <div class="grid grid-2" style="margin-top: 8px">
        <input v-model="newUser.username" placeholder="Utente" />
        <input v-model="newUser.password" type="password" placeholder="Password" />
        <input v-model="newUser.full_name" placeholder="Nome completo (opz.)" />
        <input v-model="newUser.email" placeholder="Email (opz.)" />
      </div>
      <button class="primary" style="margin-top: 8px" :disabled="!newUser.username || !newUser.password" @click="createUser">Crea</button>
    </details>
  </div>

  <div v-if="tab === 'stations'" class="grid grid-2">
    <div class="panel">
      <div class="panel-head"><h3>Sedi</h3></div>
      <table>
        <tbody>
          <template v-for="s in sites" :key="s.id">
            <tr>
              <td>{{ s.name }}</td>
              <td><button @click="startEditSite(s)">Modifica</button></td>
            </tr>
            <tr v-if="editSite[s.id]">
              <td colspan="2">
                <input v-model="editSite[s.id].name" style="width: 100%" />
                <button class="primary" style="margin-top: 6px" @click="saveSite(s.id)">Salva</button>
                <button style="margin-top: 6px" @click="delete editSite[s.id]">Annulla</button>
              </td>
            </tr>
          </template>
          <tr v-if="sites.length === 0"><td class="hint">Nessuna sede.</td></tr>
        </tbody>
      </table>
      <details style="margin-top: 12px">
        <summary class="hint" style="cursor: pointer">Nuova sede</summary>
        <input v-model="newSite.name" placeholder="Nome sede" style="width: 100%; margin-top: 8px" />
        <button class="primary" style="margin-top: 8px" :disabled="!newSite.name" @click="createSite">Crea</button>
      </details>
    </div>
    <div class="panel">
      <div class="panel-head"><h3>Stazioni</h3></div>
      <table>
        <thead><tr><th>Nome</th><th>Sede</th><th>PC</th><th></th></tr></thead>
        <tbody>
          <template v-for="s in stations" :key="s.id">
            <tr>
              <td>{{ s.name }}</td>
              <td class="hint">{{ siteName(s.site_id) }}</td>
              <td class="mono">{{ s.computer_name || "-" }}</td>
              <td>
                <button @click="startEditStation(s)">Modifica</button>
                <button class="danger" @click="removeStation(s.id)">Elimina</button>
              </td>
            </tr>
            <tr v-if="editStation[s.id]">
              <td colspan="4">
                <div class="grid grid-3">
                  <select v-model="editStation[s.id].site_id"><option v-for="site in sites" :key="site.id" :value="site.id">{{ site.name }}</option></select>
                  <input v-model="editStation[s.id].name" placeholder="Nome stazione" />
                  <input v-model="editStation[s.id].computer_name" placeholder="Nome PC (opz.)" />
                </div>
                <button class="primary" style="margin-top: 6px" @click="saveStation(s.id)">Salva</button>
                <button style="margin-top: 6px" @click="delete editStation[s.id]">Annulla</button>
              </td>
            </tr>
          </template>
          <tr v-if="stations.length === 0"><td colspan="4" class="hint">Nessuna stazione.</td></tr>
        </tbody>
      </table>
      <details style="margin-top: 12px">
        <summary class="hint" style="cursor: pointer">Nuova stazione</summary>
        <div class="grid grid-2" style="margin-top: 8px">
          <select v-model="newStation.site_id"><option value="">Sede</option><option v-for="s in sites" :key="s.id" :value="s.id">{{ s.name }}</option></select>
          <input v-model="newStation.name" placeholder="Nome stazione" />
          <input v-model="newStation.computer_name" placeholder="Nome PC (opz.)" />
        </div>
        <button class="primary" style="margin-top: 8px" :disabled="!newStation.site_id || !newStation.name" @click="createStation">Crea</button>
      </details>
    </div>
  </div>

  <div v-if="tab === 'devices'" class="grid grid-2">
    <div class="panel">
      <div class="panel-head"><h3>Profili dispositivo</h3></div>
      <table>
        <thead><tr><th>Nome</th><th>Tipo</th><th></th></tr></thead>
        <tbody>
          <template v-for="d in devices" :key="d.id">
            <tr>
              <td>{{ d.name }}</td>
              <td class="hint">{{ d.connection_type }}</td>
              <td><button @click="startEditDevice(d)">Modifica</button></td>
            </tr>
            <tr v-if="editDevice[d.id]">
              <td colspan="3">
                <div class="grid grid-2">
                  <input v-model="editDevice[d.id].name" placeholder="Nome" />
                  <select v-model="editDevice[d.id].connection_type">
                    <option value="rs232">RS232</option>
                    <option value="usb_hid">USB-HID</option>
                    <option value="manual">Manuale</option>
                    <option value="opcua">OPC-UA</option>
                    <option value="mtconnect">MTConnect</option>
                  </select>
                </div>
                <button class="primary" style="margin-top: 6px" @click="saveDevice(d.id)">Salva</button>
                <button style="margin-top: 6px" @click="delete editDevice[d.id]">Annulla</button>
              </td>
            </tr>
          </template>
          <tr v-if="devices.length === 0"><td colspan="3" class="hint">Nessun profilo.</td></tr>
        </tbody>
      </table>
      <details style="margin-top: 12px">
        <summary class="hint" style="cursor: pointer">Nuovo profilo dispositivo</summary>
        <div class="grid grid-2" style="margin-top: 8px">
          <input v-model="newDevice.name" placeholder="Nome" />
          <select v-model="newDevice.connection_type">
            <option value="rs232">RS232</option>
            <option value="usb_hid">USB-HID</option>
            <option value="manual">Manuale</option>
            <option value="opcua">OPC-UA</option>
            <option value="mtconnect">MTConnect</option>
          </select>
        </div>
        <button class="primary" style="margin-top: 8px" :disabled="!newDevice.name" @click="createDevice">Crea</button>
      </details>
    </div>
    <div class="panel">
      <div class="panel-head"><h3>Sorgenti DAQ</h3><span class="hint">porta/canale su una stazione</span></div>
      <table>
        <thead><tr><th>Nome</th><th>Porta</th><th>Dispositivo</th><th></th></tr></thead>
        <tbody>
          <template v-for="s in sources" :key="s.id">
            <tr>
              <td>{{ s.name }}</td>
              <td class="mono">{{ s.port || "-" }}<span v-if="s.channel_no != null"> / ch{{ s.channel_no }}</span></td>
              <td class="hint">{{ deviceName(s.device_id) }}</td>
              <td>
                <button @click="testSource(s.id)">Prova</button>
                <button @click="startEditSource(s)">Modifica</button>
                <button class="danger" @click="removeSource(s.id)">Elimina</button>
              </td>
            </tr>
            <tr v-if="testResults[s.id]">
              <td colspan="4">
                <span class="badge" :class="testResults[s.id].ok ? 'ok' : 'danger'">{{ testResults[s.id].ok ? "OK" : "Fallito" }}</span>
                <span class="hint" style="margin-left: 8px">{{ testResults[s.id].message }}</span>
              </td>
            </tr>
            <tr v-if="editSource[s.id]">
              <td colspan="4">
                <div class="grid grid-3">
                  <select v-model="editSource[s.id].station_id"><option v-for="st in stations" :key="st.id" :value="st.id">{{ st.name }}</option></select>
                  <select v-model="editSource[s.id].device_id"><option v-for="d in devices" :key="d.id" :value="d.id">{{ d.name }}</option></select>
                  <input v-model="editSource[s.id].name" placeholder="Nome sorgente" />
                  <input v-model="editSource[s.id].port" placeholder="Porta" />
                  <input v-model="editSource[s.id].channel_no" type="number" placeholder="Canale (opz.)" />
                </div>
                <button class="primary" style="margin-top: 6px" @click="saveSource(s.id)">Salva</button>
                <button style="margin-top: 6px" @click="delete editSource[s.id]">Annulla</button>
              </td>
            </tr>
          </template>
          <tr v-if="sources.length === 0"><td colspan="4" class="hint">Nessuna sorgente.</td></tr>
        </tbody>
      </table>
      <details style="margin-top: 12px">
        <summary class="hint" style="cursor: pointer">Nuova sorgente DAQ</summary>
        <div class="grid grid-2" style="margin-top: 8px">
          <select v-model="newSource.station_id"><option value="">Stazione</option><option v-for="s in stations" :key="s.id" :value="s.id">{{ s.name }}</option></select>
          <select v-model="newSource.device_id"><option value="">Dispositivo</option><option v-for="d in devices" :key="d.id" :value="d.id">{{ d.name }}</option></select>
          <input v-model="newSource.name" placeholder="Nome sorgente" />
          <input v-model="newSource.port" placeholder="Porta (es. COM3)" />
          <input v-model="newSource.channel_no" type="number" placeholder="Canale (opz.)" />
        </div>

        <button style="margin-top: 8px" :disabled="!newSource.station_id || portScan.loading" @click="scanAvailablePorts">
          {{ portScan.loading ? "Rilevamento..." : "Rileva porte disponibili sulla stazione" }}
        </button>
        <p class="hint" style="margin: 4px 0 0">Richiede l'Edge Agent gia' avviato su quella stazione (riporta le porte che vede lui in questo momento).</p>
        <div v-if="portScan.error" class="error-box" style="margin-top: 8px">{{ portScan.error }}</div>
        <div v-else-if="portScan.agentConnected === false" class="hint" style="margin-top: 8px">Nessun Edge Agent connesso per questa stazione in questo momento.</div>
        <div v-else-if="portScan.ports !== null" style="margin-top: 8px">
          <table v-if="portScan.ports.length">
            <thead><tr><th>Porta</th><th>Descrizione</th><th></th></tr></thead>
            <tbody>
              <tr v-for="p in portScan.ports" :key="p.device">
                <td class="mono">{{ p.device }}</td>
                <td class="hint">{{ p.description || p.hwid || "-" }}</td>
                <td><button @click="usePort(p.device)">Usa</button></td>
              </tr>
            </tbody>
          </table>
          <span v-else class="hint">L'agent e' connesso ma non vede nessuna porta seriale in questo momento.</span>
        </div>

        <button class="primary" style="margin-top: 8px" :disabled="!newSource.station_id || !newSource.device_id || !newSource.name" @click="createSource">Crea</button>
      </details>
    </div>
  </div>
</template>
