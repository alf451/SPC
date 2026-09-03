import re
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.routers import (
    admin_import,
    auth,
    calibrations,
    daq,
    features,
    gages,
    measurements,
    parts,
    production,
    routines,
    runs,
    stations,
    users,
)
from app.routers.stations import sites_router
from app.ws import agent_hub, dashboard_hub

# Il testo del messaggio Postgres e' nella lingua configurata sul server
# (qui: italiano - "un valore chiave duplicato viola il vincolo univoco...",
# non l'inglese "duplicate key value violates..."), quindi non e' affidabile
# per il riconoscimento. Il NOME della classe di eccezione di asyncpg invece
# e' sempre in inglese a prescindere dalla lingua del server (compare come
# "<class 'asyncpg.exceptions.UniqueViolationError'>" dentro str(exc.orig)) -
# e' quello il segnale robusto da cercare. Il dettaglio "(colonna)=(valore)"
# e' invece strutturalmente uguale in entrambe le lingue (solo le parole
# intorno cambiano: "Key (...)=(...)"" vs "La chiave (...)=(...)""), quindi la
# regex cerca solo quella struttura, non le parole che la introducono.
_UNIQUE_KEY_RE = re.compile(r"\(([a-zA-Z_][a-zA-Z0-9_]*)\)=\(([^)]*)\)")


async def _integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Traduce le violazioni di vincolo del database (duplicati, riferimenti
    ancora in uso) in un errore HTTP con un messaggio comprensibile, invece di
    lasciar risalire un 500 con lo stack trace grezzo di SQLAlchemy/asyncpg.
    Centralizzato qui una volta sola, vale per ogni endpoint - niente
    try/except da ripetere in ogni router.
    """
    detail = str(exc.orig) if exc.orig else str(exc)

    if "UniqueViolationError" in detail:
        match = _UNIQUE_KEY_RE.search(detail)
        if match:
            field, value = match.group(1), match.group(2)
            message = f'Esiste già un elemento con {field} = "{value}" - scegli un valore diverso.'
        else:
            message = "Esiste già un elemento con questi stessi dati - scegli un valore diverso."
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": message})

    if "ForeignKeyViolationError" in detail:
        message = (
            "Impossibile completare l'operazione: questo elemento è ancora collegato ad altri dati "
            "(es. stazioni, sorgenti, misure) che vanno rimossi prima."
        )
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": message})

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "Operazione non consentita: violazione di un vincolo del database."},
    )


def create_app() -> FastAPI:
    app = FastAPI(title="leank-spc API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(IntegrityError, _integrity_error_handler)

    for router in (
        auth.router,
        parts.router,
        routines.router,
        features.router,
        runs.router,
        measurements.router,
        stations.router,
        daq.router,
        gages.router,
        calibrations.router,
        users.router,
        production.router,
        admin_import.router,
        sites_router,
    ):
        app.include_router(router)

    app.include_router(agent_hub.router)
    app.include_router(dashboard_hub.router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    # Frontend Vue (frontend/dist/, prodotto da "npm run build") - montato per
    # ultimo e solo se presente, cosi' chi non lo ha ancora buildato continua
    # ad avere un backend funzionante (API/Swagger/pannello admin invariati).
    # "html=True" serve le pagine di vue-router (createWebHistory) risolvendo
    # ogni percorso non trovato su index.html invece di un 404 statico.
    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app


app = create_app()
