from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.daq import DaqDevice, DaqSource, FeatureDaqBinding
from app.schemas.daq import (
    DaqDeviceCreate,
    DaqDeviceOut,
    DaqSourceCreate,
    DaqSourceOut,
    FeatureDaqBindingCreate,
)
from app.security import get_current_user

router = APIRouter(prefix="/api", tags=["daq"], dependencies=[Depends(get_current_user)])


@router.get("/daq-devices", response_model=list[DaqDeviceOut])
async def list_daq_devices(session: Annotated[AsyncSession, Depends(get_session)]) -> list[DaqDevice]:
    result = await session.execute(select(DaqDevice).order_by(DaqDevice.name))
    return list(result.scalars())


@router.post("/daq-devices", response_model=DaqDeviceOut, status_code=status.HTTP_201_CREATED)
async def create_daq_device(
    payload: DaqDeviceCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> DaqDevice:
    device = DaqDevice(**payload.model_dump())
    session.add(device)
    await session.commit()
    await session.refresh(device)
    return device


@router.get("/daq-sources", response_model=list[DaqSourceOut])
async def list_daq_sources(
    session: Annotated[AsyncSession, Depends(get_session)], station_id: int | None = None
) -> list[DaqSource]:
    query = select(DaqSource)
    if station_id is not None:
        query = query.where(DaqSource.station_id == station_id)
    result = await session.execute(query.order_by(DaqSource.name))
    return list(result.scalars())


@router.post("/daq-sources", response_model=DaqSourceOut, status_code=status.HTTP_201_CREATED)
async def create_daq_source(
    payload: DaqSourceCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> DaqSource:
    source = DaqSource(**payload.model_dump())
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


@router.put("/feature-daq-bindings", status_code=status.HTTP_204_NO_CONTENT)
async def upsert_feature_daq_binding(
    payload: FeatureDaqBindingCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> None:
    """Collega una Feature (nell'ambito di una Routine) a una porta/canale fisico.

    È questo binding che l'Edge Agent riceve nel messaggio "config" per sapere
    a quale Feature appartiene ogni lettura che invia.
    """
    key = {"routine_id": payload.routine_id, "feature_id": payload.feature_id}
    binding = await session.get(FeatureDaqBinding, key)
    if binding is None:
        session.add(FeatureDaqBinding(**payload.model_dump()))
    else:
        binding.daq_source_id = payload.daq_source_id
    await session.commit()
