from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.core import Station
from app.schemas.daq import StationCreate, StationOut
from app.security import get_current_user

router = APIRouter(prefix="/api/stations", tags=["stations"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[StationOut])
async def list_stations(
    session: Annotated[AsyncSession, Depends(get_session)], site_id: int | None = None
) -> list[Station]:
    query = select(Station)
    if site_id is not None:
        query = query.where(Station.site_id == site_id)
    result = await session.execute(query.order_by(Station.name))
    return list(result.scalars())


@router.post("", response_model=StationOut, status_code=status.HTTP_201_CREATED)
async def create_station(payload: StationCreate, session: Annotated[AsyncSession, Depends(get_session)]) -> Station:
    station = Station(**payload.model_dump())
    session.add(station)
    await session.commit()
    await session.refresh(station)
    return station


@router.get("/{station_id}", response_model=StationOut)
async def get_station(station_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> Station:
    station = await session.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stazione non trovata")
    return station
