from typing import Any

from pydantic import BaseModel, ConfigDict


class StationCreate(BaseModel):
    site_id: int
    name: str
    description: str | None = None
    computer_name: str | None = None


class StationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    site_id: int
    name: str
    description: str | None
    computer_name: str | None
    status: str


class DaqDeviceCreate(BaseModel):
    name: str
    description: str | None = None
    connection_type: str  # rs232 | usb_hid | manual | opcua | mtconnect
    terminator: str | None = None
    max_string_length: int | None = None
    config: dict[str, Any] = {}


class DaqDeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    connection_type: str
    config: dict[str, Any]


class DaqSourceCreate(BaseModel):
    station_id: int
    device_id: int
    name: str
    port: str | None = None
    channel_no: int | None = None


class DaqSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    station_id: int
    device_id: int
    name: str
    port: str | None
    channel_no: int | None
    status: str


class FeatureDaqBindingCreate(BaseModel):
    routine_id: int
    feature_id: int
    daq_source_id: int
