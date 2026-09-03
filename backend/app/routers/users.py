from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.core import User
from app.reference_check import check_not_referenced
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


class UserUpdate(BaseModel):
    # "username" volutamente escluso: e' l'identificativo di login, cambiarlo
    # e' un'operazione piu' delicata (andrebbe pensata a parte, non un campo
    # di modifica qualunque). "password" opzionale: se presente resetta la
    # password, altrimenti resta quella esistente.
    email: str | None = None
    full_name: str | None = None
    status: str | None = None
    password: str | None = None


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


@router.put("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int, payload: UserUpdate, session: Annotated[AsyncSession, Depends(get_session)]
) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente non trovato")
    data = payload.model_dump(exclude_unset=True)
    new_password = data.pop("password", None)
    for key, value in data.items():
        setattr(user, key, value)
    if new_password:
        user.password_hash = hash_password(new_password)
    await session.commit()
    await session.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Non puoi eliminare l'utente con cui hai effettuato l'accesso."
        )
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente non trovato")
    await check_not_referenced(session, "users", "id", user_id)
    await session.delete(user)
    await session.commit()
