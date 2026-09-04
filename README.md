# leank-spc

App web (FastAPI + PostgreSQL + frontend Vue) per SPC e raccolta dati in officina, in sostituzione di Mitutoyo MeasurLink 9. Installabile su Windows (pilota, zero costi) o Ubuntu/Debian (deployment permanente); può importare la configurazione da un MeasurLink esistente e integrarsi con qualunque ERP per commesse/stampi.

## Documentazione

- [`docs/guida-installazione-e-test.md`](docs/guida-installazione-e-test.md) — **guida unica passo-passo**: installazione Windows (pilota) e Ubuntu (permanente), frontend, configurazione strumenti, test end-to-end, troubleshooting — punto di partenza consigliato
- [`docs/problemi-riscontrati.md`](docs/problemi-riscontrati.md) — diagnosi dettagliata dei problemi reali incontrati durante il collaudo dal vivo (cause, non solo soluzioni)
- [`docs/test-mitutoyo-uwave.md`](docs/test-mitutoyo-uwave.md) — collaudo specifico del sistema Mitutoyo U-Wave (wireless)
- [`CHANGELOG.md`](CHANGELOG.md) — versioni rilasciate (visibile anche in Amministrazione → Info nel frontend)
- [`docs/measurlink-analysis.md`](docs/measurlink-analysis.md) — analisi dello schema originale MeasurLink9 (SQL Server), base del redesign
- [`docs/schema.sql`](docs/schema.sql) — DDL PostgreSQL completo, commentato con il confronto rispetto all'originale
- [`docs/api.md`](docs/api.md) — elenco endpoint REST e protocollo messaggi WebSocket
- [`docs/integrazione-erp.md`](docs/integrazione-erp.md) — commesse, stampi/attrezzature, tracciamento per posizione/cavità
- [`frontend/README.md`](frontend/README.md) — sviluppo/build del frontend Vue (Cruscotto, Raccolta Dati, Routine & Quote, Strumenti, Amministrazione)
- [`edge-agent/README.md`](edge-agent/README.md) — configurazione e avvio dell'Edge Agent (RS232/USB-ITN)
- [`import-measurlink/README.md`](import-measurlink/README.md) — import configurazione/storico da MeasurLink
- [`admin/README.md`](admin/README.md) — pannello web standalone (senza build) per configurare stazioni/DAQ e lanciare l'import — resta disponibile accanto al frontend Vue

## Struttura

```
backend/            API FastAPI + modelli SQLAlchemy + migration Alembic
frontend/            App Vue 3 + Vite - interfaccia operativa (build statica servita dal backend)
edge-agent/          Agente Python da eseguire sui PC di stazione (RS232 + USB-ITN Digimatic)
import-measurlink/   Tool di import da MeasurLink (SQL Server) verso leank-spc
admin/                Pannello web (vanilla JS, senza build) per configurare stazioni/DAQ e l'import
docs/                Analisi, schema, documentazione API, guide installazione/integrazione
installer/           Installer Windows (pilot mode) e Ubuntu (.sh + unit systemd)
mockup/, site/        Anteprima UI e pagina di presentazione (statiche, per valutazione/demo)
```

## Avvio rapido — Windows, modalità pilota (consigliata per i test dal cliente)

```
installer\install.cmd   # una tantum: scarica Python+PostgreSQL portable, crea il DB, applica lo schema
installer\start.cmd     # a ogni avvio
installer\stop.cmd      # per fermare tutto
installer\uninstall.cmd # per rimuovere tutto senza lasciare traccia
```

