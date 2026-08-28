from datetime import datetime

from sqlalchemy import ForeignKey, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class GageFolder(Base):
    __tablename__ = "gage_folders"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("gage_folders.id"))
    name: Mapped[str]


class Gage(Base):
    __tablename__ = "gages"

    id: Mapped[int] = mapped_column(primary_key=True)
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("gage_folders.id"))
    name: Mapped[str]
    classification: Mapped[str | None]
    model: Mapped[str | None]
    serial_number: Mapped[str | None]
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))
    custodian_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(default="in_service")  # in_service | out_of_service | retired
    created_at: Mapped[datetime] = mapped_column(server_default="now()")


class GageStationActive(Base):
    """Strumento fisico attualmente collegato/attivo su una stazione — equivalente GageActive."""

    __tablename__ = "gage_station_active"

    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"), primary_key=True)
    gage_id: Mapped[int] = mapped_column(ForeignKey("gages.id", ondelete="CASCADE"), primary_key=True)
    activated_at: Mapped[datetime] = mapped_column(server_default="now()")


class GageTrackingLog(Base):
    """Ledger movimenti/attività strumento — equivalente GageTracking. Tabella partizionata."""

    __tablename__ = "gage_tracking_log"
    __table_args__ = (PrimaryKeyConstraint("id", "occurred_at"),)

    id: Mapped[int] = mapped_column(autoincrement=True)
    gage_id: Mapped[int] = mapped_column(ForeignKey("gages.id"))
    activity: Mapped[str]
    location_id: Mapped[int | None]
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    occurred_at: Mapped[datetime] = mapped_column(server_default="now()")


class CalibrationProcedure(Base):
    __tablename__ = "calibration_procedures"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    classification: Mapped[str | None]
    definition: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")


class Calibration(Base):
    __tablename__ = "calibrations"

    id: Mapped[int] = mapped_column(primary_key=True)
    gage_id: Mapped[int] = mapped_column(ForeignKey("gages.id"))
    procedure_id: Mapped[int | None] = mapped_column(ForeignKey("calibration_procedures.id"))
    status: Mapped[str] = mapped_column(default="in_progress")  # in_progress | passed | failed
    started_at: Mapped[datetime] = mapped_column(server_default="now()")
    completed_at: Mapped[datetime | None]
    performed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class CalibrationResult(Base):
    __tablename__ = "calibration_results"
    __table_args__ = (UniqueConstraint("calibration_id", "point_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    calibration_id: Mapped[int] = mapped_column(ForeignKey("calibrations.id", ondelete="CASCADE"))
    point_no: Mapped[int]
    nominal: Mapped[float | None]
    found: Mapped[float | None]
    adjusted: Mapped[float | None]


class CalibrationCertificate(Base):
    __tablename__ = "calibration_certificates"

    id: Mapped[int] = mapped_column(primary_key=True)
    calibration_id: Mapped[int] = mapped_column(ForeignKey("calibrations.id", ondelete="CASCADE"))
    certificate_no: Mapped[str] = mapped_column(unique=True)
    issued_at: Mapped[datetime] = mapped_column(server_default="now()")
    html_body: Mapped[str | None]  # generato a partire dal template certificato_taratura.html
