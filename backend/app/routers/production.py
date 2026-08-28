from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.production import Tool, ToolPosition, WorkOrder
from app.schemas.production import (
    ToolCreate,
    ToolOut,
    ToolPositionOut,
    WorkOrderCreate,
    WorkOrderOut,
)
from app.security import get_current_user

router = APIRouter(prefix="/api", tags=["production"], dependencies=[Depends(get_current_user)])


# --------------------------------------------------------------------------- tools
@router.get("/tools", response_model=list[ToolOut])
async def list_tools(session: Annotated[AsyncSession, Depends(get_session)]) -> list[Tool]:
    result = await session.execute(select(Tool).order_by(Tool.name))
    return list(result.scalars())


@router.post("/tools", response_model=ToolOut, status_code=status.HTTP_201_CREATED)
async def create_tool(payload: ToolCreate, session: Annotated[AsyncSession, Depends(get_session)]) -> Tool:
    tool = Tool(
        name=payload.name,
        tool_type=payload.tool_type,
        position_count=payload.position_count,
        description=payload.description,
    )
    session.add(tool)
    await session.flush()

    # se non sono state passate posizioni esplicite, ne creo position_count numerate 1..N
    positions = payload.positions or [
        {"position_no": n, "label": None, "notes": None} for n in range(1, payload.position_count + 1)
    ]
    for pos in positions:
        pos_kwargs = pos if isinstance(pos, dict) else pos.model_dump()
        session.add(ToolPosition(tool_id=tool.id, **pos_kwargs))

    await session.commit()
    await session.refresh(tool)
    return tool


@router.get("/tools/{tool_id}", response_model=ToolOut)
async def get_tool(tool_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> Tool:
    tool = await session.get(Tool, tool_id)
    if tool is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attrezzatura non trovata")
    return tool


@router.get("/tools/{tool_id}/positions", response_model=list[ToolPositionOut])
async def list_tool_positions(
    tool_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> list[ToolPosition]:
    result = await session.execute(
        select(ToolPosition).where(ToolPosition.tool_id == tool_id).order_by(ToolPosition.position_no)
    )
    return list(result.scalars())


@router.delete("/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(tool_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> None:
    tool = await session.get(Tool, tool_id)
    if tool is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attrezzatura non trovata")
    await session.delete(tool)  # ON DELETE CASCADE rimuove anche le tool_positions
    await session.commit()


# --------------------------------------------------------------------------- work orders (commesse)
@router.get("/work-orders", response_model=list[WorkOrderOut])
async def list_work_orders(
    session: Annotated[AsyncSession, Depends(get_session)],
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[WorkOrder]:
    query = select(WorkOrder)
    if status_filter is not None:
        query = query.where(WorkOrder.status == status_filter)
    query = query.order_by(WorkOrder.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    return list(result.scalars())


@router.post("/work-orders", response_model=WorkOrderOut, status_code=status.HTTP_201_CREATED)
async def upsert_work_order(
    payload: WorkOrderCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> WorkOrder:
    """Endpoint pensato per essere chiamato da un ERP qualsiasi.

    Idempotente su (external_system, external_id) quando entrambi sono valorizzati:
    un secondo invio della stessa commessa aggiorna invece di duplicare — un ERP
    può reinviare lo stesso evento (retry, sincronizzazione periodica) senza rischio.
    """
    existing: WorkOrder | None = None
    if payload.external_system and payload.external_id:
        result = await session.execute(
            select(WorkOrder).where(
                WorkOrder.external_system == payload.external_system,
                WorkOrder.external_id == payload.external_id,
            )
        )
        existing = result.scalar_one_or_none()

    if existing is not None:
        for field, value in payload.model_dump().items():
            setattr(existing, field, value)
        work_order = existing
    else:
        work_order = WorkOrder(**payload.model_dump())
        session.add(work_order)

    await session.commit()
    await session.refresh(work_order)
    return work_order


@router.get("/work-orders/{work_order_id}", response_model=WorkOrderOut)
async def get_work_order(work_order_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> WorkOrder:
    work_order = await session.get(WorkOrder, work_order_id)
    if work_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commessa non trovata")
    return work_order
