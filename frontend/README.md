# Frontend leank-spc

App Vue 3 + Vite: l'interfaccia operativa quotidiana (Cruscotto, Raccolta Dati, Routine & Quote, Strumenti, Amministrazione). Non sostituisce [`admin/index.html`](../admin/index.html), che resta disponibile invariato per una configurazione rapida senza build.

## Sviluppo

Richiede [Node.js](https://nodejs.org/) 20+ (qualunque versione LTS recente va bene - non serve una versione specifica).

```bash
cd frontend
npm install
npm run dev
```

Apre su `http://localhost:5173`. Il backend deve girare separatamente (es. `installer\start.cmd`, o `uvicorn app.main:app --reload` in `backend/`) — di default il frontend in sviluppo si aspetta il backend su `http://127.0.0.1:8000` (cambiabile copiando `.env.example` in `.env` e modificando `VITE_API_BASE_URL`).

## Build per la distribuzione (pilot mode Windows/Ubuntu)

```bash
npm run build
```

Produce `frontend/dist/` (statico, nessun Node.js richiesto per usarlo). Il backend FastAPI lo serve automaticamente sulla propria root se la cartella `frontend/dist/` esiste accanto a `backend/` (vedi `backend/app/main.py`) — nessuna configurazione aggiuntiva, nessun secondo webserver.

### `frontend/dist/` è versionato in git (scelta deliberata)

A differenza della prassi comune (di solito i build non si versionano), qui `frontend/dist/` **è committato** — non è nel `.gitignore`. Motivo concreto: il PC del cliente pilota è spesso un Windows datato (es. Server 2012/2012 R2) su cui Node.js 18+ **non gira affatto** ("Node.js is only supported on Windows 10, Windows Server 2016, or higher" — riscontrato dal vivo), quindi non può buildare da solo. Tenere `dist/` in git significa che un semplice

```powershell
git pull
installer\stop.cmd
installer\start.cmd
```

sulla macchina di destinazione aggiorna **sia il backend sia il frontend** in un colpo solo, senza dover ricostruire/trasferire uno zip separato ad ogni modifica.

**Regola per chi modifica `frontend/src/`**: rilanciare `npm run build` e includere il `frontend/dist/` risultante nello stesso commit delle modifiche sorgente — un commit che tocca `src/` senza aggiornare `dist/` lascia il PC cliente con un frontend disallineato dal codice, silenziosamente (nessun errore, semplicemente la versione vecchia continua a essere servita).

## Struttura

- `src/api/` — un modulo per risorsa REST (wrapper sottili su `fetch`, vedi `src/api/client.js`), rispecchia `docs/api.md`
- `src/ws/dashboardSocket.js` — client per `/ws/dashboard/{run_id}` (misure live)
- `src/stores/auth.js` — login JWT (Pinia), stesso schema di `admin/index.html`
- `src/views/` — una per voce di navigazione
- `src/styles/tokens.css` — palette/tema chiaro-scuro, estratta da `mockup/leank-spc-preview.html`

## Nota di sicurezza

Il token JWT viene salvato in `sessionStorage` (non sopravvive alla chiusura della scheda), stesso approccio del pannello admin — coerente con l'uso su un PC condiviso di reparto.
