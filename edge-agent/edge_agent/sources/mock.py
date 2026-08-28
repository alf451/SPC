from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from edge_agent.models import Reading
from edge_agent.sources.base import Source


class MockSource(Source):
    """Sorgente finta per validare il flusso outbox -> ws_client -> backend senza
    hardware reale (vedi sezione "Verifica" nel piano di progetto). Genera una
    lettura casuale attorno a `center` ogni `interval_seconds`.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.port = config.get("port", "MOCK1")
        self.channel_no = config.get("channel_no")
        self._center = config.get("center", 10.0)
        self._spread = config.get("spread", 0.05)
        self._interval_s = config.get("interval_seconds", 2.0)

    async def read(self) -> AsyncIterator[Reading]:
        while True:
            await asyncio.sleep(self._interval_s)
            value = round(random.gauss(self._center, self._spread), 4)
            yield Reading(
                port=self.port,
                channel_no=self.channel_no,
                raw_value=value,
                raw_text=str(value),
                captured_at=datetime.now(timezone.utc),
            )
