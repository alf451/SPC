# Changelog

Registro delle versioni rilasciate. La versione corrente è mostrata anche in **Amministrazione → Info** nel frontend (letta da `backend/app/version.py`).

## 0.7.1

- **Fix — formato reale del frame U-Wave finalmente confermato** (cattura diretta su hardware reale, 3 strumenti su un ricevitore): il parser generico avrebbe estratto il codice canale ("10000") al posto del valore vero ("+11.88"), e trattato i messaggi di stato (`ST`/`TI`) come letture invalide invece di ignorarli. Aggiunto un parser dedicato (`parse_uwave_frame`, `frame_format: "uwave"`) e supporto esplicito per più canali multiplexati sulla stessa porta COM (`channels: [...]` in `config.yaml`, invece di un blocco per canale che avrebbe tentato di aprire la stessa porta più volte). Confermato anche il terminatore reale: CR da solo, non CRLF. Vedi `docs/test-mitutoyo-uwave.md` e `docs/problemi-riscontrati.md`.

## 0.7.0

- **Fix architetturale importante**: prima d'ora una stazione poteva avere una sola Run "attiva" alla volta — se due Run venivano avviate sulla stessa stazione (es. due strumenti collegati, due commesse diverse in corso in parallelo), **tutte** le letture di **entrambi** gli strumenti finivano attribuite silenziosamente alla Run avviata per ultima. Ora ogni sorgente DAQ (strumento) viene assegnata ("claim") a una Run specifica — automaticamente all'avvio, in base alle sorgenti previste dalla sua Routine — e le letture in arrivo vengono risolte per strumento, non più per stazione. Verificato dal vivo simulando due strumenti reali su una stazione con due Run contemporanee, stesso risultato atteso su entrambe.
- Nuovi endpoint: `GET/POST /api/runs/{id}/daq-claims`, `DELETE /api/runs/{id}/daq-claims/{daq_source_id}` (assegnazione manuale, serve solo per il caso raro in cui uno strumento vada riassegnato prima che la Run che lo possiede sia completata).
- **Novità**: colonna "Stato" nella tabella Sorgenti DAQ (Amministrazione → Dispositivi) — mostra se una sorgente è libera o assegnata a quale Run, utile per capire perché una sorgente non riceve letture per la Run attesa.
- Il messaggio WebSocket `config` ora riporta `active_run_ids` (elenco) invece di `active_run_id` (singolo) — solo informativo per il log dell'Edge Agent, che resta "dumb" e non decide nulla in base a questo.

## 0.6.0

- **Novità — flusso di acquisizione completo**: "Avvia un nuovo Run" ora permette di scegliere Commessa, Attrezzatura/stampo e Lotto, oltre a Routine e Stazione (i primi tre erano già nello schema dalla v0.2 ma senza nessuna interfaccia).
- **Novità — posizione/cavità**: quando il Run usa un'attrezzatura multi-cavità, la Raccolta Dati mostra la cavità attiva, il conteggio misure per ciascuna Feature rispetto al numero richiesto (`subgroup_size`), un pulsante per saltare una cavità chiusa/inutilizzata (registrato a DB, annullabile) e per passare alla successiva. Ogni misura (da Edge Agent o manuale) viene marcata automaticamente con la posizione attiva del Run.
- **Novità**: campo "Nr. misure richieste" (`subgroup_size`) nella configurazione di una Feature (Routine & Quote) — esisteva già nello schema/API, mancava solo nell'interfaccia.
- **Novità**: nuovo tab "Produzione" in Amministrazione per creare Commesse e Attrezzature/stampi (con le rispettive cavità, generate automaticamente).
- Nuovi endpoint: `PUT/GET /api/runs/{id}/current-position`, `POST/DELETE /api/runs/{id}/skip-position`, `GET /api/runs/{id}/position-progress`, `GET/PUT /api/runs/{id}/traceability/{campo}`.

## 0.5.0

