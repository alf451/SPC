from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.spc import Feature, FeaturePropertyVersion
from app.schemas.spc import FeatureCreate, FeatureOut, FeaturePropertiesIn, FeaturePropertyVersionOut
from app.security import get_current_user

router = APIRouter(prefix="/api", tags=["features"], dependencies=[Depends(get_current_user)])


@router.get("/parts/{part_id}/features", response_model=list[FeatureOut])
async def list_part_features(part_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> list[Feature]:
    result = await session.execute(select(Feature).where(Feature.part_id == part_id).order_by(Feature.order_no))
    features = list(result.scalars())

    # Versione di tolleranze/limiti attiva ora, una per Feature - popolata a
    # mano (non e' una relationship SQLAlchemy) cosi' il frontend puo' mostrare
    # "Quote della routine" con un'unica chiamata invece di N richieste extra.
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


@router.get("/features/{feature_id}/properties", response_model=list[FeaturePropertyVersionOut])
async def list_feature_property_versions(
    feature_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> list[FeaturePropertyVersion]:
    """Storico versioni di tolleranze/limiti, piu' recente prima - non cambia mai
    in-place (vedi create_feature_property_version sotto), quindi questa e' la
    cronologia completa usata dal pannello "Versioni proprietà" del frontend."""
    result = await session.execute(
        select(FeaturePropertyVersion)
        .where(FeaturePropertyVersion.feature_id == feature_id)
        .order_by(FeaturePropertyVersion.version_no.desc())
    )
    return list(result.scalars())


@router.post("/features", response_model=FeatureOut, status_code=status.HTTP_201_CREATED)
async def create_feature(payload: FeatureCreate, session: Annotated[AsyncSession, Depends(get_session)]) -> Feature:
    feature = Feature(
        part_id=payload.part_id,
        feature_type=payload.feature_type,
        name=payload.name,
        description=payload.description,
        order_no=payload.order_no,
    )
    session.add(feature)
    await session.flush()  # ottiene feature.id senza commit

    if payload.properties is not None:
        session.add(FeaturePropertyVersion(feature_id=feature.id, version_no=1, **payload.properties.model_dump()))

    await session.commit()
    await session.refresh(feature)
    return feature


@router.post("/features/{feature_id}/properties", status_code=status.HTTP_201_CREATED)
async def create_feature_property_version(
    feature_id: int,
    payload: FeaturePropertiesIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Crea una nuova versione di tolleranze/limiti — non aggiorna mai in-place.

    Mantiene lo stesso pattern di versionamento di MeasurLink (FeatureProperties + PropID):
    la versione precedente viene chiusa (valid_to=now()) e i dati storici restano
    legati alla versione che era attiva quando sono stati raccolti.
    """
    feature = await session.get(Feature, feature_id)
    if feature is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature non trovata")

    await session.execute(
        update(FeaturePropertyVersion)
        .where(FeaturePropertyVersion.feature_id == feature_id, FeaturePropertyVersion.valid_to.is_(None))
        .values(valid_to=func.now())
    )
    max_version = await session.scalar(
        select(func.max(FeaturePropertyVersion.version_no)).where(FeaturePropertyVersion.feature_id == feature_id)
    )
    new_version = FeaturePropertyVersion(
        feature_id=feature_id, version_no=(max_version or 0) + 1, **payload.model_dump()
    )
    session.add(new_version)
    await session.commit()
    await session.refresh(new_version)
    return {"id": new_version.id, "version_no": new_version.version_no}
