"""Passi dell'import MeasurLink -> leank-spc.

Ogni funzione `import_*` fa un passo, è idempotente (via id_map), e ritorna
un dict di conteggi. `progress(message)` viene chiamato ad ogni passo
significativo — nel CLI stampa a video, nel pannello admin finisce nel log
del job che il frontend interroga (vedi backend/app/routers/admin_import.py).

Nota sul versionamento tolleranze: MeasurLink non registra *quando* è
cambiata una versione di FeatureProperties/PartProperties (nessuna colonna
timestamp in quelle tabelle). Se un Feature ha più righe FeaturePropID le
importiamo tutte, ordinate per FeaturePropID crescente (l'euristica migliore
disponibile: gli ID sono assegnati in sequenza alla creazione), l'ultima
diventa la versione "corrente" (valid_to NULL) e le altre vengono marcate
come storiche con valid_to = now() — un confine approssimato, non il momento
reale del cambiamento, che MeasurLink stesso non conosce.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import pyodbc
from sqlalchemy.orm import Session

from import_measurlink import id_map, source_db, target_db

ProgressFn = Callable[[str], None]


def _noop_progress(message: str) -> None:
    pass


# --------------------------------------------------------------------------- lookups
def import_lookups(conn: pyodbc.Connection, session: Session, progress: ProgressFn = _noop_progress) -> dict:
    units = source_db.fetch_units(conn)
    n = 0
    for u in units:
        existing = session.query(target_db.Unit).filter_by(symbol=u["Symbol"]).one_or_none()
        if existing is None:
            session.add(target_db.Unit(symbol=u["Symbol"] or f"unit{u['UnitID']}", name=u["UnitName"], si_factor=u["Factor"] or 1.0, si_offset=u["Offset"] or 0.0))
            n += 1
    session.commit()
    progress(f"Unità di misura: {n} nuove ({len(units)} trovate in MeasurLink)")

    # una sola Site di default: MeasurLink non ha un concetto di "sito" separato dalla Station
    site = session.query(target_db.Site).filter_by(name="Sede principale").one_or_none()
    if site is None:
        site = target_db.Site(name="Sede principale")
        session.add(site)
        session.commit()

    stations = source_db.fetch_stations(conn)
    n = 0
    for s in stations:
        target_id = id_map.get_target_id(session, "Station", s["StationID"])
        if target_id is not None:
            continue
        station = target_db.Station(
            site_id=site.id,
            name=s["StationName"],
            description=s.get("StationDesc"),
            computer_name=s.get("ComputerName"),
            status="active",
        )
        session.add(station)
        session.flush()
        id_map.record(session, "Station", s["StationID"], "stations", station.id)
        n += 1
    session.commit()
    progress(f"Stazioni: {n} nuove ({len(stations)} trovate in MeasurLink)")
    return {"units": len(units), "stations_new": n, "stations_total": len(stations)}


# --------------------------------------------------------------------------- parts
def import_parts(conn: pyodbc.Connection, session: Session, progress: ProgressFn = _noop_progress) -> dict:
    folders = source_db.fetch_part_folders(conn)
    folder_map: dict[int, int] = {}
    # due passate: crea tutte le folder senza parent, poi collega i parent (potrebbero riferirsi in avanti)
    for f in folders:
        target_id = id_map.get_target_id(session, "PartFolder", f["PartFolderID"])
        if target_id is None:
            row = target_db.PartFolder(name=f["FolderName"])
            session.add(row)
            session.flush()
            id_map.record(session, "PartFolder", f["PartFolderID"], "part_folders", row.id)
            target_id = row.id
        folder_map[f["PartFolderID"]] = target_id
    session.commit()
    for f in folders:
        if f["ParentID"]:
            row = session.get(target_db.PartFolder, folder_map[f["PartFolderID"]])
            row.parent_id = folder_map.get(f["ParentID"])
    session.commit()

    parts = source_db.fetch_parts(conn)
    part_props_by_part: dict[int, list[dict]] = {}
    for pp in source_db.fetch_part_properties(conn):
        part_props_by_part.setdefault(pp["PartID"], []).append(pp)

    n_parts = 0
    n_versions = 0
    for p in parts:
        target_id = id_map.get_target_id(session, "Part", p["PartID"])
        if target_id is None:
            row = target_db.Part(
                folder_id=folder_map.get(p["PartFolderID"]),
                name=p["PartName"],
                description=p.get("PartDesc"),
            )
            session.add(row)
            session.flush()
            id_map.record(session, "Part", p["PartID"], "parts", row.id)
            target_id = row.id
            n_parts += 1

        versions = sorted(part_props_by_part.get(p["PartID"], []), key=lambda r: r["PartPropID"])
        for i, v in enumerate(versions):
            if id_map.get_target_id(session, "PartProperties", f"{p['PartID']}:{v['PartPropID']}") is not None:
                continue
            is_current = i == len(versions) - 1
            row = target_db.PartPropertyVersion(
                part_id=target_id,
                version_no=i + 1,
                sample_size=v.get("SampleSize"),
                lower_control_limit=v.get("LowerControlLimit"),
                center_line=v.get("CenterLine"),
                upper_control_limit=v.get("UpperControlLimit"),
                decimal_length=v.get("DecimalLength"),
                rounded=bool(v.get("Rounded", 1)),
                valid_to=None if is_current else datetime.now(timezone.utc),
            )
            session.add(row)
            session.flush()
            id_map.record(session, "PartProperties", f"{p['PartID']}:{v['PartPropID']}", "part_property_versions", row.id)
            n_versions += 1
    session.commit()
    progress(f"Parti: {n_parts} nuove, {n_versions} versioni proprietà ({len(parts)} parti trovate in MeasurLink)")
    return {"parts_new": n_parts, "property_versions": n_versions, "parts_total": len(parts)}


# --------------------------------------------------------------------------- routines
def import_routines(conn: pyodbc.Connection, session: Session, progress: ProgressFn = _noop_progress) -> dict:
    folders = source_db.fetch_routine_folders(conn)
    folder_map: dict[int, int] = {}
    for f in folders:
        target_id = id_map.get_target_id(session, "RoutineFolder", f["RoutineFolderID"])
        if target_id is None:
            row = target_db.RoutineFolder(name=f["FolderName"])
            session.add(row)
            session.flush()
            id_map.record(session, "RoutineFolder", f["RoutineFolderID"], "routine_folders", row.id)
            target_id = row.id
        folder_map[f["RoutineFolderID"]] = target_id
    session.commit()
    for f in folders:
        if f["ParentID"]:
            row = session.get(target_db.RoutineFolder, folder_map[f["RoutineFolderID"]])
            row.parent_id = folder_map.get(f["ParentID"])
    session.commit()

    routines = source_db.fetch_routines(conn)
    routine_map: dict[int, int] = {}
    n = 0
    for r in routines:
        target_id = id_map.get_target_id(session, "Routine", r["RoutineID"])
        if target_id is None:
            row = target_db.Routine(folder_id=folder_map.get(r["RoutineFolderID"]), name=r["RoutineName"])
            session.add(row)
            session.flush()
            id_map.record(session, "Routine", r["RoutineID"], "routines", row.id)
            target_id = row.id
            n += 1
        routine_map[r["RoutineID"]] = target_id
    session.commit()
    progress(f"Routine: {n} nuove ({len(routines)} trovate in MeasurLink)")
    return {"routines_new": n, "routines_total": len(routines)}


# --------------------------------------------------------------------------- features
def import_features(conn: pyodbc.Connection, session: Session, progress: ProgressFn = _noop_progress) -> dict:
    features = source_db.fetch_features(conn)
    feature_props: dict[int, list[dict]] = {}
    for fp in source_db.fetch_feature_properties(conn):
        feature_props.setdefault(fp["FeatureID"], []).append(fp)
    units_by_source_id = {}  # UnitID (MeasurLink) -> target unit id, risolto via import_map su Unit

    n_features = 0
    n_versions = 0
    for f in features:
        part_target_id = id_map.get_target_id(session, "Part", f["PartID"])
        if part_target_id is None:
            continue  # Part non importato (non dovrebbe succedere se import_parts gira prima)

        target_id = id_map.get_target_id(session, "Feature", f["FeatureID"])
        if target_id is None:
            row = target_db.Feature(
                part_id=part_target_id,
                feature_type=f["feature_type_mapped"],
                name=f["FeatureName"],
                description=f.get("FeatureDesc"),
                order_no=f.get("OrderNo", 0),
            )
            session.add(row)
            session.flush()
            id_map.record(session, "Feature", f["FeatureID"], "features", row.id)
            target_id = row.id
            n_features += 1

        versions = sorted(feature_props.get(f["FeatureID"], []), key=lambda r: r["FeaturePropID"])
        for i, v in enumerate(versions):
            key = f"{f['FeatureID']}:{v['FeaturePropID']}"
            if id_map.get_target_id(session, "FeatureProperties", key) is not None:
                continue
            is_current = i == len(versions) - 1
            row = target_db.FeaturePropertyVersion(
                feature_id=target_id,
                version_no=i + 1,
                target=v.get("Target"),
                lower_tolerance_limit=v.get("LowerToleranceLimit"),
                upper_tolerance_limit=v.get("UpperToleranceLimit"),
                lower_warning_limit=v.get("LowerWarningLimit"),
                upper_warning_limit=v.get("UpperWarningLimit"),
                subgroup_size=v.get("SubgroupSize") or 1,
                lower_control_limit_x=v.get("LowerControlLimitX"),
                center_line_x=v.get("CenterControlLimitX"),
                upper_control_limit_x=v.get("UpperControlLimitX"),
                lower_control_limit_r=v.get("LowerControlLimitR"),
                center_line_r=v.get("CenterControlLimitR"),
                upper_control_limit_r=v.get("UpperControlLimitR"),
                sigma_estimate=v.get("SigmaEstimate"),
                decimal_length=v.get("DecimalLength") or 3,
                rounded=bool(v.get("Rounded", 1)),
                tolerance_standard=v.get("ToleranceStandard"),
                tolerance_grade=v.get("ToleranceGrade"),
                valid_to=None if is_current else datetime.now(timezone.utc),
            )
            session.add(row)
            session.flush()
            id_map.record(session, "FeatureProperties", key, "feature_property_versions", row.id)
            n_versions += 1
    session.commit()

    # routine_features (join Routine<->Feature)
    n_bindings = 0
    for rf in source_db.fetch_routine_features(conn):
        routine_target = id_map.get_target_id(session, "Routine", rf["RoutineID"])
        feature_target = id_map.get_target_id(session, "Feature", rf["FeatureID"])
        if routine_target is None or feature_target is None:
            continue
        existing = session.get(target_db.RoutineFeature, {"routine_id": routine_target, "feature_id": feature_target})
        if existing is None:
            session.add(target_db.RoutineFeature(routine_id=routine_target, feature_id=feature_target, order_no=rf.get("OrderNo", 0)))
            n_bindings += 1
    session.commit()

    progress(f"Quote (Feature): {n_features} nuove, {n_versions} versioni proprietà, {n_bindings} collegamenti a Routine")
    return {"features_new": n_features, "property_versions": n_versions, "routine_bindings_new": n_bindings}


# --------------------------------------------------------------------------- daq (solo porte RS232, popolate nel DB del cliente)
def import_daq(conn: pyodbc.Connection, session: Session, progress: ProgressFn = _noop_progress) -> dict:
    devices_by_id = {d["DeviceID"]: d for d in source_db.fetch_devices(conn)}
    rs232_by_device = {r["DeviceID"]: r for r in source_db.fetch_rs232_params(conn)}
    port_sources = {p["DAQSourceID"]: p for p in source_db.fetch_daq_port_sources(conn)}
    daq_sources = source_db.fetch_daq_sources(conn)

    n_devices = 0
    n_sources = 0
    device_target_by_source_device_id: dict[int, int] = {}

    for src in daq_sources:
        if src["SourceType"] != source_db.SOURCE_TYPE_PORT:
            continue  # per ora importiamo solo le sorgenti RS232 (quelle popolate nel DB del cliente)
        port_row = port_sources.get(src["DAQSourceID"])
        if port_row is None:
            continue
        device = devices_by_id.get(port_row["DeviceID"])
        rs232 = rs232_by_device.get(port_row["DeviceID"])

        device_target_id = device_target_by_source_device_id.get(port_row["DeviceID"])
        if device_target_id is None:
            device_target_id = id_map.get_target_id(session, "Device", port_row["DeviceID"])
        if device_target_id is None and device is not None:
            row = target_db.DaqDevice(
                name=device["DeviceName"],
                description=device.get("DeviceDesc"),
                connection_type="rs232",
                terminator=device.get("Terminator"),
                max_string_length=device.get("MaxStringLength"),
                config={
                    "baud_rate": rs232["BaudRate"] if rs232 else 9600,
                    "data_bits": rs232["DataBits"] if rs232 else 7,
                    "parity": rs232["parity_mapped"] if rs232 else "E",
                    "stop_bits": rs232["StopBits"] if rs232 else 1,
                },
            )
            session.add(row)
            session.flush()
            id_map.record(session, "Device", port_row["DeviceID"], "daq_devices", row.id)
            device_target_id = row.id
            device_target_by_source_device_id[port_row["DeviceID"]] = device_target_id
            n_devices += 1

        if device_target_id is None:
            continue

        station_target_id = id_map.get_target_id(session, "Station", src["StationID"])
        if station_target_id is None:
            continue

        if id_map.get_target_id(session, "DAQSource", src["DAQSourceID"]) is not None:
            continue
        row = target_db.DaqSource(
            station_id=station_target_id,
            device_id=device_target_id,
            name=src["DAQSourceName"],
            port=port_row.get("Port"),
            channel_no=port_row.get("Channel"),
            status="active",
        )
        session.add(row)
        session.flush()
        id_map.record(session, "DAQSource", src["DAQSourceID"], "daq_sources", row.id)
        n_sources += 1

    session.commit()
    progress(f"DAQ: {n_devices} dispositivi, {n_sources} sorgenti RS232 importate ({len(daq_sources)} sorgenti totali in MeasurLink, le altre modalità non sono ancora importate)")
    return {"devices_new": n_devices, "sources_new": n_sources}


# --------------------------------------------------------------------------- gage/calibrazione
def import_gages(gage_conn: pyodbc.Connection, session: Session, progress: ProgressFn = _noop_progress) -> dict:
    gages = source_db.fetch_gages(gage_conn)
    details_by_gage = {d["GageID"]: d for d in source_db.fetch_gage_details(gage_conn)}

    n = 0
    for g in gages:
        if id_map.get_target_id(session, "Gage", g["GageID"]) is not None:
            continue
        detail = details_by_gage.get(g["GageID"], {})
        row = target_db.Gage(
            name=g["GageName"],
            model=g.get("Model"),
            serial_number=detail.get("SerialNumber"),
            status="in_service",
        )
        session.add(row)
        session.flush()
        id_map.record(session, "Gage", g["GageID"], "gages", row.id)
        n += 1
    session.commit()

    calibrations = source_db.fetch_calibrations(gage_conn)
    n_cal = 0
    for c in calibrations:
        gage_target_id = id_map.get_target_id(session, "Gage", c["GageID"])
        if gage_target_id is None or id_map.get_target_id(session, "Calibration", c["CalibrationID"]) is not None:
            continue
        row = target_db.Calibration(
            gage_id=gage_target_id,
            status="passed" if c.get("Status") else "in_progress",
            started_at=c.get("StartTime") or datetime.now(timezone.utc),
            completed_at=c.get("EndTime"),
        )
        session.add(row)
        session.flush()
        id_map.record(session, "Calibration", c["CalibrationID"], "calibrations", row.id)
        n_cal += 1
    session.commit()

    progress(f"Strumenti: {n} gage nuovi, {n_cal} calibrazioni ({len(gages)} strumenti trovati in MeasurLink9_GAGE)")
    return {"gages_new": n, "calibrations_new": n_cal}


# --------------------------------------------------------------------------- storico misure (a batch)
def import_runs_and_measurements(
    conn: pyodbc.Connection,
    session: Session,
    since_months: int,
    dry_run: bool,
    progress: ProgressFn = _noop_progress,
) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=30 * since_months)
    runs = source_db.fetch_runs_since(conn, since)
    progress(f"Trovati {len(runs)} Run da MeasurLink dal {since.date()} in poi")

    n_runs = 0
    for r in runs:
        routine_target = id_map.get_target_id(session, "Routine", r["RoutineID"])
        station_target = id_map.get_target_id(session, "Station", r["StationID"])
        if routine_target is None or station_target is None:
            continue
        if id_map.get_target_id(session, "Run", r["RunID"]) is not None:
            continue
        if dry_run:
            n_runs += 1
            continue
        row = target_db.Run(
            routine_id=routine_target,
            station_id=station_target,
            name=r["RunName"] or f"Run {r['RunID']}",
            status="completed",
            started_at=r["BeginTimestamp"],
            ended_at=r.get("EndTimestamp"),
        )
        session.add(row)
        session.flush()
        id_map.record(session, "Run", r["RunID"], "runs", row.id)
        n_runs += 1
    if not dry_run:
        session.commit()
    progress(f"Run: {n_runs} {'da importare (dry-run)' if dry_run else 'importati'}")

    n_measurements = 0
    if not dry_run:
        for batch in source_db.iter_feature_run_data_since(conn, since):
            for row_data in batch:
                run_target = id_map.get_target_id(session, "Run", row_data["RunID"])
                feature_target = id_map.get_target_id(session, "Feature", row_data["FeatureID"])
                if run_target is None or feature_target is None:
                    continue
                session.add(
                    target_db.Measurement(
                        run_id=run_target,
                        feature_id=feature_target,
                        obs_no=row_data["ObsNo"],
                        value=row_data["Value"],
                        captured_at=row_data["ObsTimestamp"],
                        source="import",
                    )
                )
                n_measurements += 1
            session.commit()
            progress(f"  ...{n_measurements} misure importate finora")
    else:
        # in dry-run contiamo senza scrivere, solo per dare un numero realistico all'utente
        for batch in source_db.iter_feature_run_data_since(conn, since):
            n_measurements += len(batch)

    progress(f"Misure (FeatureRunData): {n_measurements} {'stimate (dry-run)' if dry_run else 'importate'}")
    return {"runs": n_runs, "measurements": n_measurements, "dry_run": dry_run}
