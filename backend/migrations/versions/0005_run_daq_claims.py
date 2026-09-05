"""assegnazione di una sorgente DAQ (strumento) a una Run specifica -
necessario per supportare piu' Run attive in parallelo sulla stessa stazione

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-05

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE run_daq_claims (
            id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            run_id          bigint NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
            daq_source_id   bigint NOT NULL REFERENCES daq_sources(id) ON DELETE CASCADE,
            claimed_at      timestamptz NOT NULL DEFAULT now(),
            released_at     timestamptz
        )
    """)
    # Un solo "possessore" attivo per sorgente DAQ alla volta - un secondo
    # tentativo di reclamare la stessa sorgente mentre e' gia' assegnata a
    # un'altra Run viene rifiutato dall'applicazione PRIMA di arrivare qui,
    # ma l'indice e' la garanzia di ultima istanza a livello di database.
    op.execute(
        "CREATE UNIQUE INDEX ix_run_daq_claims_active_source ON run_daq_claims (daq_source_id) "
        "WHERE released_at IS NULL"
    )
    op.execute("CREATE INDEX ix_run_daq_claims_run ON run_daq_claims (run_id)")


def downgrade() -> None:
    op.execute("DROP TABLE run_daq_claims")
