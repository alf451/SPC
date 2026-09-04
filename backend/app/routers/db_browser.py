import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.security import get_current_user

router = APIRouter(prefix="/api/admin/db", tags=["admin-db"], dependencies=[Depends(get_current_user)])

_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Colonne mai mostrate, anche sfogliando la tabella - non ci sono altri campi
# segreto/hash noti nello schema attuale (vedi docs/schema.sql).
_HIDDEN_COLUMNS = {
    "users": {"password_hash"},
}


async def _table_exists(session: AsyncSession, table: str) -> bool:
    result = await session.execute(
        text("SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t"),
        {"t": table},
    )
    return result.scalar_one_or_none() is not None


@router.get("/tables")
async def list_tables(session: Annotated[AsyncSession, Depends(get_session)]) -> list[dict]:
    """Elenco tabelle con conteggio approssimato (da pg_stat_user_tables,
    aggiornato dal planner/autovacuum - evita una COUNT(*) reale su ogni
    tabella solo per popolare una lista, potenzialmente lenta su quelle grandi)."""
    result = await session.execute(
        text("SELECT relname AS name, n_live_tup AS approx_rows FROM pg_stat_user_tables ORDER BY relname")
    )
    return [{"name": row.name, "approx_rows": max(row.approx_rows, 0)} for row in result]


@router.get("/tables/{table}/rows")
async def table_rows(
    table: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Sola lettura, per esplorare i dati come in un client SQL (stile SSMS)
    senza dare accesso diretto al database. `table` viene validato contro
    information_schema (whitelist dinamica) prima di essere interpolato
    nell'SQL - i soli identificatori di tabella/colonna non sono
    parametrizzabili con i bind SQL normali, ma qui non arriva mai testo
    libero dell'utente in quella posizione."""
    if not _IDENTIFIER_RE.match(table) or not await _table_exists(session, table):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tabella non trovata")

    limit = max(1, min(limit, 500))
    offset = max(0, offset)

    columns_result = await session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :t ORDER BY ordinal_position"
        ),
        {"t": table},
    )
    hidden = _HIDDEN_COLUMNS.get(table, set())
    columns = [row.column_name for row in columns_result if row.column_name not in hidden]
    if not columns:
        return {"columns": [], "rows": [], "approx_total": 0}

    col_list = ", ".join(f'"{c}"' for c in columns)
    rows_result = await session.execute(
        text(f'SELECT {col_list} FROM "{table}" ORDER BY 1 LIMIT :limit OFFSET :offset'),
        {"limit": limit, "offset": offset},
    )
    rows = [dict(zip(columns, row, strict=True)) for row in rows_result]

    total_result = await session.execute(
        text("SELECT n_live_tup FROM pg_stat_user_tables WHERE relname = :t"), {"t": table}
    )
    approx_total = max(total_result.scalar_one_or_none() or 0, 0)

    return {"columns": columns, "rows": rows, "approx_total": approx_total}