- **Novità — auto-configurazione stazione**: l'Edge Agent può indicare la stazione per nome (`station: {site_name, name}` in `config.yaml`) invece di un `station_id` numerico da cercare a mano — risolto/creato da solo al primo avvio (`POST /api/stations/resolve`). Causa reale di configurazioni sbagliate durante il collaudo, vedi `docs/problemi-riscontrati.md`. `station_id` resta supportato per compatibilità.
- **Novità — esplorazione database**: nuovo tab "Database" in Amministrazione, sola lettura, stile SSMS — elenco tabelle con conteggio righe, visualizzazione righe paginata, colonne sensibili (`users.password_hash`) sempre escluse (`GET /api/admin/db/tables`, `GET /api/admin/db/tables/{table}/rows`).
- **Novità — notifiche email**: configurazione SMTP gestibile da Amministrazione → Notifiche (host/utente/password/destinatario, password mai restituita dall'API), con invio di prova. Tre trigger: pulsante globale "Richiedi assistenza" (con contesto pagina precompilato), Edge Agent disconnesso (con cooldown anti-spam), errore di sistema non gestito. Destinatario di default `mcdataviewerinfo@gmail.com`, modificabile.

## 0.4.0

- **Fix**: il refresh della pagina su una sotto-rotta (es. `/amministrazione`, `/raccolta-dati`) restituiva un 404 invece di ricaricare l'app — mancava il fallback SPA lato server per le rotte non gestite da `StaticFiles(html=True)`.
- **Fix**: il Run attivo di una stazione non veniva mai riconosciuto dal backend (`_active_run()` filtrava per uno stato che nessun Run aveva mai) — vedi `docs/problemi-riscontrati.md` per il dettaglio della diagnosi.
- **Fix**: nessun log visibile nell'Edge Agent per una lettura seriale ricevuta con successo — aggiunto log a livello INFO in `digimatic_rs232.py`.
- **Novità**: numero di versione e changelog visibili direttamente in Amministrazione (`GET /api/version`, `GET /api/changelog`).

## 0.3.0

- CRUD completo per le entità di Amministrazione (Utenti, Sedi, Stazioni, Dispositivi DAQ, Sorgenti DAQ): modifica ed eliminazione, con controllo dei riferimenti prima di eliminare (`app/reference_check.py`) e validazione visiva dei campi obbligatori.
- Gestione errori centralizzata e comprensibile per le violazioni di vincolo del database (duplicati, riferimenti ancora in uso), indipendente dalla lingua configurata sul server Postgres.
- Interfaccia per collegare una Feature a una sorgente DAQ (`PUT /api/feature-daq-bindings`), prima priva di UI dedicata.
- Rilevamento delle porte seriali disponibili su una stazione, dal messaggio `hello` dell'Edge Agent (`GET /api/stations/{id}/available-ports`).
- Scanner di rete nativo (`edge-agent/tools/network-device-scanner.ps1`) per elencare i device COM/USB collegati su un altro PC della rete.
- `frontend/dist/` tracciato in git, per aggiornare il frontend sui PC client con un semplice `git pull` (Node.js non è disponibile/supportato su Windows Server 2012).

## 0.2.x

- Deploy Ubuntu (`installer/install.sh`, `start.sh`, `stop.sh`, `uninstall.sh`, template systemd).
- Import di configurazione e storico misure da Mitutoyo MeasurLink (`import-measurlink/`).
- Integrazione ERP generica: commesse (`work_orders`), attrezzature/stampi con posizioni/cavità (`tools`, `tool_positions`).
- Test live di una sorgente DAQ dal pannello admin (`POST /api/daq-sources/{id}/test`), tramite l'Edge Agent connesso.

## 0.1.0

- Prima versione: schema PostgreSQL, backend FastAPI (REST + WebSocket), Edge Agent Python (RS232 + USB-HID), frontend Vue (Cruscotto, Raccolta Dati, Routine & Quote, Strumenti), installer Windows a zero-admin.
