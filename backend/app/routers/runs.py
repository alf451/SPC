from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.daq_claims import auto_claim_for_run, release_all_for_run
from app.db import get_session
from app.models.core import User
from app.models.daq import RunDaqClaim
from app.models.production import RunSkippedPosition, ToolPosition
from app.models.spc import AttributeObservation, Measurement, Run, RunTraceabilityValue, TraceabilityField
from app.schemas.spc import (
    ClaimDaqSourceIn,
    CurrentPositionIn,
    DaqClaimOut,
    PositionOut,
    PositionProgressOut,
    RunCreate,
    RunOut,
    SkipPositionIn,
    TraceabilityValueIn,
    TraceabilityValueOut,
)
from app.security import get_current_user

router = APIRouter(prefix="/api/runs", tags=["runs"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[RunOut])
async def list_runs(
    session: Annotated[AsyncSession, Depends(get_session)],
    station_id: int | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Run]:
    query = select(Run)
    if station_id is not None:
        query = query.where(Run.station_id == station_id)
    if status_filter is not None:
        query = query.where(Run.status == status_filter)
    query = query.order_by(Run.started_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    return list(result.scalars())


@router.post("", response_model=RunOut, status_code=status.HTTP_201_CREATED)
async def create_run(
    payload: RunCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Run:
    run = Run(**payload.model_dump(), started_by=current_user.id)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    # Assegna alla Run le sorgenti DAQ della sua Routine, cosi' le letture in
    # arrivo da quello strumento sanno gia' a quale Run appartenere - vedi
    # app/daq_claims.py e ws/agent_hub.py::_run_for_daq_source (necessario da
    # quando piu' Run possono essere attive in parallelo sulla stessa stazione).
    await auto_claim_for_run(session, run)
    await session.commit()
    # TODO: notificare la stazione via /ws/agent che un nuovo Run è attivo,
    # così l'Edge Agent riceve i feature_daq_bindings correnti nel messaggio "config".
    return run


@router.get("/{run_id}", response_model=RunOut)
async def get_run(run_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> Run:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run non trovato")
    return run


@router.post("/{run_id}/complete", response_model=RunOut)
async def complete_run(run_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> Run:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run non trovato")
    run.status = "completed"
    run.ended_at = datetime.now(timezone.utc)
    await release_all_for_run(session, run_id)
    await session.commit()
    await session.refresh(run)
    return run


@router.get("/{run_id}/daq-claims", response_model=list[DaqClaimOut])
async def list_run_daq_claims(
    run_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> list[DaqClaimOut]:
    result = await session.execute(
        select(RunDaqClaim.daq_source_id).where(RunDaqClaim.run_id == run_id, RunDaqClaim.released_at.is_(None))
    )
    return [DaqClaimOut(daq_source_id=row[0]) for row in result]


@router.post("/{run_id}/daq-claims", status_code=status.HTTP_204_NO_CONTENT)
async def claim_daq_source(
    run_id: int, payload: ClaimDaqSourceIn, session: Annotated[AsyncSession, Depends(get_session)]
) -> None:
    """Assegna esplicitamente uno strumento a questa Run - normalmente non
    serve (avviene da solo alla creazione, vedi create_run sopra); utile solo
    per il caso raro in cui lo stesso strumento serva a una Run diversa da
    quella che lo ha reclamato per prima automaticamente."""
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run non trovato")
    existing_result = await session.execute(
        select(RunDaqClaim).where(
            RunDaqClaim.daq_source_id == payload.daq_source_id, RunDaqClaim.released_at.is_(None)
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        if existing.run_id == run_id:
            return
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Questa sorgente DAQ è già assegnata alla Run #{existing.run_id} - liberarla prima da lì.",
        )
    session.add(RunDaqClaim(run_id=run_id, daq_source_id=payload.daq_source_id))
    await session.commit()


@router.delete("/{run_id}/daq-claims/{daq_source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def release_daq_source(
    run_id: int, daq_source_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> None:
    result = await session.execute(
        select(RunDaqClaim).where(
            RunDaqClaim.run_id == run_id, RunDaqClaim.daq_source_id == daq_source_id, RunDaqClaim.released_at.is_(None)
        )
    )
    claim = result.scalar_one_or_none()
    if claim is not None:
        claim.released_at = datetime.now(timezone.utc)
        await session.commit()


@router.put("/{run_id}/current-position", response_model=RunOut)
async def set_current_position(
    run_id: int, payload: CurrentPositionIn, session: Annotated[AsyncSession, Depends(get_session)]
) -> Run:
    """Posizione/cavità "attiva" in questo momento per il Run - ogni nuova
    misura in arrivo (dall'Edge Agent via WS o inserita a mano) viene marcata
    con questa (vedi ws/agent_hub.py::_persist_reading), cosi' l'Edge Agent
    non deve sapere nulla di posizioni/cavità."""
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run non trovato")
    if payload.tool_position_id is not None:
        position = await session.get(ToolPosition, payload.tool_position_id)
        if position is None or position.tool_id != run.tool_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La posizione indicata non appartiene all'attrezzatura di questo Run.",
            )
    run.current_tool_position_id = payload.tool_position_id
    await session.commit()
    await session.refresh(run)
    return run


@router.post("/{run_id}/skip-position", status_code=status.HTTP_204_NO_CONTENT)
async def skip_position(
    run_id: int,
    payload: SkipPositionIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Registra che l'operatore ha saltato una posizione/cavità (es. chiusa
    o inutilizzata per ragioni tecniche) - idempotente, richiamarlo due volte
    sulla stessa posizione non duplica nulla."""
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run non trovato")
    existing = await session.get(RunSkippedPosition, (run_id, payload.tool_position_id))
    if existing is None:
        session.add(
            RunSkippedPosition(run_id=run_id, tool_position_id=payload.tool_position_id, skipped_by=current_user.id)
        )
        await session.commit()


@router.delete("/{run_id}/skip-position/{tool_position_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unskip_position(
    run_id: int, tool_position_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> None:
    existing = await session.get(RunSkippedPosition, (run_id, tool_position_id))
    if existing is not None:
        await session.delete(existing)
        await session.commit()


@router.get("/{run_id}/position-progress", response_model=PositionProgressOut)
async def get_position_progress(
    run_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> PositionProgressOut:
    """Per ogni posizione/cavità dell'attrezzatura del Run: se è stata
    saltata e quante misure/osservazioni esistono già per ciascuna Feature -
    il frontend confronta questi conteggi con il subgroup_size della Feature
    per sapere quando una posizione è "completa"."""
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run non trovato")
    if run.tool_id is None:
        return PositionProgressOut(has_tool=False, positions=[])

    positions_result = await session.execute(
        select(ToolPosition).where(ToolPosition.tool_id == run.tool_id).order_by(ToolPosition.position_no)
    )
    positions = list(positions_result.scalars())

    skipped_result = await session.execute(
        select(RunSkippedPosition.tool_position_id).where(RunSkippedPosition.run_id == run_id)
    )
    skipped_ids = {row[0] for row in skipped_result}

    counts_by_position: dict[int, dict[int, int]] = {}
    for model in (Measurement, AttributeObservation):
        counts_result = await session.execute(
            select(model.tool_position_id, model.feature_id, func.count())
            .where(model.run_id == run_id, model.tool_position_id.is_not(None))
            .group_by(model.tool_position_id, model.feature_id)
        )
        for tool_position_id, feature_id, count in counts_result:
            counts_by_position.setdefault(tool_position_id, {})[feature_id] = count

    return PositionProgressOut(
        has_tool=True,
        positions=[
            PositionOut(
                id=p.id,
                position_no=p.position_no,
                label=p.label,
                skipped=p.id in skipped_ids,
                counts=counts_by_position.get(p.id, {}),
            )
            for p in positions
        ],
    )


@router.get("/{run_id}/traceability", response_model=list[TraceabilityValueOut])
async def get_run_traceability(
    run_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> list[TraceabilityValueOut]:
    result = await session.execute(
        select(TraceabilityField.name, RunTraceabilityValue.value)
        .join(RunTraceabilityValue, RunTraceabilityValue.field_id == TraceabilityField.id)
        .where(RunTraceabilityValue.run_id == run_id)
    )
    return [TraceabilityValueOut(field_name=name, value=value) for name, value in result]


@router.put("/{run_id}/traceability/{field_name}", response_model=TraceabilityValueOut)
async def set_run_traceability(
    run_id: int,
    field_name: str,
    payload: TraceabilityValueIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TraceabilityValueOut:
    """Campo generico (es. "Lotto", seminato dalla migration 0004) - un
    valore per Run, upsert. Altri campi di tracciabilità si aggiungono
    creando una riga in traceability_fields, senza toccare questo endpoint."""
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run non trovato")
    field_result = await session.execute(select(TraceabilityField).where(TraceabilityField.name == field_name))
    field = field_result.scalar_one_or_none()
    if field is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f'Campo di tracciabilità "{field_name}" non definito'
        )
    existing = await session.get(RunTraceabilityValue, (run_id, field.id))
    if existing is None:
        session.add(RunTraceabilityValue(run_id=run_id, field_id=field.id, value=payload.value))
    else:
        existing.value = payload.value
    await session.commit()
    return TraceabilityValueOut(field_name=field_name, value=payload.value)
