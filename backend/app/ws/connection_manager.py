from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    """Pub/sub in-process per gli hub WebSocket.

    Sufficiente per un singolo worker Uvicorn. Se in futuro serviranno più
    worker/repliche del backend, sostituire il dizionario in-memory con
    Redis pub/sub (canale per station_id / run_id) mantenendo la stessa interfaccia.
    """

    def __init__(self) -> None:
        self._agents: dict[str, WebSocket] = {}
        self._dashboards: dict[int, set[WebSocket]] = defaultdict(set)

    # --- Edge Agent connections (una per stazione) -----------------------

    def connect_agent(self, station_id: str, websocket: WebSocket) -> None:
        self._agents[station_id] = websocket

    def disconnect_agent(self, station_id: str) -> None:
        self._agents.pop(station_id, None)

    def get_agent(self, station_id: str) -> WebSocket | None:
        return self._agents.get(station_id)

    # --- Dashboard connections (N per run) --------------------------------

    def connect_dashboard(self, run_id: int, websocket: WebSocket) -> None:
        self._dashboards[run_id].add(websocket)

    def disconnect_dashboard(self, run_id: int, websocket: WebSocket) -> None:
        self._dashboards[run_id].discard(websocket)
        if not self._dashboards[run_id]:
            self._dashboards.pop(run_id, None)

    async def broadcast_to_run(self, run_id: int, message: dict) -> None:
        dead: list[WebSocket] = []
        for ws in self._dashboards.get(run_id, ()):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect_dashboard(run_id, ws)


manager = ConnectionManager()
