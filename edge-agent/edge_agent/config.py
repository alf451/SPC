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
class AgentConfig:
    station_id: int
    backend: BackendConfig
    outbox: OutboxConfig
    sources: list[dict[str, Any]]


def load_config(path: str | Path) -> AgentConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return AgentConfig(
        station_id=data["station_id"],
        backend=BackendConfig(**data["backend"]),
        outbox=OutboxConfig(**data.get("outbox", {})),
        sources=data["sources"],
    )
