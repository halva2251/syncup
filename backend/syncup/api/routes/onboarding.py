"""GET /api/onboarding/status — current onboarding progress for the authenticated user."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from syncup.auth.router import RequireAuth
from syncup.db.models import ManualObsession, ServiceConnection
from syncup.db.session import get_db
from syncup.limiter import limiter

router = APIRouter(prefix="/api", tags=["onboarding"])

_OBSESSIONS_THRESHOLD = 3


class OnboardingStatusOut(BaseModel):
    has_display_name: bool
    has_languages: bool
    has_connection_or_obsessions: bool
    has_reviewed_taste: bool
    has_set_matchable: bool
    next_step: str | None


@router.get("/onboarding/status", response_model=OnboardingStatusOut)
@limiter.limit("60/minute")
def get_onboarding_status(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> OnboardingStatusOut:
    ok_connections = db.scalars(
        select(ServiceConnection).where(
            ServiceConnection.user_id == user.id,
            ServiceConnection.sync_status == "ok",
        )
    ).all()

    obsessions = db.scalars(
        select(ManualObsession).where(ManualObsession.user_id == user.id)
    ).all()

    has_connection_or_obsessions = (
        len(ok_connections) > 0 or len(obsessions) >= _OBSESSIONS_THRESHOLD
    )

    if not has_connection_or_obsessions:
        next_step: str | None = "connect_service"
    elif not user.is_matchable:
        next_step = "set_matchable"
    else:
        next_step = None

    return OnboardingStatusOut(
        has_display_name=bool(user.display_name),
        has_languages=user.languages is not None,
        has_connection_or_obsessions=has_connection_or_obsessions,
        has_reviewed_taste=has_connection_or_obsessions,
        has_set_matchable=user.is_matchable,
        next_step=next_step,
    )
