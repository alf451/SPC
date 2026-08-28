# Pannello admin

Pagina singola (`index.html`, vanilla JS, nessun build) per configurare stazioni/DAQ e lanciare/monitorare l'import da MeasurLink — parla direttamente con le API REST del backend, via `fetch()`.

## Uso

Aprire `index.html` con doppio click (funziona da `file://`: il backend accetta esplicitamente le richieste da pagine aperte così, vedi `CORS_ORIGINS` in `backend/.env`). Se il browser è più restrittivo su `file://`, servirla da un piccolo server locale invece:

```bash
cd admin
python -m http.server 8899
```

e aprire `http://127.0.0.1:8899`.

Al primo accesso: URL del backend (default `http://127.0.0.1:8000`, cambiare se il backend gira altrove), utente/password (vedi `runtime/secrets/admin_password.txt` sul PC dove gira l'installer pilota).

## Cosa fa

- **Stazioni & DAQ**: crea/elimina sedi, stazioni, dispositivi DAQ (profilo RS232/USB-HID/manuale), sorgenti DAQ (porta/canale su una stazione). Il pulsante "Prova" su una sorgente chiede all'Edge Agent di quella stazione (se connesso) lo stato reale della porta — il backend non ha accesso diretto all'hardware della stazione, vedi il protocollo `test_source`/`test_result` in `docs/api.md`.
- **Import MeasurLink**: form di connessione al SQL Server di MeasurLink, pulsante "Testa connessione" (verifica senza importare nulla), avvio sincronizzazione con opzione "solo configurazione" o "+ storico ultimi N mesi", opzione "prova" (dry-run: conta senza scrivere), e un monitor che segue il job in tempo reale (polling ogni 1,5s) mostrando log e riepilogo finale.

## Nota di sicurezza

Questa pagina non ha una sua autenticazione: usa il token JWT dell'utente che fa login, con gli stessi permessi che avrebbe usando direttamente le API. Non esporla fuori da una rete fidata (va bene in LAN/localhost per configurare un'installazione, non pensata per essere pubblicata).
