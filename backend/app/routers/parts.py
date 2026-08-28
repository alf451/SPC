from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.spc import Part, PartFolder
from app.schemas.spc import PartCreate, PartFolderOut, PartOut
from app.security import get_current_user

router = APIRouter(prefix="/api", tags=["parts"], dependencies=[Depends(get_current_user)])


@router.get("/part-folders", response_model=list[PartFolderOut])
async def list_part_folders(session: Annotated[AsyncSession, Depends(get_session)]) -> list[PartFolder]:
    result = await session.execute(select(PartFolder).order_by(PartFolder.name))
    return list(result.scalars())


@router.get("/parts", response_model=list[PartOut])
async def list_parts(
    session: Annotated[AsyncSession, Depends(get_session)],
    folder_id: int | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Part]:
    query = select(Part)
    if folder_id is not None:
        query = query.where(Part.folder_id == folder_id)
    if search:
        query = query.where(Part.name.ilike(f"%{search}%"))
    query = query.order_by(Part.name).limit(limit).offset(offset)
    result = await session.execute(query)
    return list(result.scalars())


@router.post("/parts", response_model=PartOut, status_code=status.HTTP_201_CREATED)
async def create_part(
    payload: PartCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Part:
    part = Part(**payload.model_dump())
    session.add(part)
    await session.commit()
    await session.refresh(part)
    return part


@router.get("/parts/{part_id}", response_model=PartOut)
async def get_part(part_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> Part:
    part = await session.get(Part, part_id)
    if part is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part non trovato")
    return part
