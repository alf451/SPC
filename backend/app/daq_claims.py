"""Assegnazione di una sorgente DAQ (strumento) a una Run specifica.

Necessario perché più Run possono essere attive in parallelo sulla stessa
stazione (es. due strumenti collegati, due commesse diverse in corso
contemporaneamente) - vedi RunDaqClaim in app/models/daq.py per il perché.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daq import FeatureDaqBinding, RunDaqClaim
from app.models.spc import Run


async def auto_claim_for_run(session: AsyncSession, run: Run) -> None:
    """Assegna alla Run le sorgenti DAQ della sua Routine che sono libere in
    questo momento - lascia stare quelle già in uso da un'altra Run ancora
    attiva (caso raro: stesso strumento richiesto da due Run in parallelo,
    fisicamente ambiguo - va risolto a mano, vedi claim_daq_source sotto,
    non deciso automaticamente al posto dell'operatore)."""
    bindings_result = await session.execute(
        select(FeatureDaqBinding.daq_source_id).where(FeatureDaqBinding.routine_id == run.routine_id).distinct()
    )
    daq_source_ids = [row[0] for row in bindings_result]
    if not daq_source_ids:
        return

    claimed_result = await session.execute(
        select(RunDaqClaim.daq_source_id).where(
            RunDaqClaim.daq_source_id.in_(daq_source_ids), RunDaqClaim.released_at.is_(None)
        )
    )
    already_claimed = {row[0] for row in claimed_result}
    for daq_source_id in daq_source_ids:
        if daq_source_id not in already_claimed:
            session.add(RunDaqClaim(run_id=run.id, daq_source_id=daq_source_id))


async def release_all_for_run(session: AsyncSession, run_id: int) -> None:
    """Libera tutte le sorgenti DAQ possedute da questa Run (es. al suo
    completamento), cosi' tornano disponibili per la prossima Run che le usa."""
    result = await session.execute(
        select(RunDaqClaim).where(RunDaqClaim.run_id == run_id, RunDaqClaim.released_at.is_(None))
    )
    now = datetime.now(timezone.utc)
    for claim in result.scalars():
        claim.released_at = now
