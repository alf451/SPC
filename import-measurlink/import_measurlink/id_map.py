"""Tabella di appoggio per rendere l'import idempotente/ri-eseguibile.

Non fa parte dello schema di dominio (docs/schema.sql) — è un dettaglio
operativo di questo tool, creata da lui stesso al primo utilizzo (bootstrap
esplicito invece di una migration Alembic, perché appartiene all'operazione
di import, non al prodotto).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

_BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS import_map (
    source_system   text NOT NULL,
    source_table    text NOT NULL,
    source_id       text NOT NULL,
    target_table    text NOT NULL,
    target_id       bigint NOT NULL,
    imported_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source_system, source_table, source_id)
)
"""


def ensure_bootstrapped(session: Session) -> None:
    session.execute(text(_BOOTSTRAP_SQL))
    session.commit()


def get_target_id(session: Session, source_table: str, source_id, source_system: str = "measurlink") -> int | None:
    row = session.execute(
        text(
            "SELECT target_id FROM import_map "
            "WHERE source_system = :sys AND source_table = :tbl AND source_id = :sid"
        ),
        {"sys": source_system, "tbl": source_table, "sid": str(source_id)},
    ).first()
    return row[0] if row else None


def record(
    session: Session, source_table: str, source_id, target_table: str, target_id: int, source_system: str = "measurlink"
) -> None:
    session.execute(
        text(
            "INSERT INTO import_map (source_system, source_table, source_id, target_table, target_id) "
            "VALUES (:sys, :tbl, :sid, :ttbl, :tid) "
            "ON CONFLICT (source_system, source_table, source_id) "
            "DO UPDATE SET target_id = EXCLUDED.target_id, imported_at = now()"
        ),
        {"sys": source_system, "tbl": source_table, "sid": str(source_id), "ttbl": target_table, "tid": target_id},
    )
