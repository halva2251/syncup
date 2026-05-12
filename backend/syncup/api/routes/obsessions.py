"""POST/GET/DELETE /api/me/obsessions — manual taste entries."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from syncup.auth.router import RequireAuth
from syncup.db.models import ManualObsession
from syncup.db.session import get_db
from syncup.exceptions import SyncUpError
from syncup.limiter import limiter

router = APIRouter(prefix="/api/me", tags=["obsessions"])

_Category = Literal[
    "game", "music", "film", "book", "show",
    "anime", "manga", "community", "other",
]


class ObsessionIn(BaseModel):
    category: _Category
    name: str = Field(min_length=1, max_length=200)
    weight: float = Field(default=1.0, gt=0, le=10.0)

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("cannot be blank")
        return v


class ObsessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    name: str
    weight: float
    created_at: datetime


@router.get("/obsessions", response_model=list[ObsessionOut])
@limiter.limit("60/minute")
def list_obsessions(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> list[ObsessionOut]:
    rows = db.scalars(
        select(ManualObsession)
        .where(ManualObsession.user_id == user.id)
        .order_by(ManualObsession.created_at.desc())
    ).all()
    return [ObsessionOut.model_validate(r) for r in rows]


@router.post("/obsessions", response_model=ObsessionOut, status_code=201)
@limiter.limit("30/minute")
def create_obsession(
    body: ObsessionIn,
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> ObsessionOut:
    obs = ManualObsession(
        id=uuid.uuid4(),
        created_at=datetime.now(UTC),
        user_id=user.id,
        category=body.category,
        name=body.name,
        weight=body.weight,
    )
    db.add(obs)
    db.commit()
    return ObsessionOut.model_validate(obs)


@router.delete("/obsessions/{obsession_id}", status_code=204)
@limiter.limit("30/minute")
def delete_obsession(
    obsession_id: uuid.UUID,
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> None:
    obs = db.scalar(
        select(ManualObsession).where(
            ManualObsession.id == obsession_id,
            ManualObsession.user_id == user.id,
        )
    )
    if obs is None:
        raise SyncUpError("NOT_FOUND", "Obsession not found", 404)
    db.delete(obs)
    db.commit()
