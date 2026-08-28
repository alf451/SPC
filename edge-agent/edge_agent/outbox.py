from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from edge_agent.models import Reading

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pending_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    port TEXT NOT NULL,
    channel_no INTEGER,
    raw_value REAL,
    raw_text TEXT,
    captured_at TEXT NOT NULL,
    daq_source_id INTEGER,          -- valorizzato appena noto (dopo "hello"/"config")
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


@dataclass
class OutboxRow:
    id: int
    port: str
    channel_no: int | None
    raw_value: float | None
    captured_at: str
    daq_source_id: int | None


class Outbox:
    """Coda locale SQLite per bufferizzare le letture quando il backend non è
    raggiungibile. Ogni lettura viene scritta qui PRIMA di tentare l'invio via
    WebSocket (write-ahead), così un crash/riavvio dell'agent non perde dati
    non ancora confermati dal server.
    """

    def __init__(self, sqlite_path: str) -> None:
        self._path = sqlite_path
        self._conn = sqlite3.connect(sqlite_path, check_same_thread=False)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    async def add(self, reading: Reading, daq_source_id: int | None) -> int:
        return await asyncio.to_thread(self._add_sync, reading, daq_source_id)

    def _add_sync(self, reading: Reading, daq_source_id: int | None) -> int:
        cur = self._conn.execute(
            "INSERT INTO pending_readings (port, channel_no, raw_value, raw_text, captured_at, daq_source_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                reading.port,
                reading.channel_no,
                reading.raw_value,
                reading.raw_text,
                reading.captured_at.isoformat(),
                daq_source_id,
            ),
        )
        self._conn.commit()
        return cur.lastrowid

    async def set_daq_source_id(self, row_id: int, daq_source_id: int) -> None:
        await asyncio.to_thread(self._set_daq_source_id_sync, row_id, daq_source_id)

    def _set_daq_source_id_sync(self, row_id: int, daq_source_id: int) -> None:
        self._conn.execute("UPDATE pending_readings SET daq_source_id = ? WHERE id = ?", (daq_source_id, row_id))
        self._conn.commit()

    async def backfill_daq_source_id(self, port: str, channel_no: int | None, daq_source_id: int) -> None:
        """Valorizza daq_source_id sulle righe rimaste in sospeso perché scritte
        prima che arrivasse il messaggio "config" dal backend (tipicamente le
        righe accumulate offline prima della prima connessione riuscita)."""
        await asyncio.to_thread(self._backfill_sync, port, channel_no, daq_source_id)

    def _backfill_sync(self, port: str, channel_no: int | None, daq_source_id: int) -> None:
        self._conn.execute(
            "UPDATE pending_readings SET daq_source_id = ? "
            "WHERE port = ? AND channel_no IS ? AND daq_source_id IS NULL",
            (daq_source_id, port, channel_no),
        )
        self._conn.commit()

    async def ack(self, row_id: int) -> None:
        await asyncio.to_thread(self._ack_sync, row_id)

    def _ack_sync(self, row_id: int) -> None:
        self._conn.execute("DELETE FROM pending_readings WHERE id = ?", (row_id,))
        self._conn.commit()

    async def pending(self, limit: int = 100) -> list[OutboxRow]:
        return await asyncio.to_thread(self._pending_sync, limit)

    def _pending_sync(self, limit: int) -> list[OutboxRow]:
        cur = self._conn.execute(
            "SELECT id, port, channel_no, raw_value, captured_at, daq_source_id "
            "FROM pending_readings WHERE daq_source_id IS NOT NULL ORDER BY id LIMIT ?",
            (limit,),
        )
        return [OutboxRow(*row) for row in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()
