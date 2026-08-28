"""Pannello admin: import da MeasurLink (SQL Server) verso leank-spc.

Il tool vero e proprio vive in `import-measurlink/` (progetto Python separato,
vedi il README lì dentro per il perché) — questo router lo invoca in-process
per esporlo al pannello web: test connessione, avvio import (con opzione
"prova"/dry-run che non scrive nulla), e un monitor di avanzamento che il
frontend interroga mentre l'import gira in background.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.engine import make_url

from app.config import settings
from app.security import get_current_user

# import-measurlink/ vive a fianco di backend/, non dentro: va aggiunto a
# sys.path esplicitamente (stesso motivo/soluzione di create_admin.py e
# target_db.py per l'inverso).
_IMPORT_TOOL_DIR = Path(__file__).resolve().parents[3] / "import-measurlink"
if str(_IMPORT_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_IMPORT_TOOL_DIR))

from import_measurlink import source_db as ml_source_db  # noqa: E402
from import_measurlink import target_db as ml_target_db  # noqa: E402
from import_measurlink.cli import run_import  # noqa: E402

router = APIRouter(prefix="/api/admin/measurlink-import", tags=["admin"], dependencies=[Depends(get_current_user)])


class SqlServerConnectionParams(BaseModel):
    driver: str = "{ODBC Driver 17 for SQL Server}"
    server: str
    database: str = "MeasurLink9"
    username: str
    password: str
    gage_database: str | None = "MeasurLink9_GAGE"


class TestConnectionResult(BaseModel):
    ok: bool
    message: str
    counts: dict[str, int] | None = None


class RunImportRequest(SqlServerConnectionParams):
    since_months: int = 3
    only_config: bool = False
    dry_run: bool = False


class ImportJobOut(BaseModel):
    job_id: str
    status: str  # pending | running | completed | failed
    log: list[str]
    summary: dict | None
    error: str | None
    started_at: datetime
    finished_at: datetime | None


class _ImportJob:
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        self.status = "pending"
        self.log: list[str] = []
        self.summary: dict | None = None
        self.error: str | None = None
        self.started_at = datetime.now(timezone.utc)
        self.finished_at: datetime | None = None

    def to_out(self) -> ImportJobOut:
        return ImportJobOut(
            job_id=self.job_id, status=self.status, log=self.log, summary=self.summary,
            error=self.error, started_at=self.started_at, finished_at=self.finished_at,
        )


# Registro job in memoria: sufficiente per un singolo worker Uvicorn (stesso
# limite/stessa nota di app/ws/connection_manager.py::ConnectionManager) — un
# import è un'operazione occasionale lanciata da un operatore, non ha bisogno
# di sopravvivere a un riavvio del processo.
_jobs: dict[str, _ImportJob] = {}


def _target_config_from_settings() -> ml_target_db.TargetConnectionConfig:
    """Il target Postgres è sempre il database già configurato per questo backend
    (backend/.env) — l'admin non deve reinserire credenziali che ha già messo lì."""
    url = make_url(settings.database_url)
    return ml_target_db.TargetConnectionConfig(
        host=url.host, port=url.port or 5432, database=url.database,
        username=url.username, password=url.password,
    )


@router.post("/test-connection", response_model=TestConnectionResult)
async def test_connection(payload: SqlServerConnectionParams) -> TestConnectionResult:
    cfg = ml_source_db.SourceConnectionConfig(
        driver=payload.driver, server=payload.server, database=payload.database,
        username=payload.username, password=payload.password,
    )
    try:
        result = await asyncio.to_thread(ml_source_db.test_connection, cfg)
        return TestConnectionResult(ok=True, message="Connessione riuscita", counts=result["counts"])
    except Exception as exc:  # noqa: BLE001 - vogliamo mostrare qualunque errore di connessione all'utente
        return TestConnectionResult(ok=False, message=str(exc))


def _run_job(job: _ImportJob, payload: RunImportRequest) -> None:
    job.status = "running"

    def progress(message: str) -> None:
        job.log.append(message)

    try:
        source_cfg = ml_source_db.SourceConnectionConfig(
            driver=payload.driver, server=payload.server, database=payload.database,
            username=payload.username, password=payload.password,
        )
        target_cfg = _target_config_from_settings()
        job.summary = run_import(
            source_cfg, target_cfg,
            since_months=payload.since_months,
            only_config=payload.only_config,
            dry_run=payload.dry_run,
            gage_database=payload.gage_database,
            progress=progress,
        )
        job.status = "completed"
    except Exception as exc:  # noqa: BLE001 - un job fallito deve riportare l'errore al monitor, non far cadere il worker
        job.error = str(exc)
        job.status = "failed"
        progress(f"ERRORE: {exc}")
    finally:
        job.finished_at = datetime.now(timezone.utc)


@router.post("/run", response_model=ImportJobOut, status_code=status.HTTP_202_ACCEPTED)
async def start_import(payload: RunImportRequest) -> ImportJobOut:
    job_id = str(uuid.uuid4())
    job = _ImportJob(job_id)
    _jobs[job_id] = job

    async def runner() -> None:
        await asyncio.to_thread(_run_job, job, payload)

    asyncio.create_task(runner())
    return job.to_out()


@router.get("/jobs/{job_id}", response_model=ImportJobOut)
async def get_job(job_id: str) -> ImportJobOut:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job non trovato")
    return job.to_out()


@router.get("/jobs", response_model=list[ImportJobOut])
async def list_jobs() -> list[ImportJobOut]:
    return [job.to_out() for job in sorted(_jobs.values(), key=lambda j: j.started_at, reverse=True)]
