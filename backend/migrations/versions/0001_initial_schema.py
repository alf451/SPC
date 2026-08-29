"""schema iniziale leank-spc

Il DDL vero e proprio vive in docs/schema.sql (unica fonte, tenuta leggibile e
commentata a scopo di documentazione/review) — questa migration lo esegue así
com'è per evitare di duplicare ~300 righe di SQL in due posti che potrebbero
disallinearsi. Se in futuro serviranno migration incrementali generate da
`alembic revision --autogenerate`, questa resta la baseline (revisione 0001).

Revision ID: 0001
Revises:
Create Date: 2026-08-08

"""
from pathlib import Path
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA_SQL_PATH = Path(__file__).resolve().parents[3] / "docs" / "schema.sql"

# docs/schema.sql è la fonte di riferimento leggibile per l'INTERO schema,
# comprese le sezioni aggiunte da migration successive (es. "v0.2" creata da
# 0002_work_orders_tools.py) — tenute lì solo a scopo di documentazione, come
# dice il commento sopra quella sezione nel file stesso. Questa migration deve
# eseguire SOLO lo schema v1 originale: se leggesse l'intero file duplicherebbe
# le tabelle che le migration successive creano da sole, con un
# "DuplicateTableError" ad ogni installazione pulita (bug riscontrato dal vivo
# su un'installazione reale: 0001 creava già "tools" eseguendo tutto schema.sql,
# poi 0002 falliva provando a ricrearla).
V02_MARKER = "-- v0.2 — Integrazione ERP: commesse, attrezzature (stampi/fustelle), posizioni"


def upgrade() -> None:
    sql = SCHEMA_SQL_PATH.read_text(encoding="utf-8")
    if V02_MARKER not in sql:
        raise RuntimeError(
            f"Marcatore '{V02_MARKER}' non trovato in {SCHEMA_SQL_PATH}: se il "
            "commento e' stato rinominato/spostato in docs/schema.sql, aggiornare "
            "questa costante - altrimenti questa migration (0001) eseguirebbe "
            "anche le sezioni aggiunte da migration successive, duplicandole."
        )
    sql = sql.split(V02_MARKER)[0]
    # schema.sql contiene già BEGIN/COMMIT: Alembic esegue già dentro una
    # transazione, quindi li rimuoviamo per evitare nested transaction non supportate.
    sql = sql.replace("BEGIN;", "").replace("COMMIT;", "")

    connection = op.get_bind()
    # Due problemi da evitare eseguendo l'intero script in un colpo solo:
    # 1) op.execute() passa la stringa attraverso sqlalchemy.text(), che interpreta
    #    ogni ":parola" (anche dentro i commenti JSON di esempio tipo "baud_rate":9600)
    #    come bind parameter con nome, corrompendo lo script.
    # 2) anche con exec_driver_sql(), il driver asyncpg prepara sempre lo statement
    #    (protocollo esteso) e Postgres non ammette comandi multipli in un unico
    #    prepared statement ("cannot insert multiple commands into a prepared
    #    statement") — quindi lo script va spezzato in singole istruzioni.
    for statement in sql.split(";"):
        statement = statement.strip()
        # Non filtrare via i frammenti che iniziano con un commento "--": alcuni
        # (es. prima di CREATE EXTENSION pg_trgm) hanno un commento in testa e
        # la vera istruzione SQL sulle righe successive dello stesso frammento.
        if statement:
            connection.exec_driver_sql(statement)


def downgrade() -> None:
    op.get_bind().exec_driver_sql("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
