from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

    return app


app = create_app()
