# Strumenti diagnostici (non fanno parte dell'app in produzione)

## serial-monitor.html — Test connessione seriale U-Wave/Digimatic

Pagina standalone (nessun build, nessun backend) che apre una porta COM
**direttamente dal browser** tramite la [Web Serial API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Serial_API)
e mostra ogni byte ricevuto — in hex e ASCII — oltre a provare a riconoscere
ogni riga come numero con la stessa regex usata dal parser reale
(`edge_agent/sources/digimatic_rs232.py`, funzione `parse_digimatic_frame`).

Serve a rispondere alla domanda "cosa manda davvero questo dispositivo?" prima
di finalizzare il parser — collegando un U-WAVE-R (o qualunque altro
convertitore Digimatic→seriale) reale, senza dover scrivere codice Python ad
hoc ogni volta.

### Come usarla

1. Aprire `serial-monitor.html` con doppio click, **in Chrome o Edge**
   (Firefox/Safari non supportano la Web Serial API).
2. Se il browser lo richiede, usare `file://` direttamente o servirla da un
   piccolo server locale (`python -m http.server` nella cartella `tools/`,
   poi `http://localhost:PORTA/serial-monitor.html`) — entrambi sono
   "contesti sicuri" validi per la Web Serial API. **Non funziona** aprendola
   da un indirizzo di rete tipo `http://192.168.x.x/...`, serve HTTPS in
   quel caso.
3. Click "Connetti...", scegliere la porta COM dal selettore nativo del
   browser (appare solo se ci sono porte seriali disponibili sul PC).
4. I parametri sono preimpostati per Mitutoyo U-Wave (57600-N-8-1, dal
   manuale — vedi `external-documents/U-Wave-sintesi-italiano.md`), ma
   modificabili per testare altri dispositivi.
5. Premere il tasto dati sullo strumento collegato: la riga arrivata compare
   nel log, con sotto l'esito del riconoscimento numerico.
6. "Scarica log" salva tutto in un `.txt` — utile per allegarlo a un
   messaggio quando si chiede aiuto per calibrare il parser.

### Perché una pagina web e non uno script Python

Nessuna dipendenza da installare sul PC di stazione (niente Python/pyserial
da configurare al volo): basta un browser già presente su qualunque PC
Windows moderno. Il limite è che serve Chrome/Edge e un "contesto sicuro" —
compromesso ragionevole per uno strumento diagnostico usato una tantum
durante il collaudo, non per l'uso quotidiano (quello lo fa l'Edge Agent vero,
in Python).

## network-device-scanner.ps1 — Scoprire PC in rete e i loro dispositivi COM/USB

Strumento diagnostico **precedente** alla configurazione vera e propria:
serve a capire "cosa c'è collegato a quel PC" **da remoto**, senza doverci
accedere via RDP e senza che l'Edge Agent sia già installato lì (per quello,
una volta che l'Edge Agent gira su una stazione, il frontend stesso mostra le
sue porte disponibili — vedi `GET /api/stations/{id}/available-ports` in
`docs/api.md` — questo script serve per la fase *prima* di quel punto).

Non è una pagina web: un browser non ha modo di scansionare una rete o
interrogare WMI su un'altra macchina. È uno script PowerShell con una piccola
interfaccia grafica nativa (Windows Forms).

### Come usarlo

```powershell
powershell -ExecutionPolicy Bypass -File network-device-scanner.ps1
```

(o doppio click, se l'associazione file `.ps1` lo permette)

1. Inserire la sottorete (es. `192.168.1`, precompilata da sola con quella di
   questo PC) e premere **"Scansiona rete"** — ping su `.1`-`.254`, qualche
   secondo
2. Selezionare un PC dall'elenco (doppio click, o selezione + pulsante
   **"Elenca dispositivi COM/USB"**)
3. L'elenco a destra mostra i dispositivi COM/USB trovati via WMI
   (`Win32_PnPEntity`) su quel PC

### Requisiti e limiti

- Usa `Get-CimInstance -ComputerName` (WMI/DCOM) — **non richiede** PowerShell
  Remoting/WinRM abilitato sul PC remoto, più probabile che funzioni "di
  serie" su una LAN aziendale tipica
- Serve però che il firewall del PC remoto permetta **"Windows Management
  Instrumentation (WMI)"** in ingresso, e credenziali con diritti sufficienti
  su quella macchina (di default usa l'utente della sessione corrente sullo
  script; la casella "Usa credenziali diverse" chiede username/password
  alternativi)
- Se l'interrogazione fallisce, il log nello script riporta la causa più
  probabile (firewall, credenziali, PC non raggiungibile via DCOM)
