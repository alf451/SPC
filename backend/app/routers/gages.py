from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.gage import Gage
from app.schemas.gage import GageCreate, GageOut
from app.security import get_current_user

router = APIRouter(prefix="/api/gages", tags=["gages"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[GageOut])
async def list_gages(
    session: Annotated[AsyncSession, Depends(get_session)],
    folder_id: int | None = None,
    status_filter: str | None = None,
) -> list[Gage]:
    query = select(Gage)
    if folder_id is not None:
        query = query.where(Gage.folder_id == folder_id)
    if status_filter is not None:
        query = query.where(Gage.status == status_filter)
    result = await session.execute(query.order_by(Gage.name))
    return list(result.scalars())


@router.post("", response_model=GageOut, status_code=status.HTTP_201_CREATED)
async def create_gage(payload: GageCreate, session: Annotated[AsyncSession, Depends(get_session)]) -> Gage:
    gage = Gage(**payload.model_dump())
    session.add(gage)
    await session.commit()
    await session.refresh(gage)
    return gage


@router.get("/{gage_id}", response_model=GageOut)
async def get_gage(gage_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> Gage:
    gage = await session.get(Gage, gage_id)
    if gage is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gage non trovato")
    return gage
