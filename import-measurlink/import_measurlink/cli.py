"""Orchestratore dell'import. Usabile da riga di comando:

    python -m import_measurlink --config config.yaml --since-months 3
    python -m import_measurlink --config config.yaml --only-config
    python -m import_measurlink --config config.yaml --dry-run

...oppure importato come libreria (usato da backend/app/routers/admin_import.py
per il pannello admin, che passa i parametri di connessione ricevuti dal form
invece di leggerli da un file yaml).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

import yaml

from import_measurlink import id_map, pipeline, source_db, target_db

ProgressFn = Callable[[str], None]


def run_import(
    source_cfg: source_db.SourceConnectionConfig,
    target_cfg: target_db.TargetConnectionConfig,
    since_months: int = 3,
    only_config: bool = False,
    dry_run: bool = False,
    gage_database: str | None = None,
    progress: ProgressFn = print,
) -> dict:
    """Punto d'ingresso unico, chiamato sia dal CLI che dal pannello admin."""
    summary: dict = {}

    progress("Connessione al database MeasurLink...")
    conn = source_db.connect(source_cfg)
    progress(f"Connesso a {source_cfg.database} su {source_cfg.server}")

    progress("Connessione a leank-spc (PostgreSQL)...")
    session = target_db.make_session(target_cfg)
    id_map.ensure_bootstrapped(session)
    progress("Connesso.")

    try:
        summary["lookups"] = pipeline.import_lookups(conn, session, progress)
        summary["parts"] = pipeline.import_parts(conn, session, progress)
        summary["routines"] = pipeline.import_routines(conn, session, progress)
        summary["features"] = pipeline.import_features(conn, session, progress)
        summary["daq"] = pipeline.import_daq(conn, session, progress)

        if gage_database:
            progress(f"Connessione al database strumenti {gage_database}...")
            gage_cfg = source_db.SourceConnectionConfig(
                driver=source_cfg.driver, server=source_cfg.server, database=gage_database,
                username=source_cfg.username, password=source_cfg.password,
            )
            gage_conn = source_db.connect(gage_cfg)
            try:
                summary["gages"] = pipeline.import_gages(gage_conn, session, progress)
            finally:
                gage_conn.close()

        if not only_config:
            summary["history"] = pipeline.import_runs_and_measurements(conn, session, since_months, dry_run, progress)

        progress("Import completato." if not dry_run else "Prova di sincronizzazione completata (nessun dato scritto).")
        return summary
    finally:
        conn.close()
        session.close()


def _load_yaml_config(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--since-months", type=int, default=None, help="sovrascrive since_months del config")
    parser.add_argument("--only-config", action="store_true", help="salta l'import dello storico misure")
    parser.add_argument("--dry-run", action="store_true", help="prova di sincronizzazione: nessuna scrittura su Postgres per lo storico")
    args = parser.parse_args()

    cfg = _load_yaml_config(args.config)
    # gage_database non è un parametro di connessione pyodbc, va tolto prima di **cfg
    source_cfg_dict = dict(cfg["source_sqlserver"])
    gage_database = source_cfg_dict.pop("gage_database", None)
    source_cfg = source_db.SourceConnectionConfig(**source_cfg_dict)
    target_cfg = target_db.TargetConnectionConfig(**cfg["target_postgres"])
    since_months = args.since_months if args.since_months is not None else cfg.get("since_months", 3)

    run_import(
        source_cfg, target_cfg,
        since_months=since_months,
        only_config=args.only_config,
        dry_run=args.dry_run,
        gage_database=gage_database,
    )


if __name__ == "__main__":
    sys.exit(main())
