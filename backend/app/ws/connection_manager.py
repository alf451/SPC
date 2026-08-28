import asyncio
import uuid
from collections import defaultdict

from fastapi import WebSocket


class AgentOfflineError(Exception):
    """La stazione richiesta non ha un Edge Agent connesso in questo momento."""


class ConnectionManager:
    """Pub/sub in-process per gli hub WebSocket.

    Sufficiente per un singolo worker Uvicorn. Se in futuro serviranno più
    worker/repliche del backend, sostituire il dizionario in-memory con
    Redis pub/sub (canale per station_id / run_id) mantenendo la stessa interfaccia.
    """

    def __init__(self) -> None:
        self._agents: dict[str, WebSocket] = {}
        self._dashboards: dict[int, set[WebSocket]] = defaultdict(set)
        self._pending_requests: dict[str, asyncio.Future] = {}

    # --- Edge Agent connections (una per stazione) -----------------------

    def connect_agent(self, station_id: str, websocket: WebSocket) -> None:
        self._agents[station_id] = websocket

    def disconnect_agent(self, station_id: str) -> None:
        self._agents.pop(station_id, None)

    def get_agent(self, station_id: str) -> WebSocket | None:
        return self._agents.get(station_id)

    # --- Richieste request/response verso un agent (es. "prova la porta X") --

    async def send_agent_request(self, station_id: str, message: dict, timeout: float = 8.0) -> dict:
        """Invia un messaggio all'Edge Agent di una stazione e attende la risposta
        correlata (stesso `request_id`, inviato dal chiamante dentro `message`).

        Usato per operazioni "test collegamento" avviate dal pannello admin: il
        backend non ha accesso diretto alle porte seriali della stazione, quindi
        deve chiedere all'agent di provare e riportare l'esito.
        """
        websocket = self._agents.get(station_id)
        if websocket is None:
            raise AgentOfflineError(f"Nessun Edge Agent connesso per la stazione {station_id}")

        request_id = message.setdefault("request_id", str(uuid.uuid4()))
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending_requests[request_id] = future
        try:
            await websocket.send_json(message)
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending_requests.pop(request_id, None)

    def resolve_agent_request(self, request_id: str, result: dict) -> bool:
        """Chiamato da agent_hub quando arriva un `test_result` dall'agent.
        Ritorna False se non c'era nessuno in attesa (es. timeout già scaduto)."""
        future = self._pending_requests.get(request_id)
        if future is None or future.done():
            return False
        future.set_result(result)
        return True

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
