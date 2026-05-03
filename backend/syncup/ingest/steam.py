"""Steam Web API client (API key auth — no OAuth required)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import ClassVar

import httpx

from syncup.db.models import ServiceConnection
from syncup.ingest.protocol import RawItem, TokenPair

_API_BASE = "https://api.steampowered.com"


@dataclass
class SteamClient:
    service_name: ClassVar[str] = "steam"

    api_key: str
    http: httpx.Client = field(
        default_factory=lambda: httpx.Client(timeout=httpx.Timeout(10.0)), repr=False
    )

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> SteamClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def resolve_vanity_url(self, vanity: str) -> str:
        """Resolve a Steam vanity URL to a 64-bit Steam ID.

        Raises ValueError if the vanity URL is not found.
        """
        resp = self.http.get(
            f"{_API_BASE}/ISteamUser/ResolveVanityURL/v1/",
            params={"key": self.api_key, "vanityurl": vanity},
        )
        resp.raise_for_status()
        body = resp.json()["response"]
        if body.get("success") != 1:
            raise ValueError(f"Vanity URL {vanity!r} not found: {body.get('message', 'unknown')}")
        return str(body["steamid"])

    def get_owned_games(self, steam_id: str) -> list[dict]:  # type: ignore[type-arg]
        """Return the list of games owned by a Steam user.

        Each dict has at minimum: appid, name, playtime_forever (minutes).
        """
        if not steam_id:
            raise ValueError("steam_id must be a non-empty string")
        resp = self.http.get(
            f"{_API_BASE}/IPlayerService/GetOwnedGames/v1/",
            params={
                "key": self.api_key,
                "steamid": steam_id,
                "include_appinfo": "true",
                "include_played_free_games": "true",
            },
        )
        resp.raise_for_status()
        return resp.json()["response"].get("games", [])  # type: ignore[no-any-return]

    def get_player_summary(self, steam_id: str) -> dict:  # type: ignore[type-arg]
        """Return the public profile dict for a single Steam user.

        Raises ValueError for an empty steam_id.
        """
        if not steam_id:
            raise ValueError("steam_id must be a non-empty string")
        resp = self.http.get(
            f"{_API_BASE}/ISteamUser/GetPlayerSummaries/v2/",
            params={"key": self.api_key, "steamids": steam_id},
        )
        resp.raise_for_status()
        players = resp.json()["response"]["players"]
        if not players:
            raise ValueError(f"No Steam profile found for steam_id {steam_id!r}")
        return players[0]  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # ServiceClient Protocol implementation
    # ------------------------------------------------------------------

    def fetch_items(self, connection: ServiceConnection) -> list[RawItem]:
        """Fetch all owned games for the connected Steam account."""
        steam_id: str = connection.external_user_id
        games = self.get_owned_games(steam_id)
        if not games:
            return []
        max_playtime = max((g.get("playtime_forever", 0) for g in games), default=1) or 1
        result: list[RawItem] = []
        for game in games:
            appid = str(game["appid"])
            playtime = float(game.get("playtime_forever", 0))
            rtime = game.get("rtime_last_played")
            last_at: datetime | None = (
                datetime.fromtimestamp(rtime, tz=UTC) if rtime else None
            )
            result.append(
                RawItem(
                    external_id=appid,
                    name=game.get("name", f"App {appid}"),
                    item_type="game",
                    engagement_score=playtime / max_playtime,
                    raw_value=playtime,
                    raw_type="consumption",
                    metadata={"img_icon_url": game.get("img_icon_url", "")},
                    last_engaged_at=last_at,
                )
            )
        return result

    def refresh_token(self, connection: ServiceConnection) -> TokenPair | None:
        """Steam uses an API key — no OAuth token refresh needed."""
        return None