L'installer chiede anche che PostgreSQL usare: **portable** (default, nessun privilegio di amministratore, nessun servizio Windows, tutto vive in `runtime\` cancellabile in ogni momento) oppure **completo** (servizio Windows vero — riusa un'installazione già presente sulla macchina, o ne installa una nuova con l'installer ufficiale EDB, richiede admin solo in quel caso). Vedi [PostgreSQL: portable o completo](docs/guida-installazione-e-test.md#postgresql-portable-o-completo). Chiede poi porta, raggiungibilità in rete e HTTPS — vedi [le tre modalità di rete](docs/guida-installazione-e-test.md#le-tre-modalità-di-rete-valgono-su-entrambi-i-sistemi-operativi).

## Avvio rapido — Ubuntu/Debian, deployment permanente

```bash
./installer/install.sh
./installer/start.sh
```

Usa i pacchetti di sistema (`apt`, PostgreSQL via systemd) — niente trucco "zero admin", qui è normale. Avvio automatico al boot opzionale via `installer/leank-spc.service`. Dettagli in [`docs/guida-installazione-e-test.md`](docs/guida-installazione-e-test.md#parte-1bis--installazione-ubuntudebian-deployment-permanente).

## Frontend web (uso quotidiano)

Dopo l'installazione, l'indirizzo mostrato in fondo apre il frontend Vue: Cruscotto, Raccolta Dati (la schermata operativa per il collaudo, con misure live via WebSocket), Routine & Quote, Strumenti, Amministrazione (utenti/stazioni/dispositivi, più versione e changelog in "Info"). Vedi [Parte 2 della guida](docs/guida-installazione-e-test.md#parte-2--frontend-linterfaccia-web-vera-e-propria) e [`frontend/README.md`](frontend/README.md) per sviluppo/build.

## Configurare stazioni/DAQ e importare da MeasurLink

In alternativa alla sezione "Amministrazione" del frontend, resta disponibile [`admin/index.html`](admin/index.html) (vedi [`admin/README.md`](admin/README.md)): pannello standalone senza build, con test di collegamento reale (chiede all'Edge Agent lo stato della porta) e monitor di avanzamento per l'import.

## Avvio backend (sviluppo locale, alternativa manuale)

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # poi modificare DATABASE_URL/JWT_SECRET
alembic upgrade head
python create_admin.py admin <password>   # crea il primo utente (nessuna API può farlo senza un token esistente)
uvicorn app.main:app --reload
```

Richiede un PostgreSQL raggiungibile (locale o Docker) con il database/utente indicati in `DATABASE_URL`.

## Avvio Edge Agent (PC di stazione, alternativa manuale)

```bash
cd edge-agent
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy config.example.yaml config.yaml   # poi modificare station_id/token/sources
python -m edge_agent.main config.yaml
```

Vedi [`edge-agent/README.md`](edge-agent/README.md) per come ottenere il token e configurare le sorgenti RS232/USB-ITN. Per validare il flusso end-to-end senza hardware reale, aggiungere in `config.yaml` una sorgente `type: mock` — genera letture finte a intervalli regolari.

## Stato del progetto

**Collaudato dal vivo, non solo scritto** — su una macchina Windows reale e contro il database MeasurLink9 reale del cliente pilota:

- Installer Windows: installazione pulita, avvio/stop/riavvio, login, creazione dati via API, persistenza dopo restart. Trovati e corretti 6 bug reali nel farlo (incompatibilità `passlib`/`bcrypt`, parsing SQLAlchemy su `:numero` nei commenti SQL, limite asyncpg su script multi-statement, hang di `pg_ctl` su pipe Windows, API .NET assente su PowerShell 5.1, `Expand-Archive` assente su Server 2012).
- Import da MeasurLink: eseguito per davvero contro il DB del cliente (303 Part, 351 Routine, 6394 Feature, 316 strumenti, 4826 calibrazioni) — idempotenza verificata rilanciandolo due volte.
- Pannello admin: login, CRUD stazioni/DAQ, test di collegamento (con Edge Agent offline → messaggio corretto), avvio import + monitor, tutto verificato in un browser reale.
- API commesse/stampi (v0.2): creazione idempotente via `external_system`+`external_id`, tools con posizioni auto-generate, verificate via chiamate reali.
- Le tre modalità di rete (v0.2): porta custom, esposizione LAN con regola firewall, HTTPS con certificato auto-firmato — installate e verificate con login + chiamate API reali su tutte e tre. Un altro bug trovato nel farlo: `ServerCertificateValidationCallback` non funziona in modo affidabile su PowerShell 5.1 (nessun runspace nel thread .NET che lo invoca) — risolto con la vecchia interfaccia `ICertificatePolicy`, collaudata.
- Modalità PostgreSQL Portable/Completo (v0.2.2): il refactor che introduce la scelta è stato verificato con una **regressione completa** dell'installazione Portable pre-esistente (identica, nessuna rottura).
- Frontend Vue (v0.3): tutte e 5 le sezioni collaudate in un browser reale contro il backend e i dati reali importati da MeasurLink (11 stazioni, centinaia di Part/Routine/Feature, 316 strumenti) — login, navigazione, creazione Run, quote/tolleranze mostrate correttamente. Flusso end-to-end **Raccolta Dati** verificato per davvero: avvio Run → inserimento manuale di una misura → comparsa immediata via WebSocket, senza refresh. Trovati e corretti 2 bug backend reali nel farlo: (1) `measurements.captured_at`/altre colonne `timestamptz` mappate come naive lato SQLAlchemy (mancava `type_annotation_map` sul `Base`) → `DataError` su qualunque insert con un datetime timezone-aware; (2) l'inserimento manuale di una misura via REST non pubblicava l'evento WebSocket verso la dashboard (solo il percorso Edge Agent lo faceva). Aggiunto anche `GET /api/features/{id}/properties` e `current_properties` su `FeatureOut`, mancanti per mostrare le tolleranze nel frontend.

- Installazione reale sul PC del cliente pilota (Windows Server 2012): `install.cmd` collaudato dal vivo end-to-end, incluso il frontend servito dal backend tramite `frontend/dist/` (ora versionato in git, vedi `frontend/README.md` — nessun build richiesto su quella macchina, dove peraltro Node.js 18+ non gira affatto: "Node.js is only supported on Windows 10, Windows Server 2016, or higher"). Diversi bug reali trovati e corretti in questo giro (vedi cronologia commit): Ctrl+C che può uccidere PostgreSQL, recovery da processo Postgres residuo, validazione della porta durante l'installazione, `type_annotation_map` mancante per i timestamp, broadcast WebSocket mancante sull'inserimento manuale di una misura.

Non ancora verificato: gli script Ubuntu (nessuna macchina Linux disponibile in questa sessione — la logica ricalca quella Windows già validata, ma va provata alla prima occasione), il collegamento a strumenti Digimatic fisici veri (finora solo sorgente `mock` più cattura del formato reale ancora da fare con `edge-agent/tools/serial-monitor.html`), il percorso HTTPS con certificato pubblico/Caddy (solo documentato, richiede un dominio reale per essere testato), il ramo **PostgreSQL Completo** (installazione nuova via installer ufficiale EDB, o riuso di una esistente): implementato dalla documentazione ufficiale, ma questa sessione non ha mai avuto una PowerShell da amministratore né un PostgreSQL "completo" già installato a disposizione, quindi **nessuno dei due sotto-percorsi è stato collaudato dal vivo** — solo il guard "richiede amministratore" è stato verificato in isolamento.

Resta da fare (vedi TODO nel codice):

- Calcolo statistico (Cp/Cpk, regole SPC Western Electric) alla ricezione di una misura
- Generazione del corpo HTML dei certificati di taratura dal template esistente
- Dependency `require_permission()` per l'autorizzazione granulare (schema roles/permissions già pronto)
- Collaudo e calibrazione del parsing del frame Digimatic RS232 e della decodifica USB-HID sull'**hardware reale di officina**
- Frontend Vue (oggi solo mockup statico in `mockup/`)
