"""integrazione ERP: commesse, attrezzature (stampi/fustelle), posizioni

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-28

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE tools (
            id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name            text NOT NULL,
            tool_type       text NOT NULL DEFAULT 'other' CHECK (tool_type IN ('mold', 'die', 'other')),
            position_count  integer NOT NULL DEFAULT 1,
            description     text,
            created_at      timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE tool_positions (
            id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            tool_id         bigint NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
            position_no     integer NOT NULL,
            label           text,
            notes           text,
            UNIQUE (tool_id, position_no)
        )
    """)

    op.execute("""
        CREATE TABLE work_orders (
            id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            order_number        text NOT NULL UNIQUE,
            part_id             bigint REFERENCES parts(id),
            customer            text,
            quantity_ordered    integer,
            status              text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'closed')),
            external_system     text,
            external_id         text,
            created_at          timestamptz NOT NULL DEFAULT now(),
            UNIQUE (external_system, external_id)
        )
    """)

    op.execute("ALTER TABLE runs ADD COLUMN work_order_id bigint REFERENCES work_orders(id)")
    op.execute("ALTER TABLE runs ADD COLUMN tool_id bigint REFERENCES tools(id)")
    op.execute("ALTER TABLE measurements ADD COLUMN tool_position_id bigint REFERENCES tool_positions(id)")
    op.execute("ALTER TABLE attribute_observations ADD COLUMN tool_position_id bigint REFERENCES tool_positions(id)")

    op.execute("CREATE INDEX ix_runs_work_order ON runs(work_order_id)")
    op.execute("CREATE INDEX ix_runs_tool ON runs(tool_id)")
    op.execute("CREATE INDEX ix_tool_positions_tool ON tool_positions(tool_id)")


def downgrade() -> None:
    op.execute("ALTER TABLE attribute_observations DROP COLUMN tool_position_id")
    op.execute("ALTER TABLE measurements DROP COLUMN tool_position_id")
    op.execute("ALTER TABLE runs DROP COLUMN tool_id")
    op.execute("ALTER TABLE runs DROP COLUMN work_order_id")
    op.execute("DROP TABLE work_orders")
    op.execute("DROP TABLE tool_positions")
    op.execute("DROP TABLE tools")
