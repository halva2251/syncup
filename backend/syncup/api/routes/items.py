"""PATCH /api/me/items/{item_id} — exclude or re-include a user item."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import joinedload

from syncup.auth.router import RequireAuth
from syncup.db.models import Item, UserItem
from syncup.db.session import get_db
from syncup.exceptions import SyncUpError
from syncup.limiter import limiter

router = APIRouter(prefix="/api/me", tags=["items"])


class ItemSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    service: str
    item_type: str


class UserItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item: ItemSummary
    engagement_score: float
    excluded: bool


class ItemExcludePatch(BaseModel):
    excluded: bool


class TasteItemChoiceOut(BaseModel):
    """A selectable, user-owned item for taste-control forms."""

    id: uuid.UUID
    name: str
    service: str
    item_type: str


@router.get("/items", response_model=list[TasteItemChoiceOut])
@limiter.limit("60/minute")
def list_taste_items(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
    limit: int = Query(default=1000, ge=1, le=2000),
) -> list[TasteItemChoiceOut]:
    """List a user's included items for name-based taste-control pickers."""
    rows = db.scalars(
        select(UserItem)
        .join(Item, UserItem.item_id == Item.id)
        .where(UserItem.user_id == user.id, UserItem.excluded == False)  # noqa: E712
        .options(joinedload(UserItem.item))
        .order_by(UserItem.engagement_score.desc(), Item.name.asc())
        .limit(limit)
    ).all()
    return [
        TasteItemChoiceOut(
            id=row.item.id,
            name=row.item.name,
            service=row.item.service,
            item_type=row.item.item_type,
        )
        for row in rows
    ]


@router.patch("/items/{item_id}", response_model=UserItemOut)
@limiter.limit("60/minute")
def patch_item_exclusion(
    item_id: uuid.UUID,
    body: ItemExcludePatch,
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> UserItemOut:
    """Toggle the excluded flag on a user_items row.

    Excluded items are skipped in embedding builds, LLM vibe synthesis, and
    recommendations. Returns 404 whether the item doesn't exist or belongs to
    another user — caller should not learn about other users' items.
    """
    user_item = db.scalar(
        select(UserItem)
        .where(UserItem.id == item_id, UserItem.user_id == user.id)
        .options(joinedload(UserItem.item))
    )
    if user_item is None:
        raise SyncUpError("NOT_FOUND", "Item not found", 404)

    user_item.excluded = body.excluded
    db.commit()

    return UserItemOut.model_validate(user_item)
