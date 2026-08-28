# Guida installazione — modalità pilot (affiancamento a MeasurLink)

Questa modalità installa leank-spc **senza toccare il sistema**: nessun software di sistema installato, nessun servizio Windows, nessun privilegio di amministratore richiesto. Tutto vive dentro la cartella del progetto, in una sottocartella `runtime\` — cancellabile in qualunque momento senza lasciare traccia.

Pensata per essere eseguita **sullo stesso PC dove gira MeasurLink**, in parallelo, durante il periodo di test.

## Requisiti

- Windows 10/11
- Connessione internet (solo per la prima installazione, scarica ~250 MB tra Python e PostgreSQL)
- Nessun software da installare prima: lo script scarica tutto da solo
- **La cartella `leank-spc` NON deve stare dentro una cartella sincronizzata con OneDrive/Dropbox/Google Drive sul PC del cliente.** PostgreSQL scrive continuamente sui suoi file dati (`runtime\pgdata`) mentre è in esecuzione: se quella cartella viene sincronizzata nel frattempo (upload di un file a metà scrittura, evizione "solo online" di OneDrive, ecc.) si rischiano dati corrotti. Copiare il progetto in un percorso locale non sincronizzato, es. `C:\leank-spc`, prima di eseguire `install.cmd` sul PC del cliente.

## Installazione (una tantum)

1. Copiare l'intera cartella `leank-spc` sul PC (chiavetta USB, cartella di rete, o zip)
2. Aprire la cartella `leank-spc\installer`
3. Doppio click su **`install.cmd`**
4. Attendere (qualche minuto, scarica ed estrae Python e PostgreSQL, crea il database)
5. Alla fine viene mostrata la password dell'utente `admin` — **annotarla**, serve per accedere

Lo script è rieseguibile in sicurezza: se lo si lancia di nuovo, salta i passi già completati.

## Uso quotidiano

- **Avviare** (a ogni riavvio del PC o dopo aver fermato tutto): doppio click su `start.ps1`... in realtà usare **`start.cmd`**
- **Fermare**: doppio click su **`stop.cmd`**
- Il backend risponde su [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) — quella pagina (Swagger UI) permette di provare tutte le API dal browser, utile in fase di test senza aspettare il frontend

## Disinstallazione

Doppio click su **`uninstall.cmd`** → conferma scrivendo `si`. Rimuove tutto (PostgreSQL, pacchetti Python, database, dati) dalla cartella `runtime\`; il codice del progetto resta intatto e riutilizzabile per una nuova installazione pulita.

## Cosa NON fa questa modalità (di proposito)

- Non si avvia da sola al riavvio del PC (va rilanciato `start.cmd` manualmente) — corretto per una fase di test dove non si vuole competere con MeasurLink in modo permanente
- Non è raggiungibile dalla rete (PostgreSQL e backend ascoltano solo su `127.0.0.1`, cioè solo dallo stesso PC) — per collegare l'Edge Agent da un'altra postazione della stessa officina serve un passo successivo (aprire la porta sul firewall e cambiare `listen_addresses`), volutamente non fatto in questa fase pilota
- Non installa un servizio Windows: quando si è convinti che leank-spc debba restare attivo in modo permanente, si passa a un'installazione "di produzione" (fuori ambito di questa guida)

## Collegare il primo strumento (Edge Agent)

Vedi [`edge-agent/README.md`](../edge-agent/README.md) *(da creare insieme al primo test sul campo)* — in sintesi: copiare `edge-agent\config.example.yaml` in `config.yaml`, indicare la porta COM dello strumento, ottenere un token di accesso facendo login come utente `admin` su `http://127.0.0.1:8000/docs` (endpoint `POST /api/auth/login`), poi lanciare l'agent con lo stesso Python embeddable già pronto in `runtime\python\python.exe`.

## Risoluzione problemi

- **"impossibile eseguire script"**: usare sempre i file `.cmd` (non i `.ps1` direttamente) — i `.cmd` aggirano l'execution policy di PowerShell senza bisogno di cambiarla a livello di sistema
- **Il backend non risponde dopo `start.cmd`**: controllare `runtime\logs\backend.err.log`
- **Serve ricominciare da capo**: `uninstall.cmd` poi `install.cmd`
