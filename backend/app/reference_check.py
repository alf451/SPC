"""Controllo generico "questa riga è ancora usata altrove?" prima di
un'eliminazione — usa information_schema per trovare le foreign key che
puntano alla tabella/colonna indicate, quindi resta corretto anche se lo
schema cambia, senza dover mantenere a mano una mappa delle relazioni per
ogni entità (utenti, sedi, stazioni, dispositivi/sorgenti DAQ, ...).
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Nomi tabella -> etichetta leggibile per il messaggio d'errore. Le tabelle
# non presenti qui vengono mostrate con il loro nome grezzo (comunque
# comprensibile, sono già in snake_case quasi-italiano) invece di fallire.
_FRIENDLY_TABLE_NAMES: dict[str, str] = {
    "sites": "sedi",
    "stations": "stazioni",
    "daq_devices": "dispositivi DAQ",
    "daq_sources": "sorgenti DAQ",
    "feature_daq_bindings": "collegamenti Feature↔DAQ",
    "runs": "run",
    "measurements": "misure",
    "attribute_observations": "osservazioni attributive",
    "gages": "strumenti di misura",
    "gage_station_active": "strumenti attivi in stazione",
    "gage_tracking_log": "movimentazioni strumenti",
    "calibrations": "calibrazioni",
    "part_property_versions": "versioni proprietà Part",
    "feature_property_versions": "versioni proprietà Feature",
    "work_orders": "commesse",
    "tools": "attrezzature",
    "users": "utenti",
}


def friendly_table_name(table: str) -> str:
    return _FRIENDLY_TABLE_NAMES.get(table, table)


class ReferencedElsewhereError(Exception):
    """Sollevata quando un'entità è ancora referenziata da altre tabelle e
    quindi non può essere eliminata. `references` è la lista di
    {"table", "friendly_name", "count"} trovate."""

    def __init__(self, references: list[dict]) -> None:
        self.references = references
        tables = ", ".join(f"{r['friendly_name']} ({r['count']})" for r in references)
        super().__init__(f"Ancora referenziato in: {tables}")


_FK_LOOKUP_SQL = text(
    """
    SELECT tc.table_name AS referencing_table, kcu.column_name AS referencing_column
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage ccu
        ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
        AND ccu.table_name = :table
        AND ccu.column_name = :column
        AND tc.table_schema = 'public'
    """
)


async def check_not_referenced(session: AsyncSession, table: str, column: str, value: object) -> None:
    """Solleva ReferencedElsewhereError se qualche altra tabella referenzia
    (table.column = value) tramite foreign key. Va chiamata PRIMA di
    session.delete(...) nel router, non dopo - questo da' un elenco preciso
    di tutte le tabelle coinvolte in un colpo solo, mentre lasciare fallire
    la DELETE stessa riporterebbe solo la prima foreign key che Postgres
    incontra (l'IntegrityError generico in app/main.py resta comunque come
    rete di sicurezza per i casi non coperti qui).
    """
    fk_result = await session.execute(_FK_LOOKUP_SQL, {"table": table, "column": column})
    references: list[dict] = []
    for row in fk_result:
        ref_table, ref_column = row.referencing_table, row.referencing_column
        # ref_table/ref_column vengono da information_schema (catalogo del
        # database, non input utente): sicuro comporli nella query anche se
        # non sono passabili come bind parameter (Postgres non lo permette
        # per nomi di tabella/colonna).
        count_sql = text(f'SELECT COUNT(*) FROM "{ref_table}" WHERE "{ref_column}" = :value')  # noqa: S608
        count = await session.scalar(count_sql, {"value": value})
        if count:
            references.append({"table": ref_table, "friendly_name": friendly_table_name(ref_table), "count": count})

    if references:
        raise ReferencedElsewhereError(references)
