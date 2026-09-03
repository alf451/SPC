# Guida completa — installazione, configurazione strumenti, test

Guida passo-passo pensata per essere seguita **senza saltare nessun passaggio e senza dover indovinare nulla**. Ogni sezione dice esattamente cosa digitare e cosa dovresti vedere se è andato tutto bene. Le note "⚠️ Errore noto" raccolgono problemi già capitati davvero durante i test di questo progetto, con la soluzione già pronta.

---

## Parte 1 — Installazione backend (Windows)

### Prerequisiti

- Windows 10/11, oppure Windows Server 2012 R2 o più recente (Windows Server 2012 "originale", non R2, non è garantito)
- Connessione internet (solo per il primo avvio — scarica Python e PostgreSQL)
- **La cartella del progetto NON deve stare dentro OneDrive/Dropbox/Google Drive** sul PC di destinazione — PostgreSQL scrive di continuo sui suoi file, e la sincronizzazione può corrompere i dati. Va bene una cartella locale semplice, es. `E:\leank-spc` o `C:\leank-spc`.

### 1.1 Procurarsi il progetto

**Se hai già Git installato** su questa macchina:

```powershell
cd E:\
git clone https://github.com/alf451/SPC.git leank-spc
cd E:\leank-spc
```

**Se non hai Git**: scarica lo zip da <https://github.com/alf451/SPC> (pulsante verde "Code" → "Download ZIP") con Chrome/Edge, estrailo in `E:\leank-spc`.

> ⚠️ **Non hai Git e vuoi installarlo** (consigliato — rende gli aggiornamenti futuri un semplice `git pull` invece di riscaricare tutto a mano): scarica l'installer con **Chrome o Edge**, mai con PowerShell direttamente — su Windows Server datati `Invoke-WebRequest` fallisce spesso per limiti di cifrari TLS del .NET Framework installato. Link: <https://git-scm.com/download/win>. Installa con "Esegui come amministratore", poi apri una **finestra PowerShell nuova** (il PATH si aggiorna solo per le finestre aperte dopo l'installazione).

### 1.2 Avviare l'installer

Doppio click su:
```
installer\install.cmd
```

oppure da PowerShell:
```powershell
cd E:\leank-spc
installer\install.cmd
```

> ⚠️ **ATTENZIONE — non premere mai Ctrl+C in questa finestra durante l'esecuzione**, anche se sembra ferma per qualche minuto (è normale durante il download o l'inizializzazione del database). Su Windows un Ctrl+C in questa console può arrestare in modo anomalo anche PostgreSQL, che gira nella stessa finestra — capitato davvero durante i test, con conseguente "Accesso negato" al riavvio successivo (vedi troubleshooting sotto).

Lo script farà alcune domande, in quest'ordine:

1. **Modalità PostgreSQL** — premi Invio per **"portable"** (il default: nessun servizio Windows, zero privilegi richiesti). L'altra opzione, "completa", richiede una sessione da amministratore e installa PostgreSQL come vero servizio Windows — usarla solo per un deployment permanente, non per un test.
2. **Porta del backend** — premi Invio per usare `8000`, oppure scrivi un numero diverso se sai già che qualcos'altro (IIS, Reporting Services, un altro programma) occupa quella porta su questa macchina.
   > ⚠️ Rispondi **solo con un numero**. Se per errore scrivi altro (es. una password, capitato durante i test), lo script te lo segnala e richiede di nuovo, non si blocca più.
