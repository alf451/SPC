# Import da MeasurLink

Porta la configurazione (Part/Routine/Quote/Stazioni/DAQ/Strumenti) e opzionalmente lo storico misure recente da un database SQL Server di MeasurLink 9 verso leank-spc. **Collaudato sul database reale del cliente pilota** durante lo sviluppo (303 Part, 351 Routine, 6394 Feature, 316 strumenti — vedi il riepilogo nel job di import).

Il modo più comodo per usarlo è la scheda **Import MeasurLink** del [pannello admin](../admin/index.html), che lo invoca in-process con un test-connessione e un monitor in tempo reale. Questo file documenta l'uso da riga di comando, per script/automazioni.

## Uso da riga di comando

```bash
cd import-measurlink
python -m venv .venv && .venv\Scripts\activate   # oppure source .venv/bin/activate su Linux
pip install -r requirements.txt
copy config.example.yaml config.yaml   # poi compilare con le credenziali reali
python -m import_measurlink --config config.yaml
```

Opzioni:
- `--since-months N` — sovrascrive `since_months` del config (default 3)
- `--only-config` — salta l'import dello storico misure (solo Part/Routine/Quote/Stazioni/DAQ/Strumenti)
- `--dry-run` — "prova": conta cosa verrebbe importato senza scrivere nulla nello storico (la configurazione viene comunque scritta, essendo poco rischiosa/idempotente)

Richiede il driver ODBC per SQL Server installato a livello di sistema (es. "ODBC Driver 17 for SQL Server" su Windows; su Linux, pacchetto `msodbcsql17` da Microsoft).

## Cosa importa

| MeasurLink | leank-spc | Note |
|---|---|---|
| PartFolder, Part, PartProperties | part_folders, parts, part_property_versions | tutte le versioni proprietà, ordinate per PropID |
| RoutineFolder, Routine, RoutineFeatures | routine_folders, routines, routine_features | |
| Feature, FeatureProperties | features, feature_property_versions | FeatureType 1→variabile, 2→attributiva |
| Station | sites (una sola, "Sede principale"), stations | MeasurLink non ha un concetto di "sito" separato |
| Device, RS232DeviceParam, DAQSource, DAQPortSource | daq_devices, daq_sources | **solo sorgenti RS232** per ora (quelle popolate nei DB visti finora) — DDE/Import/MTConnect/OPC-UA non ancora mappate |
| Gage, GageDetail, Calibration | gages, calibrations | dal database gemello `_GAGE`, opzionale |
| Run, FeatureRunData, AttFeatureRunData | runs, measurements, attribute_observations | solo se non `--only-config`, filtrate per data (`--since-months`), lette a batch |

**Non importato** (fuori ambito v1, vedi `docs/measurlink-analysis.md`): tabelle `PA*` (Process Analyzer), `AdvancedControlData` (EWMA/CUSUM), istogrammi precalcolati, tracciabilità per-range-osservazione, sorgenti DAQ non-RS232.

## Limite noto: versionamento tolleranze

MeasurLink non registra *quando* è cambiata una versione di `FeatureProperties`/`PartProperties` (nessuna colonna timestamp in quelle tabelle). Se una Feature ha più righe `FeaturePropID`, l'import le importa tutte ordinate per ID crescente (l'euristica migliore disponibile — gli ID sono assegnati in sequenza alla creazione), l'ultima diventa la versione "corrente" e le altre vengono marcate storiche con `valid_to = now()` (il momento dell'import, non il momento reale del cambiamento — che MeasurLink stesso non conosce).

## Idempotenza

Ogni riga importata viene registrata in una tabella `import_map` (creata automaticamente in leank-spc al primo utilizzo) che lega l'ID sorgente all'ID di destinazione. Rilanciare l'import — anche con parametri diversi, es. `--since-months` più ampio — aggiorna invece di duplicare.
