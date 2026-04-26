"""GET /api/me — current user profile and service connections."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from syncup.auth.router import RequireAuth, UserOut
from syncup.db.models import ServiceConnection
from syncup.db.session import get_db

router = APIRouter(prefix="/api", tags=["users"])


class ServiceConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    service: str
    external_user_id: str
    sync_status: str
    last_synced_at: datetime | None
    token_expires_at: datetime | None
    sync_error: str | None


class MeOut(BaseModel):
    user: UserOut
    connections: list[ServiceConnectionOut]


@router.get("/me", response_model=MeOut)
def get_me(
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> MeOut:
    """Return the authenticated user's profile and service connection statuses."""
    connections = db.scalars(
        select(ServiceConnection).where(ServiceConnection.user_id == user.id)
    ).all()

    return MeOut(
        user=UserOut.model_validate(user),
        connections=[ServiceConnectionOut.model_validate(c) for c in connections],
    )
