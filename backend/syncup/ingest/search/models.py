"""Shared model for search suggestions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SearchSuggestion:
    """A single autocomplete suggestion from an upstream source."""

    name: str
    service: str
    item_type: str
    external_id: str | None = None
    extra: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.extra is None:
            object.__setattr__(self, "extra", {})
