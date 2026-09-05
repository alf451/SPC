# Edge Agent — guida rapida

Legge le misure da uno o più strumenti Digimatic (RS232 o USB-ITN) collegati al PC e le invia al backend leank-spc via WebSocket. Vedi [`../docs/api.md`](../docs/api.md) per il protocollo completo e [`../docs/guida-installazione-e-test.md`](../docs/guida-installazione-e-test.md) per l'installazione del backend.

## Setup (PC con backend già installato in modalità pilot)

Se il backend è già installato in `installer\` (modalità pilot), l'Edge Agent può riusare lo stesso Python — non serve installarne un altro:

```powershell
cd edge-agent
..\runtime\python\python.exe -m pip install -r requirements.txt
copy config.example.yaml config.yaml
notepad config.yaml   # impostare sede/stazione (o station_id), port(e) COM, ecc.
```

## Configurare la stazione (per nome, consigliato)

Nel `config.yaml`, invece di cercare/copiare a mano uno `station_id` numerico (facile sbagliarlo — vedi [`problemi-riscontrati.md`](../docs/problemi-riscontrati.md)), basta indicare sede e nome **esattamente come compaiono in Amministrazione → Stazioni**:

```yaml
station:
  site_name: "Mopla"
  name: "SCQ3"
  # computer_name: se omesso, rilevato automaticamente (nome di questo PC)
```

Al primo avvio l'agent chiama da solo `POST /api/stations/resolve`: se sede/stazione non esistono ancora le crea, altrimenti riusa quelle esistenti — idempotente, si può rilanciare senza creare doppioni. Se preferisci indicare direttamente un id numerico già noto, usa `station_id: 2` al posto del blocco `station:` (ha la precedenza se presente).

Se invece l'Edge Agent gira su un **PC diverso** dalla stazione dove c'è il backend (altra postazione della stessa officina), serve un Python 3.11+ locale a quel PC (embeddable o installato normalmente) e la rete deve raggiungere il backend — vedi [le tre modalità di rete](../docs/guida-installazione-e-test.md#le-tre-modalità-di-rete-valgono-su-entrambi-i-sistemi-operativi), da superare prima di questo scenario.

## Ottenere il token per config.yaml

L'Edge Agent si autentica con lo stesso JWT usato dalle API REST. Il modo più semplice per ottenerne uno, con il backend avviato (`installer\start.cmd`):

1. Aprire [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
2. `POST /api/auth/login` → username `admin`, password da `runtime\secrets\admin_password.txt`
3. Copiare `access_token` dalla risposta in `config.yaml` → `backend.token`

Nota: l'access token scade (default 30 minuti, vedi `ACCESS_TOKEN_EXPIRE_MINUTES` in `backend/.env`) — per un test rapido va bene, ma per un uso prolungato meglio creare un utente/account dedicato all'agent con scadenza più lunga, oppure implementare il refresh automatico nel `ws_client.py` (oggi non c'è, è un TODO).

## Configurare una sorgente RS232

Nel `config.yaml`, sezione `sources`, un blocco per porta:

```yaml
- type: rs232
  port: "COM3"          # vedi Gestione Dispositivi di Windows -> Porte (COM e LPT)
  channel_no: null       # valorizzare solo se lo strumento è su un box multiplex a più canali
  baud_rate: 9600         # verificare sul manuale del convertitore/box
  data_bits: 7
  parity: "E"
  stop_bits: 1
  mode: "push"            # "push": lo strumento invia da solo alla pressione di DATA
  frame_terminator: "\r\n"
```

**Ricevitore multi-canale su una sola porta** (es. Mitutoyo U-Wave-R con più trasmettitori abbinati): non usare più blocchi con lo stesso `port` (fallirebbe, una porta si apre una volta sola) — usa invece `channels: [10000, 10001, ...]` + `frame_format: "uwave"` in un unico blocco. Vedi [`../docs/test-mitutoyo-uwave.md`](../docs/test-mitutoyo-uwave.md) per il formato di frame confermato via cattura reale, e [`config.example.yaml`](../config.example.yaml) per l'esempio completo.

**Prima connessione reale**: il formato esatto del frame (quello che arriva sulla porta quando si preme DATA) va verificato — vedi il TODO in `edge_agent/sources/digimatic_rs232.py::parse_digimatic_frame`. Il modo più rapido per vederlo senza scrivere codice: [`tools/serial-monitor.html`](tools/serial-monitor.html) — pagina standalone (Chrome/Edge) che apre la porta dal browser, mostra ogni byte in hex/ASCII e prova subito il riconoscimento numerico con la stessa regex del parser reale (dettagli in `tools/README.md`). In alternativa un terminale seriale generico (es. PuTTY in modalità Serial, stessi parametri baud/parity/stopbits).

## Configurare una sorgente USB-ITN

```yaml
- type: usb_hid
  device_path: null       # lasciare null per il fallback "hook tastiera globale"
  poll_interval_ms: 50
```

Se sul PC è collegato **un solo** convertitore USB-ITN, `device_path: null` va bene. Se ce n'è più di uno, serve il path hidapi specifico del dispositivo — vedi il TODO in `edge_agent/sources/digimatic_usb_hid.py`.

## Test senza hardware

```yaml
sources:
  - type: mock
    port: "MOCK1"
    center: 10.0
    spread: 0.05
    interval_seconds: 2
```

Genera letture finte ogni 2 secondi — utile per verificare che il collegamento al backend e il flusso outbox funzionino prima di collegare uno strumento vero.

## Avvio

```powershell
..\runtime\python\python.exe -m edge_agent.main config.yaml
```

Log a video; `Ctrl+C` per fermare. Le letture non ancora confermate dal server restano in `outbox.sqlite3` e vengono reinviate automaticamente alla riconnessione — non serve fare nulla manualmente dopo un'interruzione di rete.

## "Prova collegamento" dal pannello admin

Il [pannello admin](../admin/index.html) ha un pulsante "Prova" per ogni sorgente DAQ configurata: chiede a questo Edge Agent (se connesso) lo stato reale della porta. Non forza una lettura — in modalità `push` non è possibile senza premere il tasto DATA sullo strumento — riporta invece se la porta è aperta e quando è arrivata l'ultima lettura, leggendo lo stato che `main.py::run_source` tiene aggiornato su ogni `Source` (`is_connected`, `last_reading_at`, `last_raw`). Vedi il protocollo `test_source`/`test_result` in `docs/api.md`.

## Rilevamento porte disponibili (v0.3)

Ad ogni connessione, l'agent riporta al backend anche l'elenco di **tutte** le porte seriali che vede sul PC in quel momento (`port_scan.py`, via `serial.tools.list_ports` — non solo quelle già configurate in `config.yaml`). Serve a chi configura una sorgente DAQ dal pannello Amministrazione/admin: vede un elenco reale ("COM3 - U-WAVE Virtual COM Port") invece di doverlo scoprire da Gestione dispositivi via RDP. Nessuna configurazione richiesta - avviene automaticamente ad ogni `hello`. Vedi `GET /api/stations/{id}/available-ports` in `docs/api.md`.
