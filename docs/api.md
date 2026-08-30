# API leank-spc

Backend FastAPI, prefisso `/api` per REST, `/ws` per WebSocket. Auth: JWT (OAuth2 password flow).

## Autenticazione

- `POST /api/auth/login` — form `username`/`password` → `{access_token, refresh_token, token_type}`
- `POST /api/auth/refresh` — `{refresh_token}` → nuova coppia di token
- `GET /api/auth/me` — utente corrente (richiede `Authorization: Bearer <access_token>`)

Tutte le altre route REST richiedono il bearer token. Autorizzazione granulare per permesso (`spc.run.create`, `gage.calibration.approve`, ...) è predisposta nello schema (`roles`/`permissions`/`role_permissions`) ma la dependency `require_permission()` è ancora da implementare in `app/security.py` (vedi TODO nel file) — per ora tutte le route protette richiedono solo autenticazione, non un permesso specifico.

## REST

| Risorsa | Endpoint | Note |
|---|---|---|
| Part folders | `GET /api/part-folders` | |
| Parts | `GET/POST /api/parts`, `GET /api/parts/{id}` | filtri `folder_id`, `search` |
| Features | `GET /api/parts/{part_id}/features`, `POST /api/features` | creare una Feature con `properties` crea anche la prima versione di tolleranze; ogni Feature nella risposta include `current_properties` (la versione con `valid_to IS NULL`, `null` se non ancora creata) |
| Feature properties | `GET /api/features/{id}/properties`, `POST /api/features/{id}/properties` | GET restituisce lo storico versioni (più recente prima) - **v0.3**, aggiunto per il frontend; POST crea una **nuova versione** (mai update in-place), chiude quella corrente |
| Routines | `GET/POST /api/routines`, `GET /api/routines/{id}` | |
| Routine features | `GET /api/routines/{id}/features`, `PUT /api/routines/{id}/features/{feature_id}` | binding N:N con ordine |
| Runs | `GET/POST /api/runs`, `GET /api/runs/{id}`, `POST /api/runs/{id}/complete` | |
| Measurements | `GET/POST /api/runs/{run_id}/measurements` | POST è per inserimento **manuale**; le misure da strumento arrivano via WS (vedi sotto) |
| Stations | `GET/POST /api/stations`, `GET /api/stations/{id}` | |
| DAQ devices | `GET/POST /api/daq-devices` | profilo dispositivo (RS232/USB-HID/...), parametri in `config` jsonb |
| DAQ sources | `GET/POST /api/daq-sources` | porta/canale fisico su una stazione |
| Feature↔DAQ binding | `PUT /api/feature-daq-bindings` | quale sorgente alimenta quale Feature per una Routine |
| Gages | `GET/POST /api/gages`, `GET /api/gages/{id}` | |
| Calibrations | `GET/POST /api/calibrations`, `POST /api/calibrations/{id}/results`, `POST /api/calibrations/{id}/complete`, `POST /api/calibrations/{id}/certificate` | generazione certificato ancora stub (TODO template HTML) |
| Users | `GET/POST /api/users` | il primo utente si crea con `backend/create_admin.py`, non via API (vedi TODO in `routers/users.py`) |
| Sites | `GET/POST /api/sites` | |
| **v0.2 — DAQ live** | `DELETE /api/daq-devices/{id}`, `DELETE /api/daq-sources/{id}`, `DELETE /api/feature-daq-bindings`, `POST /api/daq-sources/{id}/test` | il test chiede all'Edge Agent connesso lo stato reale della porta, vedi protocollo `test_source` sotto |
| **v0.2 — Tools/commesse** | `GET/POST /api/tools`, `GET /api/tools/{id}`, `GET /api/tools/{id}/positions`, `DELETE /api/tools/{id}` | "tool" generalizza stampo/fustella/attrezzatura; posizioni = cavità |
| | `GET/POST /api/work-orders`, `GET /api/work-orders/{id}` | POST è l'endpoint di integrazione ERP — idempotente su `(external_system, external_id)`, vedi `docs/integrazione-erp.md` |
| **v0.2 — Admin import** | `POST /api/admin/measurlink-import/test-connection`, `POST /api/admin/measurlink-import/run`, `GET /api/admin/measurlink-import/jobs/{id}`, `GET /api/admin/measurlink-import/jobs` | invoca in-process il tool in `import-measurlink/`, vedi quel README |

