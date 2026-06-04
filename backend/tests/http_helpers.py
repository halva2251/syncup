"""Shared HTTP mock utilities for enrichment script tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx


class SequenceTransport(httpx.BaseTransport):
    """Replays a fixed sequence of responses, one per request."""

    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = list(responses)
        self._idx = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self._idx >= len(self._responses):
            raise RuntimeError("No more mock responses")
        resp = self._responses[self._idx]
        self._idx += 1
        return resp


def make_http(responses: list[httpx.Response]) -> httpx.Client:
    """Build an httpx.Client backed by a SequenceTransport."""
    return httpx.Client(transport=SequenceTransport(responses))


def json_response(body: dict, status: int = 200) -> httpx.Response:  # type: ignore[type-arg]
    """Convenience: build an httpx.Response with a JSON body."""
    return httpx.Response(status, json=body)


def make_session(items: list) -> MagicMock:
    """Build a MagicMock SQLAlchemy session that returns *items* from .all()."""
    session = MagicMock()
    session.query.return_value.filter.return_value.all.return_value = items
    return session
