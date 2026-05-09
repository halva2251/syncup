"""Reddit OAuth client — community membership ingest."""
from __future__ import annotations

import math
import urllib.parse
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, ClassVar, cast

import httpx

from syncup.ingest.crypto import decrypt_token
from syncup.ingest.protocol import RawItem, SyncClientError, TokenPair

if TYPE_CHECKING:
    from syncup.db.models import ServiceConnection

_AUTHORIZE_URL = "https://www.reddit.com/api/v1/authorize"
_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"  # nosec B105
_API_BASE = "https://oauth.reddit.com"
# Reddit requires a descriptive User-Agent per their API rules. The /u/ portion
# must identify the responsible developer — update if project ownership changes.
_USER_AGENT = "web:syncup:0.1.0 (by /u/REDDIT_DEV_USERNAME)"

# Reddit access tokens expire in 1 hour.
_TOKEN_LIFETIME_SECONDS = 3600

# Subreddits with more than this many subscribers are excluded (mainstream noise).
_MAX_SUBSCRIBERS = 1_000_000

# Reddit's hard limit is ~10,500 subscriptions per account; 110 pages * 100 = 11,000.
# This cap guards against an infinite loop if Reddit returns a stuck cursor.
_MAX_PAGINATION_PAGES = 110

# Exclude private/banned subreddits with no subscribers — they carry no taste signal.
_MIN_SUBSCRIBERS = 1

_SCOPES = "identity mysubreddits"


