from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Reading:
    """Una singola lettura da una sorgente fisica (porta RS232 o dispositivo HID).

    `port`/`channel_no` identificano la sorgente in termini locali (quelli scritti
    in config.yaml); il backend li risolve nel daq_source_id reale al messaggio
    "hello" — l'agent non ha bisogno di conoscere l'id lato database.
    """

    port: str
    channel_no: int | None
    raw_value: float | None
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_text: str | None = None  # frame grezzo pre-parsing, utile per debug/calibrazione del parser
