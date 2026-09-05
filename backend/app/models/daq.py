from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DaqDevice(Base):
    """Profilo dispositivo — generalizza Device + RS232DeviceParam + USBKeyboardParam di MeasurLink.

    I parametri specifici per tipo di connessione vivono in `config` (jsonb) invece
    di una tabella per sottotipo, perché non servono query relazionali su quei campi:
      rs232:   {"baud_rate":9600,"data_bits":7,"parity":"E","stop_bits":1,
                "mode":"push"|"polled","channels":[{"no":1,"tag":"CH1"}],
                "commands":[{"name":"request","value":"R"}]}
      usb_hid: {"poll_interval_ms":50,"vendor_id":"...","product_id":"..."}
    """

    __tablename__ = "daq_devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[str | None]
    connection_type: Mapped[str]  # rs232 | usb_hid | manual | opcua | mtconnect
    terminator: Mapped[str | None]
    max_string_length: Mapped[int | None]
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default="now()")


class DaqSource(Base):
    """Porta/canale fisico su una stazione — equivalente DAQPortSource + RS232DeviceChannel."""

    __tablename__ = "daq_sources"
    __table_args__ = (UniqueConstraint("station_id", "port", "channel_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"))
    device_id: Mapped[int] = mapped_column(ForeignKey("daq_devices.id"))
    name: Mapped[str]
    port: Mapped[str | None]  # es. "COM3" o path HID
    channel_no: Mapped[int | None]  # canale su box multiplexato
    status: Mapped[str] = mapped_column(default="active")


class RunDaqClaim(Base):
    """Quale Run possiede in questo momento una sorgente DAQ (strumento) -
    necessario perché più Run possono essere attive in parallelo sulla
    stessa stazione (es. due strumenti, due commesse diverse): senza questo,
    una lettura in arrivo non saprebbe a quale delle Run attive appartenere.

    Un `released_at IS NULL` = claim ancora attivo (vincolo di unicità a
    livello di indice, vedi migration 0005). Creato automaticamente
    all'avvio di una Run per le sorgenti già libere e legate alla sua
    Routine (vedi routers/runs.py::create_run); rilasciato al completamento
    della Run, o manualmente se serve riassegnare uno strumento prima.
    """

    __tablename__ = "run_daq_claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    daq_source_id: Mapped[int] = mapped_column(ForeignKey("daq_sources.id", ondelete="CASCADE"))
    claimed_at: Mapped[datetime] = mapped_column(server_default="now()")
    released_at: Mapped[datetime | None]


class FeatureDaqBinding(Base):
    """Quale sorgente DAQ alimenta quale Feature per una Routine — equivalente FeatureRun.DAQSourceID."""

    __tablename__ = "feature_daq_bindings"

    routine_id: Mapped[int] = mapped_column(ForeignKey("routines.id", ondelete="CASCADE"), primary_key=True)
    feature_id: Mapped[int] = mapped_column(ForeignKey("features.id", ondelete="CASCADE"), primary_key=True)
    daq_source_id: Mapped[int] = mapped_column(ForeignKey("daq_sources.id", ondelete="CASCADE"))
