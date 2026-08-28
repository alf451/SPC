from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

from edge_agent.config import AgentConfig, load_config
from edge_agent.outbox import Outbox
from edge_agent.sources.base import Source
from edge_agent.sources.digimatic_rs232 import DigimaticRS232Source
from edge_agent.sources.digimatic_usb_hid import DigimaticUSBHIDSource
from edge_agent.sources.mock import MockSource
from edge_agent.ws_client import WsClient

logger = logging.getLogger(__name__)

_SOURCE_FACTORIES = {
    "rs232": DigimaticRS232Source,
    "usb_hid": DigimaticUSBHIDSource,
    "mock": MockSource,
}


def build_source(spec: dict[str, Any]) -> Source:
    factory = _SOURCE_FACTORIES.get(spec["type"])
    if factory is None:
        raise ValueError(f"Tipo sorgente non supportato: {spec['type']!r}")
    return factory(spec)


async def run_source(source: Source, ws_client: WsClient) -> None:
    """Consuma lo stream di una Source e inoltra ogni lettura al WsClient
    (che a sua volta la scrive prima nell'outbox locale). Se la sorgente
    fisica cade (es. cavo scollegato), riprova ad aprirla con backoff fisso —
    a differenza della connessione al backend, qui un semplice retry basta
    perché il problema è quasi sempre "strumento/porta non disponibile ora"."""
    while True:
        try:
            source.is_connected = True
            async for reading in source.read():
                source.last_reading_at = reading.captured_at
                source.last_raw = reading.raw_text
                await ws_client.submit_reading(reading)
        except Exception:
            source.is_connected = False
            logger.exception("Sorgente %s (canale %s) in errore, retry tra 5s", source.port, source.channel_no)
            await source.close()
            await asyncio.sleep(5)


async def async_main(config: AgentConfig) -> None:
    outbox = Outbox(config.outbox.sqlite_path)
    sources = [build_source(spec) for spec in config.sources]
    ws_client = WsClient(config, outbox, sources)

    logger.info("Avvio edge agent — stazione %s, %d sorgenti configurate", config.station_id, len(sources))

    async with asyncio.TaskGroup() as tg:
        tg.create_task(ws_client.run_forever())
        for source in sources:
            tg.create_task(run_source(source, ws_client))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    config = load_config(config_path)
    try:
        asyncio.run(async_main(config))
    except KeyboardInterrupt:
        logger.info("Arresto richiesto dall'utente")


if __name__ == "__main__":
    main()
