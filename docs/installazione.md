# Guida installazione

Due modalità, a seconda dello scopo:

- **[Windows — modalità pilota](#windows--modalità-pilota)**: per affiancare MeasurLink durante un test sul campo, sullo stesso PC del reparto qualità. Zero costi, zero admin, tutto reversibile.
- **[Ubuntu/Debian — deployment permanente](#ubuntudebian--deployment-permanente)**: per un server dedicato (proprio o del cliente), pensato per restare attivo stabilmente, non per convivere temporaneamente con qualcos'altro.

---

## Windows — modalità pilota

Installa leank-spc **senza toccare il sistema**: nessun software di sistema installato, nessun servizio Windows, nessun privilegio di amministratore richiesto. Tutto vive dentro la cartella del progetto, in una sottocartella `runtime\` — cancellabile in qualunque momento senza lasciare traccia.

Pensata per essere eseguita **sullo stesso PC dove gira MeasurLink**, in parallelo, durante il periodo di test.

### Requisiti

- Windows 10/11 (Windows Server più datati come il 2012 R2 dovrebbero funzionare; il 2012 originale non è garantito — vedi nota in fondo a [`installer/common.ps1`](../installer/common.ps1))
- Connessione internet (solo per la prima installazione, scarica ~250 MB tra Python e PostgreSQL)
- Nessun software da installare prima: lo script scarica tutto da solo
- **La cartella `leank-spc` NON deve stare dentro una cartella sincronizzata con OneDrive/Dropbox/Google Drive sul PC del cliente.** PostgreSQL scrive continuamente sui suoi file dati (`runtime\pgdata`) mentre è in esecuzione: se quella cartella viene sincronizzata nel frattempo (upload di un file a metà scrittura, evizione "solo online" di OneDrive, ecc.) si rischiano dati corrotti. Copiare il progetto in un percorso locale non sincronizzato, es. `C:\leank-spc`, prima di eseguire `install.cmd` sul PC del cliente.

### Installazione (una tantum)

1. Copiare l'intera cartella `leank-spc` sul PC (chiavetta USB, cartella di rete, o zip)
2. Aprire la cartella `leank-spc\installer`
3. Doppio click su **`install.cmd`**
4. Attendere (qualche minuto, scarica ed estrae Python e PostgreSQL, crea il database)
5. Alla fine viene mostrata la password dell'utente `admin` — **annotarla**, serve per accedere

Lo script è rieseguibile in sicurezza: se lo si lancia di nuovo, salta i passi già completati.

### Uso quotidiano

- **Avviare** (a ogni riavvio del PC o dopo aver fermato tutto): doppio click su **`start.cmd`**
- **Fermare**: doppio click su **`stop.cmd`**
- Il backend risponde su [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) (Swagger UI, per provare le API dal browser) e il [pannello admin](../admin/index.html) permette di configurare stazioni/DAQ e lanciare l'import da MeasurLink senza scrivere codice

### Disinstallazione

Doppio click su **`uninstall.cmd`** → conferma scrivendo `si`. Rimuove tutto (PostgreSQL, pacchetti Python, database, dati) dalla cartella `runtime\`; il codice del progetto resta intatto e riutilizzabile per una nuova installazione pulita.

### Cosa NON fa questa modalità (di proposito)

- Non si avvia da sola al riavvio del PC (va rilanciato `start.cmd` manualmente) — corretto per una fase di test dove non si vuole competere con MeasurLink in modo permanente
- Non è raggiungibile dalla rete (PostgreSQL e backend ascoltano solo su `127.0.0.1`, cioè solo dallo stesso PC) — per collegare l'Edge Agent da un'altra postazione della stessa officina serve un passo successivo (aprire la porta sul firewall e cambiare `listen_addresses`), volutamente non fatto in questa fase pilota
- Non installa un servizio Windows: quando si è convinti che leank-spc debba restare attivo in modo permanente, valutare il passaggio a Ubuntu (sotto)

### Risoluzione problemi

- **"impossibile eseguire script"**: usare sempre i file `.cmd` (non i `.ps1` direttamente) — i `.cmd` aggirano l'execution policy di PowerShell senza bisogno di cambiarla a livello di sistema
- **Il backend non risponde dopo `start.cmd`**: controllare `runtime\logs\backend.err.log`
- **I download falliscono** (tipico su Windows Server datati): `common.ps1` forza già TLS 1.2, ma se il problema persiste verificare manualmente che TLS 1.2 sia abilitato in `certutil -v -store My` o negli aggiornamenti di sistema
- **Serve ricominciare da capo**: `uninstall.cmd` poi `install.cmd`

---

## Ubuntu/Debian — deployment permanente

A differenza della modalità Windows, qui si usano i pacchetti di sistema (`apt`) e PostgreSQL gira come servizio systemd normale — niente trucco "zero admin": su Linux un'installazione del genere è più probabilmente un server dedicato, non una convivenza temporanea su un PC di produzione altrui.

### Requisiti

- Ubuntu 22.04+ o Debian equivalente (systemd, `apt`)
- Un utente con accesso `sudo`
- Connessione internet per l'installazione dei pacchetti

### Installazione (una tantum)

```bash
cd leank-spc/installer
chmod +x install.sh start.sh stop.sh uninstall.sh   # se i permessi non sono già stati preservati dalla copia
./install.sh
```

Chiede la password sudo se mancano pacchetti (`python3`, `python3-venv`, `postgresql`). Alla fine mostra la password dell'utente `admin` — annotarla.

### Uso quotidiano

- **Avviare**: `./installer/start.sh` (PostgreSQL è già gestito da systemd, si avvia da solo col sistema)
- **Fermare**: `./installer/stop.sh` (ferma solo il backend, non PostgreSQL)
- Backend: `http://127.0.0.1:8000/docs`

### Avvio automatico al boot (opzionale)

Non attivato di default da `install.sh` — è un passo deliberato in più per chi vuole il backend sempre attivo. Vedi [`installer/leank-spc.service`](../installer/leank-spc.service):

```bash
sudo cp installer/leank-spc.service /etc/systemd/system/
# modificare USER e il percorso assoluto nel file prima di attivarlo
sudo systemctl daemon-reload
sudo systemctl enable --now leank-spc
journalctl -u leank-spc -f   # per i log
```

### Disinstallazione

```bash
./installer/uninstall.sh
```

Rimuove il virtualenv Python e `backend/.env`. **Non tocca il database PostgreSQL** (potrebbe contenere dati reali importati) né disinstalla i pacchetti di sistema — lo script stampa i comandi da lanciare a mano se li si vuole rimuovere anche quelli.

---

## Collegare il primo strumento (Edge Agent)

Vedi [`edge-agent/README.md`](../edge-agent/README.md): copiare `edge-agent/config.example.yaml` in `config.yaml`, indicare la porta COM/dispositivo, ottenere un token di accesso via login (`POST /api/auth/login`, o dal pannello admin), poi lanciare l'agent.

## Importare la configurazione da MeasurLink

Vedi [`import-measurlink/README.md`](../import-measurlink/README.md) o, più comodo, la scheda **Import MeasurLink** del [pannello admin](../admin/index.html) — permette di testare la connessione, avviare una prova (dry-run) e seguire l'avanzamento in tempo reale prima di lanciare l'import vero.
