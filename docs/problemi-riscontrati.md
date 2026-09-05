# Problemi riscontrati durante il collaudo e soluzioni

Registro dei problemi reali diagnosticati durante l'installazione e il collaudo dal vivo presso il cliente (pilota su Windows Server 2012, strumento Mitutoyo U-WAVE), con causa e soluzione — utile per non ripetere la stessa diagnosi la prossima volta che si presenta un sintomo simile.

## Installazione

**PostgreSQL non si avvia / "un altro server potrebbe essere in esecuzione"** — causato da un Ctrl+C durante un `install.ps1` precedente: su Windows il segnale si propaga ai processi figli che condividono la console, terminando in modo anomalo il cluster Postgres (visibile in `postgres.log` come `STATUS_CONTROL_C_EXIT`). Soluzione: `taskkill /F /IM postgres.exe /T` + rimozione del `postmaster.pid` residuo. `install.ps1`/`start.ps1` mostrano ora un avviso esplicito di non premere Ctrl+C, e `install.ps1` verifica che Postgres sia davvero partito prima di proseguire.

**`git pull` bloccato con "local changes would be overwritten"** senza modifiche intenzionali — causato dalla normalizzazione automatica dei fine riga di Windows (`core.autocrlf`) che fa apparire `installer/install.ps1`/`start.ps1` come modificati. Verificare con `git diff` che sia solo rumore di fine riga, poi `git checkout -- <file>` e ripetere il pull.

**Node.js non si avvia su Windows Server 2012/2012 R2** ("Node.js is only supported on Windows 10, Windows Server 2016, or higher") — `frontend/dist/` viene quindi buildato su un'altra macchina e tracciato direttamente in git: sul PC client basta un `git pull`, senza installare Node.

## Configurazione stazione/Edge Agent

**"Nessun Edge Agent connesso" per una stazione** — verificare innanzitutto che l'Edge Agent stia girando sul PC giusto: lo strumento (porta COM) potrebbe essere collegato a un PC diverso da quello su cui si sta configurando la stazione nel frontend.

**Il binding Feature → Sorgente DAQ manca e le misure non arrivano mai** — è un collegamento **diverso e aggiuntivo** rispetto ad "aggiungi Feature alla Routine": il primo (`PUT /api/feature-daq-bindings`, sezione "Collega Feature → Sorgente DAQ" in Routine & Quote) dice al backend a quale Feature assegnare le letture in arrivo da una porta; il secondo è solo l'ordine di collaudo delle Feature nella Routine. Senza il primo, l'Edge Agent invia le letture ma il backend risponde `unbound_daq_source` e la misura non viene mai scritta.

**Il Run non viene mai riconosciuto come "attivo" dal backend** — bug reale (risolto in v0.4.0): `_active_run()` in `agent_hub.py` cercava un valore di stato sbagliato. Il modello `Run` (in `app/models/spc.py`) usa gli stati `active | completed | aborted` — **non** `in_progress` (quel valore è usato invece dalle Calibrazioni, in `app/models/gage.py`, uno stato omonimo ma di un'altra entità: facile confonderli leggendo il codice). Il sintomo era: Run creato con successo, visibile nel database, ma l'Edge Agent riceveva sempre `active_run_id: null` nel messaggio di `config`, e ogni lettura veniva rifiutata con `no_active_run`. La stessa svista era anche nel frontend (`DataCollectionView.vue`, `DashboardView.vue`), che filtrava i run con `status_filter=in_progress`: la select "Seleziona un Run in corso" restava quindi sempre vuota anche con un Run realmente attivo.

**Nessun log visibile nell'Edge Agent per una lettura ricevuta** — non era un guasto: `digimatic_rs232.py` non aveva nessuna riga di log per una lettura riuscita (solo per errori/connessione). Aggiunta una riga INFO all'apertura porta e una per ogni frame ricevuto/parsato (v0.4.0), per rendere visibile a colpo d'occhio se lo strumento sta davvero inviando dati.

**Pulsante che "non fa nulla" al click** — capitato due volte con cause diverse:
1. Il pulsante era realmente **disabilitato** (menu a tendina non compilati) — nessun errore perché la richiesta non parte nemmeno. Controllare sempre il colore/stato del pulsante prima di sospettare un bug.
2. Il messaggio di conferma **c'era**, ma in una posizione della pagina non notata subito (banner verde in alto).

**Sessione che scade durante un collaudo lungo** ("Connessione persa" persistente, o un'azione che sembra non fare nulla) — il token JWT dura 30 minuti di default; l'Edge Agent non fa refresh automatico e continua a riprovare con lo stesso token scaduto. Soluzione nell'immediato: rifare login/ottenere un nuovo token. Per una sessione di collaudo lunga, si può alzare temporaneamente `ACCESS_TOKEN_EXPIRE_MINUTES` in `backend/.env`.

**Parametri seriali dello strumento** — il Mitutoyo U-WAVE (tramite U-WAVEPAK, porta COM virtuale) usa **57600 baud, 8 data bit, nessuna parità, 1 stop bit**. Un `config.yaml` con più blocchi `sources:` sovrapposti sulla stessa porta con parametri incompatibili (visto durante il collaudo: 9600-7-E-1 e 4800-8-N-1 sulla stessa COM) non può funzionare — un'unica porta seriale ha un'unica velocità/formato per volta.

**Formato del frame U-Wave — il parser generico estraeva il numero sbagliato** — una cattura diretta sull'hardware reale (ricevitore + 3 trasmettitori) ha mostrato frame tipo `DT10000+00000011.88M\r` (canale a 5 cifre + segno + valore + unità, terminati da **CR da solo, non CRLF**) intervallati da messaggi di stato `ST...`/`TI...` (non misure). Il parser generico (`_NUMERIC_RE`, pensato per un valore semplice senza prefisso) avrebbe estratto "10000" come se fosse il valore, invece del vero "+11.88" — perché cerca il primo numero nella stringa, e il codice canale viene prima del segno. Inoltre avrebbe trattato le righe di stato come letture invalide invece di ignorarle. Risolto con un parser dedicato (`parse_uwave_frame`) e un modo esplicito (`frame_format: "uwave"` + `channels: [...]`) per gestire più canali multiplexati sulla stessa porta — vedi [`test-mitutoyo-uwave.md`](test-mitutoyo-uwave.md).

## Debug via browser

Per capire se una richiesta dal frontend arriva davvero al backend e cosa risponde: F12 → scheda **Network** (non "Sources", che mostra il codice, non le richieste) → azione nell'app → cliccare sulla riga della richiesta → **Status** e **Response**. In alternativa, spesso più veloce in una sessione di debug remoto: testare l'endpoint direttamente da Swagger (`/docs`), che elimina ogni dubbio sullo stato della pagina frontend.
