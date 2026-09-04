from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class BackendConfig:
    ws_url: str
    token: str
    reconnect_backoff_seconds: list[int] = field(default_factory=lambda: [1, 2, 5, 10, 30])
    heartbeat_interval_seconds: int = 20


@dataclass
class OutboxConfig:
    sqlite_path: str = "./outbox.sqlite3"
    retry_interval_seconds: int = 5


@dataclass
class StationRef:
    """Sede+nome di una stazione, per farsela risolvere in un id numerico dal
    backend (POST /api/stations/resolve) invece di doverlo cercare/copiare a
    mano - vedi edge_agent/station_resolve.py."""

    site_name: str
    name: str
    computer_name: str | None = None


@dataclass
class AgentConfig:
    backend: BackendConfig
    outbox: OutboxConfig
    sources: list[dict[str, Any]]
    # Uno dei due va indicato in config.yaml: station_id (numero già noto,
    # compatibilità con configurazioni esistenti) oppure station (site_name +
    # name, risolto automaticamente all'avvio - vedi main.py).
    station_id: int | None = None
    station_ref: StationRef | None = None


def load_config(path: str | Path) -> AgentConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    station_ref = StationRef(**data["station"]) if "station" in data else None
    return AgentConfig(
        station_id=data.get("station_id"),
        station_ref=station_ref,
        backend=BackendConfig(**data["backend"]),
        outbox=OutboxConfig(**data.get("outbox", {})),
        sources=data["sources"],
    )
