from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.core import User
from app.models.spc import Run
from app.schemas.spc import RunCreate, RunOut
from app.security import get_current_user

router = APIRouter(prefix="/api/runs", tags=["runs"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[RunOut])
async def list_runs(
    session: Annotated[AsyncSession, Depends(get_session)],
    station_id: int | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Run]:
    query = select(Run)
    if station_id is not None:
        query = query.where(Run.station_id == station_id)
    if status_filter is not None:
        query = query.where(Run.status == status_filter)
    query = query.order_by(Run.started_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    return list(result.scalars())


@router.post("", response_model=RunOut, status_code=status.HTTP_201_CREATED)
async def create_run(
    payload: RunCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Run:
    run = Run(**payload.model_dump(), started_by=current_user.id)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    # TODO: notificare la stazione via /ws/agent che un nuovo Run è attivo,
    # così l'Edge Agent riceve i feature_daq_bindings correnti nel messaggio "config".
    return run


@router.get("/{run_id}", response_model=RunOut)
async def get_run(run_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> Run:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run non trovato")
    return run


@router.post("/{run_id}/complete", response_model=RunOut)
async def complete_run(run_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> Run:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run non trovato")
    run.status = "completed"
    run.ended_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(run)
    return run
