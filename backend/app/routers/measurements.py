from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.spc import Measurement
from app.schemas.spc import MeasurementCreate, MeasurementOut
from app.security import get_current_user
from app.ws.connection_manager import manager

router = APIRouter(prefix="/api/runs/{run_id}/measurements", tags=["measurements"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[MeasurementOut])
async def list_measurements(
    run_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    feature_id: int | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[Measurement]:
    query = select(Measurement).where(Measurement.run_id == run_id)
    if feature_id is not None:
        query = query.where(Measurement.feature_id == feature_id)
    query = query.order_by(Measurement.obs_no).limit(limit).offset(offset)
    result = await session.execute(query)
    return list(result.scalars())


@router.post("", response_model=MeasurementOut, status_code=status.HTTP_201_CREATED)
async def create_measurement(
    run_id: int,
    payload: MeasurementCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Measurement:
    """Inserimento manuale di una misura (es. operatore senza DAQ collegato).

    Le misure acquisite da strumento arrivano invece dall'Edge Agent via
    WebSocket (/ws/agent/{station_id}) e vengono scritte da app/ws/agent_hub.py,
    non da questa route REST.
    """
    measurement = Measurement(run_id=run_id, **payload.model_dump())
    session.add(measurement)
    await session.commit()
    await session.refresh(measurement)

    # Stesso evento pubblicato da agent_hub.py per le letture da Edge Agent
    # (vedi docs/api.md) - senza questo, un inserimento manuale non compare in
    # tempo reale nella dashboard/frontend, solo dopo un refresh (bug
    # riscontrato dal vivo collaudando la vista "Raccolta Dati" del frontend).
    await manager.broadcast_to_run(
        run_id,
        {
            "type": "measurement",
            "feature_id": measurement.feature_id,
            "obs_no": measurement.obs_no,
            "value": measurement.value,
            "captured_at": measurement.captured_at.isoformat(),
        },
    )
    return measurement
