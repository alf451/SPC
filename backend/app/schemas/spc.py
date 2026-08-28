from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PartFolderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    parent_id: int | None
    name: str


class PartCreate(BaseModel):
    folder_id: int | None = None
    name: str
    description: str | None = None


class PartOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    folder_id: int | None
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class RoutineCreate(BaseModel):
    folder_id: int | None = None
    name: str


class RoutineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    folder_id: int | None
    name: str
    created_at: datetime


class FeaturePropertiesIn(BaseModel):
    """Payload per creare una nuova versione di proprietà — mai un update in-place."""

    target: float | None = None
    lower_tolerance_limit: float | None = None
    upper_tolerance_limit: float | None = None
    lower_warning_limit: float | None = None
    upper_warning_limit: float | None = None
    subgroup_size: int = 1
    control_method: str | None = None
    unit_id: int | None = None
    decimal_length: int = 3


class FeatureCreate(BaseModel):
    part_id: int
    feature_type: str  # "variable" | "attribute"
    name: str
    description: str | None = None
    order_no: int = 0
    properties: FeaturePropertiesIn | None = None


class FeatureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    part_id: int
    feature_type: str
    name: str
    description: str | None
    order_no: int


class RunCreate(BaseModel):
    routine_id: int
    station_id: int
    name: str


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    routine_id: int
    station_id: int
    name: str
    status: str
    started_at: datetime
    ended_at: datetime | None


class MeasurementCreate(BaseModel):
    feature_id: int
    obs_no: int
    value: float | None
    unit_id: int | None = None
    captured_at: datetime
    source: str = "manual"


class MeasurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    run_id: int
    feature_id: int
    obs_no: int
    value: float | None
    unit_id: int | None
    flags: int
    captured_at: datetime
    source: str
