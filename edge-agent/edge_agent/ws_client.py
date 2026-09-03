from __future__ import annotations

import asyncio
import itertools
import json
import logging
from datetime import datetime, timezone

import websockets

from edge_agent.config import AgentConfig
from edge_agent.models import Reading
from edge_agent.outbox import Outbox
from edge_agent.port_scan import list_available_ports
from edge_agent.sources.base import Source

logger = logging.getLogger(__name__)


class WsClient:
    """Client WebSocket verso /ws/agent/{station_id}.

    Ogni Reading passa PRIMA dall'Outbox locale (write-ahead) e viene inviata
    solo se una connessione è attiva; alla riconnessione, `_drain_outbox`
    reinvia tutto ciò che non ha ancora ricevuto un ack dal server. Questo
    garantisce zero perdita dati durante un'interruzione di rete.
    """

    def __init__(self, config: AgentConfig, outbox: Outbox, sources: list[Source]) -> None:
        self._config = config
        self._outbox = outbox
        self._sources = sources  # per rispondere a "test_source" senza aprire una seconda connessione sulla porta
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
        # Porte seriali fisicamente presenti su QUESTA macchina in questo momento
        # (non solo quelle gia' configurate in sources) - il backend le tiene da
        # parte per il pannello admin/frontend, cosi' si vede cosa c'e' davvero
        # collegato a una stazione senza doverci accedere via RDP.
        await self._ws.send(
            json.dumps({"type": "hello", "sources": sources, "available_ports": list_available_ports()})
        )

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

            elif msg_type == "test_source":
                await self._handle_test_source(message)

    async def _handle_test_source(self, message: dict) -> None:
        """Risponde al pulsante "Prova collegamento" del pannello admin (via
        POST /api/daq-sources/{id}/test sul backend). Non apre una seconda
        connessione sulla porta — quella e' gia' tenuta aperta dal task in
        main.py::run_source — riporta invece lo stato "live" di quella sorgente:
        se e' connessa e quando e' arrivata l'ultima lettura. Per una sorgente in
        modalita' "push" (lo strumento invia solo alla pressione del tasto DATA)
        e' l'informazione onesta da dare: non possiamo forzare una lettura,
        possiamo dire se il canale è aperto e pronto a riceverla.
        """
        port = message.get("port")
        channel_no = message.get("channel_no")
        source = next((s for s in self._sources if s.port == port and s.channel_no == channel_no), None)

        if source is None:
            result = {"ok": False, "message": f"Nessuna sorgente configurata per {port} (canale {channel_no})"}
        elif not source.is_connected:
            result = {"ok": False, "message": "Porta non aperta - controllare che lo strumento sia collegato e la porta corretta"}
        elif source.last_reading_at is None:
            result = {"ok": True, "message": "Porta aperta, in attesa della prima lettura (premere il tasto DATA sullo strumento)"}
        else:
            age_s = (datetime.now(timezone.utc) - source.last_reading_at).total_seconds()
            result = {
                "ok": True,
                "message": f"Porta aperta, ultima lettura {age_s:.0f}s fa",
                "sample_raw": source.last_raw,
            }

        await self._ws.send(json.dumps({"type": "test_result", "request_id": message.get("request_id"), **result}))

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
