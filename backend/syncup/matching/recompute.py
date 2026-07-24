"""Background refresh for derived matching data after a taste change."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


def recompute_user_matching_data(
    db_factory: sessionmaker[DbSession], user_id: uuid.UUID
) -> None:
    """Rebuild a user's taste vector, then refresh its cached matches.

    This is deliberately not rate limited: it runs internally after a successful
    taste mutation, whereas the public refresh endpoint remains user-throttled.
    Imports are local to avoid a routes-module import cycle at application start.
    """
    from syncup.api.routes.matches import (
        _build_embedding_bg,
        _refresh_match_cache,
        _try_acquire_refresh,
    )

    _build_embedding_bg(db_factory, user_id)
    if _try_acquire_refresh(user_id):
        _refresh_match_cache(db_factory, user_id)
