"""Tests for ORM model column defaults and invariants (D11, D13)."""
from __future__ import annotations


# ---------------------------------------------------------------------------
# D11 — UserItem.fetched_at must have a Python-side default
# ---------------------------------------------------------------------------


def test_user_item_fetched_at_column_has_python_default() -> None:
    """D11: UserItem.fetched_at needs default=_now so ORM inserts work without a live DB."""
    from sqlalchemy import inspect as sa_inspect
    from syncup.db.models import UserItem

    col = sa_inspect(UserItem).c.fetched_at
    assert col.default is not None, (
        "UserItem.fetched_at must have a Python-side default=_now; "
        "server_default alone fails in unit tests that don't hit a real DB."
    )


# ---------------------------------------------------------------------------
# D13 — UserEmbedding.computed_at must have a Python-side default
# ---------------------------------------------------------------------------


def test_user_embedding_computed_at_column_has_python_default() -> None:
    """D13: UserEmbedding.computed_at needs default=_now so ORM inserts work without a live DB."""
    from sqlalchemy import inspect as sa_inspect
    from syncup.db.models import UserEmbedding

    col = sa_inspect(UserEmbedding).c.computed_at
    assert col.default is not None, (
        "UserEmbedding.computed_at must have a Python-side default=_now."
    )


# ---------------------------------------------------------------------------
# D9 — User.updated_at must NOT have onupdate (DB trigger handles it)
# ---------------------------------------------------------------------------


def test_user_updated_at_has_no_sqlalchemy_onupdate() -> None:
    """D9: DB trigger (migration 0005) owns updated_at; SQLAlchemy onupdate would double-set it."""
    from sqlalchemy import inspect as sa_inspect
    from syncup.db.models import User

    col = sa_inspect(User).c.updated_at
    assert col.onupdate is None, (
        "User.updated_at must not have onupdate=func.now(); "
        "the DB trigger in migration 0005 already handles this."
    )
