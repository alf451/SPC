# Guida d'uso — collaudo per commessa/articolo/lotto

Guida operativa per chi usa leank-spc tutti i giorni in reparto (non per chi lo installa — per quello vedi [`guida-installazione-e-test.md`](guida-installazione-e-test.md)). Copre: configurazione, ciclo di acquisizione, cosa fare dei dati raccolti, e i diversi modi in cui puoi collegare gli strumenti a seconda di quanti ne hai e come li usi.

---

## 1. Concetti e corrispondenze

| Nel gergo di reparto | Nell'app si chiama | Cos'è |
|---|---|---|
| Articolo | **Part** | Il pezzo che produci/collaudi |
| Quota/caratteristica da misurare | **Feature** | Una singola misura da prendere su un Articolo (con tolleranze, nr. di misure richieste) |
| Programma/tipo di misurazione | **Routine** | L'elenco ordinato di Feature da collaudare in una sessione |
| Sessione di collaudo | **Run** | Un'esecuzione concreta di una Routine, con le misure vere raccolte |
| Commessa | **Work Order** | Cliente, quantità, articolo — di solito arriva da un ERP, ma si può creare anche a mano |
| Lotto | Campo di tracciabilità sulla Run | Testo libero collegato alla Run (es. "L2026-0912") |
| Stampo/fustella/attrezzatura | **Tool** | Se ha più cavità, ogni cavità è una **posizione** |
| Profilo di uno strumento | **Dispositivo DAQ** | Come parla un tipo di strumento (protocollo, parametri) |
| Lo strumento fisico collegato | **Sorgente DAQ** | Una porta/canale specifico su una stazione, con un profilo dispositivo |

Gerarchia: un **Part** ha molte **Feature**. Una **Routine** raggruppa Feature (anche di Part diversi, se serve) in un ordine di collaudo. Una **Run** esegue una Routine su una Stazione, in un certo momento, opzionalmente per una Commessa/Lotto/Attrezzatura specifici.

---

## 2. Configurazione preliminare (una tantum per ogni nuovo articolo/programma)

Tutta in **Routine & Quote** e **Amministrazione**.

### 2.1 Articolo e caratteristiche (Routine & Quote)

