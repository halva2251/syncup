"""Steam Web API client (API key auth — no OAuth required)."""
from __future__ import annotations

import urllib.parse
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import ClassVar

import httpx

from syncup.db.models import ServiceConnection
from syncup.ingest.protocol import RawItem, SyncClientError, TokenPair

_API_BASE = "https://api.steampowered.com"
_OPENID_URL = "https://steamcommunity.com/openid/login"
_OPENID_ID_PREFIX = "https://steamcommunity.com/openid/id/"


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

        Raises SyncClientError if the vanity URL is not found.
        """
        resp = self.http.get(
            f"{_API_BASE}/ISteamUser/ResolveVanityURL/v1/",
            params={"key": self.api_key, "vanityurl": vanity},
        )
        resp.raise_for_status()
        body = resp.json()["response"]
        if body.get("success") != 1:
            msg = body.get("message", "unknown")
            raise SyncClientError(f"Vanity URL {vanity!r} not found: {msg}")
        return str(body["steamid"])

    def get_openid_authorize_url(
        self,
        state: str,
        return_to: str,
        realm: str,
    ) -> str:
        """Return the Steam OpenID 2.0 authorization URL."""
        # Embed state in the return_to query so we can validate it on callback.
        separator = "&" if "?" in return_to else "?"
        return_to_with_state = f"{return_to}{separator}state={urllib.parse.quote(state, safe='')}"
        params = {
            "openid.ns": "http://specs.openid.net/auth/2.0",
            "openid.mode": "checkid_setup",
            "openid.return_to": return_to_with_state,
            "openid.realm": realm,
            "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
            "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
        }
        return f"{_OPENID_URL}?{urllib.parse.urlencode(params)}"

    def validate_openid_assertion(
        self,
        params: dict[str, str],
        *,
        expected_return_to: str,
        expected_realm: str,
    ) -> str:
        """Validate a Steam OpenID assertion and return the Steam ID.

        Raises SyncClientError if validation fails.
        """
        if params.get("openid.op_endpoint") != _OPENID_URL:
            raise SyncClientError("Invalid Steam OpenID provider")

        if params.get("openid.return_to") != expected_return_to:
            raise SyncClientError("Invalid Steam OpenID return URL")

        realm = params.get("openid.realm")
        if realm is not None and realm != expected_realm:
            raise SyncClientError("Invalid Steam OpenID realm")

        identity = params.get("openid.identity")
        claimed_id = params.get("openid.claimed_id")
        if not identity or not claimed_id:
            raise SyncClientError("Missing Steam OpenID identity")
        if identity != claimed_id:
            raise SyncClientError("Steam OpenID identity mismatch")
        if not identity.startswith(_OPENID_ID_PREFIX):
            raise SyncClientError("Invalid Steam OpenID identity")

        steam_id = identity.removeprefix(_OPENID_ID_PREFIX)
        if not steam_id.isdigit():
            raise SyncClientError("Invalid Steam OpenID identity")

        validation = dict(params)
        validation["openid.mode"] = "check_authentication"
        resp = self.http.post(_OPENID_URL, data=validation)
        resp.raise_for_status()
        if "is_valid:true" not in resp.text:
            raise SyncClientError("Steam OpenID validation failed")

        return steam_id

    def get_owned_games(self, steam_id: str) -> list[dict]:  # type: ignore[type-arg]
        """Return the list of games owned by a Steam user.

        Each dict has at minimum: appid, name, playtime_forever (minutes).
        """
        if not steam_id:
            raise SyncClientError("steam_id must be a non-empty string")
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
            raise SyncClientError("steam_id must be a non-empty string")
        resp = self.http.get(
            f"{_API_BASE}/ISteamUser/GetPlayerSummaries/v2/",
            params={"key": self.api_key, "steamids": steam_id},
        )
        resp.raise_for_status()
        players = resp.json()["response"]["players"]
        if not players:
            raise SyncClientError(f"No Steam profile found for steam_id {steam_id!r}")
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
