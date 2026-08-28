from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import datetime

from edge_agent.models import Reading


class Source(ABC):
    """Interfaccia comune per ogni sorgente di acquisizione (porta RS232, HID, mock, ...).

    `main.py` avvia un task asyncio per ciascuna Source configurata e consuma
    `read()` come stream infinito — permette di gestire N strumenti in parallelo
    su una stessa stazione (equivalente ai canali multiplexati di RS232DeviceChannel
    o a più convertitori USB-ITN sullo stesso PC).
    """

    #: identificatore locale della sorgente, deve combaciare con {port, channel_no}
    #: annunciati nel messaggio "hello" e con i record daq_sources sul backend
    port: str
    channel_no: int | None

    #: stato "live" aggiornato da main.py::run_source, letto dal gestore del
    #: messaggio "test_source" (pannello admin -> backend -> agent) per rispondere
    #: senza dover aprire una seconda connessione concorrente sulla stessa porta
    is_connected: bool = False
    last_reading_at: datetime | None = None
    last_raw: str | None = None

    @abstractmethod
    async def read(self) -> AsyncIterator[Reading]:
        """Yield di una Reading per ogni misura ricevuta. Non ritorna mai finché
        la sorgente è attiva; solleva un'eccezione se la connessione fisica cade
        (il chiamante decide se/come riconnettersi)."""
        raise NotImplementedError
        yield  # pragma: no cover - rende la funzione un generatore per mypy/type-checkers

    async def close(self) -> None:
        """Rilascia la risorsa fisica (porta seriale, handle HID, ...). Default no-op."""
        return None
