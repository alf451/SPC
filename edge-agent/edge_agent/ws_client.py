from __future__ import annotations

import asyncio
import itertools
import json
import logging

import websockets

from edge_agent.config import AgentConfig
from edge_agent.models import Reading
from edge_agent.outbox import Outbox

logger = logging.getLogger(__name__)


class WsClient:
    """Client WebSocket verso /ws/agent/{station_id}.

    Ogni Reading passa PRIMA dall'Outbox locale (write-ahead) e viene inviata
    solo se una connessione è attiva; alla riconnessione, `_drain_outbox`
    reinvia tutto ciò che non ha ancora ricevuto un ack dal server. Questo
    garantisce zero perdita dati durante un'interruzione di rete.
    """

    def __init__(self, config: AgentConfig, outbox: Outbox) -> None:
        self._config = config
        self._outbox = outbox
        self._daq_source_map: dict[tuple[str, int | None], int] = {}
        self._active_run_id: int | None = None
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._connected = asyncio.Event()

    @property
    def is_ready(self) -> bool:
        """True quando la connessione è aperta E il mapping porta->daq_source_id è noto."""
        return self._connected.is_set() and bool(self._daq_source_map)

    async def submit_reading(self, reading: Reading) -> None:
        daq_source_id = self._daq_source_map.get((reading.port, reading.channel_no))
        row_id = await self._outbox.add(reading, daq_source_id)
        if daq_source_id is not None:
            await self._outbox.set_daq_source_id(row_id, daq_source_id)
        # l'invio effettivo avviene nel drain loop: qui ci si limita a garantire
        # la persistenza locale, che è la parte che non deve mai fallire

    async def run_forever(self) -> None:
        """Entry point: mantiene la connessione, riconnettendosi con backoff.
        Va eseguito come task asyncio indipendente (vedi main.py)."""
        backoff = itertools.cycle(self._config.backend.reconnect_backoff_seconds)
        url = f"{self._config.backend.ws_url}/{self._config.station_id}?token={self._config.backend.token}"

        while True:
            try:
                async with websockets.connect(url) as ws:
                    self._ws = ws
                    self._connected.set()
                    logger.info("Connesso al backend: %s", url)
                    await self._send_hello()

                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self._receive_loop())
                        tg.create_task(self._heartbeat_loop())
                        tg.create_task(self._drain_loop())

            except* Exception as exc_group:  # noqa: BLE001 - vogliamo loggare qualunque causa di disconnessione
                logger.warning("Connessione persa, riconnessione in corso: %s", exc_group.exceptions)
            finally:
                self._ws = None
                self._connected.clear()

            await asyncio.sleep(next(backoff))

    async def _send_hello(self) -> None:
        sources = [{"port": s.get("port") or s.get("device_path"), "channel_no": s.get("channel_no")} for s in self._config.sources]
        await self._ws.send(json.dumps({"type": "hello", "sources": sources}))

    async def _receive_loop(self) -> None:
        async for raw in self._ws:
            message = json.loads(raw)
            msg_type = message.get("type")

            if msg_type == "config":
                self._active_run_id = message.get("active_run_id")
                self._daq_source_map = {
                    (item["port"], item["channel_no"]): item["daq_source_id"]
                    for item in message.get("daq_sources", [])
                }
                for (port, channel_no), daq_source_id in self._daq_source_map.items():
                    await self._outbox.backfill_daq_source_id(port, channel_no, daq_source_id)
                logger.info("Config ricevuta: run attivo=%s, sorgenti risolte=%d", self._active_run_id, len(self._daq_source_map))

            elif msg_type == "ack":
                if message.get("ok") and message.get("ref") is not None:
                    await self._outbox.ack(message["ref"])
                elif not message.get("ok"):
                    logger.warning("Lettura rifiutata dal server: %s", message.get("reason"))

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(self._config.backend.heartbeat_interval_seconds)
            await self._ws.send(json.dumps({"type": "heartbeat"}))

    async def _drain_loop(self) -> None:
        """Reinvia periodicamente le letture in outbox non ancora confermate.
        Usa l'id della riga outbox come `ref` per correlare l'ack in arrivo."""
        while True:
            for row in await self._outbox.pending():
                await self._ws.send(
                    json.dumps(
                        {
                            "type": "reading",
                            "ref": row.id,
                            "daq_source_id": row.daq_source_id,
                            "raw_value": row.raw_value,
                            "captured_at": row.captured_at,
                        }
                    )
                )
            await asyncio.sleep(self._config.outbox.retry_interval_seconds)
