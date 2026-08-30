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

Per distribuire il frontend insieme al resto del progetto (es. sul PC del cliente per il pilot Windows): buildare qui, poi copiare `frontend/dist/` dentro la cartella del progetto insieme a `backend/`, `installer/`, ecc. — l'installer esistente non richiede modifiche, il backend lo trova e lo serve da solo al prossimo avvio.

## Struttura

- `src/api/` — un modulo per risorsa REST (wrapper sottili su `fetch`, vedi `src/api/client.js`), rispecchia `docs/api.md`
- `src/ws/dashboardSocket.js` — client per `/ws/dashboard/{run_id}` (misure live)
- `src/stores/auth.js` — login JWT (Pinia), stesso schema di `admin/index.html`
- `src/views/` — una per voce di navigazione
- `src/styles/tokens.css` — palette/tema chiaro-scuro, estratta da `mockup/leank-spc-preview.html`

## Nota di sicurezza

Il token JWT viene salvato in `sessionStorage` (non sopravvive alla chiusura della scheda), stesso approccio del pannello admin — coerente con l'uso su un PC condiviso di reparto.
