from typing import Any

from pydantic import BaseModel, ConfigDict


class SiteCreate(BaseModel):
    name: str


class SiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class SiteUpdate(BaseModel):
    name: str | None = None


class StationCreate(BaseModel):
    site_id: int
    name: str
    description: str | None = None
    computer_name: str | None = None


class StationUpdate(BaseModel):
    # Tutti i campi opzionali: solo quelli davvero presenti nel payload (vedi
    # model_dump(exclude_unset=True) nel router) vengono applicati - un PUT
    # parziale non azzera gli altri campi non menzionati.
    site_id: int | None = None
    name: str | None = None
    description: str | None = None
    computer_name: str | None = None
    status: str | None = None


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


class DaqDeviceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    connection_type: str | None = None
    terminator: str | None = None
    max_string_length: int | None = None
    config: dict[str, Any] | None = None


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


class DaqSourceUpdate(BaseModel):
    station_id: int | None = None
    device_id: int | None = None
    name: str | None = None
    port: str | None = None
    channel_no: int | None = None
    status: str | None = None


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


class DaqSourceTestResult(BaseModel):
    ok: bool
    message: str
    sample_raw: str | None = None


class AvailablePortOut(BaseModel):
    device: str
    description: str
    hwid: str


class AvailablePortsOut(BaseModel):
    agent_connected: bool
    # None = l'agent non ha ancora mandato nessun "hello" da quando si e'
    # connesso (dato non disponibile); lista vuota = ha risposto ma non vede
    # nessuna porta seriale in questo momento - due situazioni diverse.
    ports: list[AvailablePortOut] | None
