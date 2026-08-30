from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.spc import Feature, FeaturePropertyVersion, Routine, RoutineFeature
from app.schemas.spc import FeatureOut, RoutineCreate, RoutineOut
from app.security import get_current_user

router = APIRouter(prefix="/api", tags=["routines"], dependencies=[Depends(get_current_user)])


class RoutineFeatureOrder(BaseModel):
    order_no: int


@router.get("/routines", response_model=list[RoutineOut])
async def list_routines(
    session: Annotated[AsyncSession, Depends(get_session)],
    folder_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Routine]:
    query = select(Routine)
    if folder_id is not None:
        query = query.where(Routine.folder_id == folder_id)
    query = query.order_by(Routine.name).limit(limit).offset(offset)
    result = await session.execute(query)
    return list(result.scalars())


@router.post("/routines", response_model=RoutineOut, status_code=status.HTTP_201_CREATED)
async def create_routine(payload: RoutineCreate, session: Annotated[AsyncSession, Depends(get_session)]) -> Routine:
    routine = Routine(**payload.model_dump())
    session.add(routine)
    await session.commit()
    await session.refresh(routine)
    return routine


@router.get("/routines/{routine_id}", response_model=RoutineOut)
async def get_routine(routine_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> Routine:
    routine = await session.get(Routine, routine_id)
    if routine is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routine non trovata")
    return routine


@router.get("/routines/{routine_id}/features", response_model=list[FeatureOut])
async def list_routine_features(
    routine_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> list[Feature]:
    query = (
        select(Feature)
        .join(RoutineFeature, RoutineFeature.feature_id == Feature.id)
        .where(RoutineFeature.routine_id == routine_id)
        .order_by(RoutineFeature.order_no)
    )
    result = await session.execute(query)
    features = list(result.scalars())

    # stesso arricchimento di list_part_features (routers/features.py): la
    # vista "Raccolta Dati" del frontend chiama questo endpoint per mostrare
    # target/tolleranze insieme all'elenco Feature della Routine.
    feature_ids = [f.id for f in features]
    if feature_ids:
        current = await session.execute(
            select(FeaturePropertyVersion).where(
                FeaturePropertyVersion.feature_id.in_(feature_ids),
                FeaturePropertyVersion.valid_to.is_(None),
            )
        )
        current_by_feature = {v.feature_id: v for v in current.scalars()}
        for feature in features:
            feature.current_properties = current_by_feature.get(feature.id)

    return features


@router.put("/routines/{routine_id}/features/{feature_id}", status_code=status.HTTP_204_NO_CONTENT)
async def bind_feature_to_routine(
    routine_id: int,
    feature_id: int,
    payload: RoutineFeatureOrder,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    link = await session.get(RoutineFeature, {"routine_id": routine_id, "feature_id": feature_id})
    if link is None:
        session.add(RoutineFeature(routine_id=routine_id, feature_id=feature_id, order_no=payload.order_no))
    else:
        link.order_no = payload.order_no
    await session.commit()
