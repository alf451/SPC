import logging
import re
import traceback
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from app.config import settings
from app.notifications.mailer import notify_background
from app.reference_check import ReferencedElsewhereError
from app.version import APP_VERSION

logger = logging.getLogger(__name__)
from app.routers import (
    admin_import,
    auth,
    calibrations,
    daq,
    db_browser,
    features,
    gages,
    measurements,
    notifications,
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


_STATIC_ROUTE_PREFIXES = ("/api", "/ws", "/docs", "/redoc", "/openapi.json", "/health")


def _make_spa_fallback_handler(frontend_dist: Path | None):
    """StaticFiles(html=True) serve index.html solo per un path che e' una
    directory reale - per una rotta di vue-router come /amministrazione (che
    non esiste come file ne' come cartella in frontend/dist) restituisce un
    404 vero invece del fallback, mandando in errore il refresh della pagina.
    Questo handler intercetta quei 404 e serve comunque index.html, lasciando
    intatti i 404 "veri" delle API (es. GET /api/runs/999).

    Registrato SEMPRE (non solo se frontend_dist esiste): senza un handler
    esplicito per StarletteHTTPException, un 404/404/409 "voluto" (es. da
    HTTPException nei router) finirebbe altrimenti intercettato dall'handler
    generico per Exception qui sotto (piu' generico, quindi meno specifico
    solo se questo manca) - restituendo un fuorviante 500 invece del codice
    corretto, e generando notifiche email spurie per un errore che non lo e'.
    """

    async def handler(request: Request, exc: StarletteHTTPException) -> Response:
        path = request.url.path
        if frontend_dist is not None and exc.status_code == 404 and not path.startswith(_STATIC_ROUTE_PREFIXES):
            index_file = frontend_dist / "index.html"
            if index_file.is_file():
                return FileResponse(index_file)
        return await http_exception_handler(request, exc)

    return handler


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Ultima rete di sicurezza: qualunque eccezione non gia' intercettata da
    un handler piu' specifico (IntegrityError, ReferencedElsewhereError,
    HTTPException...) finisce qui. Logga e notifica via email (se
    configurata) invece di far sparire l'errore in silenzio in un log che
    magari nessuno guarda finche' non arriva una lamentela dal cliente."""
    logger.exception("Errore non gestito su %s %s", request.method, request.url.path)
    body = f"{request.method} {request.url}\n\n{traceback.format_exc()}"
    await notify_background("system_error", subject="[leank-spc] Errore di sistema", body=body)
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": "Errore interno del server."})


async def _referenced_elsewhere_handler(request: Request, exc: ReferencedElsewhereError) -> JSONResponse:
    """Controllo PROATTIVO (vedi app/reference_check.py): a differenza di
    _integrity_error_handler sopra, che reagisce al primo vincolo che
    Postgres incontra provando davvero l'eliminazione, questo elenca TUTTE
    le tabelle coinvolte in un colpo solo, controllate prima di tentare la
    DELETE.
    """
    tables = ", ".join(f"{r['friendly_name']} ({r['count']} record)" for r in exc.references)
    message = f"Impossibile eliminare: ancora utilizzato in → {tables}. Rimuovere prima quei riferimenti."
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": message})


def create_app() -> FastAPI:
    app = FastAPI(title="leank-spc API", version=APP_VERSION)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(IntegrityError, _integrity_error_handler)
    app.add_exception_handler(ReferencedElsewhereError, _referenced_elsewhere_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)

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
        db_browser.router,
        notifications.router,
        notifications.support_router,
        sites_router,
    ):
        app.include_router(router)

    app.include_router(agent_hub.router)
    app.include_router(dashboard_hub.router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/version")
    async def version() -> dict:
        return {"version": APP_VERSION}

    @app.get("/api/changelog")
    async def changelog() -> dict:
        changelog_path = Path(__file__).resolve().parents[2] / "CHANGELOG.md"
        text = changelog_path.read_text(encoding="utf-8") if changelog_path.is_file() else ""
        return {"markdown": text}

    # Frontend Vue (frontend/dist/, prodotto da "npm run build") - montato per
    # ultimo e solo se presente, cosi' chi non lo ha ancora buildato continua
    # ad avere un backend funzionante (API/Swagger/pannello admin invariati).
    # "html=True" serve /assets/* e index.html sulla root; il fallback per le
    # altre rotte di vue-router (es. /amministrazione) e' nell'exception
    # handler sotto, perche' StaticFiles(html=True) da solo NON lo copre
    # (serve index.html solo per path che sono directory reali).
    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    frontend_dist_exists = frontend_dist.is_dir()
    app.add_exception_handler(StarletteHTTPException, _make_spa_fallback_handler(frontend_dist if frontend_dist_exists else None))
    if frontend_dist_exists:
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app


app = create_app()
