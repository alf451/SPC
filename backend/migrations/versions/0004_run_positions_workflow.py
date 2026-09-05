"""flusso posizione/cavita' durante l'acquisizione: posizione corrente del
Run, posizioni saltate, campo di tracciabilita' "Lotto"

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-05

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Posizione/cavita' attualmente attiva per il Run - l'Edge Agent resta
    # "dumb" (non sa nulla di posizioni), e' il backend che marca ogni nuova
    # misura in arrivo (via WS o manuale) con questa posizione al momento
    # della scrittura (vedi app/ws/agent_hub.py::_persist_reading).
    op.execute("ALTER TABLE runs ADD COLUMN current_tool_position_id bigint REFERENCES tool_positions(id)")

    op.execute("""
        CREATE TABLE run_skipped_positions (
            run_id              bigint NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
            tool_position_id    bigint NOT NULL REFERENCES tool_positions(id) ON DELETE CASCADE,
            skipped_by          bigint REFERENCES users(id),
            skipped_at          timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (run_id, tool_position_id)
        )
    """)

    # Campo di tracciabilita' generico gia' previsto dallo schema v1
    # (traceability_fields/run_traceability_values) - "Lotto" e' il primo
    # caso d'uso reale, altri (turno, operatore...) si aggiungono allo
    # stesso modo, senza nuove migration.
    op.execute(
        "INSERT INTO traceability_fields (name, field_type) VALUES ('Lotto', 'text') "
        "ON CONFLICT (name) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DELETE FROM traceability_fields WHERE name = 'Lotto'")
    op.execute("DROP TABLE run_skipped_positions")
    op.execute("ALTER TABLE runs DROP COLUMN current_tool_position_id")
