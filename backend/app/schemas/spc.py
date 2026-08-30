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


class FeaturePropertyVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    version_no: int
    target: float | None
    lower_tolerance_limit: float | None
    upper_tolerance_limit: float | None
    lower_warning_limit: float | None
    upper_warning_limit: float | None
    subgroup_size: int
    control_method: str | None
    unit_id: int | None
    decimal_length: int
    valid_from: datetime
    valid_to: datetime | None


class FeatureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    part_id: int
    feature_type: str
    name: str
    description: str | None
    order_no: int
    # versione di tolleranze/limiti attiva ora (valid_to IS NULL) - None se la
    # Feature non ne ha ancora nessuna. Popolata a mano dal router (non e' una
    # relationship SQLAlchemy), vedi list_part_features in routers/features.py.
    current_properties: FeaturePropertyVersionOut | None = None


class RunCreate(BaseModel):
    routine_id: int
    station_id: int
    name: str
    work_order_id: int | None = None  # v0.2: commessa collaudata da questo Run
    tool_id: int | None = None  # v0.2: attrezzatura (stampo/fustella/...) in uso


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    routine_id: int
    station_id: int
    name: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    work_order_id: int | None
    tool_id: int | None


class MeasurementCreate(BaseModel):
    feature_id: int
    obs_no: int
    value: float | None
    unit_id: int | None = None
    captured_at: datetime
    source: str = "manual"
    tool_position_id: int | None = None  # v0.2: da quale posizione/cavità viene il campione


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
    tool_position_id: int | None
