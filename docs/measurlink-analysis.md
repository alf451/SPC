# Analisi schema dati MeasurLink9 (SQL Server) — base per il redesign PostgreSQL

Fonte: database `MeasurLink9` (309 tabelle) e `MeasurLink9_GAGE` (310 tabelle, schema quasi identico, +1 tabella `DAQDataGatewaySource`), istanza SQL Express locale `.\SQLEXPRESS`. Schema estratto via `sqlcmd` su `sys.tables`/`sys.columns`/`sys.foreign_keys`. Nessuna FK di dominio a livello DB (le uniche 12 FK trovate riguardano le tabelle interne `QRTZ_*` di Quartz.NET scheduler) — l'integrità referenziale in MeasurLink è solo applicativa, va dedotta dal naming delle colonne (`XxxID` → tabella `Xxx`).

## 1. Entità core del dominio SPC

**Gerarchia organizzativa (folder + entità)**
- `PartFolder`(PartFolderID PK, FolderName, ParentID→self) — albero cartelle Parti
- `Part`(PartID PK, PartName, PartDesc, PartFolderID→PartFolder, PartPropID→PartProperties)
- `PartProperties`(PartID+PartPropID PK composita, PartPropName, SampleSize, DefaultControlChart, LimitCalcType, LowerControlLimit/CenterLine/UpperControlLimit, DecimalLength, Rounded) — proprietà **versionate** del Part
- `RoutineFolder`(RoutineFolderID PK, FolderName, ParentID)
- `Routine`(RoutineID PK, RoutineName, RoutineFolderID→RoutineFolder) — piano di collaudo, minimale (3 colonne dirette)
- `RoutineFeatures`(RoutineID+FeatureID PK, OrderNo, FeaturePropID, PartPropID) — ponte N:N Routine↔Feature con ordine e versione proprietà attiva

**Feature (caratteristica misurata)**
- `Feature`(FeatureID PK, FeatureType, FeatureName, PartID→Part, OrderNo, FeatureDesc, FeaturePropID, PartPropID)
- `FeatureProperties`(**FeatureID+FeaturePropID PK composita**, FeaturePropName, Target, LowerToleranceLimit, UpperToleranceLimit, SubgroupSize, LowerWarningLimit/UpperWarningLimit, Lower/Center/UpperControlLimitR, Lower/Center/UpperControlLimitX, LowerOutlierLimit/UpperOutlierLimit, LimitType, DefaultChart, DefaultControlChart, ControlMethod, SigmaEstimate, StandardDeviationUnit, MeasureUnit→Unit, DecimalLength, Rounded, DistributionType, DistributionEstimation, ToleranceStandard, ToleranceGrade, Uncertainty)
- `DerivedFeature`(FeatureID+TextSegmentNo PK, TextSegment nvarchar(2048)) — formula feature calcolata, spezzata su più righe (workaround SQL Server per testi lunghi)
- `FeatureAttachment`, `FeaturePropOptions`(PartFolderID+PartID+FeatureID+FeaturePropID PK, WarningPercentage, ControlLimitsBase, ControlLimitsBaseValue, OutlierPercentage)

**Pattern architetturale chiave — versionamento delle proprietà**: sia `FeatureProperties` che `PartProperties` hanno PK composita (EntitàID + PropID). Ogni modifica a nominale/tolleranze/limiti crea una **nuova versione** invece di un UPDATE in-place. Le tabelle di run/dati portano con sé il riferimento a QUALE versione era attiva quando il dato è stato raccolto, così modifiche future a tolleranze non alterano retroattivamente Cpk/grafici storici. **Replicato nel nuovo schema Postgres** con `feature_property_versions`/`part_property_versions` a `valid_from`/`valid_to`.

