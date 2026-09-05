from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

import serial

from edge_agent.models import Reading
from edge_agent.sources.base import Source

logger = logging.getLogger(__name__)

_PARITY_MAP = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD}

# Il formato del frame Digimatic varia tra convertitori/box (alcuni inviano già
# ASCII decimale tipo "+0.0125\r\n", altri BCD grezzo da decodificare in base a
# decimal_length/segno separati). Questa regex copre il caso comune "ASCII già
# formattato, nessun prefisso" — un convertitore Digimatic diretto (non U-Wave,
# vedi sotto), un canale statico per porta.
#
# "\d*" (non "\d+") prima del punto: un convertitore Mitutoyo-compatibile reale
# (MicroRidge GageWay, stesso output "clocked serial" Digimatic decodificato -
# vedi external-documents/U-Wave-sintesi-italiano.md) invia il valore SENZA
# zero iniziale quando |valore| < 1, es. ".1455" o "-.5725" - con "\d+"
# obbligatorio quei casi non verrebbero riconosciuti.
_NUMERIC_RE = re.compile(r"[-+]?\d*\.?\d+")


def parse_digimatic_frame(raw_text: str) -> float | None:
    """Estrae il valore numerico da un frame Digimatic testuale "semplice"
    (un solo strumento per porta, nessun prefisso di canale). Per il
    ricevitore U-Wave multi-canale vedi parse_uwave_frame() sotto — usano
    formati diversi, non intercambiabili."""
    match = _NUMERIC_RE.search(raw_text)
    return float(match.group()) if match else None


# Formato U-Wave CONFERMATO via cattura diretta su hardware reale (sessione
# reale con un ricevitore U-Wave-R e 3 trasmettitori U-Wave-T abbinati a
# calibri/micrometro diversi, ciascuno su un canale assegnato via U-WAVEPAK):
#
#   DT10000+00000011.88M\r    <- misura: canale 10000, valore +11.88, unità M (mm)
#   DT10002-0000000.001M\r    <- canale 10002, valore -0.001 (nr di cifre prima/dopo
#                                 il punto NON è fisso, vedi \d+ non \d{n} sotto)
#   ST1000100009233899\r      <- messaggio di STATO (registrazione canale/strumento
#                                 abbinato) - NON una misura, va ignorato
#   TI1120000009241511\r      <- altro messaggio di stato - NON una misura, ignorato
#
# Punti importanti confermati da questa cattura (prima non documentati da
# nessuna fonte, vedi il TODO che c'era qui):
#   - il terminatore è CR da solo (\r, 0x0D) - NON CRLF come nel default
#     generico sopra; con CRLF configurato per errore, read_until non trova
#     mai il terminatore e ogni frame va in timeout (ritardo, non silenzio
#     totale - vedi docs/problemi-riscontrati.md)
#   - il "canale" (5 cifre dopo "DT") è l'identificativo dello strumento
#     fisico assegnato via U-WAVEPAK - corrisponde esattamente al nostro
#     daq_sources.channel_no, quindi un ricevitore con N trasmettitori è UNA
#     sola porta seriale con N canali multiplexati nel testo del frame
#     stesso (non N porte separate) - vedi DigimaticRS232Source più sotto
#     per come una singola connessione seriale li smista tutti
#   - "ST"/"TI" intervallati tra le misure vanno scartati, non trattati come
#     letture invalide/a zero
#
# Non ancora confermato da questa cattura (resta un TODO): il frame del
# comando di "ritiro" (tasto dati del trasmettitore tenuto premuto 5
# secondi) - nessun esempio catturato finora lo mostra distintamente.
_UWAVE_MEASUREMENT_RE = re.compile(r"^DT(\d{5})([+-]\d+\.\d+)[A-Za-z]?$")


def parse_uwave_frame(raw_text: str) -> tuple[int, float] | None:
    """Estrae (channel_no, valore) da un frame di misura U-Wave ("DT...").
    Restituisce None per i frame che non sono misure (es. "ST"/"TI") - il
    chiamante deve scartarli silenziosamente, non generare una Reading."""
    match = _UWAVE_MEASUREMENT_RE.match(raw_text)
    if match is None:
        return None
    return int(match.group(1)), float(match.group(2))


class DigimaticRS232Source(Source):
    """Legge un calibro/micrometro Digimatic collegato via RS232 (diretto o tramite
    box multiplexato con più canali, come RS232DeviceChannel in MeasurLink).

    Due modalità:
      - "push":   ascolto continuo, lo strumento invia alla pressione del tasto DATA
      - "polled": invia periodicamente `request_command` e attende una riga di risposta

    Due formati di frame (`frame_format`):
      - "generic" (default): un canale statico per porta, valore semplice
        "+0.0125" - vedi parse_digimatic_frame()
      - "uwave": il canale è multiplexato NEL TESTO del frame stesso
        ("DT10000+...") - un ricevitore con più trasmettitori usa UNA sola
        porta/connessione, indicare i canali attesi con `channels: [...]`
        invece di `channel_no` (vedi config.example.yaml) - ogni Reading
        porta il channel_no letto dal frame corrente, non uno fisso.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.port = config["port"]
        self.channel_no = config.get("channel_no")
        self._frame_format = config.get("frame_format", "generic")
        self._baud_rate = config.get("baud_rate", 9600)
        self._data_bits = config.get("data_bits", 7)
        self._parity = _PARITY_MAP[config.get("parity", "E")]
        self._stop_bits = config.get("stop_bits", 1)
        self._mode = config.get("mode", "push")
        self._request_command = config.get("request_command")
        default_terminator = "\r" if self._frame_format == "uwave" else "\r\n"
        self._terminator = config.get("frame_terminator", default_terminator).encode()
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
        logger.info(
            "Porta %s aperta (%d baud, %d%s%d, modo=%s, formato=%s) - in ascolto",
            self.port,
            self._baud_rate,
            self._data_bits,
            self._serial.parity,
            self._stop_bits,
            self._mode,
            self._frame_format,
        )
        try:
            while True:
                if self._mode == "polled":
                    if self._request_command:
                        await asyncio.to_thread(self._serial.write, self._request_command.encode())
                    await asyncio.sleep(self._poll_interval_s)

                line = await asyncio.to_thread(self._serial.read_until, self._terminator)
                if not line:
                    logger.debug("Porta %s: nessun dato entro il timeout, riprovo", self.port)
                    continue  # timeout senza dati, riprova (rilevante soprattutto in modalità polled)

                raw_text = line.decode(errors="replace").strip()

                if self._frame_format == "uwave":
                    parsed = parse_uwave_frame(raw_text)
                    if parsed is None:
                        logger.debug("Porta %s: frame non di misura ignorato: %r", self.port, raw_text)
                        continue
                    channel_no, value = parsed
                    logger.info("Porta %s: ricevuto canale %s -> valore=%s", self.port, channel_no, value)
                    yield Reading(
                        port=self.port,
                        channel_no=channel_no,
                        raw_value=value,
                        raw_text=raw_text,
                        captured_at=datetime.now(timezone.utc),
                    )
                else:
                    value = parse_digimatic_frame(raw_text)
                    logger.info("Porta %s: ricevuto %r -> valore=%s", self.port, raw_text, value)
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
