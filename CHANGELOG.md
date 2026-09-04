# Changelog

Registro delle versioni rilasciate. La versione corrente è mostrata anche in **Amministrazione → Info** nel frontend (letta da `backend/app/version.py`).

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
