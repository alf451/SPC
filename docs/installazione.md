# Guida installazione

Due sistemi operativi supportati, e per ciascuno **tre modalità di rete** indipendenti — la scelta si fa rispondendo a due domande durante l'installazione, non modificando file a mano:

- **[Windows — modalità pilota](#windows--modalità-pilota)**: per affiancare MeasurLink durante un test sul campo, sullo stesso PC del reparto qualità. Zero costi, zero admin, tutto reversibile.
- **[Ubuntu/Debian — deployment permanente](#ubuntudebian--deployment-permanente)**: per un server dedicato (proprio o del cliente), pensato per restare attivo stabilmente, non per convivere temporaneamente con qualcos'altro.

## Le tre modalità di rete (valgono su entrambi i sistemi operativi)

Durante l'installazione (`install.cmd`/`install.sh`) vengono chieste due cose: **la porta** (utile se qualcos'altro, es. IIS, occupa già la 8000) e **su quale indirizzo il backend deve rispondere**. Su Windows quest'ultima domanda propone come default l'IP di rete rilevato automaticamente sulla macchina (basta premere invio per accettarlo) — scrivere `127.0.0.1` o `localhost` per limitare l'accesso a questo solo PC. Da queste due risposte nascono le tre modalità:

| Modalità | Quando serve | Cosa succede | Risposta alla domanda sull'indirizzo |
|---|---|---|---|
| **1. Locale** | Un solo PC, backend ed Edge Agent sulla stessa macchina | `http://127.0.0.1:PORTA`, raggiungibile solo da questo PC | `127.0.0.1` o `localhost` |
| **2. Intranet (LAN)** | Edge Agent su altre postazioni della stessa officina/rete | `http://IP-o-NOME-PC:PORTA`, raggiungibile da tutta la rete locale | Invio (accetta l'IP proposto) — aperta anche la porta sul firewall |
| **3. HTTPS** | Come sopra ma con traffico cifrato — obbligatorio se il backend è raggiungibile anche da fuori la rete fidata | `https://...`, con un certificato auto-firmato (LAN) o vero (uso pubblico, vedi sezione dedicata sotto) | Come sopra, poi "sì" a "Usare HTTPS?" |

Le modalità 1 e 2 sono completamente automatiche e non richiedono nulla oltre a rispondere alle domande. La modalità 3 con certificato **auto-firmato** (per LAN) è automatica; con certificato **pubblico vero** (per esposizione su internet) richiede alcuni prerequisiti che l'installer non può procurarsi da solo — vedi [HTTPS con certificato pubblico](#https-con-certificato-pubblico-esposizione-su-internet) in fondo a questa pagina.

**Non sei sicuro di quale scegliere?** Se hai un solo PC e un solo strumento collegato: modalità 1. Se hai più postazioni in officina che devono mandare misure allo stesso backend: modalità 2. Se il backend deve essere raggiungibile da fuori la rete aziendale (es. accesso da remoto): modalità 3 con certificato pubblico — chiedi consiglio prima di procedere, ha implicazioni di sicurezza da valutare caso per caso.

---

## Usare il frontend web

Dopo l'installazione, l'indirizzo mostrato alla fine (es. `http://127.0.0.1:8000`) apre il **frontend web** — l'interfaccia per l'uso quotidiano, con cinque sezioni nel menu laterale:

| Sezione | A cosa serve |
|---|---|
| **Cruscotto** | Panoramica: stazioni registrate, quante hanno un Run attivo in questo momento |
| **Raccolta Dati** | La schermata operativa per il collaudo in officina: si seleziona (o avvia) un Run, si vedono le quote/tolleranze della Routine, le misure arrivano in tempo reale (da Edge Agent o inserite a mano se lo strumento non è ancora collegato) |
| **Routine & Quote** | Creare/consultare Part, Routine, Feature e le loro versioni di tolleranze (ingegneria/qualità) |
| **Strumenti** | Anagrafica gage e gestione calibrazioni |
| **Amministrazione** | Utenti, sedi/stazioni, profili e sorgenti DAQ — stessa funzione di [`admin/index.html`](../admin/index.html) ma integrata nell'app principale |

Login con l'utente `admin` e la password mostrata a fine installazione (la stessa usata per il pannello admin standalone).

### admin/index.html resta disponibile

Il pannello di configurazione standalone (`admin/index.html`, apribile con doppio click, senza build) **non è stato tolto** ed è tenuto aggiornato in parallelo: utile per una configurazione rapida senza aprire il frontend completo, o come alternativa se per qualche motivo il frontend non è stato ancora buildato su questa installazione (vedi sotto). Le due interfacce parlano con le stesse identiche API — quello che si fa in una si vede subito nell'altra.

### Se il frontend non compare (mostra solo `/docs`)

Il frontend è un'app Vue che va **buildata una volta** prima di essere distribuita (richiede Node.js solo sulla macchina dove si builda, mai su quella del cliente):

```bash
cd frontend
npm install
npm run build
```

Questo crea `frontend/dist/` — copiarla dentro la cartella del progetto (accanto a `backend/`, `installer/`, ecc.) **prima** di eseguire `install.cmd`/`install.sh` sul PC di destinazione, oppure semplicemente riavviare il backend (`stop.cmd`/`start.cmd`) se il progetto è già installato: il backend la rileva da sola e la serve sulla propria root, senza nessuna configurazione aggiuntiva né un secondo webserver. Dettagli in [`frontend/README.md`](../frontend/README.md).

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
4. Attendere (qualche minuto, scarica ed estrae Python e, a seconda della scelta fatta al passo successivo, PostgreSQL)
5. Quando chiede la **modalità PostgreSQL**: vedi la sezione dedicata [PostgreSQL: portable o completo](#postgresql-portable-o-completo) subito sotto — invio per "portable" (il default, zero admin)
6. Quando chiede la **porta**: premere Invio per usare la 8000, oppure digitarne un'altra se sospetti un conflitto (es. con IIS)
7. Quando chiede **su quale indirizzo rendere raggiungibile il backend**: premere invio per accettare l'IP di rete proposto (serve per collegare Edge Agent su altre postazioni), oppure scrivere `127.0.0.1`/`localhost` per restare raggiungibili solo da questo PC (vedi [le tre modalità](#le-tre-modalità-di-rete-valgono-su-entrambi-i-sistemi-operativi) sopra)
8. Quando chiede se usare **HTTPS**: rispondere "s" solo se serve traffico cifrato (consigliato se si è risposto "s" al punto precedente e la rete non è completamente fidata)
9. Alla fine viene mostrata la password dell'utente `admin` — **annotarla**, serve per accedere, insieme all'indirizzo esatto da usare (cambia in base alle risposte date sopra)

Lo script è rieseguibile in sicurezza: se lo si lancia di nuovo senza specificare parametri, ripropone le stesse domande solo se non ha già una configurazione salvata — altrimenti riparte con quella esistente senza chiedere nulla.

### PostgreSQL: portable o completo

Al primo avvio di `install.cmd`, prima ancora della porta, viene chiesto che tipo di PostgreSQL usare. La scelta viene salvata (`runtime\postgres_mode.txt`) e non viene richiesta di nuovo nelle esecuzioni successive.

| Modalità | Cosa fa | Richiede admin? | Quando sceglierla |
|---|---|---|---|
| **Portable** (default, invio) | Scarica lo zip binario di PostgreSQL, lo estrae in `runtime\pgsql`, nessun servizio Windows registrato — esattamente come nella modalità pilota "zero admin" descritta sopra | No | Test sul campo, PC del cliente, quando non si vuole/può toccare il sistema |
| **Completo** | Usa un PostgreSQL vero, con servizio Windows: se ne trova già uno installato sulla macchina lo riusa da solo (chiede solo la password dell'utente `postgres` esistente); altrimenti scarica l'installer ufficiale EDB (~350 MB) e lo esegue in modalità silenziosa, registrando il servizio `postgresql-leankspc` | Sì, **solo per installarne uno nuovo** (se ne riusa uno esistente non serve) | Deployment più stabile/permanente su Windows, o quando si vuole condividere la stessa istanza PostgreSQL con altri usi sulla macchina |

Note importanti sulla modalità **Completo**:

- Se non c'è ancora nessun PostgreSQL installato e la sessione non è amministratore, l'installer si ferma con un errore chiaro invece di procedere a metà — rilanciare `install.cmd` con tasto destro → "Esegui come amministratore", oppure scegliere "portable".
- Le password generate (superuser `postgres`, account di servizio, utente applicativo `leank_spc`) vengono salvate in `runtime\secrets\` esattamente come in modalità portable — non finiscono mai nella console né in git.
- **Questo ramo (installazione di un PostgreSQL nuovo) è implementato secondo la documentazione ufficiale EDB ma non è stato collaudato dal vivo** in fase di sviluppo, perché l'ambiente usato per costruirlo non aveva una sessione con privilegi di amministratore disponibile. Il riuso di un'installazione già esistente idem non è stato provabile per mancanza di un PostgreSQL "completo" già installato a disposizione. **Prima di usarla su una macchina del cliente, va provata almeno una volta su una macchina non critica** (es. il server Windows 2012 "cavia" di cui si è già parlato) — se qualcosa non torna nei parametri dell'installer silenzioso o nella rilevazione via registro, è lì che va aggiustato.
- `uninstall.cmd` in modalità Completo **non disinstalla PostgreSQL** (potrebbe contenere dati importanti o essere usato da altro): rimuove solo la cartella `runtime\` del progetto e stampa i comandi da lanciare a mano se si vuole rimuovere anche il servizio (`Stop-Service postgresql-leankspc; sc.exe delete postgresql-leankspc`, oppure disinstallarlo da Pannello di controllo).

### Uso quotidiano

- **Avviare** (a ogni riavvio del PC o dopo aver fermato tutto): doppio click su **`start.cmd`**
- **Fermare**: doppio click su **`stop.cmd`**
- Il backend risponde all'indirizzo mostrato alla fine dell'installazione (es. `http://127.0.0.1:8000/docs` in modalità locale, `https://NOME-PC:8443/docs` in modalità HTTPS — Swagger UI, per provare le API dal browser) e il [pannello admin](../admin/index.html) permette di configurare stazioni/DAQ e lanciare l'import da MeasurLink senza scrivere codice

### Disinstallazione

Doppio click su **`uninstall.cmd`** → conferma scrivendo `si`. Rimuove tutto (PostgreSQL, pacchetti Python, database, dati) dalla cartella `runtime\`; il codice del progetto resta intatto e riutilizzabile per una nuova installazione pulita.

### Cosa NON fa questa modalità (di proposito)

- Non si avvia da sola al riavvio del PC (va rilanciato `start.cmd` manualmente) — corretto per una fase di test dove non si vuole competere con MeasurLink in modo permanente
- **PostgreSQL** (in entrambe le modalità Portable e Completo) resta comunque raggiungibile solo su `127.0.0.1` anche scegliendo la modalità "intranet" per il backend — solo il backend (le API) diventa raggiungibile dalla rete, il database resta privato a questo PC in ogni caso
- In modalità PostgreSQL **Portable** non viene installato nessun servizio Windows (nemmeno per il database): quando si è convinti che leank-spc debba restare attivo in modo permanente, valutare la modalità PostgreSQL **Completo** (sopra) oppure il passaggio a Ubuntu (sotto)

### Risoluzione problemi

- **"impossibile eseguire script"**: usare sempre i file `.cmd` (non i `.ps1` direttamente) — i `.cmd` aggirano l'execution policy di PowerShell senza bisogno di cambiarla a livello di sistema
- **Il backend non risponde dopo `start.cmd`**: controllare `runtime\logs\backend.err.log`
- **I download falliscono con "Connessione sottostante chiusa: errore imprevisto durante un'operazione di invio"** (riscontrato su un Windows Server 2012 di test): non è mancanza di TLS 1.2 (`common.ps1` lo forza già) ma più spesso un limite sui **cifrari** che il .NET Framework installato offre — il sito di destinazione rifiuta la connessione a metà. Lo script tenta da solo un metodo alternativo (`bitsadmin`, che usa lo stack di rete del sistema operativo invece di .NET) prima di arrendersi; se fallisce anche quello, vedi [Installazione offline](#installazione-offline--senza-download) qui sotto.
- **Serve ricominciare da capo**: `uninstall.cmd` poi `install.cmd`
- **"Non sono riuscito a creare la regola firewall"** (modalità intranet/HTTPS): serve una sessione PowerShell **da amministratore** solo per questo passo specifico — lo script stampa il comando esatto da incollare in una finestra PowerShell aperta con "Esegui come amministratore". Il resto dell'installazione non richiede privilegi elevati.
- **Il browser mostra "connessione non sicura"** con HTTPS: atteso con un certificato auto-firmato (modalità LAN) — il traffico è comunque cifrato, si può procedere/accettare l'eccezione. Se invece ci si aspettava un certificato pubblico riconosciuto, vedi la sezione sotto.

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

Chiede la password sudo se mancano pacchetti (`python3`, `python3-venv`, `postgresql`), poi le stesse tre domande della versione Windows (porta, raggiungibilità in rete, HTTPS — vedi [le tre modalità](#le-tre-modalità-di-rete-valgono-su-entrambi-i-sistemi-operativi) sopra). Alla fine mostra la password dell'utente `admin` e l'indirizzo esatto da usare — annotarli entrambi.

Per un'installazione senza domande (script/automazioni), impostare le variabili prima di lanciarlo:

```bash
PORT=8443 EXPOSE_NETWORK=si HTTPS=si ./install.sh
```

### Uso quotidiano

- **Avviare**: `./installer/start.sh` (PostgreSQL è già gestito da systemd, si avvia da solo col sistema)
- **Fermare**: `./installer/stop.sh` (ferma solo il backend, non PostgreSQL)
- Backend: indirizzo mostrato alla fine dell'installazione

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

---

## HTTPS con certificato pubblico (esposizione su internet)

Il certificato **auto-firmato** generato in automatico dall'installer va bene per una LAN aziendale fidata, ma **non per esporre il backend su internet**: nessun browser/client si fiderà di un certificato non firmato da una Certification Authority riconosciuta, e c'è il rischio concreto che qualcuno (te compreso, in futuro, per fretta) disabiliti la verifica del certificato altrove per "far sparire l'avviso" — a quel punto la cifratura non protegge più da niente.

Per un vero certificato pubblico servono tre cose che **nessuno script può procurarti da solo**, perché non sono sotto il controllo di questa macchina:

1. **Un nome a dominio** (es. `spc.tuaazienda.it`) che punti all'IP pubblico del server
2. **La porta 443 raggiungibile dall'esterno** — va aperta sul router/firewall perimetrale dell'azienda, non solo sul firewall Windows/Linux di questa macchina (passo che va fatto da chi amministra la rete aziendale)
3. Un modo per **dimostrare il controllo del dominio** a una Certification Authority (Let's Encrypt è gratuita e automatizzata, è la scelta di gran lunga più comune)

Una volta disponibili questi tre elementi, il modo più semplice — su entrambi i sistemi operativi — è mettere **[Caddy](https://caddyserver.com/)** davanti al backend: è un web server che ottiene e rinnova da solo i certificati Let's Encrypt, con una configurazione di poche righe.

**Ubuntu:**

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
```

Poi in `/etc/caddy/Caddyfile`:

```
spc.tuaazienda.it {
    reverse_proxy 127.0.0.1:8000
}
```

```bash
sudo systemctl reload caddy
```

Da questo momento leank-spc **resta in modalità locale (HTTP, 127.0.0.1)** — è Caddy a parlare HTTPS con il mondo esterno e a inoltrare in chiaro solo verso il backend sulla stessa macchina, che non serve più esporre direttamente né in HTTPS né in rete.

**Windows**: Caddy è disponibile anche come singolo eseguibile per Windows ([download](https://caddyserver.com/download)) con lo stesso principio (`Caddyfile` + `caddy run`), ma per un uso permanente su Windows è più naturale valutare il passaggio a Ubuntu per questo scenario specifico (rinnovo certificati via systemd timer, gestione più matura).

Se preferisci non introdurre un altro componente (Caddy) e vuoi dare il certificato direttamente a leank-spc: ottienilo con [certbot](https://certbot.eff.org/) (Ubuntu) o [win-acme](https://www.win-acme.com/) (Windows), poi passa i percorsi dei file a `install.sh`/`install.ps1` con `SSL_CERT_FILE`/`SSL_KEY_FILE` (Ubuntu) o `-SslCertFile`/`-SslKeyFile` (Windows) — attenzione però al rinnovo: un certificato Let's Encrypt scade ogni 90 giorni e va rigenerato/ricopiato a mano con questa via, mentre Caddy lo fa da solo.
