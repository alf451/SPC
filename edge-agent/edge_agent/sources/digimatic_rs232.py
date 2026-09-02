from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

import serial

from edge_agent.models import Reading
from edge_agent.sources.base import Source

_PARITY_MAP = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD}

# Il formato del frame Digimatic varia tra convertitori/box (alcuni inviano già
# ASCII decimale tipo "+0.0125\r\n", altri BCD grezzo da decodificare in base a
# decimal_length/segno separati). Questa regex copre il caso comune "ASCII già
# formattato" — è il primo punto da adattare quando si collauda l'hardware reale.
#
# "\d*" (non "\d+") prima del punto: un convertitore Mitutoyo-compatibile reale
# (MicroRidge GageWay, stesso output "clocked serial" Digimatic decodificato -
# vedi external-documents/U-Wave-sintesi-italiano.md) invia il valore SENZA
# zero iniziale quando |valore| < 1, es. ".1455" o "-.5725" - con "\d+"
# obbligatorio quei casi non verrebbero riconosciuti (bug trovato via
# documentazione esterna, non ancora su hardware reale).
_NUMERIC_RE = re.compile(r"[-+]?\d*\.?\d+")


def parse_digimatic_frame(raw_text: str) -> float | None:
    """Estrae il valore numerico da un frame Digimatic testuale.

    TODO(collaudo in officina): verificare il formato reale restituito dal
    convertitore RS232 in uso (alcuni box Mitutoyo inviano cifre BCD senza
    punto decimale esplicito, con la posizione del decimale codificata in un
    nibble separato — in quel caso questa funzione va riscritta per quel
    formato specifico, mantenendo la stessa firma).

    Nel caso specifico del convertitore Mitutoyo U-WAVE (in uso presso Mopla):
    vedi external-documents/U-Wave-sintesi-italiano.md - confermati solo i
    parametri seriali (57600 baud, 8N1, nessuna parità, esposti da U-WAVEPAK
    su una porta COM virtuale sopra USB); il formato byte-per-byte del frame
    NON è documentato in quella fonte e resta da verificare via cattura diretta
    sull'hardware reale. Da notare anche: il tasto "dati" del trasmettitore
    U-WAVE-T, se tenuto premuto 5 secondi, invia un comando di "ritiro" (rimuove
    l'ultima misura) invece di un valore - il parser reale dovrà distinguere
    questo caso da una lettura numerica valida, non solo scartarlo come rumore.
    """
    match = _NUMERIC_RE.search(raw_text)
    return float(match.group()) if match else None


class DigimaticRS232Source(Source):
    """Legge un calibro/micrometro Digimatic collegato via RS232 (diretto o tramite
    box multiplexato con più canali, come RS232DeviceChannel in MeasurLink).

    Due modalità:
      - "push":   ascolto continuo, lo strumento invia alla pressione del tasto DATA
      - "polled": invia periodicamente `request_command` e attende una riga di risposta
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.port = config["port"]
        self.channel_no = config.get("channel_no")
        self._baud_rate = config.get("baud_rate", 9600)
        self._data_bits = config.get("data_bits", 7)
        self._parity = _PARITY_MAP[config.get("parity", "E")]
        self._stop_bits = config.get("stop_bits", 1)
        self._mode = config.get("mode", "push")
        self._request_command = config.get("request_command")
        self._terminator = config.get("frame_terminator", "\r\n").encode()
        self._poll_interval_s = config.get("poll_interval_seconds", 1.0)
        self._serial: serial.Serial | None = None

    def _open(self) -> serial.Serial:
        return serial.Serial(
            port=self.port,
            baudrate=self._baud_rate,
            bytesize=self._data_bits,
            parity=self._parity,
            stopbits=self._stop_bits,
            timeout=2,
        )

    async def read(self) -> AsyncIterator[Reading]:
        self._serial = await asyncio.to_thread(self._open)
        try:
            while True:
                if self._mode == "polled":
                    if self._request_command:
                        await asyncio.to_thread(self._serial.write, self._request_command.encode())
                    await asyncio.sleep(self._poll_interval_s)

                line = await asyncio.to_thread(self._serial.read_until, self._terminator)
                if not line:
                    continue  # timeout senza dati, riprova (rilevante soprattutto in modalità polled)

                raw_text = line.decode(errors="replace").strip()
                value = parse_digimatic_frame(raw_text)
                yield Reading(
                    port=self.port,
                    channel_no=self.channel_no,
                    raw_value=value,
                    raw_text=raw_text,
                    captured_at=datetime.now(timezone.utc),
                )
        finally:
            await self.close()

    async def close(self) -> None:
        if self._serial is not None and self._serial.is_open:
            await asyncio.to_thread(self._serial.close)
