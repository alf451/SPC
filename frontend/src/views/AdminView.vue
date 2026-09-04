<script setup>
import { reactive, ref } from "vue";
import { usersApi } from "../api/users";
import { sitesApi, stationsApi } from "../api/stations";
import { daqDevicesApi, daqSourcesApi } from "../api/daq";
import { systemApi } from "../api/system";
import { dbBrowserApi } from "../api/dbBrowser";
import { notificationSettingsApi } from "../api/notifications";

// Questa vista copre lo stesso ambito di admin/index.html (rimasto invariato,
// gia' collaudato) ma integrato nel frontend Vue principale, cosi' chi lavora
// gia' dentro l'app non deve aprire una pagina separata per configurare
// utenti/stazioni/dispositivi. admin/index.html resta disponibile come
// alternativa standalone (vedi docs/guida-installazione-e-test.md).
const tab = ref("users");
const error = ref("");

// Un campo obbligatorio vuoto/solo spazi prende il bordo rosso finche' non
// viene compilato (vedi input.invalid in styles/base.css), poi torna al
// bordo di default da solo appena isBlank() ritorna false.
function isBlank(v) {
  return v === null || v === undefined || String(v).trim() === "";
}

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
async function removeUser(id) {
  if (!confirm("Eliminare questo utente?")) return;
  error.value = "";
  try {
    await usersApi.remove(id);
    await loadUsers();
  } catch (e) {
    error.value = e.message || "Impossibile eliminare l'utente.";
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
async function removeSite(id) {
  if (!confirm("Eliminare questa sede?")) return;
  error.value = "";
  try {
    await sitesApi.remove(id);
    await loadSitesAndStations();
  } catch (e) {
    error.value = e.message || "Impossibile eliminare la sede.";
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
  error.value = "";
  try {
    await stationsApi.remove(id);
    await loadSitesAndStations();
  } catch (e) {
    error.value = e.message || "Impossibile eliminare la stazione.";
  }
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
async function removeDevice(id) {
  if (!confirm("Eliminare questo profilo dispositivo?")) return;
  error.value = "";
  try {
    await daqDevicesApi.remove(id);
    await loadDaq();
  } catch (e) {
    error.value = e.message || "Impossibile eliminare il dispositivo.";
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
  error.value = "";
  try {
    await daqSourcesApi.remove(id);
    await loadDaq();
  } catch (e) {
    error.value = e.message || "Impossibile eliminare la sorgente.";
  }
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

// --- Info (versione e changelog) ---
const appVersion = ref("");
const changelogHtml = ref("");
async function loadInfo() {
  const [v, c] = await Promise.all([systemApi.version(), systemApi.changelog()]);
  appVersion.value = v.version;
  changelogHtml.value = markdownToHtml(c.markdown);
}
// Rendering minimale, senza dipendenze esterne: il changelog e' un file
// controllato da noi (non input utente), non serve un parser markdown vero.
function inlineMarkdown(text) {
  return text
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}
function markdownToHtml(md) {
  const lines = (md || "").split("\n");
  let html = "";
  let inList = false;
  const closeList = () => {
    if (inList) {
      html += "</ul>";
      inList = false;
    }
  };
  for (const line of lines) {
    if (line.startsWith("## ")) {
      closeList();
      html += `<h4 style="margin:18px 0 6px">${inlineMarkdown(line.slice(3))}</h4>`;
    } else if (line.startsWith("# ")) {
      closeList();
      html += `<h3 style="margin:0 0 8px">${inlineMarkdown(line.slice(2))}</h3>`;
    } else if (line.startsWith("- ")) {
      if (!inList) {
        html += "<ul style=\"margin:0 0 8px;padding-left:20px\">";
        inList = true;
      }
      html += `<li style="margin-bottom:4px">${inlineMarkdown(line.slice(2))}</li>`;
    } else if (line.trim() === "") {
      closeList();
    } else {
      closeList();
      html += `<p class="hint" style="margin:0 0 8px">${inlineMarkdown(line)}</p>`;
    }
  }
  closeList();
  return html;
}

// --- Database (esplorazione sola lettura, stile SSMS) ---
const dbTables = ref([]);
const dbSelectedTable = ref(null);
const dbColumns = ref([]);
const dbRows = ref([]);
const dbOffset = ref(0);
const DB_PAGE_SIZE = 50;
const dbApproxTotal = ref(0);
const dbLoading = ref(false);

async function loadDbTables() {
  dbTables.value = await dbBrowserApi.tables();
}
async function loadDbRows() {
  if (!dbSelectedTable.value) return;
  dbLoading.value = true;
  error.value = "";
  try {
    const res = await dbBrowserApi.rows(dbSelectedTable.value, { limit: DB_PAGE_SIZE, offset: dbOffset.value });
    dbColumns.value = res.columns;
    dbRows.value = res.rows;
    dbApproxTotal.value = res.approx_total;
  } catch (e) {
    error.value = e.message || "Impossibile leggere la tabella.";
  } finally {
    dbLoading.value = false;
  }
}
async function openDbTable(name) {
  dbSelectedTable.value = name;
  dbOffset.value = 0;
  await loadDbRows();
}
async function dbNextPage() {
  dbOffset.value += DB_PAGE_SIZE;
  await loadDbRows();
}
async function dbPrevPage() {
  dbOffset.value = Math.max(0, dbOffset.value - DB_PAGE_SIZE);
  await loadDbRows();
}
function formatCell(v) {
  if (v === null || v === undefined) return "";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

// --- Notifiche email (SMTP) ---
const notifSettings = reactive({
  smtp_host: "",
  smtp_port: 587,
  smtp_username: "",
  smtp_password: "",
  smtp_password_set: false,
  smtp_use_tls: true,
  from_email: "",
  to_email: "",
  notify_on_agent_disconnected: true,
  notify_on_system_error: true,
});
const notifOk = ref("");
const notifTesting = ref(false);

async function loadNotifSettings() {
  const s = await notificationSettingsApi.get();
  Object.assign(notifSettings, s, { smtp_password: "" });
}
async function saveNotifSettings() {
  error.value = "";
  notifOk.value = "";
  try {
    const { smtp_password_set, ...payload } = notifSettings;
    if (!payload.smtp_password) delete payload.smtp_password;
    const s = await notificationSettingsApi.update(payload);
    Object.assign(notifSettings, s, { smtp_password: "" });
    notifOk.value = "Impostazioni salvate.";
  } catch (e) {
    error.value = e.message || "Impossibile salvare le impostazioni.";
  }
}
async function testNotifSettings() {
  error.value = "";
  notifOk.value = "";
  notifTesting.value = true;
  try {
    await notificationSettingsApi.test();
    notifOk.value = "Email di prova inviata con successo.";
  } catch (e) {
    error.value = e.message || "Invio di prova fallito.";
  } finally {
    notifTesting.value = false;
  }
}

loadUsers();
loadSitesAndStations();
loadDaq();
loadInfo();
loadDbTables();
loadNotifSettings();
</script>

<template>
  <div v-if="error" class="error-box">{{ error }}</div>

  <div style="margin-bottom: 16px; display: flex; gap: 8px">
    <button :class="{ primary: tab === 'users' }" @click="tab = 'users'">Utenti</button>
    <button :class="{ primary: tab === 'stations' }" @click="tab = 'stations'">Stazioni</button>
    <button :class="{ primary: tab === 'devices' }" @click="tab = 'devices'">Dispositivi</button>
    <button :class="{ primary: tab === 'database' }" @click="tab = 'database'">Database</button>
    <button :class="{ primary: tab === 'notifications' }" @click="tab = 'notifications'">Notifiche</button>
    <button :class="{ primary: tab === 'info' }" @click="tab = 'info'">Info</button>
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
            <td>
              <button @click="startEditUser(u)">Modifica</button>
              <button class="danger" @click="removeUser(u.id)">Elimina</button>
            </td>
          </tr>
          <tr v-if="editUser[u.id]">
            <td colspan="5">
              <div class="grid grid-2">
                <div class="field">
                  <label>Nome completo</label>
                  <input v-model="editUser[u.id].full_name" />
                </div>
                <div class="field">
                  <label>Email</label>
                  <input v-model="editUser[u.id].email" />
                </div>
                <div class="field">
                  <label>Stato</label>
                  <select v-model="editUser[u.id].status">
                    <option value="active">active</option>
                    <option value="disabled">disabled</option>
                  </select>
                </div>
                <div class="field">
                  <label>Nuova password</label>
                  <input v-model="editUser[u.id].password" type="password" placeholder="lascia vuoto per non cambiarla" />
                </div>
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
        <div class="field">
          <label>Utente<span class="required-mark">*</span></label>
          <input v-model="newUser.username" :class="{ invalid: isBlank(newUser.username) }" />
        </div>
        <div class="field">
          <label>Password<span class="required-mark">*</span></label>
          <input v-model="newUser.password" type="password" :class="{ invalid: isBlank(newUser.password) }" />
        </div>
        <div class="field">
          <label>Nome completo</label>
          <input v-model="newUser.full_name" />
        </div>
        <div class="field">
          <label>Email</label>
          <input v-model="newUser.email" />
        </div>
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
              <td>
                <button @click="startEditSite(s)">Modifica</button>
                <button class="danger" @click="removeSite(s.id)">Elimina</button>
              </td>
            </tr>
            <tr v-if="editSite[s.id]">
              <td colspan="2">
                <div class="field">
                  <label>Nome<span class="required-mark">*</span></label>
                  <input v-model="editSite[s.id].name" :class="{ invalid: isBlank(editSite[s.id].name) }" style="width: 100%" />
                </div>
                <button class="primary" :disabled="isBlank(editSite[s.id].name)" @click="saveSite(s.id)">Salva</button>
                <button @click="delete editSite[s.id]">Annulla</button>
              </td>
            </tr>
          </template>
          <tr v-if="sites.length === 0"><td class="hint">Nessuna sede.</td></tr>
        </tbody>
      </table>
      <details style="margin-top: 12px">
        <summary class="hint" style="cursor: pointer">Nuova sede</summary>
        <div class="field" style="margin-top: 8px">
          <label>Nome<span class="required-mark">*</span></label>
          <input v-model="newSite.name" :class="{ invalid: isBlank(newSite.name) }" style="width: 100%" />
        </div>
        <button class="primary" :disabled="!newSite.name" @click="createSite">Crea</button>
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
                  <div class="field">
                    <label>Sede<span class="required-mark">*</span></label>
                    <select v-model="editStation[s.id].site_id" :class="{ invalid: isBlank(editStation[s.id].site_id) }">
                      <option v-for="site in sites" :key="site.id" :value="site.id">{{ site.name }}</option>
                    </select>
                  </div>
                  <div class="field">
                    <label>Nome stazione<span class="required-mark">*</span></label>
                    <input v-model="editStation[s.id].name" :class="{ invalid: isBlank(editStation[s.id].name) }" />
                  </div>
                  <div class="field">
                    <label>Nome PC</label>
                    <input v-model="editStation[s.id].computer_name" />
                  </div>
                </div>
                <button class="primary" :disabled="isBlank(editStation[s.id].site_id) || isBlank(editStation[s.id].name)" @click="saveStation(s.id)">Salva</button>
                <button @click="delete editStation[s.id]">Annulla</button>
              </td>
            </tr>
          </template>
          <tr v-if="stations.length === 0"><td colspan="4" class="hint">Nessuna stazione.</td></tr>
        </tbody>
      </table>
      <details style="margin-top: 12px">
        <summary class="hint" style="cursor: pointer">Nuova stazione</summary>
        <div class="grid grid-2" style="margin-top: 8px">
          <div class="field">
            <label>Sede<span class="required-mark">*</span></label>
            <select v-model="newStation.site_id" :class="{ invalid: isBlank(newStation.site_id) }">
              <option value="">-- scegli --</option>
              <option v-for="s in sites" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </div>
          <div class="field">
            <label>Nome stazione<span class="required-mark">*</span></label>
            <input v-model="newStation.name" :class="{ invalid: isBlank(newStation.name) }" />
          </div>
          <div class="field">
            <label>Nome PC</label>
            <input v-model="newStation.computer_name" />
          </div>
        </div>
        <button class="primary" :disabled="!newStation.site_id || !newStation.name" @click="createStation">Crea</button>
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
              <td>
                <button @click="startEditDevice(d)">Modifica</button>
                <button class="danger" @click="removeDevice(d.id)">Elimina</button>
              </td>
            </tr>
            <tr v-if="editDevice[d.id]">
              <td colspan="3">
                <div class="grid grid-2">
                  <div class="field">
                    <label>Nome<span class="required-mark">*</span></label>
                    <input v-model="editDevice[d.id].name" :class="{ invalid: isBlank(editDevice[d.id].name) }" />
                  </div>
                  <div class="field">
                    <label>Tipo connessione<span class="required-mark">*</span></label>
                    <select v-model="editDevice[d.id].connection_type">
                      <option value="rs232">RS232</option>
                      <option value="usb_hid">USB-HID</option>
                      <option value="manual">Manuale</option>
                      <option value="opcua">OPC-UA</option>
                      <option value="mtconnect">MTConnect</option>
                    </select>
                  </div>
                </div>
                <button class="primary" :disabled="isBlank(editDevice[d.id].name)" @click="saveDevice(d.id)">Salva</button>
                <button @click="delete editDevice[d.id]">Annulla</button>
              </td>
            </tr>
          </template>
          <tr v-if="devices.length === 0"><td colspan="3" class="hint">Nessun profilo.</td></tr>
        </tbody>
      </table>
      <details style="margin-top: 12px">
        <summary class="hint" style="cursor: pointer">Nuovo profilo dispositivo</summary>
        <div class="grid grid-2" style="margin-top: 8px">
          <div class="field">
            <label>Nome<span class="required-mark">*</span></label>
            <input v-model="newDevice.name" :class="{ invalid: isBlank(newDevice.name) }" />
          </div>
          <div class="field">
            <label>Tipo connessione<span class="required-mark">*</span></label>
            <select v-model="newDevice.connection_type">
              <option value="rs232">RS232</option>
              <option value="usb_hid">USB-HID</option>
              <option value="manual">Manuale</option>
              <option value="opcua">OPC-UA</option>
              <option value="mtconnect">MTConnect</option>
            </select>
          </div>
        </div>
        <button class="primary" :disabled="!newDevice.name" @click="createDevice">Crea</button>
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
                  <div class="field">
                    <label>Stazione<span class="required-mark">*</span></label>
                    <select v-model="editSource[s.id].station_id" :class="{ invalid: isBlank(editSource[s.id].station_id) }">
                      <option v-for="st in stations" :key="st.id" :value="st.id">{{ st.name }}</option>
                    </select>
                  </div>
                  <div class="field">
                    <label>Dispositivo<span class="required-mark">*</span></label>
                    <select v-model="editSource[s.id].device_id" :class="{ invalid: isBlank(editSource[s.id].device_id) }">
                      <option v-for="d in devices" :key="d.id" :value="d.id">{{ d.name }}</option>
                    </select>
                  </div>
                  <div class="field">
                    <label>Nome sorgente<span class="required-mark">*</span></label>
                    <input v-model="editSource[s.id].name" :class="{ invalid: isBlank(editSource[s.id].name) }" />
                  </div>
                  <div class="field">
                    <label>Porta</label>
                    <input v-model="editSource[s.id].port" />
                  </div>
                  <div class="field">
                    <label>Canale</label>
                    <input v-model="editSource[s.id].channel_no" type="number" />
                  </div>
                </div>
                <button class="primary" :disabled="isBlank(editSource[s.id].station_id) || isBlank(editSource[s.id].device_id) || isBlank(editSource[s.id].name)" @click="saveSource(s.id)">Salva</button>
                <button @click="delete editSource[s.id]">Annulla</button>
              </td>
            </tr>
          </template>
          <tr v-if="sources.length === 0"><td colspan="4" class="hint">Nessuna sorgente.</td></tr>
        </tbody>
      </table>
      <details style="margin-top: 12px">
        <summary class="hint" style="cursor: pointer">Nuova sorgente DAQ</summary>
        <div class="grid grid-2" style="margin-top: 8px">
          <div class="field">
            <label>Stazione<span class="required-mark">*</span></label>
            <select v-model="newSource.station_id" :class="{ invalid: isBlank(newSource.station_id) }">
              <option value="">-- scegli --</option>
              <option v-for="s in stations" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </div>
          <div class="field">
            <label>Dispositivo<span class="required-mark">*</span></label>
            <select v-model="newSource.device_id" :class="{ invalid: isBlank(newSource.device_id) }">
              <option value="">-- scegli --</option>
              <option v-for="d in devices" :key="d.id" :value="d.id">{{ d.name }}</option>
            </select>
          </div>
          <div class="field">
            <label>Nome sorgente<span class="required-mark">*</span></label>
            <input v-model="newSource.name" :class="{ invalid: isBlank(newSource.name) }" />
          </div>
          <div class="field">
            <label>Porta</label>
            <input v-model="newSource.port" placeholder="es. COM3" />
          </div>
          <div class="field">
            <label>Canale</label>
            <input v-model="newSource.channel_no" type="number" />
          </div>
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

  <div v-if="tab === 'database'" class="grid grid-2">
    <div class="panel">
      <div class="panel-head"><h3>Tabelle</h3><span class="hint">{{ dbTables.length }}</span></div>
      <p class="hint" style="margin-top: -4px">Sola lettura — conteggio righe approssimato.</p>
      <table>
        <tbody>
          <tr
            v-for="t in dbTables"
            :key="t.name"
            class="tree-item"
            :class="{ sel: t.name === dbSelectedTable }"
            style="cursor: pointer"
            @click="openDbTable(t.name)"
          >
            <td class="mono">{{ t.name }}</td>
            <td class="hint" style="text-align: right">{{ t.approx_rows }}</td>
          </tr>
          <tr v-if="dbTables.length === 0"><td class="hint">Nessuna tabella.</td></tr>
        </tbody>
      </table>
    </div>
    <div class="panel">
      <div class="panel-head">
        <h3>{{ dbSelectedTable || "-- seleziona una tabella --" }}</h3>
        <span v-if="dbSelectedTable" class="hint">righe {{ dbOffset + 1 }}-{{ dbOffset + dbRows.length }} di ~{{ dbApproxTotal }}</span>
      </div>
      <div v-if="dbLoading" class="hint">Caricamento...</div>
      <div v-else-if="dbSelectedTable" style="overflow-x: auto">
        <table>
          <thead>
            <tr><th v-for="c in dbColumns" :key="c">{{ c }}</th></tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in dbRows" :key="i">
              <td v-for="c in dbColumns" :key="c" class="mono">{{ formatCell(r[c]) }}</td>
            </tr>
            <tr v-if="dbRows.length === 0"><td :colspan="dbColumns.length || 1" class="hint">Nessuna riga.</td></tr>
          </tbody>
        </table>
        <div style="margin-top: 10px; display: flex; gap: 8px">
          <button :disabled="dbOffset === 0" @click="dbPrevPage">&larr; Precedenti</button>
          <button :disabled="dbOffset + dbRows.length >= dbApproxTotal" @click="dbNextPage">Successive &rarr;</button>
        </div>
      </div>
      <div v-else class="hint">Seleziona una tabella dall'elenco a sinistra.</div>
    </div>
  </div>

  <div v-if="tab === 'notifications'" class="panel" style="max-width: 640px">
    <div class="panel-head"><h3>Notifiche email</h3></div>
    <p class="hint" style="margin-top: -6px">
      Usate per: richieste di assistenza inviate dall'app, Edge Agent disconnesso, errori di sistema.
    </p>
    <div v-if="notifOk" class="badge ok" style="display: block; padding: 8px 12px; margin-bottom: 12px; width: fit-content">{{ notifOk }}</div>
    <div class="grid grid-2">
      <div class="field">
        <label>Host SMTP</label>
        <input v-model="notifSettings.smtp_host" placeholder="es. smtp.gmail.com" />
      </div>
      <div class="field">
        <label>Porta</label>
        <input v-model.number="notifSettings.smtp_port" type="number" />
      </div>
      <div class="field">
        <label>Utente SMTP</label>
        <input v-model="notifSettings.smtp_username" />
      </div>
      <div class="field">
        <label>Password SMTP</label>
        <input
          v-model="notifSettings.smtp_password"
          type="password"
          :placeholder="notifSettings.smtp_password_set ? 'già impostata — lascia vuoto per non cambiarla' : ''"
        />
      </div>
      <div class="field">
        <label>Mittente (From)</label>
        <input v-model="notifSettings.from_email" placeholder="opzionale, altrimenti usa l'utente SMTP" />
      </div>
      <div class="field">
        <label>Destinatario</label>
        <input v-model="notifSettings.to_email" />
      </div>
    </div>
    <label style="display: block; margin-top: 8px">
      <input v-model="notifSettings.smtp_use_tls" type="checkbox" /> Usa STARTTLS
    </label>
    <label style="display: block; margin-top: 4px">
      <input v-model="notifSettings.notify_on_agent_disconnected" type="checkbox" /> Avvisa quando un Edge Agent si disconnette
    </label>
    <label style="display: block; margin-top: 4px">
      <input v-model="notifSettings.notify_on_system_error" type="checkbox" /> Avvisa in caso di errore di sistema
    </label>
    <div style="margin-top: 12px; display: flex; gap: 8px">
      <button class="primary" @click="saveNotifSettings">Salva</button>
      <button :disabled="notifTesting" @click="testNotifSettings">{{ notifTesting ? "Invio in corso..." : "Invia email di prova" }}</button>
    </div>
  </div>

  <div v-if="tab === 'info'" class="panel">
    <div class="panel-head">
      <h3>leank SPC</h3>
      <span class="badge ok">v{{ appVersion }}</span>
    </div>
    <div v-html="changelogHtml"></div>
  </div>
</template>
