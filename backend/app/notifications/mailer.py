from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models.notifications import NotificationSettings

logger = logging.getLogger(__name__)


class EmailNotConfigured(Exception):
    """SMTP non ancora configurato (host/destinatario mancanti) - non e' un
    errore di invio, e' proprio "non c'e' niente da provare a spedire"."""


async def get_settings(session: AsyncSession) -> NotificationSettings:
    settings = await session.get(NotificationSettings, 1)
    if settings is None:  # non dovrebbe succedere (riga creata dalla migration), difensivo
        settings = NotificationSettings(id=1)
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
    return settings


def _send_sync(settings: NotificationSettings, subject: str, body: str, to_override: str | None) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.from_email or settings.smtp_username or "leank-spc@localhost"
    msg["To"] = to_override or settings.to_email
    msg.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password or "")
        server.send_message(msg)


async def send_email(session: AsyncSession, subject: str, body: str, to_override: str | None = None) -> None:
    """Invia un'email subito, propagando l'errore al chiamante - per le azioni
    dirette dell'utente (es. "richiedi assistenza"), dove serve un feedback
    chiaro se l'invio fallisce. Per notifiche automatiche in background, vedi
    notify_background() sotto, che invece non propaga mai."""
    settings = await get_settings(session)
    if not settings.smtp_host or not (to_override or settings.to_email):
        raise EmailNotConfigured("Configurazione SMTP incompleta (host o destinatario mancante).")
    await asyncio.to_thread(_send_sync, settings, subject, body, to_override)


async def notify_background(kind: str, subject: str, body: str) -> None:
    """Notifica "fire and forget" per eventi di sistema (agent disconnesso,
    errore non gestito): apre una propria sessione (chiamata da contesti che
    non hanno gia' una request/session FastAPI, es. handler WebSocket ed
    exception handler globale) e non fa mai fallire il chiamante - un
    problema con l'invio email non deve mai rompere il flusso principale."""
    try:
        async with SessionLocal() as session:
            settings = await get_settings(session)
            flag = {
                "agent_disconnected": settings.notify_on_agent_disconnected,
                "system_error": settings.notify_on_system_error,
            }.get(kind, True)
            if not flag or not settings.smtp_host or not settings.to_email:
                return
            await send_email(session, subject, body)
    except Exception:  # noqa: BLE001 - qualunque causa, non deve propagare
        logger.exception("Invio notifica email (%s) fallito", kind)
