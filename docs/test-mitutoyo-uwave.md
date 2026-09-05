# Test con il sistema Mitutoyo U-Wave

Guida pratica per collegare e collaudare un sistema **U-Wave** (Mitutoyo) — raccolta dati wireless da strumenti di misura — con leank-spc. Presuppone di aver già completato l'installazione base (vedi [`guida-installazione-e-test.md`](guida-installazione-e-test.md)).

## Cos'è il sistema U-Wave

Tre componenti:

- **U-WAVE-T** (trasmettitore) — piccolo dispositivo a batteria collegato al singolo strumento (calibro, micrometro, comparatore...) tramite il cavo Digimatic dello strumento stesso
- **U-WAVE-R** (ricevitore) — si collega via **USB** al PC, riceve via radio da più U-WAVE-T contemporaneamente
- **U-WAVEPAK** — software Mitutoyo (dal CD/sito del prodotto) che va installato sul PC: crea una **porta COM virtuale** sopra la connessione USB del ricevitore. leank-spc (tramite l'Edge Agent) legge quella porta come una normale porta seriale, senza sapere nulla del livello radio sottostante.

**Importante**: senza U-WAVEPAK installato e configurato, la porta COM virtuale non esiste — leank-spc può solo *leggere* quella porta una volta creata, non sostituisce il driver Mitutoyo.

## Multi-strumento: come funziona

Il sistema supporta nativamente più strumenti, ed è già coerente con il modello dati di leank-spc:

- Ogni U-WAVE-T ha un **canale** assegnabile via U-WAVEPAK → corrisponde a `daq_sources.channel_no`
- Più U-WAVE-T riportano sulla **stessa porta COM virtuale** (stesso ricevitore), distinti per canale → una `daq_sources` per canale, tutte con lo stesso `port` e lo stesso `daq_devices` (profilo "U-Wave")
- Si possono usare più U-WAVE-R sullo stesso PC (una porta COM virtuale per ricevitore, un "Group ID" evita interferenze tra gruppi)

## Parametri di comunicazione

Confermati dal manuale Mitutoyo **e** da una cattura diretta sull'hardware reale (vedi sotto):

```
Baud rate:    57600
Parità:       nessuna
Bit dati:     8
Bit di stop:  1
Terminatore:  CR (\r, 0x0D) da solo — NON CRLF
```

### Formato del frame — confermato ✅

Catturato dal vivo con un ricevitore U-Wave-R e più trasmettitori U-Wave-T abbinati:

```
DT10000+00000011.88M
DT10002-0000000.001M
ST1000100009233899
TI1120000009241511
```

- **`DT<5 cifre><segno><cifre>.<cifre><lettera unità>`** — è una misura. Le 5 cifre dopo "DT" sono il **canale** assegnato al trasmettitore via U-WAVEPAK (corrisponde esattamente a `daq_sources.channel_no`) — es. `DT10000` = canale 10000. Il numero di cifre prima/dopo il punto **non è fisso** (es. `+00000011.88` vs `-0000000.001`), il parser non deve assumere una lunghezza costante. La lettera finale (`M` in tutte le catture) è l'unità.
- **`ST...`** e **`TI...`** — messaggi di **stato** (es. registrazione/conferma del canale), **non misure** — vanno scartati, non interpretati come letture a zero o non valide.
- Più trasmettitori abbinati allo stesso ricevitore condividono **la stessa porta COM virtuale** — il canale che li distingue è dentro al testo del frame, non nella porta stessa.

Il parser (`edge_agent/sources/digimatic_rs232.py::parse_uwave_frame`) implementa esattamente questo formato — vedi il codice per i dettagli, incluso un test rapido contro le righe reali catturate.

**Ancora non confermato**: il frame del comando di "ritiro" (tasto dati tenuto premuto 5 secondi) — nessuna cattura finora lo mostra distintamente; se capita di osservarlo, segnalarlo per aggiornare il parser.

**Mappatura strumenti osservata in una sessione di test reale** (utile come riferimento, verificare comunque in U-WAVEPAK quale canale è assegnato a quale trasmettitore sulla propria installazione):

| Canale (`channel_no`) | Strumento |
|---|---|
| 10000 | Calibro "TSVETI" |
| 10001 | Calibro "LUCIA" |
| 10002 | Micrometro |

## Procedura di test

### 1. Prerequisiti sul PC di stazione

- U-WAVEPAK installato e configurato (il ricevitore USB collegato, almeno un trasmettitore abbinato/registrato — verificabile nell'interfaccia di U-WAVEPAK, colonna "S": `r` = registrato non connesso, `c` = connesso)
- Annotare il **numero di porta COM virtuale** assegnato (visibile in U-WAVEPAK o in Gestione dispositivi di Windows)

### 2. (facoltativo) Guardare i byte grezzi con un terminale seriale

Il formato è già confermato (sopra), questo passo serve solo se si vuole verificare la propria installazione specifica o si sospetta un problema. Usa [`edge-agent/tools/serial-monitor.html`](../edge-agent/tools/serial-monitor.html) (standalone, Chrome/Edge — richiede Web Serial API) oppure un qualunque terminale seriale generico (es. quello di sistema, o PuTTY in modalità Serial), parametri 57600-N-8-1, terminatore CR.

Premi il tasto dati sullo strumento: dovresti vedere righe `DT<canale><valore>M` per ogni misura, e occasionalmente righe `ST...`/`TI...` di stato — normali, il parser le ignora da solo.

### 3. Configurare U-Wave in leank-spc

Segui la Parte 3 di [`guida-installazione-e-test.md`](guida-installazione-e-test.md#parte-3--configurare-gli-strumenti-di-misura-daq):

1. **Amministrazione → Dispositivi → Nuovo profilo dispositivo**: nome `U-Wave`, tipo `rs232`, parametri 57600-N-8-1
2. **Nuova sorgente DAQ** per ogni canale/trasmettitore in uso, tutte sulla stessa porta COM virtuale, ciascuna con il proprio `channel_no` (es. 10000, 10001, 10002 — vedi tabella sopra)
3. Configura l'Edge Agent sulla stazione (`edge-agent/config.yaml`): un'unica voce con `port`, `channels: [10000, 10001, 10002]` e `frame_format: "uwave"` — vedi l'esempio in [`edge-agent/config.example.yaml`](../edge-agent/config.example.yaml) e [`edge-agent/README.md`](../edge-agent/README.md)

### 4. Test end-to-end

Segui la Parte 4 di `guida-installazione-e-test.md`: avvia un Run, premi il tasto dati sullo strumento, verifica che la misura compaia in tempo reale nella schermata "Raccolta Dati", associata alla Feature giusta per quel canale/strumento.

## Cosa NON è coperto da questa procedura

- Il comportamento con **più ricevitori U-WAVE-R contemporaneamente** sullo stesso PC (concettualmente supportato, non ancora testato dal vivo)
- Il collegamento diretto via cavo Digimatic **senza** U-Wave (altro convertitore, es. IT-016U USB-ITN) — vedi invece `sources/digimatic_usb_hid.py` e la sezione USB-ITN in `edge-agent/README.md`
- Il frame del comando di "ritiro" (vedi sopra)
