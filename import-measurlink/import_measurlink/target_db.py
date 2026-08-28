"""Connessione (sincrona, psycopg2) al Postgres di leank-spc.

Riusa le classi ORM già definite in backend/app/models (niente doppia
definizione dello schema): i modelli SQLAlchemy non sono legati al motore
async/sync, solo la Session lo è, quindi possono essere condivisi tra backend
(asyncpg, async) e questo tool (psycopg2, sincrono).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# backend/ deve essere su sys.path perché "app.models" sia importabile — questo
# tool vive a fianco di backend/, non dentro, quindi va aggiunto esplicitamente
# (stesso motivo/stessa soluzione di backend/create_admin.py con l'embeddable python).
_BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.models.core import Site, Station, Unit  # noqa: E402
from app.models.daq import DaqDevice, DaqSource  # noqa: E402
from app.models.gage import Calibration, Gage  # noqa: E402
from app.models.spc import (  # noqa: E402
    AttributeObservation,
    Feature,
    FeaturePropertyVersion,
    Measurement,
    Part,
    PartFolder,
    PartPropertyVersion,
    Routine,
    RoutineFeature,
    RoutineFolder,
    Run,
)

__all__ = [
    "Site", "Station", "Unit", "DaqDevice", "DaqSource", "Calibration", "Gage",
    "AttributeObservation", "Feature", "FeaturePropertyVersion", "Measurement",
    "Part", "PartFolder", "PartPropertyVersion", "Routine", "RoutineFeature",
    "RoutineFolder", "Run", "TargetConnectionConfig", "make_session",
]


@dataclass
class TargetConnectionConfig:
    host: str
    port: int
    database: str
    username: str
    password: str

    @property
    def url(self) -> str:
        return f"postgresql+psycopg2://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


def make_session(cfg: TargetConnectionConfig) -> Session:
    engine = create_engine(cfg.url)
    return sessionmaker(bind=engine)()