**Run (istanza di collaudo/lotto)**
- `Run`(RunID PK, RunName, RoutineID→Routine, StationID→Station, RunFolderID→RunFolder, RunStatus, BeginTimestamp, EndTimestamp)
- `FeatureRun`(RunID+FeatureID PK, OrderNo, DAQSourceID→DAQSource, FeaturePropID, PartPropID) — lega Feature al Run con sorgente DAQ e versione proprietà usate
- `ActiveRun`(RunID+FeatureID PK, PartID, RoutineID, StationID, nomi denormalizzati, Cp/Cpk/Pp/Ppk, timestamp) — cache "live" per dashboard real-time

**Station**
- `Station`(StationID PK, StationName, StationDesc, StationFolderID→StationFolder, ComputerName, StationStatus)
- `StationOptions`(StationID+OptionsKey+OptionsSegmentNo PK, OptionsSegment nvarchar(2048)) — config chiave/valore segmentata

**DAQ (acquisizione dati) — pattern "table per subtype"**
`DAQSource`(DAQSourceID PK, DAQSourceName, StationID→Station, SourceType, SourceStatus) tabella base; ogni sottotipo estende 1:1 sullo stesso DAQSourceID:
- `DAQPortSource`(DAQSourceID PK, Port es. "COM3", DeviceID→Device, Channel, GroupID) — **sorgente per calibri/micrometri Digimatic seriali**
- `DAQKeyboardSource`(InputType, Modal, UIAssembly, Class) — inserimento manuale/plugin UI
- `DAQDDESource`, `DAQImportSource`, `DAQMTConnectSource`, `DAQOPCUASource`, `DAQDataGatewaySource` (solo DB GAGE)
- `LinkedDAQSource`(DAQSourceID+StationID+LinkedDAQSourceID) — sorgente condivisa/mirrorata su più stazioni