`RunCreate` accetta anche `work_order_id`/`tool_id` opzionali; `MeasurementCreate` accetta `tool_position_id` opzionale (da quale cavità viene il campione).

Paginazione: `limit`/`offset` dove applicabile (default `limit=50`, misure `limit=200`).

## WebSocket

### `/ws/agent/{station_id}?token=<jwt access token>` — ingest dall'Edge Agent

L'Edge Agent apre **una connessione persistente per stazione**. Autenticazione tramite lo stesso JWT access token usato dalle REST API (query param, dato che i client WebSocket embedded non gestiscono sempre header custom) — emesso a un account "di servizio" creato via `/api/users`.

Messaggi JSON, campo `type`:

| type | Direzione | Payload | Descrizione |
|---|---|---|---|
| `hello` | agent→server | `{sources: [{port, channel_no}, ...]}` | l'agent annuncia le sue sorgenti fisiche locali |
| `config` | server→agent | `{active_run_id, daq_sources: [{port, channel_no, daq_source_id}], feature_bindings: [{feature_id, daq_source_id}]}` | il server risolve porta→daq_source_id e restituisce il binding Feature del Run attivo sulla stazione. **L'agent resta "dumb": non decide a quale Feature appartiene una lettura**, si limita a includere il `daq_source_id` corretto |
| `reading` | agent→server | `{daq_source_id, raw_value, captured_at, ref}` | una singola lettura. `ref` è l'id della riga nell'outbox locale dell'agent, echeggiato nell'ack per permettere la correlazione. Il server risolve `daq_source_id` → `feature_id` (via `feature_daq_bindings` sulla Routine del Run attivo), determina se la Feature è `variable`/`attribute` e scrive in `measurements`/`attribute_observations` |
| `ack` | server→agent | `{ok, ref, obs_no?, reason?}` | conferma scrittura (`reason`: `no_active_run` \| `unbound_daq_source`) — l'agent usa `ref` per rimuovere la riga corrispondente dall'outbox locale |
| `heartbeat` | entrambe | `{}` | keepalive |
| `test_source` | server→agent | `{request_id, port, channel_no}` | **v0.2**: chiesto da `POST /api/daq-sources/{id}/test` (pannello admin). Il backend non ha accesso diretto alla porta seriale della stazione, quindi lo chiede all'agent |
| `test_result` | agent→server | `{request_id, ok, message, sample_raw?}` | risposta al test — correlata via `request_id` a una `Future` lato server (`ConnectionManager.send_agent_request`, timeout 8s). L'agent **non apre una seconda connessione** sulla porta: riporta lo stato "live" della sorgente già in ascolto (connessa? ultima lettura quando?), dato che in modalità "push" non si può forzare una lettura senza premere il tasto DATA sullo strumento |

Dopo ogni `reading` scritta con successo, il server rilancia un evento `measurement` a tutti i client connessi su `/ws/dashboard/{run_id}` per quel Run.

### `/ws/dashboard/{run_id}?token=<jwt access token>` — push live al frontend

Il frontend si connette per un Run specifico e riceve in tempo reale:

```json
{"type": "measurement", "feature_id": 42, "obs_no": 17, "value": 10.023, "captured_at": "..."}
```

Canale in sola ricezione lato frontend in questa versione (nessun comando client→server previsto ancora).

## Note di scalabilità

Il `ConnectionManager` (`app/ws/connection_manager.py`) è in-process: funziona con un solo worker Uvicorn. Se in futuro il backend gira su più worker/repliche, va sostituito con un pub/sub esterno (es. Redis) mantenendo la stessa interfaccia (`connect_agent`, `broadcast_to_run`, ...), altrimenti un agent connesso al worker A non riesce a raggiungere una dashboard connessa al worker B.

## Fuori ambito v1

Calcolo di control limits/Cp/Cpk/regole SPC alla ricezione di una misura (oggi la misura grezza viene solo persistita e ribroadcastata) — da agganciare in `app/ws/agent_hub.py::_persist_reading` quando la logica statistica sarà implementata. Generazione del corpo HTML del certificato di taratura a partire dal template esistente.
