"""Crea (o resetta la password di) un utente amministrativo, bypassando l'API.

Serve perche' tutte le route di /api/users richiedono un utente gia' autenticato
(get_current_user) — senza questo script non ci sarebbe modo di creare il
primissimo utente dopo un'installazione pulita ("problema dell'uovo e la
gallina" classico di ogni sistema con auth: qualcuno deve poter bootstrappare
il primo account senza gia' possedere un token).

Uso:
    python create_admin.py <username> <password> [--email you@example.com]
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Con l'interprete Python embeddable (usato dall'installer pilot mode) la
# cartella dello script non finisce automaticamente in sys.path come con una
# installazione Python normale: va aggiunta esplicitamente perche' 'app' venga
# trovato indipendentemente da come/da dove questo script viene invocato.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models.core import User  # noqa: E402
from app.security import hash_password


async def create_or_reset_admin(username: str, password: str, email: str | None) -> None:
    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(username=username, email=email, password_hash=hash_password(password), status="active")
            session.add(user)
            print(f"Creato utente '{username}'.")
        else:
            user.password_hash = hash_password(password)
            user.status = "active"
            print(f"Password aggiornata per l'utente esistente '{username}'.")
        await session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    parser.add_argument("password")
    parser.add_argument("--email", default=None)
    args = parser.parse_args()

    if len(args.password) < 8:
        print("La password deve avere almeno 8 caratteri.", file=sys.stderr)
        raise SystemExit(1)

    asyncio.run(create_or_reset_admin(args.username, args.password, args.email))


if __name__ == "__main__":
    main()
