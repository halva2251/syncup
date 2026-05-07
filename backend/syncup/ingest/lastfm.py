"""Last.fm API client for fetching public user listening data."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

import httpx

from syncup.db.models import ServiceConnection
from syncup.ingest.protocol import RawItem, SyncClientError, TokenPair

_BASE_URL = "https://ws.audioscrobbler.com/2.0/"

_VALID_PERIODS = frozenset({"overall", "7day", "1month", "3month", "6month", "12month"})
_MIN_LIMIT = 1
_MAX_LIMIT = 1000


@dataclass
class LastfmClient:
    service_name: ClassVar[str] = "lastfm"

    api_key: str
    http: httpx.Client = field(
        default_factory=lambda: httpx.Client(timeout=httpx.Timeout(10.0)), repr=False
    )

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> LastfmClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _validate_period(self, period: str) -> None:
        if period not in _VALID_PERIODS:
            valid = sorted(_VALID_PERIODS)
            raise ValueError(f"period must be one of {valid}, got {period!r}")

    def _validate_limit(self, limit: int) -> None:
        if not _MIN_LIMIT <= limit <= _MAX_LIMIT:
            raise ValueError(f"limit must be {_MIN_LIMIT}–{_MAX_LIMIT}, got {limit}")

    def _validate_username(self, username: str) -> None:
        if not username:
            raise SyncClientError("username must be a non-empty string")

    def _check_api_error(self, body: dict) -> None:  # type: ignore[type-arg]
        if "error" in body:
            code = body["error"]
            message = body.get("message", "")
            raise SyncClientError(f"Last.fm API error {code}: {message}")

    def get_top_artists(
        self,
        username: str,
        limit: int = 50,
        period: str = "overall",
    ) -> list[dict]:  # type: ignore[type-arg]
        """Fetch a user's top artists from Last.fm.

        Args:
            username: Last.fm username.
            limit: Number of results to return (1–1000).
            period: Time period — one of overall, 7day, 1month, 3month, 6month, 12month.

        Returns:
            List of artist dicts, each containing at minimum name, playcount, and mbid.
        """
        self._validate_username(username)
        self._validate_period(period)
        self._validate_limit(limit)

        resp = self.http.get(
            _BASE_URL,
            params={
                "method": "user.getTopArtists",
                "user": username,
                "limit": limit,
                "period": period,
                "api_key": self.api_key,
                "format": "json",
            },
        )
        resp.raise_for_status()
        body: dict = resp.json()
        self._check_api_error(body)
        return body["topartists"]["artist"]  # type: ignore[no-any-return]

    def get_top_tracks(
        self,
        username: str,
        limit: int = 50,
        period: str = "overall",
    ) -> list[dict]:  # type: ignore[type-arg]
        """Fetch a user's top tracks from Last.fm.

        Args:
            username: Last.fm username.
            limit: Number of results to return (1–1000).
            period: Time period — one of overall, 7day, 1month, 3month, 6month, 12month.

        Returns:
            List of track dicts.
        """
        self._validate_username(username)
        self._validate_period(period)
        self._validate_limit(limit)

        resp = self.http.get(
            _BASE_URL,
            params={
                "method": "user.getTopTracks",
                "user": username,
                "limit": limit,
                "period": period,
                "api_key": self.api_key,
                "format": "json",
            },
        )
        resp.raise_for_status()
        body: dict = resp.json()
        self._check_api_error(body)
        return body["toptracks"]["track"]  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # ServiceClient Protocol implementation
    # ------------------------------------------------------------------

    def fetch_items(self, connection: ServiceConnection) -> list[RawItem]:
        """Fetch top artists and tracks for the connected Last.fm account."""
        username: str = connection.external_user_id
        top_artists = self.get_top_artists(username, limit=50, period="overall")
        top_tracks = self.get_top_tracks(username, limit=50, period="overall")

        result: list[RawItem] = []

        if top_artists:
            max_plays = (
                max((float(a.get("playcount", 0)) for a in top_artists), default=1.0) or 1.0
            )
            for artist in top_artists:
                external_id = artist.get("mbid") or artist["name"]
                playcount = float(artist.get("playcount", 0))
                result.append(
                    RawItem(
                        external_id=external_id,
                        name=artist["name"],
                        item_type="artist",
                        engagement_score=playcount / max_plays,
                        raw_value=playcount,
                        raw_type="consumption",
                        metadata={},
                        last_engaged_at=None,
                    )
                )

        if top_tracks:
            max_plays = (
                max((float(t.get("playcount", 0)) for t in top_tracks), default=1.0) or 1.0
            )
            for track in top_tracks:
                artist_name = track.get("artist", {}).get("name", "")
                external_id = track.get("mbid") or f"{track['name']}::{artist_name}"
                playcount = float(track.get("playcount", 0))
                result.append(
                    RawItem(
                        external_id=external_id,
                        name=track["name"],
                        item_type="track",
                        engagement_score=playcount / max_plays,
                        raw_value=playcount,
                        raw_type="consumption",
                        metadata={"artist": artist_name},
                        last_engaged_at=None,
                    )
                )

        return result

    def refresh_token(self, connection: ServiceConnection) -> TokenPair | None:
        """Last.fm uses an API key — no OAuth token refresh needed."""
        return None
