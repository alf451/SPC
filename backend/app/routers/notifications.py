from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.core import User
from app.notifications.mailer import EmailNotConfigured, get_settings, send_email
from app.schemas.notifications import NotificationSettingsOut, NotificationSettingsUpdate, SupportRequestIn
from app.security import get_current_user

router = APIRouter(prefix="/api/notification-settings", tags=["notifications"], dependencies=[Depends(get_current_user)])
support_router = APIRouter(prefix="/api/support", tags=["notifications"], dependencies=[Depends(get_current_user)])


def _to_out(settings) -> NotificationSettingsOut:
    return NotificationSettingsOut(
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_username=settings.smtp_username,
        smtp_password_set=bool(settings.smtp_password),
        smtp_use_tls=settings.smtp_use_tls,
        from_email=settings.from_email,
        to_email=settings.to_email,
        notify_on_agent_disconnected=settings.notify_on_agent_disconnected,
        notify_on_system_error=settings.notify_on_system_error,
    )


@router.get("", response_model=NotificationSettingsOut)
async def get_notification_settings(session: Annotated[AsyncSession, Depends(get_session)]) -> NotificationSettingsOut:
    return _to_out(await get_settings(session))


@router.put("", response_model=NotificationSettingsOut)
async def update_notification_settings(
    payload: NotificationSettingsUpdate, session: Annotated[AsyncSession, Depends(get_session)]
) -> NotificationSettingsOut:
    settings = await get_settings(session)
    data = payload.model_dump(exclude_unset=True)
    if data.get("smtp_password") == "":
        data.pop("smtp_password")  # campo lasciato vuoto = non cambiare la password salvata
    for key, value in data.items():
        setattr(settings, key, value)
    await session.commit()
    await session.refresh(settings)
    return _to_out(settings)


@router.post("/test", status_code=status.HTTP_200_OK)
async def test_notification_settings(session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    try:
        await send_email(
            session,
            subject="leank-spc — email di prova",
            body="Se ricevi questo messaggio, la configurazione SMTP di leank-spc funziona correttamente.",
        )
    except EmailNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - qualunque errore SMTP, mostrato per intero all'admin
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Invio fallito: {exc}") from exc
    return {"sent": True}


@support_router.post("/request", status_code=status.HTTP_202_ACCEPTED)
async def send_support_request(
    payload: SupportRequestIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    body = (
        f"Da: {current_user.username} ({current_user.email or 'email non impostata'})\n"
        f"Contesto: {payload.context or 'n/d'}\n\n"
        f"{payload.message}"
    )
    try:
        await send_email(session, subject=f"[leank-spc] Richiesta assistenza: {payload.subject}", body=body)
    except EmailNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Invio fallito: {exc}") from exc
    return {"sent": True}