3. **Indirizzo su cui rendere raggiungibile il backend** — lo script propone l'IP di rete di questo PC:
   - **Invio** (accetta l'IP proposto) → raggiungibile anche da altre postazioni della rete (serve se gli strumenti/Edge Agent sono su PC diversi da questo)
   - **`127.0.0.1`** o **`localhost`** → raggiungibile solo da questo PC
4. **Usare HTTPS?** → `s`/`N`. Per un primo test in LAN va bene rispondere `N` (HTTP semplice).

### 1.3 Verificare che sia andato a buon fine

Alla fine dovresti vedere:
```
=== Installazione completata ===
...
Login iniziale: utente 'admin', password in <percorso>\runtime\secrets\admin_password.txt
```

Se invece lo script si è fermato con un errore rosso **prima** di questa riga, vedi la sezione [Troubleshooting](#troubleshooting) in fondo.

**Annotati subito**:
- La password admin, aprendo il file indicato (es. con `notepad`)
- L'indirizzo esatto mostrato in fondo (es. `http://127.0.0.1:8000` o `http://NOME-PC:8000`)

### 1.4 Avviare/fermare il backend nei giorni successivi

Il backend **non parte da solo** al riavvio del PC (nessun servizio Windows registrato in modalità pilota) — va avviato a mano ogni volta:

```powershell
cd E:\leank-spc
installer\start.cmd
```

Per fermarlo:
```powershell
installer\stop.cmd
```

> ⚠️ **Il backend si ferma se ti disconnetti dalla sessione RDP** (non è un servizio Windows, è un processo legato alla sessione che lo ha avviato). Se lo installi su un server a cui accedi via Desktop remoto e ti serve che resti attivo anche disconnettendoti, vedi [Tenerlo attivo anche dopo la disconnessione RDP](#tenerlo-attivo-anche-dopo-la-disconnessione-rdp) più sotto.

### 1.5 Verifica rapida che il backend risponda

Apri nel browser:
```
http://127.0.0.1:8000/health
```
Dovresti vedere `{"status":"ok"}`. Se invece il browser dice "impossibile raggiungere il sito" / `ERR_CONNECTION_REFUSED`, il backend non è (più) in esecuzione — rilancia `installer\start.cmd`.

---

## Parte 2 — Frontend (l'interfaccia web vera e propria)

Il frontend (Cruscotto, Raccolta Dati, Routine & Quote, Strumenti, Amministrazione) è un'app che va **buildata una volta** prima di poter essere usata — il risultato sono file statici (HTML/CSS/JS) che il backend serve da solo, senza bisogno di Node.js sul PC finale dopo questo passaggio.

### 2.1 Dove buildarlo

> ⚠️ **Node.js richiede almeno Windows 10 / Server 2016**. Su un Windows Server 2012 (anche R2) l'installazione di Node.js recente **fallisce all'avvio** con l'errore "Node.js is only supported on Windows 10, Windows Server 2016, or higher" — riscontrato davvero durante i test. Se il PC dove installi leank-spc è un server datato, **non provare a buildare il frontend lì**: buildalo su un PC normale (il tuo portatile, un altro PC in ufficio con Windows 10/11) e trasferisci solo il risultato.

Sul PC dove builda (richiede [Node.js](https://nodejs.org/) 18 o superiore):

```powershell
cd frontend
npm install
npm run build
```

Questo crea la cartella `frontend\dist\` (solo file statici, nessuna dipendenza da Node.js per funzionare).

### 2.2 Portare `dist\` sul PC di destinazione

Se hai buildato su un PC diverso da quello di destinazione: copia l'intera cartella `frontend\dist\` (via chiavetta USB, cartella di rete, o clipboard RDP se stai lavorando su un server remoto) dentro:
```
<cartella progetto>\frontend\dist\
```
Deve risultare `frontend\dist\index.html` — **non** `frontend\dist\dist\index.html` (se l'estrazione di uno zip crea una sottocartella in più, sposta il contenuto di un livello più su).

### 2.3 Attivarlo

```powershell
installer\stop.cmd
installer\start.cmd
```

Il backend rileva da solo `frontend\dist\` e la serve dalla propria root. Apri:
```
http://127.0.0.1:8000/
```
Dovresti vedere la schermata di login del frontend (non più solo `/docs`).

### 2.4 Primo accesso

Utente: `admin`
Password: quella in `runtime\secrets\admin_password.txt` (vedi punto 1.3)

---

## Parte 3 — Configurare gli strumenti di misura (DAQ)

leank-spc riceve le misure tramite un **Edge Agent** (un piccolo programma Python da eseguire sul PC dove sono fisicamente collegati gli strumenti), che parla con uno o più **dispositivi DAQ** configurati centralmente nel backend. Questa parte spiega come configurarli — la sezione **Amministrazione** del frontend (o in alternativa [`admin/index.html`](../admin/index.html), pannello standalone senza build) sono l'interfaccia per farlo.

### 3.1 I tre concetti da capire

| Concetto | Cos'è | Esempio |
|---|---|---|
| **Sede/Stazione** | Il PC/postazione fisica dove avviene il collaudo | "Reparto Qualità", stazione "SPC-01" |
| **Dispositivo DAQ** (`daq_devices`) | Il **profilo** di un tipo di apparato: come parla (protocollo/parametri) | "U-Wave" (RS232, 57600-N-8-1) |
| **Sorgente DAQ** (`daq_sources`) | Una **porta/canale fisico specifico** su una stazione, che usa un certo profilo dispositivo | Stazione "SPC-01", porta COM3, canale 1, profilo "U-Wave" |

Un dispositivo (profilo) può avere **più sorgenti** — è esattamente il caso di un ricevitore multi-canale come l'U-Wave-R, dove più trasmettitori riportano sulla stessa porta COM ma su canali diversi.

### 3.2 Protocolli supportati (`connection_type`)

| Tipo | Quando usarlo | Parametri tipici (in `config`) |
|---|---|---|
| `rs232` | Strumento collegato via porta seriale/USB-seriale (cavo Digimatic + convertitore, es. Mitutoyo U-Wave, IT-016U, GageWay) | `baud_rate`, `parity`, `data_bits`, `stop_bits`, terminatore riga |
| `usb_hid` | Convertitore USB che emula una tastiera (digita il valore come se lo scrivesse un operatore) | `device_path` (opzionale, se c'è più di un convertitore sullo stesso PC) |
| `manual` | Nessun collegamento automatico — l'operatore inserisce il valore a mano dalla schermata "Raccolta Dati" | nessuno |
| `opcua` / `mtconnect` | Predisposti per integrazioni future con macchine CNC/CMM che espongono questi standard industriali | da definire caso per caso |

### 3.3 Creare un profilo dispositivo (esempio: Mitutoyo U-Wave)

Nel frontend: **Amministrazione → Dispositivi → Nuovo profilo dispositivo**
(oppure in `admin/index.html`, stessa sezione)

- Nome: `U-Wave`
- Tipo: `rs232`

Parametri di comunicazione U-Wave (dal manuale Mitutoyo): **57600 baud, 8 bit dati, nessuna parità, 1 bit di stop** — vedi [`test-mitutoyo-uwave.md`](test-mitutoyo-uwave.md) per i dettagli completi su questo dispositivo specifico.

### 3.4 Creare una sorgente (porta+canale su una stazione)

**Amministrazione → Dispositivi → Nuova sorgente DAQ**

- Stazione: quella dove è fisicamente collegato il ricevitore
- Dispositivo: il profilo creato al punto 3.3
- Nome: es. "Calibro reparto A"
- Porta: la porta COM (**virtuale**, nel caso di U-Wave — creata dal software U-WAVEPAK, non esiste finché quel software non è installato e configurato su questo PC)
- Canale: il numero di canale assegnato al trasmettitore (via U-WAVEPAK), se il ricevitore è multi-canale

### 3.5 Testare la connessione

Nella tabella delle sorgenti DAQ, pulsante **"Prova"** — chiede all'Edge Agent connesso a quella stazione lo stato reale della porta (connesso? ultima lettura quando?). Se l'Edge Agent non è ancora attivo su quella stazione, il test lo segnala chiaramente invece di dare un errore generico.

### 3.6 Avviare l'Edge Agent sulla stazione

Sul PC dove sono collegati fisicamente gli strumenti (vedi [`edge-agent/README.md`](../edge-agent/README.md) per i dettagli completi):

```powershell
cd edge-agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy config.example.yaml config.yaml
# modificare config.yaml: station_id, url del backend, token, elenco sorgenti
python -m edge_agent.main config.yaml
```

Il token si ottiene facendo login via API con un utente dedicato — istruzioni dettagliate in `edge-agent/README.md`.

---

## Parte 4 — Testare l'applicazione end-to-end

1. **Amministrazione → Stazioni**: crea almeno una sede e una stazione (se non già fatto)
2. **Routine & Quote**: crea un Part (es. "Pezzo di prova"), poi una Feature con una tolleranza (es. target 10, limite inf. 9.9, limite sup. 10.1), poi una Routine, e collega la Feature alla Routine
3. **Raccolta Dati**: avvia un nuovo Run scegliendo la Routine e la stazione create
4. **Inserisci una misura**:
   - Se hai l'Edge Agent collegato a uno strumento reale: premi il tasto dati sullo strumento, la misura deve comparire in tempo reale nella tabella "Osservazioni recenti"
   - Altrimenti: usa il form "Inserimento manuale" nella stessa schermata — stesso risultato, comparsa immediata via WebSocket
5. Se il valore è fuori dalle tolleranze impostate al punto 2, la riga compare evidenziata in rosso — è il segnale che il controllo di conformità funziona

Se tutti questi passaggi funzionano, l'installazione è verificata end-to-end.

---

## Tenerlo attivo anche dopo la disconnessione RDP

Se installi su un server a cui accedi via Desktop remoto e non vuoi che il backend si fermi disconnettendoti, la soluzione più semplice senza installare software aggiuntivo è un'**attività pianificata** di Windows configurata per girare "anche se l'utente non è connesso":

```powershell
$action = New-ScheduledTaskAction -Execute "E:\leank-spc\installer\start.cmd" -WorkingDirectory "E:\leank-spc"
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "NOME-UTENTE" -LogonType Password -RunLevel Highest
Register-ScheduledTask -TaskName "leank-spc-backend" -Action $action -Trigger $trigger -Principal $principal
```

Ti chiederà la password dell'utente al momento della registrazione (necessaria per "esegui anche se l'utente non è connesso"). Dopo la registrazione puoi avviarla subito senza aspettare il riavvio:
```powershell
Start-ScheduledTask -TaskName "leank-spc-backend"
```

Per fermarla: `installer\stop.cmd` funziona comunque normalmente (ferma il processo, non l'attività pianificata in sé — che al prossimo riavvio del PC lo farebbe ripartire).

---

## Troubleshooting

Problemi realmente incontrati durante i test di questo progetto, con la soluzione.

### "pg_ctl: un altro server potrebbe essere in esecuzione" + "Accesso negato"

Causa tipica: PostgreSQL si è arrestato in modo anomalo (es. per un Ctrl+C nella console, vedi avviso sopra) lasciando un processo residuo o un file di lock non valido.

```powershell
cd E:\leank-spc
taskkill /F /IM postgres.exe /T
Remove-Item runtime\pgdata\postmaster.pid -ErrorAction SilentlyContinue
installer\start.cmd
```

Se persiste, disinstalla e reinstalla (nessun dato reale da perdere in fase di test):
```powershell
installer\uninstall.cmd
installer\install.cmd
```

### I download falliscono con "Connessione sottostante chiusa" durante `install.cmd`

Tipico su Windows Server datati: il .NET Framework installato offre cifrari TLS troppo deboli per i siti di destinazione. Lo script tenta da solo un metodo alternativo (`bitsadmin`); se fallisce anche quello, vedi "Installazione offline" in [`installazione.md`](installazione.md#installazione-offline--senza-download) — si scaricano i file una volta con un browser (Chrome/Edge, che ha un motore TLS proprio) e si mettono in una cartella `vendor\` che l'installer controlla prima di scaricare.

### Il browser dice "impossibile raggiungere il sito" su `127.0.0.1:8000`

Il backend non è in esecuzione. Controlla `runtime\logs\backend.err.log` per vedere se c'è un errore, altrimenti rilancia `installer\start.cmd`. Se il problema si ripresenta ogni volta che ti disconnetti da RDP, vedi la sezione dedicata sopra.

### `npm run build` (o anche solo avviare Node.js) dà "Node.js is only supported on Windows 10..."

Il PC dove stai buildando è troppo vecchio per la versione di Node.js installata. Non forzare con `NODE_SKIP_PLATFORM_CHECK` (rischio di comportamento imprevedibile) — builda su un altro PC con Windows 10/11 e trasferisci solo `frontend\dist\` (vedi Parte 2).

### Il prompt di installazione per la porta dà un errore .NET invece di richiedere

Versioni del progetto precedenti a questo fix potevano crashare se si rispondeva con del testo non numerico alla domanda sulla porta. Aggiornato — ora richiede semplicemente di nuovo. Se capita ancora, assicurati di avere l'ultima versione (`git pull`).