**Protocollo seriale/dispositivo (rilevante per l'Edge Agent Digimatic)**
- `Device`(DeviceID PK, DeviceName, DeviceDesc, Type, MaxStringLength, Terminator, UsesGroupID, InitialChannelValue, InputValueHexed)
- `RS232DeviceParam`(DeviceID PK, NoOfChannels, BaudRate, DataBits, Parity, StopBits, DataFlow, BufferSize, DataFormatType, DeviceType)
- `RS232DeviceChannel`(DeviceID+ChannelNo PK, ChannelTag) — canali multiplexati (box multi-gage su una porta)
- `DeviceCommands`(DeviceID+ChannelID+CommandID PK, CommandName, Command nvarchar(8000), Sample, Type) — stringhe comando/protocollo
- `USBKeyboardParam`(DeviceID PK, Interval) — calibri USB-ITN che emulano tastiera
- `KeyboardConstant`(RunID+FeatureID+ObsID, Name, Offset)

Nota dalle note operative dell'utente (`MeasurLink.md`): `RS232DeviceChannel`, `RS232DeviceParam`, `DeviceCommands` **hanno dati reali** → in officina gli strumenti sono realmente collegati via RS232, non solo USB.

**Statistiche/controllo**
- `CapabilityIndices`(RoutineID+RunID+FeatureID+IndexID PK, IndexName, Dispersion, Factor, Target, Test)
- `CapabilityTestFail`(RunID, FeatureID, Name, CapabilityIndex, Value, UpdateTimestamp) — log, **2.802.955 righe** (tabella a volume più alto confermata)
- `AdvancedControlData`(RunID+FeatureID PK, Weight, Start, SigmaUnit, LastEwma, AggrEwma, AggrEwmaSqr, HValue, KValue, IsFirEnabled, UseStandardCusum, LowerStdDev, UpperStdDev) — parametri EWMA/CUSUM, 70.715 righe
- `AttRunStatistics`(RunID+PartID+FeatureID+StatisticsID PK, StatisticsType, StartSbgID/EndSbgID, SampleSize, SbgCount, ObsCount, AggrDefectives/Defects, AggrDefectiveRate/DefectRate, MaxDefectives/Defects/Rate)
- `LockControlLimitData`(RunID+FeatureID PK, Lower/Center/UpperLimitAverage, Lower/Center/UpperLimitRange, SubstituteTolerance) — limiti di controllo "congelati"

**Tracciabilità**
- `TraceabilityFolder`/`TraceabilityList`(TraceabilityListID PK, ListName, SpanType, TagType, ItemType, ListSize, Pattern varbinary)
- `TraceabilityItem`(TraceabilityListID+ItemNo, ItemName, Active)
- `DataTraceability`(RunID+PartID+FeatureID+TraceabilityListID+ItemOrderNo PK, ItemName, StartObsID, EndObsID) — traccia associata a un range di osservazioni
- `PartTraceability`, `RunTraceability`, `RunTraceabilityList`
- `SerialNumber`(RunID+FeatureID+ObsID PK, SerialNo)

**Gage/Calibrazione (DB gemello `_GAGE`)**
- `Gage`(GageID PK, GageName, GageFolderID, GageClassification, Model, ManufacturerID, GageType, UnitID→Unit) + `GageDetail`(1:1, SupplierCode, DistributorID, StorageLocationID, CustodianID, Cost, SerialNumber, DrawingNumber, StandardsTraceID)
- `GageModel`/`GageModelFolder` — catalogo modelli
- `GageActive`(StationID+GageID) — strumento fisico attivo su una stazione
- `GageTracking`(GageID, TrackingTimestamp, Activity, GMLocationID, GMUserID, GMContactID, Purpose, Cost, Labor) — log check-in/out, alto volume potenziale
- `Calibration`(CalibrationID PK, CalibrationName, GageID→Gage, CalibrationProcedureID→CalibrationProcedure, Status, StartTime, EndTime)
- `CalibrationData`(CalibrationID+CalibrationSegmentNo, CalibrationSegment nvarchar(2048)) — blob risultati segmentato
- `CalibrationProcedure`(CalibrationProcedureID PK, Classification, Name, FolderID, UpdateTimeStamp, UnitIDList) + `CalibrationExecProcedure(Def)`, `CalibrationGridSingleResults`, `CalibrationGridFoundAdjustedResults` (nominale/trovato/aggiustato per punto griglia), `Calibration{Standard,Var,Att}GageMeasurementSpec`, `CalibrationCertificate(Def/Folder)`, `CalibrationSignature`
- Template certificato di taratura già raccolto dall'utente: `OneDrive\Mopla\MeasurLInk\certificato_taratura.html`

**Sicurezza (RBAC granulare a matrice)**
- `SecurityEntities`(SecurityID PK, Type, Name) — polimorfica (utenti E gruppi)
- `SecurityUsers`(SecurityID PK/FK, Status, FirstName, LastName, IdleTimeout, Password, ForcePwdChange, MaxLoginAttempts, AccountLocked, PwdExpireDays)
- `SecurityProfileMembership`(ProfileID, SecurityID)
- `SecuritySettings`(SecurityID, ModuleID, FunctionID, LevelID, Setting) — permesso puntuale Modulo×Funzione×Livello
- `SecurityModules`/`SecurityFunctions`/`SecurityLevels` — tassonomia permessi

**Note/azioni correttive**
- `DataNote`(RunID+FeatureID+StartObsID+EndObsID+NoteSegmentNo PK, NoteSegment) — nota su range osservazioni, testo segmentato
- `DataCorrectiveAction`(RunID, PartID, FeatureID, StartObsID, EndObsID, AssignableCauseID, CorrectiveActionID)

**VariableGroup (grafici multi-caratteristica)**
- `VariableGroup`(GroupID PK, GroupName, GroupType, OwnerType, OwnerID, Status)
- `GroupFeatures`(GroupID, FeatureID, RunID, State)
- `GroupProperties`(GroupID PK, Ucl/Center/LclX, ...MR, ...R, ...S, ControlMethod, ControlChart)
- `GroupStatistics`, `GroupChartOptions`, `GroupTestData`, `GroupPositionalTolerance/Statistics`, `GroupTraceabilities`/`GroupTraceData`

## 2. Cuore del sistema: dove sta il valore della misura

**`FeatureRunData`** (dati variabili — quote dimensionali):

| Colonna | Tipo | Note |
|---|---|---|
| RunID | int, PK | FK→Run |
| FeatureID | int, PK | FK→Feature |
| ObsID | int, PK | numero osservazione |
| ObsNo | int | ordine sequenziale nel run |
| Value | float | valore numerico, nullable |
| ObsTimestamp | datetime | timestamp misura |
| ObsFlags | int | bitmask stato (fuori tolleranza, editato, ...) |
| MonitorTimestamp | datetime, nullable | timestamp elaborazione/streaming |

Nessuna colonna unità sulla riga: ereditata da `FeatureProperties.MeasureUnit` (per versione-proprietà, non per osservazione) — **nel redesign Postgres l'unità viene denormalizzata sulla riga misura** per robustezza storica.

Per dati attributivi (pass/fail): `AttFeatureRunData`(RunID, FeatureID, SubgroupID nullable, ObsID PK, ObsNo, DefectCount, ObsTimestamp, ObsFlags, MonitorTimestamp) e `AttSubgroupData`(RunID, PartID, PartPropID, SubgroupID PK, SubgroupSize, InspectedCount, DefectiveCount, Timestamp, State, MonitorTimestamp) — riga di riepilogo per sottogruppo p/np/c/u chart.

Non esiste una tabella "SubgroupData" pura per variabili: l'aggregazione per sottogruppo è **pre-calcolata** in `VarRunStatistics`(RunID, FeatureID, StatisticsID PK, StatisticsType, FeaturePropID, StartObsNo/EndObsNo, SubgroupSize, ObsCount, ObsSum, SumSqr, AggrMean, AggrRange, AggrMRange, AggrStandardDev, ObsMax/Min, Cp/Cpk/Pp/Ppk, HistogramMin/Max/BinCount), con istogramma in `VarRunHistogram`(RunID, FeatureID, StatisticsID, BinNo, BinValue).

## 3. Modello tolleranze/nominali

Su `FeatureProperties` (versionata): `Target` (nominale), `LowerToleranceLimit`/`UpperToleranceLimit`, `LowerWarningLimit`/`UpperWarningLimit`, limiti di controllo X e R separati (statistici, non di tolleranza), `MeasureUnit`→`Unit`(UnitID, UnitName, Symbol, UnitType, SIUnit, Factor, Offset — conversione lineare a SI), `DecimalLength`/`Rounded`. `ToleranceStandard`/`ToleranceGrade` puntano concettualmente a `StandardTolerances`(Specification, Grade, OverNominal, ToNominal, LowTol, UpTol) — lookup range nominale→tolleranza per standard/grado.

## 4. Osservazioni sul volume dati

Tabelle a scrittura intensiva (in ordine di volume atteso/confermato):
1. `FeatureRunData` / `AttFeatureRunData` — una riga per ogni singola misura, il vero collo di bottiglia
2. `CapabilityTestFail` (**2.8M righe confermate**)
3. `DataTestFailed`, `GroupTestData` — log violazioni regole SPC (Western Electric/Nelson)
4. `VarRunStatistics` / `AdvancedControlData` (**70.715 righe confermate**)
5. `GageTracking` — ledger movimenti/attività strumento
6. `SerialNumber`, `DataTraceability`, `RunTraceability`

**Nota**: esiste un intero set parallelo di tabelle `PA*` (`PARun`, `PAPart`, `PAFeatureRunData`, ...) che replica quasi 1:1 lo schema core, con colonne aggiuntive `SourceRunID`/`SourceFeatureID`/`SourceObsID`/`SourceType` — copia materializzata per analisi cross-run ("Process Analyzer"). Nel redesign Postgres è sostituibile con viste/query invece di tabelle duplicate fisiche → **omesso in v1**, riattivabile come vista se serve.

---
Fonti: export via `sqlcmd` di `sys.tables`/`sys.columns` (2226 righe per MeasurLink9, 2229 per MeasurLink9_GAGE) e `sys.foreign_keys` (12 righe, solo tabelle Quartz), più `OneDrive\Mopla\MeasurLInk\MeasurLink.md` (note preliminari dell'utente su tabelle popolate). Nessun nome di colonna è stato inventato.
