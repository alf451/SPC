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

Confermati dal manuale Mitutoyo (dichiarati per l'uso con Hyper Terminal / come preset in MeasurLink):

```
Baud rate:   57600
Parità:      nessuna
Bit dati:    8
Bit di stop: 1
```

Il **formato esatto dei byte** che arrivano sulla porta COM virtuale (dove inizia il numero, come è terminata la riga, cosa succede quando si tiene premuto il tasto "dati" 5 secondi per il "ritiro" di una misura) **non è documentato** nel manuale utente Mitutoyo — va verificato collegando l'hardware reale. È lo scopo di questa procedura.

## Procedura di test

### 1. Prerequisiti sul PC di stazione

- U-WAVEPAK installato e configurato (il ricevitore USB collegato, almeno un trasmettitore abbinato/registrato — verificabile nell'interfaccia di U-WAVEPAK, colonna "S": `r` = registrato non connesso, `c` = connesso)
- Annotare il **numero di porta COM virtuale** assegnato (visibile in U-WAVEPAK o in Gestione dispositivi di Windows)

### 2. Guardare i byte grezzi (prima di configurare qualunque cosa in leank-spc)

Usa lo strumento diagnostico incluso nel progetto: [`edge-agent/tools/serial-monitor.html`](../edge-agent/tools/serial-monitor.html) — pagina standalone, apribile con doppio click in **Chrome o Edge** (richiede la Web Serial API, non supportata da Firefox/Safari).

1. Apri la pagina, click **"Connetti..."**
2. Scegli la porta COM virtuale di U-WAVEPAK dal selettore
3. I parametri sono già preimpostati (57600-N-8-1) — lascia com'è
4. **Premi il tasto dati sullo strumento collegato** (pressione breve = invia la misura corrente)
5. Osserva cosa compare nel log:
   - **Hex e ASCII** di ogni byte ricevuto
   - Se una riga viene **riconosciuta come numero** dalla stessa regex del parser reale (evidenziata in verde)
6. Prova anche il **"ritiro"** (tasto dati tenuto premuto 5 secondi) — annota se genera un frame diverso/riconoscibile sulla porta o se non produce nessun output visibile
7. Click **"Scarica log"** — salva tutto in un `.txt`

Cosa cercare nel log:
- Il valore ha uno **zero iniziale** quando è sotto 1 (es. `0.1455`) o **no** (es. `.1455`)? Il parser attuale gestisce entrambi i casi, ma è utile saperlo
- Che carattere termina ogni misura — `\r`, `\n`, `\r\n`, o altro?
- Ci sono caratteri extra prima/dopo il numero (spazi, prefissi, codici di stato)?
- Il "ritiro" a 5 secondi produce un frame sulla porta COM, o è un effetto solo lato software (nessun byte in più)?

### 3. Se il parser va adattato

Il parsing vive in [`edge-agent/edge_agent/sources/digimatic_rs232.py`](../edge-agent/edge_agent/sources/digimatic_rs232.py), funzione `parse_digimatic_frame()`. Se il log mostra un formato diverso da quanto quella funzione già gestisce (numero decimale con segno opzionale, terminato da CR/LF), segnala il log scaricato — è la base per adattarla al formato reale osservato, invece di continuare a lavorare per ipotesi.

### 4. Configurare U-Wave in leank-spc

Una volta chiaro il comportamento reale, segui la Parte 3 di [`guida-installazione-e-test.md`](guida-installazione-e-test.md#parte-3--configurare-gli-strumenti-di-misura-daq):

1. **Amministrazione → Dispositivi → Nuovo profilo dispositivo**: nome `U-Wave`, tipo `rs232`, parametri 57600-N-8-1
2. **Nuova sorgente DAQ** per ogni canale/trasmettitore in uso, tutte sulla stessa porta COM virtuale, ciascuna con il proprio `channel_no`
3. Configura l'Edge Agent sulla stazione (`edge-agent/config.yaml`) con quella porta — vedi [`edge-agent/README.md`](../edge-agent/README.md)

### 5. Test end-to-end

Segui la Parte 4 di `guida-installazione-e-test.md`: avvia un Run, premi il tasto dati sullo strumento, verifica che la misura compaia in tempo reale nella schermata "Raccolta Dati".

## Cosa NON è coperto da questa procedura

- Il comportamento con **più ricevitori U-WAVE-R contemporaneamente** sullo stesso PC (concettualmente supportato, non ancora testato dal vivo)
- Il collegamento diretto via cavo Digimatic **senza** U-Wave (altro convertitore, es. IT-016U USB-ITN) — vedi invece `sources/digimatic_usb_hid.py` e la sezione USB-ITN in `edge-agent/README.md`
- Calibrazione fine del parser su varianti di formato non ancora osservate (es. valori BCD grezzi invece di ASCII già formattato) — da affrontare solo se il test al punto 2 rivela che il formato reale è diverso da quanto già gestito
