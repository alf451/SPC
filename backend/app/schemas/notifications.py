from pydantic import BaseModel


class NotificationSettingsOut(BaseModel):
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_password_set: bool  # mai la password stessa, solo se e' impostata
    smtp_use_tls: bool
    from_email: str | None
    to_email: str
    notify_on_agent_disconnected: bool
    notify_on_system_error: bool


class NotificationSettingsUpdate(BaseModel):
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None  # se presente e non vuoto, sostituisce quella salvata
    smtp_use_tls: bool | None = None
    from_email: str | None = None
    to_email: str | None = None
    notify_on_agent_disconnected: bool | None = None
    notify_on_system_error: bool | None = None


class SupportRequestIn(BaseModel):
    subject: str
    message: str
    context: str | None = None  # es. pagina/stazione corrente, riempito dal frontend
