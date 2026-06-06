"""PATCH /api/me/items/{item_id} — exclude or re-include a user item."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import joinedload

from syncup.auth.router import RequireAuth
from syncup.db.models import UserItem
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
