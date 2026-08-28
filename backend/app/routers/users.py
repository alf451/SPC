from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.core import User
from app.schemas.auth import UserOut
from app.security import get_current_user, hash_password

# Tutte le route qui sotto richiedono un utente gia' autenticato: per creare il
# primissimo utente dopo un'installazione pulita usare backend/create_admin.py
# (bypassa l'API, scrive direttamente sul DB).
router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(get_current_user)])


class UserCreate(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    password: str


@router.get("", response_model=list[UserOut])
async def list_users(session: Annotated[AsyncSession, Depends(get_session)]) -> list[User]:
    result = await session.execute(select(User).order_by(User.username))
    return list(result.scalars())


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, session: Annotated[AsyncSession, Depends(get_session)]) -> User:
    # TODO: proteggere con require_permission("admin.users.manage") quando la
    # dependency sarà implementata in app/security.py
    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
