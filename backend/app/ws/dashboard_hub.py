from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.security import decode_token
from app.ws.connection_manager import manager

router = APIRouter()


@router.websocket("/ws/dashboard/{run_id}")
async def dashboard_websocket(websocket: WebSocket, run_id: int, token: str | None = None) -> None:
    """Il frontend si connette qui per ricevere in tempo reale nuove misure e
    aggiornamenti control-limits/capability per un Run — vedi agent_hub.py
    per chi pubblica su questo canale (manager.broadcast_to_run).
    """
    if token is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        decode_token(token)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    manager.connect_dashboard(run_id, websocket)
    try:
        while True:
            # canale prevalentemente in sola ricezione lato frontend;
            # eventuali messaggi in ingresso sono ignorati/riservati a futuri comandi
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect_dashboard(run_id, websocket)