@dataclass
class RedditClient:
    """ServiceClient for Reddit — OAuth 2.0.

    Fetches the authenticated user's subscribed subreddits, excluding
    mainstream communities with > 1M subscribers. Tokens expire every hour;
    refresh_token exchanges the stored refresh token for a new access token.
    """

    service_name: ClassVar[str] = "reddit"

    client_id: str
    client_secret: str
    redirect_uri: str
    http: httpx.Client = field(
        default_factory=lambda: httpx.Client(timeout=httpx.Timeout(15.0)), repr=False
    )

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> RedditClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _reddit_headers(self, access_token: str | None = None) -> dict[str, str]:
        headers: dict[str, str] = {"User-Agent": _USER_AGENT}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers

    def _token_expires_at(self, expires_in: int | None) -> datetime:
        seconds = expires_in if expires_in is not None else _TOKEN_LIFETIME_SECONDS
        return datetime.now(UTC) + timedelta(seconds=seconds)

    # ------------------------------------------------------------------
    # OAuth helpers
    # ------------------------------------------------------------------

    def get_authorize_url(self, state: str) -> str:
        """Return the Reddit authorization URL for the OAuth flow."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": state,
            "scope": _SCOPES,
            "duration": "permanent",
        }
        return f"{_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str) -> TokenPair:
        """Exchange an authorization code for an access + refresh token.

        Reddit requires HTTP Basic Auth (client_id:client_secret) for token exchange.
        Raises SyncClientError on HTTP or network error.
        """
        try:
            resp = self.http.post(
                _TOKEN_URL,
                data={
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                },
                headers=self._reddit_headers(),
                auth=(self.client_id, self.client_secret),
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SyncClientError(
                f"Reddit token exchange failed: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise SyncClientError(f"Could not reach Reddit: {exc}") from exc

        try:
            data = resp.json()
            return TokenPair(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                expires_at=self._token_expires_at(data.get("expires_in")),
            )
        except (ValueError, KeyError) as exc:
            raise SyncClientError(
                "Reddit returned an invalid token response — please retry"
            ) from exc

    def fetch_me(self, access_token: str) -> dict[str, Any]:
        """Return the authenticated user's profile dict (contains at least 'name').

        Used during the OAuth callback to store the Reddit username.
        Raises SyncClientError on failure.
        """
        try:
            resp = self.http.get(
                f"{_API_BASE}/api/v1/me",
                headers=self._reddit_headers(access_token),
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SyncClientError(
                f"Reddit profile fetch failed ({exc.response.status_code}): {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise SyncClientError(f"Could not reach Reddit: {exc}") from exc
        try:
            return cast(dict[str, Any], resp.json())
        except ValueError as exc:
            raise SyncClientError(
                "Reddit returned an invalid profile response — please retry"
            ) from exc

    # ------------------------------------------------------------------
    # ServiceClient protocol
    # ------------------------------------------------------------------

    def fetch_items(self, connection: ServiceConnection) -> list[RawItem]:
        """Fetch the authenticated user's subscribed subreddits.

        Excludes communities with > 1M subscribers (mainstream noise).
        raw_value = 1 / ln(subscribers + 2) — niche communities score higher.
        engagement_score is proportion-normalized within the fetched set.
        Raises SyncClientError for expected failures.
        """
        token_bytes: bytes | None = connection.access_token_encrypted
        if token_bytes is None:
            raise SyncClientError("Missing access token — reconnect Reddit via OAuth")
        access_token = decrypt_token(token_bytes)

        subreddits = self._fetch_subscribed_subreddits(access_token)
        return self._parse_subreddits(subreddits)

    def refresh_token(self, connection: ServiceConnection) -> TokenPair | None:
        """Exchange the stored refresh token for a fresh access token.

        Reddit tokens expire every hour; this must be called before sync
        when token_expires_at is in the past.
        Raises SyncClientError on failure.
        """
        refresh_bytes: bytes | None = connection.refresh_token_encrypted
        if refresh_bytes is None:
            raise SyncClientError("Missing refresh token — reconnect Reddit via OAuth")
        refresh = decrypt_token(refresh_bytes)

        try:
            resp = self.http.post(
                _TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                },
                headers=self._reddit_headers(),
                auth=(self.client_id, self.client_secret),
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SyncClientError(
                f"Reddit token refresh failed: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise SyncClientError(f"Could not reach Reddit: {exc}") from exc

        try:
            data = resp.json()
            return TokenPair(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                expires_at=self._token_expires_at(data.get("expires_in")),
            )
        except (ValueError, KeyError) as exc:
            raise SyncClientError(
                "Reddit returned an invalid token response — please retry"
            ) from exc

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_subscribed_subreddits(self, access_token: str) -> list[dict[str, Any]]:
        """Fetch all subscribed subreddits via paginated API calls.

        Raises SyncClientError on HTTP or network error.
        """
        results: list[dict[str, Any]] = []
        after: str | None = None

        for _ in range(_MAX_PAGINATION_PAGES):
            params: dict[str, Any] = {"limit": 100}
            if after:
                params["after"] = after

            try:
                resp = self.http.get(
                    f"{_API_BASE}/subreddits/mine/subscriber",
                    params=params,
                    headers=self._reddit_headers(access_token),
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    raise SyncClientError(
                        "Reddit token rejected — please reconnect your Reddit account"
                    ) from exc
                raise SyncClientError(
                    f"Reddit API error ({exc.response.status_code}): {exc.response.text}"
                ) from exc
            except httpx.RequestError as exc:
                raise SyncClientError(f"Could not reach Reddit: {exc}") from exc

            try:
                data = cast(dict[str, Any], resp.json())
            except ValueError as exc:
                raise SyncClientError(
                    "Reddit returned an invalid response — please retry"
                ) from exc

            listing = data.get("data") or {}
            children = listing.get("children") or []
            results.extend(child.get("data") or {} for child in children)

            after = listing.get("after")
            if not after or not children:
                break

        return results

    def _parse_subreddits(self, entries: list[dict[str, Any]]) -> list[RawItem]:
        """Convert raw subreddit dicts to RawItems.

        Filters out subreddits with > _MAX_SUBSCRIBERS.
        Normalizes engagement_score = raw_value / max_raw_value (proportion-based).
        """
        filtered = [
            e for e in entries
            if _MIN_SUBSCRIBERS <= (e.get("subscribers") or 0) <= _MAX_SUBSCRIBERS
            and e.get("display_name")
        ]
        if not filtered:
            return []

        def _raw_value(subscribers: int) -> float:
            return 1.0 / math.log(subscribers + 2)

        raw_values = [_raw_value(int(e.get("subscribers") or 0)) for e in filtered]
        max_raw = max(raw_values)

        result: list[RawItem] = []
        for entry, raw_val in zip(filtered, raw_values, strict=True):
            name: str = entry["display_name"]
            sub_id = entry.get("id") or name
            subscribers = int(entry.get("subscribers") or 0)
            description = (entry.get("public_description") or "")[:200]

            result.append(
                RawItem(
                    external_id=str(sub_id),
                    name=name,
                    item_type="community",
                    engagement_score=raw_val / max_raw,
                    raw_value=raw_val,
                    raw_type="consumption",
                    metadata={
                        "subreddit_name": name,
                        "subscribers": subscribers,
                        "description": description,
                    },
                    last_engaged_at=None,
                )
            )
        return result
