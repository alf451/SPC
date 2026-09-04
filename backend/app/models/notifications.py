from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class NotificationSettings(Base):
    """Riga singola (id sempre 1, vincolato dal CHECK nella migration) con la
    configurazione SMTP e il destinatario delle notifiche - vedi
    app/notifications/mailer.py per come viene usata."""

    __tablename__ = "notification_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    smtp_host: Mapped[str | None]
    smtp_port: Mapped[int] = mapped_column(default=587)
    smtp_username: Mapped[str | None]
    smtp_password: Mapped[str | None]
    smtp_use_tls: Mapped[bool] = mapped_column(default=True)
    from_email: Mapped[str | None]
    to_email: Mapped[str] = mapped_column(default="mcdataviewerinfo@gmail.com")
    notify_on_agent_disconnected: Mapped[bool] = mapped_column(default=True)
    notify_on_system_error: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")
