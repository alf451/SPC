"""Connessione e query verso il database SQL Server di MeasurLink.

Nomi di colonna e mapping dei valori enum verificati sul DB reale del cliente
pilota (istanza .\\SQLEXPRESS, database MeasurLink9/MeasurLink9_GAGE) — non
dedotti dalla sola documentazione. In particolare:
  - Feature.FeatureType: 1 = variabile, 2 = attributiva (confermato per conteggio righe)
  - DAQSource.SourceType: 1 = porta (ha riga in DAQPortSource), 3 = tastiera/manuale
    (ha riga in DAQKeyboardSource); altri valori mappati a "manual" per default
  - RS232DeviceParam.Parity: 0 = None, 2 = Even (coerente con System.IO.Ports.Parity)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pyodbc

FEATURE_TYPE_MAP = {1: "variable", 2: "attribute"}
PARITY_MAP = {0: "N", 1: "O", 2: "E", 3: "M", 4: "S"}
SOURCE_TYPE_PORT = 1
SOURCE_TYPE_KEYBOARD = 3


@dataclass
class SourceConnectionConfig:
    driver: str
    server: str
    database: str
    username: str
    password: str


def connect(cfg: SourceConnectionConfig) -> pyodbc.Connection:
    conn_str = (
        f"DRIVER={cfg.driver};SERVER={cfg.server};DATABASE={cfg.database};"
        f"UID={cfg.username};PWD={cfg.password};TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str, timeout=10)


def _rows_as_dicts(cursor: pyodbc.Cursor) -> list[dict]:
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def test_connection(cfg: SourceConnectionConfig) -> dict:
    """Usato dal pannello admin (POST /api/admin/measurlink-import/test-connection)
    per verificare la connessione senza importare nulla — ritorna conteggi rapidi
    così l'utente vede subito se sta puntando al database giusto."""
    conn = connect(cfg)
    try:
        cur = conn.cursor()
        counts = {}
        for table in ("Part", "Routine", "Feature", "Station", "Run"):
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cur.fetchone()[0]
        return {"ok": True, "counts": counts}
    finally:
        conn.close()


# --------------------------------------------------------------------------- config
def fetch_part_folders(conn: pyodbc.Connection) -> list[dict]:
    cur = conn.cursor()
    cur.execute("SELECT PartFolderID, FolderName, ParentID FROM PartFolder")
    return _rows_as_dicts(cur)


def fetch_parts(conn: pyodbc.Connection) -> list[dict]:
    cur = conn.cursor()
    cur.execute("SELECT PartID, PartName, PartDesc, PartFolderID, PartPropID FROM Part")
    return _rows_as_dicts(cur)


def fetch_part_properties(conn: pyodbc.Connection) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        "SELECT PartID, PartPropID, SampleSize, DefaultControlChart, LimitCalcType, "
        "LowerControlLimit, CenterLine, UpperControlLimit, DecimalLength, Rounded FROM PartProperties"
    )
    return _rows_as_dicts(cur)


def fetch_routine_folders(conn: pyodbc.Connection) -> list[dict]:
    cur = conn.cursor()
    cur.execute("SELECT RoutineFolderID, FolderName, ParentID FROM RoutineFolder")
    return _rows_as_dicts(cur)


def fetch_routines(conn: pyodbc.Connection) -> list[dict]:
    cur = conn.cursor()
    cur.execute("SELECT RoutineID, RoutineName, RoutineFolderID FROM Routine")
    return _rows_as_dicts(cur)


def fetch_routine_features(conn: pyodbc.Connection) -> list[dict]:
    cur = conn.cursor()
    cur.execute("SELECT RoutineID, FeatureID, OrderNo FROM RoutineFeatures")
    return _rows_as_dicts(cur)


def fetch_features(conn: pyodbc.Connection) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        "SELECT FeatureID, FeatureType, FeatureName, PartID, OrderNo, FeatureDesc, FeaturePropID FROM Feature"
    )
    rows = _rows_as_dicts(cur)
    for row in rows:
        row["feature_type_mapped"] = FEATURE_TYPE_MAP.get(row["FeatureType"], "variable")
    return rows


def fetch_feature_properties(conn: pyodbc.Connection) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        "SELECT FeatureID, FeaturePropID, Target, LowerToleranceLimit, UpperToleranceLimit, "
        "SubgroupSize, LowerWarningLimit, UpperWarningLimit, "
        "LowerControlLimitR, CenterControlLimitR, UpperControlLimitR, "
        "LowerControlLimitX, CenterControlLimitX, UpperControlLimitX, "
        "SigmaEstimate, MeasureUnit, DecimalLength, Rounded, ToleranceStandard, ToleranceGrade "
        "FROM FeatureProperties"
    )
    return _rows_as_dicts(cur)


