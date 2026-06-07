"""GET /api/me/taste — aggregated taste profile."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from syncup.auth.router import RequireAuth
from syncup.db.models import Item, ManualObsession, PreferenceOverride, UserItem
from syncup.db.session import get_db
from syncup.limiter import limiter

router = APIRouter(prefix="/api/me", tags=["taste"])

_TASTE_TOP_N = 20


# ---------------------------------------------------------------------------
# Output schemas
# ---------------------------------------------------------------------------


class TasteItemOut(BaseModel):
    id: str
    name: str
    score: float


class SteamGameOut(TasteItemOut):
    hours: float


class LastfmArtistOut(TasteItemOut):
    play_count: float | None


class LastfmTrackOut(TasteItemOut):
    artist: str
    play_count: float | None


class SpotifyArtistOut(TasteItemOut):
    pass


class SpotifyTrackOut(TasteItemOut):
    artists: list[str]


class SteamServiceOut(BaseModel):
    top_games: list[SteamGameOut]


class LastfmServiceOut(BaseModel):
    top_artists: list[LastfmArtistOut]
    top_tracks: list[LastfmTrackOut]
    top_tags: list[str] = []


class SpotifyServiceOut(BaseModel):
    top_artists: list[SpotifyArtistOut]
    top_tracks: list[SpotifyTrackOut]


class LetterboxdFilmOut(TasteItemOut):
    release_year: int


class LetterboxdServiceOut(BaseModel):
    top_films: list[LetterboxdFilmOut]


class RateYourMusicAlbumOut(TasteItemOut):
    release_year: int
    artist: str


class RateYourMusicServiceOut(BaseModel):
    top_albums: list[RateYourMusicAlbumOut]


class ServicesOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    steam: SteamServiceOut | None = None
    lastfm: LastfmServiceOut | None = None
    spotify: SpotifyServiceOut | None = None
    letterboxd: LetterboxdServiceOut | None = None
    rateyourmusic: RateYourMusicServiceOut | None = None


class ManualObsessionOut(BaseModel):
    id: uuid.UUID
    category: str
    name: str
    weight: float


class OverrideItemOut(BaseModel):
    name: str


class PreferenceOverrideOut(BaseModel):
    id: uuid.UUID
    item: OverrideItemOut
    boost_multiplier: float


class TasteOut(BaseModel):
    services: ServicesOut
    manual_obsessions: list[ManualObsessionOut]
    overrides: list[PreferenceOverrideOut]


# ---------------------------------------------------------------------------
# Row → schema converters
# ---------------------------------------------------------------------------


def _to_steam_game(row: Any) -> SteamGameOut:
    return SteamGameOut(
        id=row.external_id,
        name=row.name,
        score=row.engagement_score,
        hours=round((row.raw_value or 0.0) / 60, 1),
    )


def _to_lastfm_artist(row: Any) -> LastfmArtistOut:
    return LastfmArtistOut(
        id=row.external_id,
        name=row.name,
        score=row.engagement_score,
        play_count=row.raw_value,
    )


def _to_lastfm_track(row: Any) -> LastfmTrackOut:
    return LastfmTrackOut(
        id=row.external_id,
        name=row.name,
        score=row.engagement_score,
        artist=row.meta.get("artist", ""),
        play_count=row.raw_value,
    )


def _to_spotify_artist(row: Any) -> SpotifyArtistOut:
    return SpotifyArtistOut(
        id=row.external_id,
        name=row.name,
        score=row.engagement_score,
    )


def _to_spotify_track(row: Any) -> SpotifyTrackOut:
    return SpotifyTrackOut(
        id=row.external_id,
        name=row.name,
        score=row.engagement_score,
        artists=row.meta.get("artists", []),
    )


def _to_letterboxd_film(row: Any) -> LetterboxdFilmOut:
    return LetterboxdFilmOut(
        id=row.external_id,
        name=row.name,
        score=row.engagement_score,
        release_year=row.meta.get("release_year", 0),
    )


def _to_rateyourmusic_album(row: Any) -> RateYourMusicAlbumOut:
    return RateYourMusicAlbumOut(
        id=row.external_id,
        name=row.name,
        score=row.engagement_score,
        release_year=row.meta.get("release_year", 0),
        artist=row.meta.get("artist_normalized", ""),
    )


_CONVERTERS: dict[tuple[str, str], Callable[[Any], TasteItemOut]] = {
    ("steam", "game"): _to_steam_game,
    ("lastfm", "artist"): _to_lastfm_artist,
    ("lastfm", "track"): _to_lastfm_track,
    ("spotify", "artist"): _to_spotify_artist,
    ("spotify", "track"): _to_spotify_track,
    ("letterboxd", "film"): _to_letterboxd_film,
    ("rateyourmusic", "album"): _to_rateyourmusic_album,
}


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.get("/taste", response_model=TasteOut, response_model_exclude_none=True)
@limiter.limit("30/minute")
def get_taste(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    user: RequireAuth,
) -> TasteOut:
    """Return the authenticated user's aggregated taste profile."""
    rn = (
        func.row_number()
        .over(
            partition_by=[Item.service, Item.item_type],
            order_by=UserItem.engagement_score.desc(),
        )
        .label("rn")
    )

    subq = (
        select(
            UserItem.engagement_score,
            UserItem.raw_value,
            Item.external_id,
            Item.service,
            Item.item_type,
            Item.name,
            Item.meta,
            rn,
        )
        .join(Item, UserItem.item_id == Item.id)
        .where(UserItem.user_id == user.id)
        .subquery()
    )

    taste_rows = db.execute(
        select(subq).where(subq.c.rn <= _TASTE_TOP_N).order_by(subq.c.engagement_score.desc())
    ).all()

    groups: defaultdict[tuple[str, str], list] = defaultdict(list)
    for row in taste_rows:
        groups[(row.service, row.item_type)].append(row)

    def _build(svc: str, itype: str) -> list:
        converter = _CONVERTERS.get((svc, itype))
        if converter is None:
            return []
        return [converter(r) for r in groups[(svc, itype)]]

    steam_games = _build("steam", "game")
    lastfm_artists = _build("lastfm", "artist")
    lastfm_tracks = _build("lastfm", "track")
    spotify_artists = _build("spotify", "artist")
    spotify_tracks = _build("spotify", "track")
    letterboxd_films = _build("letterboxd", "film")
    rym_albums = _build("rateyourmusic", "album")

    steam = SteamServiceOut(top_games=steam_games) if steam_games else None
    lastfm = (
        LastfmServiceOut(top_artists=lastfm_artists, top_tracks=lastfm_tracks)
        if lastfm_artists or lastfm_tracks
        else None
    )
    spotify = (
        SpotifyServiceOut(top_artists=spotify_artists, top_tracks=spotify_tracks)
        if spotify_artists or spotify_tracks
        else None
    )
    letterboxd = LetterboxdServiceOut(top_films=letterboxd_films) if letterboxd_films else None
    rateyourmusic = RateYourMusicServiceOut(top_albums=rym_albums) if rym_albums else None

    obsessions = db.scalars(
        select(ManualObsession)
        .where(ManualObsession.user_id == user.id)
        .order_by(ManualObsession.created_at.desc())
        .limit(100)
    ).all()

    override_rows = db.execute(
        select(
            PreferenceOverride.id,
            PreferenceOverride.boost_multiplier,
            Item.name.label("item_name"),
        )
        .join(Item, PreferenceOverride.item_id == Item.id)
        .where(PreferenceOverride.user_id == user.id)
        .order_by(PreferenceOverride.created_at.desc())
    ).all()

    return TasteOut(
        services=ServicesOut(
            steam=steam,
            lastfm=lastfm,
            spotify=spotify,
            letterboxd=letterboxd,
            rateyourmusic=rateyourmusic,
        ),
        manual_obsessions=[
            ManualObsessionOut(
                id=o.id,
                category=o.category,
                name=o.name,
                weight=o.weight,
            )
            for o in obsessions
        ],
        overrides=[
            PreferenceOverrideOut(
                id=row.id,
                item=OverrideItemOut(name=row.item_name),
                boost_multiplier=row.boost_multiplier,
            )
            for row in override_rows
        ],
    )