1. Crea il **Part** (l'articolo)
2. Per ogni quota da controllare, crea una **Feature**:
   - Tipo: `variable` (una misura numerica) o `attribute` (conforme/difettoso)
   - Target, limite inferiore/superiore
   - **Nr. misure richieste** (subgroup_size) — quante misure servono per quella caratteristica prima di considerarla "completa" per un dato pezzo/posizione (default 1)

### 2.2 Routine (il programma di misura)

1. Crea la **Routine** (es. "Collaudo dimensionale mensile")
2. "Aggiungi Feature alla Routine" per ciascuna Feature da includere, con l'ordine di collaudo desiderato — **questo definisce solo la sequenza**, non collega ancora nessuno strumento

### 2.3 Strumenti — profilo e sorgente (Amministrazione → Dispositivi)

1. **Nuovo profilo dispositivo**: che tipo di strumento è (`rs232`, `usb_hid`, `manuale`, ...) e i suoi parametri di comunicazione (es. per RS232: baud rate, parità, bit di stop)
2. **Nuova sorgente DAQ**: lo strumento fisico vero e proprio — su quale stazione, quale porta/canale, con quale profilo. Usa "Rileva porte disponibili sulla stazione" invece di indovinare la porta, se l'Edge Agent è già attivo lì

### 2.4 Collegare Feature → Sorgente DAQ (Routine & Quote) — **il passo più facile da dimenticare**

Sezione **"Collega Feature → Sorgente DAQ"**: scegli Routine, Feature, Sorgente DAQ. Senza questo passaggio **le letture arrivano dallo strumento ma il backend non sa a quale Feature assegnarle** — è la causa più comune di "l'Edge Agent è connesso, il test funziona, ma non vedo misure in Raccolta Dati". Non confonderlo con "Aggiungi Feature alla Routine" (punto 2.2): sono due collegamenti diversi con nomi simili.

### 2.5 Commessa (opzionale — Amministrazione → Produzione)

Crea la **Commessa** (numero, cliente, quantità, articolo collegato) se vuoi tracciare per quale ordine cliente stai collaudando. Se hai un ERP, può crearle lui stesso via `POST /api/work-orders` (vedi [`integrazione-erp.md`](integrazione-erp.md)) — in quel caso non serve farlo a mano qui.

### 2.6 Attrezzatura/stampo multi-cavità (opzionale — Amministrazione → Produzione)

Solo se produci/colludi pezzi da uno stampo con più cavità e vuoi sapere da quale cavità viene ogni misura. Crea l'**Attrezzatura**, indica il numero di cavità: le posizioni (1..N) si creano da sole, numerate.

---

## 3. Ciclo di acquisizione (Raccolta Dati)

### 3.1 Avviare una Run

In **Raccolta Dati → Avvia un nuovo Run**:

- **Routine** e **Stazione**: obbligatori
- **Commessa**: opzionale, se vuoi tracciare per quale ordine stai collaudando (mostra anche l'articolo collegato)
- **Attrezzatura/stampo**: opzionale, solo se vuoi il tracciamento per cavità (vedi 3.2)
- **Lotto**: opzionale, testo libero

### 3.2 Se l'attrezzatura ha più cavità

Compare un pannello **"Posizione / cavità"** con:
- La cavità attualmente attiva, e per ciascuna Feature quante misure sono già state registrate rispetto al numero richiesto
- **"Salta questa posizione"**: se una cavità è chiusa/inutilizzata per motivi tecnici — resta registrato che è stata saltata (annullabile), non sparisce silenziosamente
- **"Prossima posizione"**: avanza alla cavità successiva non ancora completa

Ogni misura (da strumento o manuale) viene marcata automaticamente con la cavità attiva in quel momento — non devi indicarla ad ogni singola misura, solo quando cambi cavità.

### 3.3 Acquisire le misure

- **Da strumento**: con l'Edge Agent collegato e il binding Feature→Sorgente DAQ fatto (punto 2.4), premi il tasto dati sullo strumento — la misura compare in tempo reale in "Osservazioni recenti"
- **A mano**: usa "Inserimento manuale" nello stesso pannello — stesso risultato, stessa comparsa in tempo reale, utile come ripiego se lo strumento non è (ancora) collegato

Un valore fuori tolleranza compare evidenziato in rosso.

### 3.4 Completare la Run

Pulsante **"Completa Run"**. Se la Run aveva strumenti assegnati (vedi scenario 5.5 sotto), vengono liberati automaticamente per essere riusati da una Run successiva.

---

## 4. Analisi dei dati raccolti

**Cosa c'è oggi:**
- **Osservazioni recenti** (Raccolta Dati): le misure della Run corrente in tempo reale, con evidenza visiva fuori tolleranza
- **Database** (Amministrazione, sola lettura): puoi sfogliare direttamente le tabelle `measurements`/`attribute_observations` per una Run, filtrando/leggendo i dati grezzi senza bisogno di accesso diretto al database
- Le API REST (`GET /api/runs/{id}/measurements`, vedi [`api.md`](api.md)) restituiscono le misure in JSON — utile per esportarle o collegare uno strumento di analisi esterno (Excel via Power Query, uno script, ecc.)

**Cosa NON c'è ancora (fuori ambito v1, vedi TODO nel codice):**
- Calcolo automatico di Cp/Cpk e carte di controllo (X-bar/R, regole Western Electric)
- Report/certificati generati automaticamente
- Grafici storici multi-Run

Se ti serve analisi statistica **oggi**, la via più pratica è esportare le misure via API (o direttamente dalla tabella nel Database di Amministrazione) e lavorarci in uno strumento esterno, nell'attesa che il calcolo statistico venga implementato lato applicativo.

---

## 5. Scenari di configurazione degli strumenti

### 5.1 Un solo strumento, una sola stazione (caso base)

Un profilo dispositivo, una sorgente DAQ, un binding Feature→Sorgente. Una Run alla volta su quella stazione. Nessuna configurazione aggiuntiva.

### 5.2 Più strumenti sulla stessa stazione, stessa Run

Es. un calibro per una quota e un micrometro per un'altra, nella stessa sessione di collaudo. Crea una sorgente DAQ per ciascuno strumento (porte diverse), e collega ciascuna alla Feature giusta (punto 2.4) **nella stessa Routine**. Le letture di entrambi arrivano correttamente alla Run in corso, ciascuna alla propria Feature.

### 5.3 Ricevitore multi-canale (es. Mitutoyo U-Wave-R)

Un solo ricevitore/porta COM virtuale, più trasmettitori (uno per strumento), ciascuno assegnato a un canale diverso via U-WAVEPAK. Crea **una sorgente DAQ per canale**, stessa porta, `channel_no` diverso per ciascuna. Vedi [`test-mitutoyo-uwave.md`](test-mitutoyo-uwave.md) per i dettagli specifici di questo dispositivo.

### 5.4 Più stazioni indipendenti

Ogni stazione ha il proprio Edge Agent e i propri strumenti — completamente indipendenti tra loro. Puoi avere una Run attiva per stazione contemporaneamente senza nessuna configurazione speciale: è il comportamento di base.

### 5.5 Due Run in parallelo sulla stessa stazione (es. due commesse contemporanee)

Supportato dalla v0.7: se hai due strumenti sulla stessa stazione, ciascuno legato a una Routine diversa (anche se le due Routine misurano concettualmente "la stessa cosa"), puoi avviare due Run in parallelo su quella stazione — ciascuna riceve correttamente solo le letture del proprio strumento. Non serve nessuna azione manuale: l'assegnazione strumento→Run avviene da sola all'avvio di ciascuna Run.

Puoi vedere in ogni momento quale strumento è assegnato a quale Run in **Amministrazione → Dispositivi → Sorgenti DAQ**, colonna "Stato" ("libera" oppure "Run #N"). Se uno strumento risulta ancora assegnato a una Run già conclusa per errore (raro), puoi liberarlo manualmente (vedi `DELETE /api/runs/{id}/daq-claims/{daq_source_id}` in [`api.md`](api.md)).

**Limite noto**: se le **due Run condividono la stessa identica Routine** e vuoi che **due strumenti diversi alimentino la stessa Feature** in parallelo (non due Feature diverse), questo non è supportato — il collegamento Feature→Sorgente DAQ è unico per (Routine, Feature). Soluzione pratica: usa due Routine distinte (anche se identiche nel contenuto) per i due collaudi paralleli, oppure segnalalo per un'estensione dedicata se questo caso ti serve davvero spesso.

### 5.6 Nessuno strumento collegato

Va bene lo stesso: usa "Inserimento manuale" in Raccolta Dati. Non serve nessun profilo/sorgente DAQ né nessun Edge Agent per quella stazione.

---

## 6. Se qualcosa non funziona

Vedi [`problemi-riscontrati.md`](problemi-riscontrati.md) per i problemi reali già incontrati e le relative soluzioni (binding dimenticato, Edge Agent su PC sbagliato, sessione scaduta, ecc.).