def fetch_units(conn: pyodbc.Connection) -> list[dict]:
    cur = conn.cursor()
    cur.execute("SELECT UnitID, UnitName, Symbol, Factor, Offset FROM Unit")
    return _rows_as_dicts(cur)


def fetch_stations(conn: pyodbc.Connection) -> list[dict]:
    cur = conn.cursor()
    cur.execute("SELECT StationID, StationName, StationDesc, ComputerName, StationStatus FROM Station")
    return _rows_as_dicts(cur)


def fetch_devices(conn: pyodbc.Connection) -> list[dict]:
    cur = conn.cursor()
    cur.execute("SELECT DeviceID, DeviceName, DeviceDesc, MaxStringLength, Terminator FROM Device")
    return _rows_as_dicts(cur)


def fetch_rs232_params(conn: pyodbc.Connection) -> list[dict]:
    cur = conn.cursor()
    cur.execute("SELECT DeviceID, NoOfChannels, BaudRate, DataBits, Parity, StopBits FROM RS232DeviceParam")
    rows = _rows_as_dicts(cur)
    for row in rows:
        row["parity_mapped"] = PARITY_MAP.get(row["Parity"], "N")
    return rows


def fetch_daq_sources(conn: pyodbc.Connection) -> list[dict]:
    cur = conn.cursor()
    cur.execute("SELECT DAQSourceID, DAQSourceName, StationID, SourceType, SourceStatus FROM DAQSource")
    return _rows_as_dicts(cur)


def fetch_daq_port_sources(conn: pyodbc.Connection) -> list[dict]:
    cur = conn.cursor()
    cur.execute("SELECT DAQSourceID, Port, DeviceID, Channel FROM DAQPortSource")
    return _rows_as_dicts(cur)


# --------------------------------------------------------------------------- gage/calibrazione (db gemello)
def fetch_gages(conn: pyodbc.Connection) -> list[dict]:
    cur = conn.cursor()
    cur.execute("SELECT GageID, GageName, GageFolderID, Model, UnitID FROM Gage")
    return _rows_as_dicts(cur)


def fetch_gage_details(conn: pyodbc.Connection) -> list[dict]:
    cur = conn.cursor()
    cur.execute("SELECT GageID, SerialNumber, CustodianID FROM GageDetail")
    return _rows_as_dicts(cur)


def fetch_calibrations(conn: pyodbc.Connection) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        "SELECT CalibrationID, CalibrationName, GageID, CalibrationProcedureID, Status, StartTime, EndTime "
        "FROM Calibration"
    )
    return _rows_as_dicts(cur)


# --------------------------------------------------------------------------- storico misure (a batch)
def fetch_runs_since(conn: pyodbc.Connection, since: datetime) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        "SELECT RunID, RunName, RoutineID, StationID, BeginTimestamp, EndTimestamp "
        "FROM Run WHERE BeginTimestamp >= ?",
        since,
    )
    return _rows_as_dicts(cur)


def iter_feature_run_data_since(conn: pyodbc.Connection, since: datetime, batch_size: int = 5000):
    """Generator a batch: non carica tutto lo storico in RAM in una volta.
    FeatureRunData e' la tabella a volume piu' alto nell'originale (equivalente
    di `measurements` in leank-spc)."""
    cur = conn.cursor()
    cur.execute(
        "SELECT RunID, FeatureID, ObsID, ObsNo, Value, ObsTimestamp "
        "FROM FeatureRunData WHERE ObsTimestamp >= ? ORDER BY RunID, FeatureID, ObsNo",
        since,
    )
    while True:
        rows = cur.fetchmany(batch_size)
        if not rows:
            break
        columns = [col[0] for col in cur.description]
        yield [dict(zip(columns, row)) for row in rows]


def iter_att_feature_run_data_since(conn: pyodbc.Connection, since: datetime, batch_size: int = 5000):
    cur = conn.cursor()
    cur.execute(
        "SELECT RunID, FeatureID, ObsID, ObsNo, DefectCount, ObsTimestamp "
        "FROM AttFeatureRunData WHERE ObsTimestamp >= ? ORDER BY RunID, FeatureID, ObsNo",
        since,
    )
    while True:
        rows = cur.fetchmany(batch_size)
        if not rows:
            break
        columns = [col[0] for col in cur.description]
        yield [dict(zip(columns, row)) for row in rows]
