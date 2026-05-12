"""GET /api/onboarding/status — current onboarding progress for the authenticated user."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from syncup.auth.router import RequireAuth
from syncup.db.models import ManualObsession, ServiceConnection, UserItem
from syncup.db.session import get_db
from syncup.limiter import limiter

router = APIRouter(prefix="/api", tags=["onboarding"])

_OBSESSIONS_THRESHOLD = 3


class OnboardingStatusOut(BaseModel):
    has_display_name: bool
    has_languages: bool
    has_connection_or_obsessions: bool
    has_taste_data: bool
    has_set_matchable: bool
    next_step: str | None


@router.get("/onboarding/status", response_model=OnboardingStatusOut)
@limiter.limit("60/minute")
def get_onboarding_status(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> OnboardingStatusOut:
    ok_connection_count: int = db.scalar(
        select(func.count()).select_from(ServiceConnection).where(
            ServiceConnection.user_id == user.id,
            ServiceConnection.sync_status == "ok",
        )
    ) or 0

    obsession_count: int = db.scalar(
        select(func.count()).select_from(ManualObsession).where(
            ManualObsession.user_id == user.id,
        )
    ) or 0

    has_connection_or_obsessions = (
        ok_connection_count > 0 or obsession_count >= _OBSESSIONS_THRESHOLD
    )

    has_taste_data = (
        db.execute(
            select(func.count()).select_from(UserItem).where(UserItem.user_id == user.id)
        ).scalar_one()
        > 0
    )

    has_display_name = bool(user.display_name)

    if not has_display_name:
        next_step: str | None = "set_display_name"
    elif not has_connection_or_obsessions:
        next_step = "connect_service"
    elif not user.is_matchable:
        next_step = "set_matchable"
    else:
        next_step = None

    return OnboardingStatusOut(
        has_display_name=has_display_name,
        has_languages=user.languages is not None,
        has_connection_or_obsessions=has_connection_or_obsessions,
        has_taste_data=has_taste_data,
        has_set_matchable=user.is_matchable,
        next_step=next_step,
    )
