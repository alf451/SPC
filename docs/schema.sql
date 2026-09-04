-- leank-spc — schema PostgreSQL
-- Redesign di Mitutoyo MeasurLink 9 per applicazione web SPC / raccolta dati officina.
-- Vedi docs/measurlink-analysis.md per il confronto con lo schema originale.
--
-- Convenzioni:
--   * PK bigint identity ovunque tranne le join table (PK composita naturale)
--   * timestamptz sempre (mai timestamp naive)
--   * double precision per le misure (coerente con "Value float" dell'originale)
--   * jsonb per configurazioni/definizioni a struttura variabile
--   * pattern di versionamento (valid_from/valid_to) per le proprietà di Part/Feature,
--     equivalente al pattern PropID di MeasurLink, ma esplicito e query-friendly

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid(), se serve altrove
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- ricerca full-text approssimata su nomi Part/Routine/Feature

-- =========================================================================
-- Anagrafica / organizzazione
-- =========================================================================

CREATE TABLE sites (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            text NOT NULL UNIQUE,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE stations (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    site_id         bigint NOT NULL REFERENCES sites(id),
    name            text NOT NULL,
    description     text,
    computer_name   text,
    status          text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (site_id, name)
);

CREATE TABLE units (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol          text NOT NULL UNIQUE,
    name            text NOT NULL,
    si_factor       double precision NOT NULL DEFAULT 1,
    si_offset       double precision NOT NULL DEFAULT 0
);

CREATE TABLE users (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username            text NOT NULL UNIQUE,
    email               text UNIQUE,
    full_name           text,
    password_hash       text NOT NULL,
    status              text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
    force_password_change boolean NOT NULL DEFAULT false,
    failed_login_count  integer NOT NULL DEFAULT 0,
    locked_until        timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE roles (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            text NOT NULL UNIQUE,
    description     text
);

-- codici a stringa gerarchica (es. "spc.run.create", "gage.calibration.approve")
-- al posto della matrice Modulo x Funzione x Livello dell'originale
CREATE TABLE permissions (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code            text NOT NULL UNIQUE,
    description     text
);

CREATE TABLE role_permissions (
    role_id         bigint NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id   bigint NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE user_roles (
    user_id         bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id         bigint NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

-- =========================================================================
-- Gerarchia SPC: Part / Routine / Feature
-- =========================================================================

CREATE TABLE part_folders (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parent_id       bigint REFERENCES part_folders(id),
    name            text NOT NULL
);

CREATE TABLE parts (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    folder_id       bigint REFERENCES part_folders(id),
    name            text NOT NULL,
    description     text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_parts_folder ON parts(folder_id);
CREATE INDEX ix_parts_name ON parts USING gin (name gin_trgm_ops);

-- proprietà versionate del Part (equivalente PartProperties + pattern PropID)
CREATE TABLE part_property_versions (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    part_id                 bigint NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
    version_no              integer NOT NULL,
    sample_size             integer,
    default_control_chart   text,
    limit_calc_type         text,
    lower_control_limit     double precision,
    center_line             double precision,
    upper_control_limit     double precision,
    decimal_length           smallint,
    rounded                 boolean NOT NULL DEFAULT true,
    valid_from              timestamptz NOT NULL DEFAULT now(),
    valid_to                timestamptz,
    created_by              bigint REFERENCES users(id),
    UNIQUE (part_id, version_no)
);
-- una sola versione "corrente" (valid_to IS NULL) per part
CREATE UNIQUE INDEX ux_part_property_current ON part_property_versions(part_id) WHERE valid_to IS NULL;

CREATE TABLE routine_folders (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parent_id       bigint REFERENCES routine_folders(id),
    name            text NOT NULL
);

CREATE TABLE routines (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    folder_id       bigint REFERENCES routine_folders(id),
    name            text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_routines_folder ON routines(folder_id);

CREATE TABLE features (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    part_id         bigint NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
    feature_type    text NOT NULL CHECK (feature_type IN ('variable', 'attribute')),
    name            text NOT NULL,
    description     text,
    order_no        integer NOT NULL DEFAULT 0,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_features_part ON features(part_id);

-- proprietà versionate della Feature: nominale/tolleranze/limiti di controllo
-- (equivalente FeatureProperties + pattern PropID)
CREATE TABLE feature_property_versions (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    feature_id                  bigint NOT NULL REFERENCES features(id) ON DELETE CASCADE,
    version_no                  integer NOT NULL,
    target                      double precision,
    lower_tolerance_limit       double precision,
    upper_tolerance_limit       double precision,
    lower_warning_limit         double precision,
    upper_warning_limit         double precision,
    subgroup_size               integer NOT NULL DEFAULT 1,
    control_method              text,
    lower_control_limit_x       double precision,
    center_line_x               double precision,
    upper_control_limit_x       double precision,
    lower_control_limit_r       double precision,
    center_line_r               double precision,
    upper_control_limit_r       double precision,
    sigma_estimate              double precision,
    unit_id                     bigint REFERENCES units(id),
    decimal_length              smallint NOT NULL DEFAULT 3,
    rounded                     boolean NOT NULL DEFAULT true,
    tolerance_standard          text,
    tolerance_grade             text,
    valid_from                  timestamptz NOT NULL DEFAULT now(),
    valid_to                    timestamptz,
    created_by                  bigint REFERENCES users(id),
    UNIQUE (feature_id, version_no)
);
CREATE UNIQUE INDEX ux_feature_property_current ON feature_property_versions(feature_id) WHERE valid_to IS NULL;

CREATE TABLE routine_features (
    routine_id      bigint NOT NULL REFERENCES routines(id) ON DELETE CASCADE,
    feature_id      bigint NOT NULL REFERENCES features(id) ON DELETE CASCADE,
    order_no        integer NOT NULL DEFAULT 0,
    PRIMARY KEY (routine_id, feature_id)
);

-- =========================================================================
-- DAQ — dispositivi e sorgenti di acquisizione
-- =========================================================================

-- generalizza Device + RS232DeviceParam + USBKeyboardParam + DAQ*Source:
-- i parametri specifici per tipo (baud/parity/stopbits, poll interval, ...)
-- vivono in config jsonb invece di una tabella per sottotipo
CREATE TABLE daq_devices (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            text NOT NULL,
    description     text,
    connection_type text NOT NULL CHECK (connection_type IN ('rs232', 'usb_hid', 'manual', 'opcua', 'mtconnect')),
    terminator      text,
    max_string_length integer,
    config          jsonb NOT NULL DEFAULT '{}'::jsonb,
    -- rs232: {"baud_rate":9600,"data_bits":7,"parity":"E","stop_bits":1,"channels":[{"no":1,"tag":"CH1"}],"commands":[{"name":"request","value":"R"}]}
    -- usb_hid: {"poll_interval_ms":50,"vendor_id":"...", "product_id":"..."}
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- porta/canale fisico su una stazione (equivalente DAQPortSource + RS232DeviceChannel)
CREATE TABLE daq_sources (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    station_id      bigint NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    device_id       bigint NOT NULL REFERENCES daq_devices(id),
    name            text NOT NULL,
    port            text,           -- es. "COM3" o path HID
    channel_no      integer,        -- canale su box multiplexato, NULL se non applicabile
    status          text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    UNIQUE (station_id, port, channel_no)
);

-- quale sorgente alimenta quale Feature per una Routine
-- (equivalente FeatureRun.DAQSourceID, configurato a livello Routine)
CREATE TABLE feature_daq_bindings (
    routine_id      bigint NOT NULL REFERENCES routines(id) ON DELETE CASCADE,
    feature_id      bigint NOT NULL REFERENCES features(id) ON DELETE CASCADE,
    daq_source_id   bigint NOT NULL REFERENCES daq_sources(id) ON DELETE CASCADE,
    PRIMARY KEY (routine_id, feature_id)
);

-- =========================================================================
-- Run e misure — cuore del sistema, tabelle partizionate per volume
-- =========================================================================

CREATE TABLE runs (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    routine_id      bigint NOT NULL REFERENCES routines(id),
    station_id      bigint NOT NULL REFERENCES stations(id),
    name            text NOT NULL,
    status          text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'aborted')),
    started_at      timestamptz NOT NULL DEFAULT now(),
    ended_at        timestamptz,
    started_by      bigint REFERENCES users(id)
);
CREATE INDEX ix_runs_routine ON runs(routine_id);
CREATE INDEX ix_runs_station_status ON runs(station_id, status);

-- misure variabili (quote dimensionali) — equivalente FeatureRunData
-- partizionata by RANGE (captured_at): una partizione mensile, creata in anticipo
-- dalla migration iniziale + da un job schedulato che ne crea di nuove
CREATE TABLE measurements (
    id              bigint GENERATED ALWAYS AS IDENTITY,
    run_id          bigint NOT NULL REFERENCES runs(id),
    feature_id      bigint NOT NULL REFERENCES features(id),
    obs_no          integer NOT NULL,
    value           double precision,
    unit_id         bigint REFERENCES units(id),
    flags           integer NOT NULL DEFAULT 0,  -- bitmask: fuori tolleranza, editato manualmente, ...
    captured_at     timestamptz NOT NULL,
    received_at     timestamptz NOT NULL DEFAULT now(),
    source          text NOT NULL DEFAULT 'daq' CHECK (source IN ('daq', 'manual', 'import')),
    PRIMARY KEY (id, captured_at)
) PARTITION BY RANGE (captured_at);

CREATE INDEX ix_measurements_run_feature ON measurements(run_id, feature_id, obs_no);

-- osservazioni attributive (pass/fail) — equivalente AttFeatureRunData
CREATE TABLE attribute_observations (
    id              bigint GENERATED ALWAYS AS IDENTITY,
    run_id          bigint NOT NULL REFERENCES runs(id),
    feature_id      bigint NOT NULL REFERENCES features(id),
    obs_no          integer NOT NULL,
    defect_count    integer NOT NULL DEFAULT 0,
    captured_at     timestamptz NOT NULL,
    received_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (id, captured_at)
) PARTITION BY RANGE (captured_at);

CREATE INDEX ix_attribute_observations_run_feature ON attribute_observations(run_id, feature_id, obs_no);

-- riepilogo per sottogruppo (p/np/c/u chart) — equivalente AttSubgroupData
CREATE TABLE attribute_subgroups (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id              bigint NOT NULL REFERENCES runs(id),
    part_id             bigint NOT NULL REFERENCES parts(id),
    subgroup_no         integer NOT NULL,
    sample_size         integer NOT NULL,
    inspected_count     integer NOT NULL,
    defective_count     integer NOT NULL,
    captured_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, subgroup_no)
);

-- snapshot dei limiti di controllo calcolati/bloccati — equivalente LockControlLimitData
CREATE TABLE control_limits (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id          bigint NOT NULL REFERENCES runs(id),
    feature_id      bigint NOT NULL REFERENCES features(id),
    computed_at     timestamptz NOT NULL DEFAULT now(),
    lcl_x           double precision,
    cl_x            double precision,
    ucl_x           double precision,
    lcl_r           double precision,
    cl_r            double precision,
    ucl_r           double precision,
    locked          boolean NOT NULL DEFAULT false
);
CREATE INDEX ix_control_limits_run_feature ON control_limits(run_id, feature_id);

-- risultati capability calcolati — equivalente parte di VarRunStatistics
CREATE TABLE capability_results (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id          bigint NOT NULL REFERENCES runs(id),
    feature_id      bigint NOT NULL REFERENCES features(id),
    computed_at     timestamptz NOT NULL DEFAULT now(),
    sample_size     integer,
    cp              double precision,
    cpk             double precision,
    pp              double precision,
    ppk             double precision
);
CREATE INDEX ix_capability_results_run_feature ON capability_results(run_id, feature_id);

-- log violazioni soglie capability — equivalente CapabilityTestFail (2.8M righe nell'originale)
CREATE TABLE capability_test_failures (
    id              bigint GENERATED ALWAYS AS IDENTITY,
    run_id          bigint NOT NULL REFERENCES runs(id),
    feature_id      bigint NOT NULL REFERENCES features(id),
    index_name      text NOT NULL,
    value           double precision,
    threshold       double precision,
    occurred_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);

CREATE INDEX ix_capability_test_failures_run_feature ON capability_test_failures(run_id, feature_id);

CREATE TABLE notes (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id          bigint NOT NULL REFERENCES runs(id),
    feature_id      bigint REFERENCES features(id),
    obs_id          bigint,
    author_id       bigint REFERENCES users(id),
    body            text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE corrective_actions (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id              bigint NOT NULL REFERENCES runs(id),
    feature_id          bigint REFERENCES features(id),
    assignable_cause    text,
    description         text NOT NULL,
    status              text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- =========================================================================
-- Tracciabilità (semplificata: per Run, non per range di osservazioni)
-- =========================================================================

CREATE TABLE traceability_fields (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            text NOT NULL UNIQUE,
    field_type      text NOT NULL DEFAULT 'text',
    pick_list       jsonb
);

CREATE TABLE run_traceability_values (
    run_id          bigint NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    field_id        bigint NOT NULL REFERENCES traceability_fields(id),
    value           text,
    PRIMARY KEY (run_id, field_id)
);

-- =========================================================================
-- Gage / Calibrazione
-- =========================================================================

CREATE TABLE gage_folders (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parent_id       bigint REFERENCES gage_folders(id),
    name            text NOT NULL
);

CREATE TABLE gages (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    folder_id       bigint REFERENCES gage_folders(id),
    name            text NOT NULL,
    classification  text,
    model           text,
    serial_number   text,
    unit_id         bigint REFERENCES units(id),
    custodian_id    bigint REFERENCES users(id),
    status          text NOT NULL DEFAULT 'in_service' CHECK (status IN ('in_service', 'out_of_service', 'retired')),
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_gages_folder ON gages(folder_id);

CREATE TABLE gage_station_active (
    station_id      bigint NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    gage_id         bigint NOT NULL REFERENCES gages(id) ON DELETE CASCADE,
    activated_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (station_id, gage_id)
);

-- ledger movimenti/attività strumento — partizionata per tempo
CREATE TABLE gage_tracking_log (
    id              bigint GENERATED ALWAYS AS IDENTITY,
    gage_id         bigint NOT NULL REFERENCES gages(id),
    activity        text NOT NULL,
    location_id     bigint,
    user_id         bigint REFERENCES users(id),
    occurred_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);

CREATE TABLE calibration_procedures (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            text NOT NULL,
    classification  text,
    definition      jsonb NOT NULL DEFAULT '{}'::jsonb, -- struttura punti griglia/step, sostituisce blob XML segmentato
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE calibrations (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    gage_id         bigint NOT NULL REFERENCES gages(id),
    procedure_id    bigint REFERENCES calibration_procedures(id),
    status          text NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'passed', 'failed')),
    started_at      timestamptz NOT NULL DEFAULT now(),
    completed_at    timestamptz,
    performed_by    bigint REFERENCES users(id)
);
CREATE INDEX ix_calibrations_gage ON calibrations(gage_id);

CREATE TABLE calibration_results (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    calibration_id  bigint NOT NULL REFERENCES calibrations(id) ON DELETE CASCADE,
    point_no        integer NOT NULL,
    nominal         double precision,
    found           double precision,
    adjusted        double precision,
    UNIQUE (calibration_id, point_no)
);

CREATE TABLE calibration_certificates (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    calibration_id  bigint NOT NULL REFERENCES calibrations(id) ON DELETE CASCADE,
    certificate_no  text NOT NULL UNIQUE,
    issued_at       timestamptz NOT NULL DEFAULT now(),
    html_body       text  -- generato a partire dal template certificato_taratura.html
);

-- =========================================================================
-- Audit trasversale — una sola tabella generica al posto delle ~50 Audit_* originali
-- =========================================================================

CREATE TABLE audit_log (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_name      text NOT NULL,
    row_pk          text NOT NULL,
    action          text NOT NULL CHECK (action IN ('insert', 'update', 'delete')),
    changed_by      bigint REFERENCES users(id),
    changed_at      timestamptz NOT NULL DEFAULT now(),
    diff            jsonb
);
CREATE INDEX ix_audit_log_table_row ON audit_log(table_name, row_pk);
CREATE INDEX ix_audit_log_changed_at ON audit_log(changed_at);

-- =========================================================================
-- Partizioni iniziali (esempio: mese corrente + prossimo).
-- In produzione: job schedulato (pg_cron o task Alembic) che crea la
-- partizione del mese successivo in anticipo.
-- =========================================================================

CREATE TABLE measurements_default PARTITION OF measurements DEFAULT;
CREATE TABLE attribute_observations_default PARTITION OF attribute_observations DEFAULT;
CREATE TABLE capability_test_failures_default PARTITION OF capability_test_failures DEFAULT;
CREATE TABLE gage_tracking_log_default PARTITION OF gage_tracking_log DEFAULT;

COMMIT;

-- =========================================================================
-- v0.2 — Integrazione ERP: commesse, attrezzature (stampi/fustelle), posizioni
-- Applicata da backend/migrations/versions/0002_work_orders_tools.py
-- (migration separata, non rieseguita da 0001 — questa sezione è solo il
-- riferimento leggibile dello stato finale dello schema).
-- =========================================================================

BEGIN;

-- "Tool" generalizza qualunque cosa produca pezzi in un evento produttivo
-- (stampo a iniezione, fustella, stampo di pressofusione, ...).
CREATE TABLE tools (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            text NOT NULL,
    tool_type       text NOT NULL DEFAULT 'other' CHECK (tool_type IN ('mold', 'die', 'other')),
    position_count  integer NOT NULL DEFAULT 1,
    description     text,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- una posizione/cavità di un Tool (es. "Cavità 3" di uno stampo a 4 impronte)
CREATE TABLE tool_positions (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tool_id         bigint NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    position_no     integer NOT NULL,
    label           text,
    notes           text,
    UNIQUE (tool_id, position_no)
);

-- commessa — creata di norma da un ERP esterno via POST /api/work-orders
CREATE TABLE work_orders (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_number        text NOT NULL UNIQUE,
    part_id             bigint REFERENCES parts(id),
    customer            text,
    quantity_ordered    integer,
    status              text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'closed')),
    external_system     text,  -- nome dell'ERP di origine, qualunque esso sia
    external_id         text,  -- id nell'anagrafica dell'ERP, per idempotenza sull'import
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (external_system, external_id)
);

-- collegamenti opzionali (nullable, nessuna rottura di compatibilità) verso lo schema v1
ALTER TABLE runs ADD COLUMN work_order_id bigint REFERENCES work_orders(id);
ALTER TABLE runs ADD COLUMN tool_id bigint REFERENCES tools(id);
ALTER TABLE measurements ADD COLUMN tool_position_id bigint REFERENCES tool_positions(id);
ALTER TABLE attribute_observations ADD COLUMN tool_position_id bigint REFERENCES tool_positions(id);

CREATE INDEX ix_runs_work_order ON runs(work_order_id);
CREATE INDEX ix_runs_tool ON runs(tool_id);
CREATE INDEX ix_tool_positions_tool ON tool_positions(tool_id);

-- notifiche email (migration 0003) — riga singola (id sempre 1), gestita da
-- app/notifications/mailer.py; smtp_password mai restituito dall'API, solo
-- se e' impostato o meno (smtp_password_set)
CREATE TABLE notification_settings (
    id                              smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    smtp_host                       text,
    smtp_port                       integer NOT NULL DEFAULT 587,
    smtp_username                   text,
    smtp_password                   text,
    smtp_use_tls                    boolean NOT NULL DEFAULT true,
    from_email                      text,
    to_email                        text NOT NULL DEFAULT 'mcdataviewerinfo@gmail.com',
    notify_on_agent_disconnected    boolean NOT NULL DEFAULT true,
    notify_on_system_error          boolean NOT NULL DEFAULT true,
    updated_at                      timestamptz NOT NULL DEFAULT now()
);

COMMIT;
