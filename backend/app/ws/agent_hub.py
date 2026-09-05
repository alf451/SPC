from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models.daq import DaqSource, FeatureDaqBinding
from app.models.spc import AttributeObservation, Feature, Measurement, Run
from app.notifications.mailer import notify_background
from app.security import decode_token
from app.ws.connection_manager import manager

router = APIRouter()

# Evita di spedire un'email ad ogni singola disconnessione (es. riavvii del
# backend durante lo sviluppo/collaudo, molto frequenti) - una per stazione
# ogni tot minuti e' sufficiente per far notare un problema reale senza
# diventare rumore.
_DISCONNECT_NOTIFY_COOLDOWN = timedelta(minutes=5)
_last_disconnect_notified: dict[str, datetime] = {}


def _should_notify_disconnect(station_key: str) -> bool:
    now = datetime.now(timezone.utc)
    last = _last_disconnect_notified.get(station_key)
    if last is not None and now - last < _DISCONNECT_NOTIFY_COOLDOWN:
        return False
    _last_disconnect_notified[station_key] = now
    return True


async def _authenticate(websocket: WebSocket, token: str | None) -> bool:
    """Autenticazione minima: JWT access token di un utente/account di servizio.

    Per uno scenario multi-stazione più rigido si può evolvere verso un token
    statico per-stazione salvato in una tabella dedicata (station_tokens),
    ma il JWT esistente evita di introdurre un secondo meccanismo di auth.
    """
    if token is None:
        return False
    try:
        payload = decode_token(token)
    except Exception:
        return False
    return payload.get("type") == "access"


async def _active_run(station_id: int) -> Run | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Run)
            .where(Run.station_id == station_id, Run.status == "active")
            .order_by(Run.started_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def _resolve_daq_sources(station_id: int, requested: list[dict]) -> list[dict]:
    """Risolve {port, channel_no} locali negli id reali daq_sources per la stazione."""
    resolved = []
    async with SessionLocal() as session:
        for item in requested:
            result = await session.execute(
                select(DaqSource).where(
                    DaqSource.station_id == station_id,
                    DaqSource.port == item.get("port"),
                    DaqSource.channel_no == item.get("channel_no"),
                )
            )
            source = result.scalar_one_or_none()
            if source is not None:
                resolved.append({"port": source.port, "channel_no": source.channel_no, "daq_source_id": source.id})
    return resolved


async def _feature_bindings_for_run(run: Run) -> list[dict]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(FeatureDaqBinding).where(FeatureDaqBinding.routine_id == run.routine_id)
        )
        return [
            {"feature_id": b.feature_id, "daq_source_id": b.daq_source_id} for b in result.scalars()
        ]


async def _persist_reading(run: Run, daq_source_id: int, raw_value: float | None, captured_at: datetime) -> dict | None:
    """Risolve la Feature dal daq_source_id (nell'ambito della Routine del Run attivo)
    e scrive la misura nella tabella corretta (variabile vs attributiva).
    """
    async with SessionLocal() as session:
        binding_result = await session.execute(
            select(FeatureDaqBinding).where(
                FeatureDaqBinding.routine_id == run.routine_id,
                FeatureDaqBinding.daq_source_id == daq_source_id,
            )
        )
        binding = binding_result.scalar_one_or_none()
        if binding is None:
            return None

        feature = await session.get(Feature, binding.feature_id)
        if feature is None:
            return None

        if feature.feature_type == "attribute":
            obs_no = (
                await session.scalar(
                    select(func.count())
                    .select_from(AttributeObservation)
                    .where(AttributeObservation.run_id == run.id, AttributeObservation.feature_id == feature.id)
                )
                or 0
            ) + 1
            row = AttributeObservation(
                run_id=run.id,
                feature_id=feature.id,
                obs_no=obs_no,
                defect_count=int(raw_value or 0),
                captured_at=captured_at,
                tool_position_id=run.current_tool_position_id,
            )
        else:
            obs_no = (
                await session.scalar(
                    select(func.count())
                    .select_from(Measurement)
                    .where(Measurement.run_id == run.id, Measurement.feature_id == feature.id)
                )
                or 0
            ) + 1
            row = Measurement(
                run_id=run.id,
                feature_id=feature.id,
                obs_no=obs_no,
                value=raw_value,
                captured_at=captured_at,
                source="daq",
                tool_position_id=run.current_tool_position_id,
            )

        session.add(row)
        await session.commit()
        await session.refresh(row)

        # TODO: qui va agganciato il ricalcolo di control_limits/capability_results
        # (Cp/Cpk, regole SPC) — per ora l'Edge Agent riceve solo l'ack e i dashboard
        # ricevono la misura grezza via broadcast_to_run.
        return {"feature_id": feature.id, "obs_no": obs_no, "value": raw_value, "captured_at": captured_at.isoformat()}


@router.websocket("/ws/agent/{station_id}")
async def agent_websocket(websocket: WebSocket, station_id: int, token: str | None = None) -> None:
    if not await _authenticate(websocket, token):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    station_key = str(station_id)
    manager.connect_agent(station_key, websocket)

    try:
        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type")

            if msg_type == "hello":
                run = await _active_run(station_id)
                resolved_sources = await _resolve_daq_sources(station_id, message.get("sources", []))
                bindings = await _feature_bindings_for_run(run) if run else []
                manager.set_available_ports(station_key, message.get("available_ports", []))
                await websocket.send_json(
                    {
                        "type": "config",
                        "active_run_id": run.id if run else None,
                        "daq_sources": resolved_sources,
                        "feature_bindings": bindings,
                    }
                )

            elif msg_type == "reading":
                ref = message.get("ref")  # id di correlazione lato agent (riga outbox locale), echeggiato nell'ack
                run = await _active_run(station_id)
                if run is None:
                    await websocket.send_json({"type": "ack", "ok": False, "ref": ref, "reason": "no_active_run"})
                    continue

                captured_at = message.get("captured_at")
                captured_dt = (
                    datetime.fromisoformat(captured_at) if captured_at else datetime.now(timezone.utc)
                )
                result = await _persist_reading(run, message["daq_source_id"], message.get("raw_value"), captured_dt)
                if result is None:
                    await websocket.send_json({"type": "ack", "ok": False, "ref": ref, "reason": "unbound_daq_source"})
                    continue

                await websocket.send_json({"type": "ack", "ok": True, "ref": ref, "obs_no": result["obs_no"]})
                await manager.broadcast_to_run(run.id, {"type": "measurement", **result})

            elif msg_type == "heartbeat":
                await websocket.send_json({"type": "heartbeat"})

            elif msg_type == "test_result":
                # risposta a un test_source avviato da POST /api/daq-sources/{id}/test
                request_id = message.get("request_id")
                if request_id:
                    manager.resolve_agent_request(request_id, message)

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect_agent(station_key)
        if _should_notify_disconnect(station_key):
            await notify_background(
                "agent_disconnected",
                subject="[leank-spc] Edge Agent disconnesso",
                body=(
                    f"L'Edge Agent della stazione {station_key} si e' disconnesso.\n"
                    "Se non era previsto (es. non e' un riavvio del backend), verificare la stazione."
                ),
            )
