"""notifiche email: configurazione SMTP + destinatario (riga singola)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-04

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE notification_settings (
            id                              smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
            smtp_host                       text,
            smtp_port                       integer NOT NULL DEFAULT 587,
            smtp_username                   text,
            smtp_password                   text,
            smtp_use_tls                    boolean NOT NULL DEFAULT true,
            from_email                      text,
            to_email                        text NOT NULL DEFAULT 'mcdataviewerinfo@gmail.com',
            notify_on_agent_disconnected    boolean NOT NULL DEFAULT true,
            notify_on_system_error          boolean NOT NULL DEFAULT true,
            updated_at                      timestamptz NOT NULL DEFAULT now()
        )
    """)
    # Riga singola (id=1, CHECK sopra impedisce di aggiungerne altre) - creata
    # subito cosi' GET /api/notification-settings trova sempre qualcosa senza
    # dover gestire il caso "nessuna configurazione ancora" lato applicativo.
    op.execute("INSERT INTO notification_settings (id) VALUES (1)")


def downgrade() -> None:
    op.execute("DROP TABLE notification_settings")
