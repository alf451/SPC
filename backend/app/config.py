from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://leank_spc:changeme@localhost:5432/leank_spc"
    # dove ascolta uvicorn (vedi backend/run.py) — 127.0.0.1 = solo questo PC,
    # 0.0.0.0 = raggiungibile anche da altre macchine della rete (impostato
    # dall'installer se si sceglie l'esposizione in rete)
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    # se entrambi valorizzati, run.py avvia uvicorn in HTTPS invece di HTTP
    # (percorsi a file .pem — auto-generati da generate_cert.py per la LAN,
    # oppure un certificato vero fornito dall'utente per l'esposizione pubblica)
    backend_ssl_certfile: str | None = None
    backend_ssl_keyfile: str | None = None
    jwt_secret: str = "change-this-to-a-random-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:8000,null"  # "null" = pagine aperte da file:// (es. admin/index.html)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
