"""Integrazione ERP: commesse e attrezzature (stampi/fustelle/...).

Concetti generici per non legarsi a un solo settore:
  - Tool ("attrezzatura"): qualunque cosa produca pezzi in un "evento" produttivo
    (stampo a iniezione, fustella, stampo di pressofusione, ...). `position_count`
    dice quanti articoli produce ogni evento (es. uno stampo a 4 cavità).
  - ToolPosition ("posizione"/cavità): una delle N posizioni di un Tool — permette
    di sapere da quale cavità viene il singolo campione misurato.
  - WorkOrder ("commessa"): l'unità di lavoro che un ERP qualsiasi comunica a
    leank-spc (prodotto, quantità, cliente) — `external_system`/`external_id`
    tracciano da dove viene, per restare integrabili con qualunque ERP.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Tool(Base):
    __tablename__ = "tools"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    tool_type: Mapped[str] = mapped_column(default="other")  # mold | die | other ("stampo"/"fustella"/"altro")
    position_count: Mapped[int] = mapped_column(default=1)
    description: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default="now()")


class ToolPosition(Base):
    """Una posizione/cavità di un Tool (es. "Cavità 3" di uno stampo a 4 impronte)."""

    __tablename__ = "tool_positions"
    __table_args__ = (UniqueConstraint("tool_id", "position_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tool_id: Mapped[int] = mapped_column(ForeignKey("tools.id", ondelete="CASCADE"))
    position_no: Mapped[int]
    label: Mapped[str | None]
    notes: Mapped[str | None]


class WorkOrder(Base):
    """Commessa — creata di norma da un ERP esterno via POST /api/work-orders."""

    __tablename__ = "work_orders"
    __table_args__ = (UniqueConstraint("external_system", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_number: Mapped[str] = mapped_column(unique=True)  # "commessa"
    part_id: Mapped[int | None] = mapped_column(ForeignKey("parts.id"))
    customer: Mapped[str | None]
    quantity_ordered: Mapped[int | None]
    status: Mapped[str] = mapped_column(default="open")  # open | in_progress | closed
    external_system: Mapped[str | None]  # es. "SAP", "Zucchetti", nome dell'ERP di origine
    external_id: Mapped[str | None]  # id nell'anagrafica dell'ERP, per idempotenza sull'import
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
