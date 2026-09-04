from __future__ import annotations

import json
import platform
import urllib.error
import urllib.request

from edge_agent.config import StationRef


def _http_base_from_ws_url(ws_url: str) -> str:
    """Deriva l'URL HTTP base del backend da quello WebSocket usato per
    /ws/agent (es. "ws://host:8000/ws/agent" -> "http://host:8000")."""
    http_url = ws_url.replace("wss://", "https://").replace("ws://", "http://")
    marker = "/ws/agent"
    idx = http_url.find(marker)
    return http_url[:idx] if idx != -1 else http_url


def resolve_station_id(ws_url: str, token: str, station_ref: StationRef, timeout: float = 10.0) -> int:
    """Chiama POST /api/stations/resolve per ottenere l'id numerico reale
    della stazione a partire da sede+nome (get-or-create, idempotente) -
    evita di dover cercare/copiare a mano lo station_id, causa reale di
    configurazioni sbagliate durante il collaudo (vedi docs/problemi-riscontrati.md)."""
    payload = {
        "site_name": station_ref.site_name,
        "name": station_ref.name,
        "computer_name": station_ref.computer_name or platform.node(),
    }
    request = urllib.request.Request(
        _http_base_from_ws_url(ws_url) + "/api/stations/resolve",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Risoluzione stazione fallita ({exc.code}): {detail}") from exc
    return data["id"]
