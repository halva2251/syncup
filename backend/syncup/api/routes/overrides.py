"""POST/GET/PATCH/DELETE /api/me/overrides — preference overrides."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import joinedload

from syncup.auth.router import RequireAuth
from syncup.db.models import Item, PreferenceOverride
from syncup.db.session import get_db
from syncup.exceptions import SyncUpError
from syncup.limiter import limiter

router = APIRouter(prefix="/api/me", tags=["overrides"])


class ItemSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class OverrideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item: ItemSummary
    boost_multiplier: float
    note: str | None
    created_at: datetime


class OverrideIn(BaseModel):
    item_id: uuid.UUID
    boost_multiplier: float = Field(gt=0, le=10.0)
    note: str | None = Field(default=None, max_length=500)


class OverridePatch(BaseModel):
    boost_multiplier: float | None = Field(default=None, gt=0, le=10.0)
    note: str | None = Field(default=None, max_length=500)


@router.get("/overrides", response_model=list[OverrideOut])
@limiter.limit("60/minute")
def list_overrides(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> list[OverrideOut]:
    rows = db.scalars(
        select(PreferenceOverride)
        .where(PreferenceOverride.user_id == user.id)
        .options(joinedload(PreferenceOverride.item))
        .order_by(PreferenceOverride.created_at.desc())
    ).all()
    return [OverrideOut.model_validate(r) for r in rows]


@router.post("/overrides", response_model=OverrideOut, status_code=201)
@limiter.limit("30/minute")
def create_override(
    body: OverrideIn,
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> OverrideOut:
    item = db.get(Item, body.item_id)
    if item is None:
        raise SyncUpError("NOT_FOUND", "Item not found", 404)

    existing = db.scalar(
        select(PreferenceOverride).where(
            PreferenceOverride.user_id == user.id,
            PreferenceOverride.item_id == body.item_id,
        )
    )
    if existing is not None:
        raise SyncUpError("CONFLICT", "Override for this item already exists", 409)

    override = PreferenceOverride(
        id=uuid.uuid4(),
        created_at=datetime.now(UTC),
        user_id=user.id,
        item_id=body.item_id,
        boost_multiplier=body.boost_multiplier,
        note=body.note,
    )
    override.item = item
    db.add(override)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SyncUpError("CONFLICT", "Override for this item already exists", 409) from exc
    return OverrideOut.model_validate(override)


@router.patch("/overrides/{override_id}", response_model=OverrideOut)
@limiter.limit("30/minute")
def update_override(
    override_id: uuid.UUID,
    body: OverridePatch,
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> OverrideOut:
    override = db.scalar(
        select(PreferenceOverride)
        .where(
            PreferenceOverride.id == override_id,
            PreferenceOverride.user_id == user.id,
        )
        .options(joinedload(PreferenceOverride.item))
    )
    if override is None:
        raise SyncUpError("NOT_FOUND", "Override not found", 404)

    if body.boost_multiplier is not None:
        override.boost_multiplier = body.boost_multiplier
    if "note" in body.model_fields_set:
        override.note = body.note

    db.commit()
    return OverrideOut.model_validate(override)


@router.delete("/overrides/{override_id}", status_code=204)
@limiter.limit("30/minute")
def delete_override(
    override_id: uuid.UUID,
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> None:
    override = db.scalar(
        select(PreferenceOverride).where(
            PreferenceOverride.id == override_id,
            PreferenceOverride.user_id == user.id,
        )
    )
    if override is None:
        raise SyncUpError("NOT_FOUND", "Override not found", 404)
    db.delete(override)
    db.commit()
