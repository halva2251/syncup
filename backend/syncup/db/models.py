"""ORM models mirroring docs/db-schema.md.

Kept flat for now because the graph is small enough to comprehend in
one file. Split by aggregate root (users/auth, items/engagement,
matching) once any single section grows past ~200 lines.

All vector columns are dimension 128, matching
``TrainingConfig.vector_size`` in syncup.embeddings.item2vec. If that
default changes, both must move together and a migration must follow.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    LargeBinary,
    Text,
    UniqueConstraint,
    desc,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from syncup.db.base import Base

EMBEDDING_DIM = 128


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _now() -> datetime:
    return datetime.now(UTC)


def _created_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_now
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str | None] = mapped_column(CITEXT, unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    discord_handle: Mapped[str | None] = mapped_column(Text, nullable=True)
    languages: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    is_matchable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    onboarded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=_now,
        onupdate=func.now(),
    )

    auth_providers: Mapped[list[AuthProvider]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    service_connections: Mapped[list[ServiceConnection]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    user_items: Mapped[list[UserItem]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    preference_overrides: Mapped[list[PreferenceOverride]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    manual_obsessions: Mapped[list[ManualObsession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    dimension_weights: Mapped[list[UserDimensionWeight]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    embeddings: Mapped[list[UserEmbedding]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index(
            "idx_users_matchable",
            "is_matchable",
            postgresql_where="is_matchable = true",
        ),
    )


class AuthProvider(Base):
    __tablename__ = "auth_providers"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()

    user: Mapped[User] = relationship(back_populates="auth_providers")

    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id"),
        Index("idx_auth_providers_user", "user_id"),
    )


class ServiceConnection(Base):
    __tablename__ = "service_connections"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    service: Mapped[str] = mapped_column(Text, nullable=False)
    external_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    access_token_encrypted: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True
    )
    refresh_token_encrypted: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True
    )
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sync_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending", server_default="pending"
    )
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _created_at()

    user: Mapped[User] = relationship(back_populates="service_connections")

    __table_args__ = (
        UniqueConstraint("user_id", "service"),
        CheckConstraint(
            "sync_status IN ('pending', 'syncing', 'ok', 'error')",
            name="ck_sync_status_values",
        ),
        Index("idx_service_connections_user", "user_id"),
    )


class Item(Base):
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = _uuid_pk()
    service: Mapped[str] = mapped_column(Text, nullable=False)
    item_type: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=True
    )
    embedding_computed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()

    user_items: Mapped[list[UserItem]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )
    preference_overrides: Mapped[list[PreferenceOverride]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )
    manual_obsessions: Mapped[list[ManualObsession]] = relationship(
        back_populates="item"
    )

    __table_args__ = (
        UniqueConstraint("service", "item_type", "external_id"),
        Index("idx_items_service_type", "service", "item_type"),
        Index(
            "idx_items_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"lists": 100},
            postgresql_where="embedding IS NOT NULL",
        ),
    )


class UserItem(Base):
    __tablename__ = "user_items"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
    )
    engagement_score: Mapped[float] = mapped_column(Float, nullable=False)
    raw_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_type: Mapped[str] = mapped_column(
        Text, nullable=False, default="consumption", server_default="consumption"
    )
    last_engaged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="user_items")
    item: Mapped[Item] = relationship(back_populates="user_items")

    __table_args__ = (
        UniqueConstraint("user_id", "item_id"),
        Index("idx_user_items_user", "user_id"),
        Index("idx_user_items_item", "item_id"),
    )


class PreferenceOverride(Base):
    __tablename__ = "preference_overrides"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
    )
    boost_multiplier: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _created_at()

    user: Mapped[User] = relationship(back_populates="preference_overrides")
    item: Mapped[Item] = relationship(back_populates="preference_overrides")

    __table_args__ = (
        UniqueConstraint("user_id", "item_id"),
        CheckConstraint("boost_multiplier > 0", name="ck_boost_multiplier_positive"),
        Index("idx_overrides_user", "user_id"),
    )


class ManualObsession(Base):
    __tablename__ = "manual_obsessions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="SET NULL"), nullable=True
    )
    weight: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0, server_default="1.0"
    )
    created_at: Mapped[datetime] = _created_at()

    user: Mapped[User] = relationship(back_populates="manual_obsessions")
    item: Mapped[Item | None] = relationship(back_populates="manual_obsessions")

    __table_args__ = (
        CheckConstraint(
            "category IN ('game', 'music', 'film', 'book', 'show', 'anime', 'manga', 'community', 'other')",
            name="ck_obsession_category_values",
        ),
        Index("idx_obsessions_user", "user_id"),
    )


class UserDimensionWeight(Base):
    __tablename__ = "user_dimension_weights"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    service: Mapped[str] = mapped_column(Text, primary_key=True)
    weight: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0, server_default="1.0"
    )

    user: Mapped[User] = relationship(back_populates="dimension_weights")

    __table_args__ = (
        CheckConstraint(
            "weight >= 0 AND weight <= 1", name="ck_dimension_weight_range"
        ),
    )


class UserEmbedding(Base):
    __tablename__ = "user_embeddings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    service: Mapped[str] = mapped_column(Text, primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=False
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="embeddings")

    __table_args__ = (
        Index(
            "idx_user_embeddings_combined",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"lists": 100},
            postgresql_where="service = 'combined'",
        ),
    )


class MatchCache(Base):
    __tablename__ = "match_cache"

    user_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    score: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    breakdown: Mapped[dict[str, float]] = mapped_column(JSONB, nullable=False)
    highlights: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB, nullable=False, server_default="[]", default=list
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("user_a_id < user_b_id", name="ck_match_cache_order"),
        Index("idx_match_cache_a", "user_a_id", desc("score")),
        Index("idx_match_cache_b", "user_b_id", desc("score")),
    )


class Session(Base):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        Index("idx_sessions_user", "user_id"),
        Index("idx_sessions_expires", "expires_at"),
    )


__all__ = [
    "EMBEDDING_DIM",
    "AuthProvider",
    "Item",
    "ManualObsession",
    "MatchCache",
    "PreferenceOverride",
    "ServiceConnection",
    "Session",
    "User",
    "UserDimensionWeight",
    "UserEmbedding",
    "UserItem",
]
