"""GET/PATCH /api/me/dimensions — per-service dimension weights."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as DbSession

from syncup.auth.router import RequireAuth
from syncup.db.models import UserDimensionWeight
from syncup.db.session import get_db
from syncup.exceptions import SyncUpError
from syncup.limiter import limiter

router = APIRouter(prefix="/api/me", tags=["dimensions"])

_VALID_SERVICES = frozenset({"steam", "lastfm", "spotify"})


class DimensionWeightsOut(BaseModel):
    weights: dict[str, float]


class DimensionWeightsIn(BaseModel):
    weights: dict[str, float]

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, v: dict[str, float]) -> dict[str, float]:
        if not v:
            raise ValueError("weights must not be empty")
        invalid = set(v) - _VALID_SERVICES
        if invalid:
            raise ValueError(f"Unknown services: {sorted(invalid)}")
        if any(w < 0 for w in v.values()):
            raise ValueError("All weights must be non-negative")
        if sum(v.values()) == 0:
            raise ValueError("At least one weight must be positive")
        return v


def _normalise(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    return {service: w / total for service, w in weights.items()}


@router.get("/dimensions", response_model=DimensionWeightsOut)
@limiter.limit("60/minute")
def get_dimensions(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> DimensionWeightsOut:
    rows = db.scalars(
        select(UserDimensionWeight).where(UserDimensionWeight.user_id == user.id)
    ).all()
    return DimensionWeightsOut(weights={r.service: r.weight for r in rows})


@router.patch("/dimensions", response_model=DimensionWeightsOut)
@limiter.limit("30/minute")
def update_dimensions(
    body: DimensionWeightsIn,
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> DimensionWeightsOut:
    normalised = _normalise(body.weights)

    db.execute(
        delete(UserDimensionWeight).where(UserDimensionWeight.user_id == user.id)
    )
    for service, weight in normalised.items():
        db.add(UserDimensionWeight(user_id=user.id, service=service, weight=weight))

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise SyncUpError("INTERNAL_ERROR", "Failed to update dimension weights", 500) from exc

    return DimensionWeightsOut(weights=normalised)
