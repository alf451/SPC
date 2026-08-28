# leank-spc

App web (FastAPI + PostgreSQL, frontend Vue da fare in una fase successiva) per SPC e raccolta dati in officina, in sostituzione di Mitutoyo MeasurLink 9.

## Documentazione

- [`docs/installazione.md`](docs/installazione.md) — **installazione pilot** (zero costi, zero admin) per test sul campo dal cliente, affiancata a MeasurLink
- [`docs/measurlink-analysis.md`](docs/measurlink-analysis.md) — analisi dello schema originale MeasurLink9 (SQL Server), base del redesign
- [`docs/schema.sql`](docs/schema.sql) — DDL PostgreSQL completo, commentato con il confronto rispetto all'originale
- [`docs/api.md`](docs/api.md) — elenco endpoint REST e protocollo messaggi WebSocket
- [`edge-agent/README.md`](edge-agent/README.md) — configurazione e avvio dell'Edge Agent (RS232/USB-ITN)

## Struttura

```
backend/       API FastAPI + modelli SQLAlchemy + migration Alembic
edge-agent/    Agente Python da eseguire sui PC di stazione (RS232 + USB-ITN Digimatic)
docs/          Analisi, schema, documentazione API, guida installazione
installer/     Installer "pilot mode": zero admin, zero servizi, tutto reversibile
```

## Avvio rapido — modalità pilot (consigliata per i test dal cliente)

```
installer\install.cmd   # una tantum: scarica Python+PostgreSQL portable, crea il DB, applica lo schema
installer\start.cmd     # a ogni avvio
installer\stop.cmd      # per fermare tutto
installer\uninstall.cmd # per rimuovere tutto senza lasciare traccia
```

Nessun privilegio di amministratore, nessuna installazione di sistema, nessun servizio Windows: tutto vive in `runtime\` (cancellabile in ogni momento). Dettagli in [`docs/installazione.md`](docs/installazione.md).

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

**Installer pilot mode collaudato end-to-end dal vivo** (non solo scritto): installazione pulita, avvio/stop/riavvio, login, creazione dati via API, persistenza dopo restart — tutto verificato su una macchina Windows reale con PowerShell 5.1. Nel farlo sono stati trovati e corretti 5 bug reali (non solo dell'installer): incompatibilità `passlib`/`bcrypt` recenti (rimosso `passlib`, si usa `bcrypt` direttamente in `app/security.py`), un bug di parsing di SQLAlchemy su script SQL grezzi con `:numero` nei commenti, il limite di asyncpg sugli script multi-statement, e un hang di `pg_ctl` su Windows quando il suo output viene messo in pipe.

Restano da fare (vedi TODO nel codice):

- Calcolo statistico (Cp/Cpk, regole SPC Western Electric) alla ricezione di una misura
- Generazione del corpo HTML dei certificati di taratura dal template esistente
- Dependency `require_permission()` per l'autorizzazione granulare (schema roles/permissions già pronto)
- Collaudo e calibrazione del parsing del frame Digimatic RS232 e della decodifica USB-HID sull'**hardware reale di officina** (finora testato solo con la sorgente `mock`, non con strumenti Digimatic veri)
- Frontend Vue
