from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ToolPositionCreate(BaseModel):
    position_no: int
    label: str | None = None
    notes: str | None = None


class ToolPositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tool_id: int
    position_no: int
    label: str | None
    notes: str | None


class ToolCreate(BaseModel):
    name: str
    tool_type: str = "other"  # mold | die | other
    position_count: int = 1
    description: str | None = None
    positions: list[ToolPositionCreate] = []
    """Se omesso, vengono create automaticamente `position_count` posizioni numerate 1..N."""


class ToolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    tool_type: str
    position_count: int
    description: str | None


class WorkOrderCreate(BaseModel):
    """Payload che un ERP qualsiasi invia per creare/aggiornare una commessa.

    Idempotente su (external_system, external_id): un secondo POST con la
    stessa coppia aggiorna la commessa esistente invece di duplicarla — utile
    perché un ERP può rimandare lo stesso evento più volte (retry, sync periodica).
    """

    order_number: str
    part_id: int | None = None
    customer: str | None = None
    quantity_ordered: int | None = None
    external_system: str | None = None
    external_id: str | None = None


class WorkOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_number: str
    part_id: int | None
    customer: str | None
    quantity_ordered: int | None
    status: str
    external_system: str | None
    external_id: str | None
    created_at: datetime
