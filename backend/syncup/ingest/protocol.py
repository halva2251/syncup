"""ServiceClient Protocol, RawItem TypedDict, and TokenPair for the ingest layer."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Protocol, runtime_checkable

from typing_extensions import TypedDict

if TYPE_CHECKING:
    from syncup.db.models import ServiceConnection


class RawItem(TypedDict):
    """Normalised output from any service client's fetch_items call.

    engagement_score is pre-computed by the client (0.0–1.0).
    raw_value preserves the original metric for debugging.
    raw_type tells the embedding builder which normalisation formula applies.
    """

    external_id: str
    name: str
    item_type: str
    engagement_score: float
    raw_value: float | None
    raw_type: Literal["consumption", "rating"]
    metadata: dict[str, Any]
    last_engaged_at: datetime | None


@dataclass(frozen=True)
class TokenPair:
    """New tokens returned by a client's OAuth refresh call."""

    access_token: str
    refresh_token: str | None
    expires_at: datetime | None


@runtime_checkable
class ServiceClient(Protocol):
    """Structural interface every ingest client must satisfy.

    The sync route and service registry use this Protocol for dispatch.
    service_name must be a ClassVar[str] set on the concrete class.
    """

    service_name: ClassVar[str]

    def fetch_items(self, connection: ServiceConnection) -> list[RawItem]:
        """Fetch all items for this user connection and return them as RawItems."""
        ...

    def refresh_token(self, connection: ServiceConnection) -> TokenPair | None:
        """Refresh the OAuth access token if needed.

        Returns a TokenPair with new credentials, or None if no refresh is
        needed (token still valid) or the service does not use OAuth tokens.
        """
        ...
