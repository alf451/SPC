from datetime import datetime

from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AuditLog(Base):
    """Log generico di modifiche — sostituisce le ~50 tabelle Audit_* di MeasurLink.

    Popolato da un'unica funzione trigger riusabile applicata alle tabelle
    di dominio che richiedono storicizzazione (vedi migration 0001).
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_table_row", "table_name", "row_pk"),
        Index("ix_audit_log_changed_at", "changed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    table_name: Mapped[str]
    row_pk: Mapped[str]
    action: Mapped[str]  # insert | update | delete
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(server_default="now()")
    diff: Mapped[dict | None] = mapped_column(JSONB)
