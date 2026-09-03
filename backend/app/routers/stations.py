from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.core import Site, Station
from app.reference_check import check_not_referenced
from app.schemas.daq import (
    AvailablePortsOut,
    SiteCreate,
    SiteOut,
    SiteUpdate,
    StationCreate,
    StationOut,
    StationUpdate,
)
from app.security import get_current_user
from app.ws.connection_manager import manager

sites_router = APIRouter(prefix="/api/sites", tags=["stations"], dependencies=[Depends(get_current_user)])


@sites_router.get("", response_model=list[SiteOut])
async def list_sites(session: Annotated[AsyncSession, Depends(get_session)]) -> list[Site]:
    result = await session.execute(select(Site).order_by(Site.name))
    return list(result.scalars())


@sites_router.post("", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
async def create_site(payload: SiteCreate, session: Annotated[AsyncSession, Depends(get_session)]) -> Site:
    site = Site(**payload.model_dump())
    session.add(site)
    await session.commit()
    await session.refresh(site)
    return site


@sites_router.put("/{site_id}", response_model=SiteOut)
async def update_site(site_id: int, payload: SiteUpdate, session: Annotated[AsyncSession, Depends(get_session)]) -> Site:
    site = await session.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sede non trovata")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(site, key, value)
    await session.commit()
    await session.refresh(site)
    return site


@sites_router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site(site_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> None:
    site = await session.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sede non trovata")
    await check_not_referenced(session, "sites", "id", site_id)
    await session.delete(site)
    await session.commit()


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


@router.put("/{station_id}", response_model=StationOut)
async def update_station(
    station_id: int, payload: StationUpdate, session: Annotated[AsyncSession, Depends(get_session)]
) -> Station:
    station = await session.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stazione non trovata")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(station, key, value)
    await session.commit()
    await session.refresh(station)
    return station


@router.delete("/{station_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_station(station_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> None:
    station = await session.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stazione non trovata")
    await check_not_referenced(session, "stations", "id", station_id)
    await session.delete(station)
    await session.commit()


@router.get("/{station_id}/available-ports", response_model=AvailablePortsOut)
async def get_available_ports(station_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> AvailablePortsOut:
    """Porte seriali fisicamente presenti sulla stazione, riportate dall'Edge
    Agent connesso ad essa nel messaggio "hello" (vedi ws/agent_hub.py e
    edge-agent/edge_agent/port_scan.py) - permette di configurare una sorgente
    DAQ scegliendo tra le porte davvero disponibili invece di scriverle a mano,
    senza dover accedere via RDP alla stazione per controllare Gestione
    dispositivi. Richiede che l'Edge Agent di quella stazione sia connesso
    (altrimenti "agent_connected": false, "ports": null - nessun dato,
    non un errore: e' una situazione normale se l'agent non e' ancora avviato).
    """
    station = await session.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stazione non trovata")
    station_key = str(station_id)
    agent_connected = manager.get_agent(station_key) is not None
    ports = manager.get_available_ports(station_key)
    return AvailablePortsOut(agent_connected=agent_connected, ports=ports)
