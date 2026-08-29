"""Entrypoint del backend: legge host/porta da backend/.env (BACKEND_HOST/BACKEND_PORT)
invece di averli passati come argomenti a `uvicorn` — così install.ps1/install.sh
scrivono la scelta una volta sola nel .env e start.ps1/start.sh non devono
conoscerla (funziona anche se qualcuno lancia questo file direttamente).

Uso: python run.py
"""

import sys
from pathlib import Path

# Con l'interprete Python embeddable (installer pilot mode) la cartella dello
# script non finisce automaticamente in sys.path come con una Python normale
# quando invocato come "python run.py" (a differenza di "python -m qualcosa",
# che invece usa la cwd) — stesso problema/soluzione di create_admin.py.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn  # noqa: E402

from app.config import settings  # noqa: E402

if __name__ == "__main__":
    kwargs = {"host": settings.backend_host, "port": settings.backend_port}
    if settings.backend_ssl_certfile and settings.backend_ssl_keyfile:
        kwargs["ssl_certfile"] = settings.backend_ssl_certfile
        kwargs["ssl_keyfile"] = settings.backend_ssl_keyfile
    uvicorn.run("app.main:app", **kwargs)
