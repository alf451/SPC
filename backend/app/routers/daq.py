from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.daq import DaqDevice, DaqSource, FeatureDaqBinding
from app.schemas.daq import (
    DaqDeviceCreate,
    DaqDeviceOut,
    DaqDeviceUpdate,
    DaqSourceCreate,
    DaqSourceOut,
    DaqSourceTestResult,
    DaqSourceUpdate,
    FeatureDaqBindingCreate,
)
from app.security import get_current_user
from app.ws.connection_manager import AgentOfflineError, manager

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


@router.put("/daq-devices/{device_id}", response_model=DaqDeviceOut)
async def update_daq_device(
    device_id: int, payload: DaqDeviceUpdate, session: Annotated[AsyncSession, Depends(get_session)]
) -> DaqDevice:
    device = await session.get(DaqDevice, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispositivo non trovato")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(device, key, value)
    await session.commit()
    await session.refresh(device)
    return device


@router.put("/daq-sources/{source_id}", response_model=DaqSourceOut)
async def update_daq_source(
    source_id: int, payload: DaqSourceUpdate, session: Annotated[AsyncSession, Depends(get_session)]
) -> DaqSource:
    source = await session.get(DaqSource, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sorgente non trovata")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, key, value)
    await session.commit()
    await session.refresh(source)
    return source


@router.delete("/daq-devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_daq_device(device_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> None:
    device = await session.get(DaqDevice, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispositivo non trovato")
    await session.delete(device)
    await session.commit()


@router.delete("/daq-sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_daq_source(source_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> None:
    source = await session.get(DaqSource, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sorgente non trovata")
    await session.delete(source)
    await session.commit()


@router.post("/daq-sources/{source_id}/test", response_model=DaqSourceTestResult)
async def test_daq_source(source_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> DaqSourceTestResult:
    """Prova il collegamento reale a uno strumento — non qualcosa che il backend
    possa fare da solo (la porta seriale è sul PC della stazione, non sul server):
    chiede all'Edge Agent di quella stazione, se connesso, di aprire la porta e
    riportare l'esito. Vedi ConnectionManager.send_agent_request + il gestore
    "test_source" nell'Edge Agent (edge_agent/ws_client.py).
    """
    source = await session.get(DaqSource, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sorgente non trovata")

    try:
        result = await manager.send_agent_request(
            str(source.station_id),
            {"type": "test_source", "port": source.port, "channel_no": source.channel_no},
        )
    except AgentOfflineError as exc:
        return DaqSourceTestResult(ok=False, message=str(exc))
    except TimeoutError:
        return DaqSourceTestResult(ok=False, message="Nessuna risposta dall'Edge Agent entro il timeout (8s)")

    return DaqSourceTestResult(ok=result.get("ok", False), message=result.get("message", ""), sample_raw=result.get("sample_raw"))


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


@router.delete("/feature-daq-bindings", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feature_daq_binding(
    routine_id: int, feature_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> None:
    binding = await session.get(FeatureDaqBinding, {"routine_id": routine_id, "feature_id": feature_id})
    if binding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Binding non trovato")
    await session.delete(binding)
    await session.commit()
