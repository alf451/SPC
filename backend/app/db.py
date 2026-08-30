from collections.abc import AsyncIterator
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    # Ogni "Mapped[datetime]" nei modelli, senza questa mappatura, verrebbe
    # legato come TIMESTAMP WITHOUT TIME ZONE lato SQLAlchemy/asyncpg anche se
    # la colonna Postgres reale e' "timestamptz" (docs/schema.sql dichiara
    # "timestamptz sempre" come convenzione) - il mismatch si manifesta solo
    # quando si passa un valore Python timezone-aware come parametro
    # (es. da un payload API con "Z"/offset), con asyncpg.exceptions.DataError
    # "can't subtract offset-naive and offset-aware datetimes" (riscontrato dal
    # vivo su POST /api/runs/{id}/measurements con "captured_at" da un client
    # reale). Questa mappatura vale per l'intero Base, non serve ripeterla
    # colonna per colonna.
    type_annotation_map = {datetime: DateTime(timezone=True)}


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
