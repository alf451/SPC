from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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


def create_app() -> FastAPI:
    app = FastAPI(title="leank-spc API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
