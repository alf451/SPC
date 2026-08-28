from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GageCreate(BaseModel):
    folder_id: int | None = None
    name: str
    classification: str | None = None
    model: str | None = None
    serial_number: str | None = None
    unit_id: int | None = None


class GageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    folder_id: int | None
    name: str
    classification: str | None
    model: str | None
    serial_number: str | None
    status: str


class CalibrationCreate(BaseModel):
    gage_id: int
    procedure_id: int | None = None


class CalibrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    gage_id: int
    procedure_id: int | None
    status: str
    started_at: datetime
    completed_at: datetime | None


class CalibrationResultCreate(BaseModel):
    point_no: int
    nominal: float | None = None
    found: float | None = None
    adjusted: float | None = None


class CalibrationCertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    calibration_id: int
    certificate_no: str
    issued_at: datetime
