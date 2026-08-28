from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.core import User
from app.models.gage import Calibration, CalibrationCertificate, CalibrationResult
from app.schemas.gage import (
    CalibrationCertificateOut,
    CalibrationCreate,
    CalibrationOut,
    CalibrationResultCreate,
)
from app.security import get_current_user

router = APIRouter(prefix="/api/calibrations", tags=["calibrations"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[CalibrationOut])
async def list_calibrations(
    session: Annotated[AsyncSession, Depends(get_session)], gage_id: int | None = None
) -> list[Calibration]:
    query = select(Calibration)
    if gage_id is not None:
        query = query.where(Calibration.gage_id == gage_id)
    result = await session.execute(query.order_by(Calibration.started_at.desc()))
    return list(result.scalars())


@router.post("", response_model=CalibrationOut, status_code=status.HTTP_201_CREATED)
async def create_calibration(
    payload: CalibrationCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Calibration:
    calibration = Calibration(**payload.model_dump(), performed_by=current_user.id)
    session.add(calibration)
    await session.commit()
    await session.refresh(calibration)
    return calibration


@router.post("/{calibration_id}/results", status_code=status.HTTP_201_CREATED)
async def add_calibration_result(
    calibration_id: int,
    payload: CalibrationResultCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    session.add(CalibrationResult(calibration_id=calibration_id, **payload.model_dump()))
    await session.commit()
    return {"status": "ok"}


@router.post("/{calibration_id}/complete", response_model=CalibrationOut)
async def complete_calibration(
    calibration_id: int, passed: bool, session: Annotated[AsyncSession, Depends(get_session)]
) -> Calibration:
    calibration = await session.get(Calibration, calibration_id)
    if calibration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calibrazione non trovata")
    calibration.status = "passed" if passed else "failed"
    calibration.completed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(calibration)
    return calibration


@router.post(
    "/{calibration_id}/certificate", response_model=CalibrationCertificateOut, status_code=status.HTTP_201_CREATED
)
async def generate_certificate(
    calibration_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> CalibrationCertificate:
    """Genera il certificato di taratura.

    TODO: caricare il template HTML esistente (OneDrive/Mopla/MeasurLInk/certificato_taratura.html),
    valorizzarlo con i dati di gage/calibration/calibration_results e renderizzare html_body.
    Per ora crea solo il record con numero certificato progressivo, senza corpo HTML.
    """
    calibration = await session.get(Calibration, calibration_id)
    if calibration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calibrazione non trovata")

    certificate_no = f"CAL-{calibration_id}-{int(datetime.now(timezone.utc).timestamp())}"
    certificate = CalibrationCertificate(calibration_id=calibration_id, certificate_no=certificate_no)
    session.add(certificate)
    await session.commit()
    await session.refresh(certificate)
    return certificate
