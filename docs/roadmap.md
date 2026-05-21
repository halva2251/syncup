# SyncUp — Implementation Roadmap

Concrete, ordered build plan. Strategy and "why" lives in [product-strategy.md](product-strategy.md). This document is about what to build, in what order, and where we stand.

---

## Current Status

### Done ✅

| What | Where |
|------|-------|
| PostgreSQL + pgvector setup (Docker) | `backend/docker-compose.yml` |
| Database schema + Alembic migration | `backend/alembic/` |
| Token encryption (AES-GCM) | `syncup/ingest/crypto.py` |
| Auth routes (signup, login, logout, sessions) | `syncup/auth/router.py` |
| Spotify OAuth + PKCE callback | `syncup/ingest/spotify.py`, `syncup/api/app.py` |
| Steam connect (steam_id or vanity URL) | `syncup/api/routes/connect.py` |
| Last.fm connect (username probe) | `syncup/api/routes/connect.py` |
| `GET /api/me` — user + service statuses | `syncup/api/routes/me.py` |
| `SpotifyClient`, `SteamClient`, `LastfmClient` | `syncup/ingest/` |
| Item2Vec training infrastructure | `syncup/embeddings/item2vec.py` |
| User embedding builder | `syncup/embeddings/user_embeddings.py` |
| Cosine similarity matching engine | `syncup/matching/engine.py` |
| Rate limiting (signup 5/min, login 10/min) | `syncup/limiter.py` |
| `POST /api/sync/{service}` — background data pull (Steam, Spotify, Last.fm) | `syncup/api/routes/sync.py` |
| `GET /api/me/taste` — aggregated taste profile (top items, obsessions, overrides) | `syncup/api/routes/taste.py` |
| `GET/POST/DELETE /api/me/obsessions` — manual taste entries | `syncup/api/routes/obsessions.py` |
| `GET/POST/PATCH/DELETE /api/me/overrides` — preference overrides (boost/demote items) | `syncup/api/routes/overrides.py` |
| `GET/PATCH /api/me/dimensions` — per-service dimension weights (normalised to 1.0) | `syncup/api/routes/dimensions.py` |
| `PATCH /api/me` — profile edit (`display_name`, `bio`, `discord_handle`, `avatar_url`, `is_matchable`) | `syncup/api/routes/me.py` |
| `GET /api/onboarding/status` — onboarding progress: booleans + `next_step` hint | `syncup/api/routes/onboarding.py` |
| `languages` field on `users` — nullable TEXT[], skippable during onboarding | `syncup/db/models.py`, migration `20260502_0003` |
| `GET /api/matches` + `GET /api/matches/{user_id}` + `POST /api/me/recompute` — heuristic matching | `syncup/api/routes/matches.py` |
| `match_cache.highlights` JSONB — cached top shared items per match pair | `syncup/db/models.py`, migration `20260502_0004` |
| `updated_at` DB trigger on `users` | migration `20260502_0005` |
| `ServiceClient` Protocol + `RawItem` TypedDict | `syncup/ingest/protocol.py` |
| `ServiceRegistry` — service-agnostic dispatch | `syncup/ingest/registry.py` |
| Migration 0006 — `raw_type TEXT` column on `user_items` | migration `20260503_0006` |
| Migration 0007 — expanded `manual_obsessions.category` CHECK | migration `20260503_0007` |
| `SteamClient`, `SpotifyClient`, `LastfmClient` — retrofitted to satisfy Protocol | `syncup/ingest/{steam,spotify,lastfm}.py` |
| Sync route generic dispatch via registry | `syncup/api/routes/sync.py` |
| Dimensions route dynamic service validation | `syncup/api/routes/dimensions.py` |
| `register_default_clients()` in app lifespan | `syncup/api/app.py` |
| AniList, Trakt, Reddit OAuth env vars | `syncup/config.py` |
| `normalize_title()` utility for cross-service film dedup | `syncup/ingest/_text.py` |
| 384 passing tests | `backend/tests/` |
| `SyncClientError` — user-safe exception class; sync task trusts its message | `syncup/ingest/protocol.py` |
| `SteamClient`, `SpotifyClient`, `LastfmClient` — raise `SyncClientError` in sync path | `syncup/ingest/{steam,spotify,lastfm}.py` |
| `LetterboxdClient` — CSV import, `parse_csv()`, Protocol conformance | `syncup/ingest/letterboxd.py` |
| `POST /api/connect/letterboxd/import` — multipart CSV, wipe-and-replace, 10 MB cap | `syncup/api/routes/connect.py` |
| `python-multipart` dependency added | `backend/pyproject.toml` |
| 417 passing tests | `backend/tests/` |
| `AniListClient` — GraphQL OAuth, combined ANIME+MANGA query, multi-format score normalization | `syncup/ingest/anilist.py` |
| `GET /api/connect/anilist/oauth/start` + `GET /api/connect/anilist/oauth/callback` | `syncup/api/routes/connect.py` |
| `AniListClient` registered in `register_default_clients` (when credentials present) | `syncup/ingest/registry.py` |
| 458 passing tests | `backend/tests/` |
| `TraktClient` — REST OAuth, watched movies + shows, proportion-based engagement_score normalization per type | `syncup/ingest/trakt.py` |
| `GET /api/connect/trakt/oauth/start` + `GET /api/connect/trakt/oauth/callback` | `syncup/api/routes/connect.py` |
| `TraktClient` registered in `register_default_clients` (when credentials present) | `syncup/ingest/registry.py` |
| 518 passing tests | `backend/tests/` |
| `RedditClient` — OAuth 2.0, subscribed subreddits, `> 1M` filter, `1/ln(subs+2)` niche scoring | `syncup/ingest/reddit.py` |
| `GET /api/connect/reddit/oauth/start` + `GET /api/connect/reddit/oauth/callback` | `syncup/api/routes/connect.py` |
| `RedditClient` registered in `register_default_clients` (when credentials present) | `syncup/ingest/registry.py` |
| 577 passing tests | `backend/tests/` |
| `RateYourMusicClient` — CSV import, `Title`/`Release_Date`/`Rating` columns, year extraction, `(rating - 1) / 9.0` normalization (1–10 integer scale) | `syncup/ingest/rateyourmusic.py` |
| `POST /api/connect/rateyourmusic/import` — multipart CSV, wipe-and-replace, 10 MB cap | `syncup/api/routes/connect.py` |
| `RateYourMusicClient` registered in `register_default_clients` | `syncup/ingest/registry.py` |
| RateYourMusic added to `GET /api/me/taste` — renders `services.rateyourmusic.top_albums` | `syncup/api/routes/taste.py` |
| 620 passing tests | `backend/tests/` |

---

## Phase 1.10 — Service Expansion

**Goal:** Add Letterboxd, AniList, Trakt, Reddit, and RateYourMusic to the ingest pipeline. Introduce a `ServiceClient` Protocol so every future service slots in without touching the sync route.

> **Status:** Foundation complete ✅ (F1–F7 landed, 2026-05-03). S1 complete ✅ (2026-05-07). S2 complete ✅ (2026-05-08). S3 complete ✅ (2026-05-08). S4 complete ✅ (2026-05-09). S5 complete ✅ (2026-05-10).

### F1–F7 Foundation (single PR)

All foundation steps are coupled and must ship together:

| Step | What | Why |
|------|------|-----|
| F1 | `syncup/ingest/protocol.py` — `ServiceClient` Protocol + `RawItem` TypedDict | Defines the contract every ingest client must satisfy |
| F2 | `syncup/ingest/registry.py` — `ServiceRegistry` | Service-agnostic dispatch; eliminates if/elif chains in sync route |
| F3 | Migration 0006 — `raw_type TEXT` on `user_items` | Distinguishes consumption signals (hours, scrobbles) from rating signals (stars) for the embedding builder |
| F4 | Dynamic service validation in dimensions route | Replace hardcoded `{"steam","lastfm","spotify"}` with `registered_services()` |
| F5 | Migration 0007 — expand `manual_obsessions.category` CHECK | Add `'anime'`, `'manga'`, `'community'` |
| F6 | Retrofit `steam.py`, `spotify.py`, `lastfm.py` to satisfy Protocol | Add `service_name: ClassVar[str]`, register in registry |
| F7 | Sync route goes generic | Calls `get_client(service).fetch_items(connection)` for any service |

**Migration 0006 SQL:**
```sql
ALTER TABLE user_items
    ADD COLUMN raw_type TEXT NOT NULL DEFAULT 'consumption'
    CHECK (raw_type IN ('consumption', 'rating'));
```

**Migration 0007 SQL:**
```sql
ALTER TABLE manual_obsessions
    DROP CONSTRAINT manual_obsessions_category_check,
    ADD CONSTRAINT manual_obsessions_category_check
        CHECK (category IN ('game','music','film','book','show','anime','manga','community','other'));
```

### S1 — Letterboxd (CSV import)

- Endpoint: `POST /api/connect/letterboxd/import` (multipart file upload)
- Format: Letterboxd diary export CSV — uses `Name`, `Year`, `Rating` columns
- Rating normalization: `(rating - 0.5) / 4.5` → `engagement_score`
- `item_type = 'film'`, `raw_type = 'rating'`
- Metadata: `{"title_normalized": str, "release_year": int}`
- Re-import: wipe-and-replace in a DB transaction
- File size cap: 10 MB
- No OAuth; connection row set to `sync_status = 'ok'` after successful import

**Also lands in S1 PR (bundled — touches the same protocol layer):**
- Add `SyncClientError` to `syncup/ingest/protocol.py` — a custom exception class for expected, user-safe errors raised by service clients. The generic sync task's `_safe_error_message` will trust `SyncClientError` messages and treat all other exceptions (including third-party `ValueError`) as a generic "Sync failed — please retry". Retrofit `SteamClient`, `SpotifyClient`, `LastfmClient` to raise `SyncClientError` instead of `ValueError` in `fetch_items()` and `refresh_token()`. `LetterboxdClient` uses it from day one.

### S2 — AniList (GraphQL OAuth)

- Auth: OAuth 2.0 authorization code flow
- Fetch: `MediaListCollection` query for ANIME + MANGA lists; skip score=0 entries
- Rating normalization: `score / 100.0` → `engagement_score`
- `item_type = 'anime'` or `'manga'`, `raw_type = 'rating'`
- Metadata: `{"title_normalized": str, "release_year": int, "format": str}`

### S3 — Trakt.tv (REST OAuth)

- Auth: OAuth 2.0 authorization code flow; tokens expire in 3 months
- Fetch: `/users/me/watched/movies` (films) + `/users/me/watched/shows` (shows)
- `raw_value = plays` for films, `raw_value = episodes_watched` for shows, `raw_type = 'consumption'`
- `item_type = 'film'` or `'show'`
- Metadata: `{"title_normalized": str, "release_year": int}`
- **Film deduplication with Letterboxd**: items remain service-specific in DB but heuristic + embedding layer match films on `(title_normalized, release_year)` across services — a film shared between Letterboxd and Trakt counts as one shared item in scoring

### S4 — Reddit (OAuth)

- Auth: OAuth 2.0, scopes `identity mysubreddits`; read-only
- Fetch: `/subreddits/mine/subscriber` (paginated)
- **Filter**: exclude subreddits with `subscribers > 1_000_000` (mainstream noise, not taste signal)
- `raw_value = 1 / log(subscribers + 2)` — niche communities score higher
- `raw_type = 'consumption'`, `item_type = 'community'`
- Metadata: `{"subreddit_name": str, "subscribers": int, "description": str (first 200 chars)}`

### S5 — RateYourMusic (CSV import)

- Same CSV import flow as Letterboxd
- Format: RateYourMusic export — uses `Title`, `Release_Date` (year), `Rating` columns
- `item_type = 'album'`, `raw_type = 'rating'`
- Rating normalization: `(rating - 0.5) / 4.5` → `engagement_score` (same as Letterboxd)

### Services explicitly NOT building (with reasons)

| Service | Reason |
|---------|--------|
| Twitter/X | API now paid, expensive, severe rate limits — no viable path |
| Instagram | Meta locked personal data API post-Cambridge Analytica; only business accounts work |
| IMDB | No public API; never had one |
| Goodreads | Amazon shut down the API in December 2020 |
| YouTube Music | Distinct from YouTube; YouTube Data API v3 does not expose music listening history |
| SoundCloud | API exists but has been unreliable and poorly documented; revisit when stable |
| PlayStation Network / Xbox Network | Limited API access; defer until user base skews console |

### Tier 2 services (deferred, not blocked)

| Service | Notes |
|---------|-------|
| Apple Music | MusicKit JWT auth is non-trivial server-side; implement after Tier 1 is stable |
| StoryGraph | No public API yet; CSV import when ready |

### Rating normalization reference

All service ratings are normalized to `engagement_score ∈ [0, 1]`. Raw values are preserved in `raw_value`.

| Service | Raw scale | Formula |
|---------|-----------|---------|
| Letterboxd | 0.5–5.0 (half-stars) | `(rating - 0.5) / 4.5` |
| RateYourMusic | 1–10 (integers, 10 = 5 stars) | `(rating - 1) / 9.0` |
| AniList | 0–100 | `rating / 100.0` |
| Trakt | 1–10 | `(rating - 1) / 9.0` |
| Steam | minutes played | `playtime / max_playtime` — proportion-based |
| Last.fm | scrobble count | `count / max_count` — proportion-based |
| Spotify (artists) | rank | `(n - i) / n` — rank-based |
| Spotify (tracks) | play count | `count / max_count` — proportion-based |

Proportion-based normalization is applied by each client in `fetch_items()`. Log1p dampening (for handling outliers) is applied by the embedding builder during item2vec training, not in `user_items`. Ratings of 0 (AniList "not rated") are treated as absent — item is not stored.

---

## Phase 1.11 — Backend Hardening Sprint

**Goal:** address 8 CRITICAL and 18 HIGH security/reliability issues found during audit. Gate for Phase 2.1 (ML training).

> **Status:** Branch 1 (fix/security-hardening) complete ✅ (2026-05-09). Branch 2 (fix/ingest-hardening) complete ✅ (2026-05-09). Branch 3 (fix/db-hardening) complete ✅ (2026-05-12). Branch 4 (fix/api-quality) complete ✅ (2026-05-12). OAuth follow-up (fix/oauth-security-h1-h2-h3) complete ✅ (2026-05-19): Spotify auth start auth guard + rate limit, encryption key length validated at startup, AniList GraphQL error forwarding fixed. 722 tests passing. Phase 1.11 sprint complete — gate for Phase 2.1 (ML training) is now open.

### Branch 1: fix/security-hardening

Security-critical OAuth and config hardening. All 12 items merged.

| Item | What | Status |
|------|------|--------|
| S1 | Timing-safe OAuth state validation with `secrets.compare_digest()` in all 4 OAuth callbacks | ✅ |
| S2 | Unconditional encryption key guard at startup (remove debug mode bypass) | ✅ |
| S3 | Strip upstream error response bodies from `SyncUpError` messages; log server-side only | ✅ |
| S4 | Switch rate limiter to trust `X-Forwarded-For` via `ProxyHeadersMiddleware` | ✅ |
| S5 | All `delete_cookie()` calls use matching attributes (`httponly`, `samesite`, `secure`, `path`) | ✅ |
| S6 | Add security headers middleware: CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy | ✅ |
| S7 | Database URL required at startup; no hardcoded default | ✅ |
| S8 | Rate limit on `POST /api/auth/logout` (30/min) to prevent session enumeration | ✅ |
| S9 | CORS origin parsing raises hard error if misconfigured (not in debug mode) | ✅ |
| S10 | Prevent error message injection: replace dynamic Reddit error string with static message | ✅ |
| S11 | Session secret default changed from `""` to `None` to distinguish unset from intentionally blank | ✅ |
| S12 | Remove version string from `GET /api/health` to prevent backend fingerprinting | ✅ |

### Branch 2: fix/ingest-hardening (complete ✅ 2026-05-09)

Client error handling, token lifecycle, and ingest robustness.

| Item | What | Status |
|------|------|--------|
| I1+M2 | Strip `exc.response.text` and `{exc}` from `SyncClientError`/`SyncUpError` messages in AniList, Trakt, Reddit clients and Steam/Last.fm/AniList connect routes; log details server-side | ✅ |
| I3 | Add token expiry guard to `TraktClient.refresh_token()` and `RedditClient.refresh_token()` — return `None` if token still valid (expires > 5 min from now); treat `None` expiry as expired | ✅ |
| I4 | Add `close_all()` to `registry.py`; call from app lifespan shutdown to release httpx connections | ✅ |
| I5 | `LastfmClient._validate_period()` and `_validate_limit()` now raise `SyncClientError` instead of `ValueError` | ✅ |
| I6 | Last.fm artist `external_id` fallback uses `normalize_title(name)` instead of raw name | ✅ |
| I7 | `normalize_title()` expands ligatures (Œ→OE, Æ→AE, ß→ss) before NFD accent-stripping | ✅ |
| I8 | `trigger_sync` route validates `app.state.db` exists before adding background task | ✅ |
| I9 | CSV imports (Letterboxd, RateYourMusic) reject >50,000 rows with 422 FILE_TOO_LARGE | ✅ |
| I10 | `engagement_score` clamped to [0.0, 1.0] in `_do_sync_generic` before upsert | ✅ |

### Branch 3: fix/db-hardening (complete ✅ 2026-05-12)

Background cleanup jobs, unbounded queries, atomicity, index maintenance.

| Item | What | Status |
|------|------|--------|
| D1 | `match_cache` hourly cleanup task + `idx_match_cache_computed_at` index | ✅ |
| D2 | `_load_cached_matches`: push `LIMIT+1`/`OFFSET` pagination to DB; returns `(rows, has_more)` | ✅ |
| D3 | `GET /api/me/taste` unbounded query → `ROW_NUMBER() OVER (PARTITION BY service, item_type)` window function | ✅ |
| D4 | `PATCH /api/me/dimensions` atomicity: wrap `DELETE`+`INSERT` in single `try/except` | ✅ |
| D5 | `idx_obsessions_item` partial index (`WHERE item_id IS NOT NULL`) | ✅ |
| D6 | `idx_overrides_item` index on `preference_overrides.item_id` | ✅ |
| D7 | `_refresh_match_cache` phase split: read → compute (pure Python) → write (short transaction) | ✅ |
| D8 | `require_auth`: replace 2× `db.get()` with single session–user `JOIN` query | ✅ |
| D9 | `User.updated_at`: remove `onupdate=func.now()` (DB trigger in migration 0005 owns it) | ✅ |
| D10 | UUID pair ordering test: `user_a_id < user_b_id` invariant verified | ✅ |
| D11 | `UserItem.fetched_at`: add `default=_now` for Python-side ORM inserts | ✅ |
| D12 | `idx_sync_status` partial index (`WHERE sync_status IN ('syncing','error')`) | ✅ |
| D13 | `UserEmbedding.computed_at`: add `default=_now` for Python-side ORM inserts | ✅ |
| D14 | IVFFlat index on `user_embeddings` — **deferred to Phase 2.1** (requires trained embeddings) | ⏸ |

### Branch 4: fix/api-quality (complete ✅ 2026-05-12)

Sync visibility, response schemas, cursor pagination, input validation, onboarding fixes.

| Item | What | Status |
|------|------|--------|
| A1 | `_set_sync_error`: narrow `except Exception` → `except SQLAlchemyError`; add `poll_url` to `SyncTriggeredOut` | ✅ |
| A2 | `signup`/`login`: add `response_model=AuthOut` for OpenAPI accuracy | ✅ |
| A3 | Match pagination: replace offset cursor with keyset on `(score DESC, user_b_id ASC)` — stable across cache refreshes | ✅ |
| A4 | Whitespace strip+validate on `display_name`/`bio`/`discord_handle` (signup, PATCH /me) and obsession `name` | ✅ |
| A5 | `ObsessionIn.weight`: add `le=10.0` upper bound; `_Category`: add `anime`/`manga`/`community` (matches DB CHECK) | ✅ |
| A6 | `OverrideIn` and `OverridePatch.boost_multiplier`: add `le=10.0`; remove redundant custom validator | ✅ |
| A7 | Onboarding `has_taste_data`: real `UserItem` count query (was incorrectly aliased from `has_connection_or_obsessions`) | ✅ |
| A8 | Onboarding `next_step`: `set_display_name` is now first in the decision chain (before `connect_service`) | ✅ |
| A9 | `RequestValidationError` handler: structured `{code, message, details}` response; ctx values sanitized for JSON | ✅ |
| A10 | Spotify OAuth routes moved from `app.py` → `routes/connect.py` (`spotify_auth_router`); URLs unchanged | ✅ |
| A11 | `lifespan` return type: `AsyncGenerator[None, None]` (removes `# type: ignore`) | ✅ |
| A12 | `_CONVERTERS`: typed as `dict[tuple[str,str], Callable[[Any], TasteItemOut]]` | ✅ |
| A13 | `MatchUserOut.model_config`: `ConfigDict(from_attributes=True)` instead of plain dict | ✅ |

---

## Phase 1 — Sync & Taste Profile

**Goal:** users connect their services, data gets pulled into the database, and they can see their taste profile. Matching not yet required.

### 1.1 Sync Routes

`POST /api/sync/{service}` — trigger a background data pull from a connected service.

For each service:
- Check the user has a `service_connections` row in `ok` status
- Set `sync_status = 'syncing'`
- Fetch items from the service API (`SpotifyClient`, `SteamClient`, `LastfmClient`)
- Upsert into `items` (canonical catalog) and `user_items` (per-user engagement)
- Set `sync_status = 'ok'`, update `last_synced_at`
- On any error: set `sync_status = 'error'`, write `sync_error`

Return `{ "status": "syncing" }` immediately; actual work runs in the background (Starlette `BackgroundTasks` is fine for now — no Celery needed yet).

**Spotify note:** access tokens expire in 1 hour. Before fetching, check `token_expires_at` — if expired, call `client.refresh_access_token()` and update the row.

### 1.2 Taste Profile Endpoint

`GET /api/me/taste` — aggregated taste view combining all connected services + manual obsessions.

Response shape (see [api-contract.md](api-contract.md) §4 for the full spec):
- Per-service top items
- Manual obsessions
- Preference overrides

This is also the foundation for the shareable taste card (Phase 3).

### 1.3 Manual Obsessions

`POST /api/me/obsessions` — let users add freeform items (books, niche albums, games not on their platforms).
`GET /api/me/obsessions`
`DELETE /api/me/obsessions/{id}`

These feed directly into the user's match profile and lower the matchability threshold (3 obsessions = matchable, no service connection required).

### 1.4 Preference Overrides

`POST /api/me/overrides` — boost or demote an item's weight in the user's vector (e.g. "I love Disco Elysium despite low playtime").
`PATCH /api/me/overrides/{id}`
`DELETE /api/me/overrides/{id}`

### 1.5 Dimension Weights

`GET /api/me/dimensions` — current per-service weights.
`PATCH /api/me/dimensions` — update weights; backend normalises to sum to 1.0.

### 1.6 Profile Edit

`PATCH /api/me` — let users set `display_name`, `bio`, `discord_handle`, `is_matchable`, `avatar_url`.

### 1.7 Onboarding Status ✅

`GET /api/onboarding/status` — tells the frontend which onboarding steps are still pending so it can route the user correctly.

**Onboarding order (confirmed):**
1. Display name (always set at signup)
2. Languages spoken (`users.languages`, nullable TEXT[], skippable)
3. Freeform interests / likes / dislikes (map to `manual_obsessions` during onboarding)
4. Connect your services
5. Review your taste card → set `is_matchable = true`

Response fields: `has_display_name`, `has_languages`, `has_connection_or_obsessions`, `has_taste_data`, `has_set_matchable`, `next_step`.

### 1.8 Recommendations Endpoint — deferred

`GET /api/me/recommendations` — skipped as a service-native API proxy. Will be built on top of Item2Vec embeddings after Phase 2.1 (model training), enabling cross-domain recommendations (e.g. music suggestions from game taste). See Phase 2 for the implementation plan.

### 1.9 Heuristic Matcher ✅

**Built.** Rarity-weighted item-overlap scorer in `syncup/matching/heuristic.py`, powering `GET /api/matches` until Item2Vec embeddings are ready. It's ~20 lines, requires no training, and produces better early matches than a poorly-trained model. Use it as the live matching engine until Item2Vec embeddings are ready.

```python
def match_score_heuristic(user_a_items, user_b_items, item_popularity):
    shared = set(user_a_items) & set(user_b_items)
    if not shared:
        return 0.0
    score = sum(1 / item_popularity[item] for item in shared)
    return normalize(score)
```

Niche overlap (both love *Disco Elysium*) scores higher than mainstream overlap (both have *CS2*).

Phase transitions (when to switch):
- **0–100 users:** heuristic only
- **100–1,000:** heuristic + Item2Vec on public datasets
- **1,000+:** co-occurrence-trained embeddings from real user data

---

## ⚠️ Phase ordering note

**Phase 3 (frontend) is deferred** — starting after Phase 2 is complete. Phase 2 (ML training + matching) is the current priority. The frontend will be built once the backend matching pipeline is functional.

See [product-strategy.md §Phase 0](product-strategy.md) for the cold-start rationale.

---

## Phase 2 — Matching Engine (ML)

**Goal:** replace the heuristic matcher with semantic embeddings + collaborative filtering re-ranking.

> **Implementation plan confirmed 2026-05-19.** Phase 2 is split into 10 sequential blocks. Build order:
>
> | Block | Branch | Depends on | Delivers |
> |-------|--------|------------|----------|
> | A | ~~`feat/phase2-schema`~~ ✅ | — | EMBEDDING_DIM 128→384, `excluded` col, vibe cols, new deps/config |
> | B | ~~`feat/phase2-semantic`~~ ✅ | A | `semantic.py`, `item_text.py`, AniList ingest genres fix |
> | C | `feat/phase2-enrichment` | A | Steam/Last.fm/TMDB enrichment scripts + populate script |
> | D | `feat/phase2-user-embeddings` | A+B | `POST /api/embeddings/build`, `aggregate_vectors()`, auto-embed post-sync |
> | E | `feat/phase2-item-exclusion` | A | `PATCH /api/me/items/{id}` |
> | F | `feat/phase2-vibe` | D | `vibe_synthesizer.py`, vibe row in user_embeddings |
> | G | `feat/phase2-cf-ranker` | A | `cf_ranker.py`, ALS user-latent-factor re-ranking |
> | H | `feat/phase2-match-upgrade` | D+F+G | Semantic ANN path, 80/20 blend, `matching_mode` field |
> | I | `feat/phase2-recommendations` | D | `GET /api/me/recommendations`, `GET /api/users/{id}/taste-card` |
> | J | `feat/phase2-evaluation` | H | `scripts/evaluate.py`, blend sweep, failure mode report |
>
> B, C, E, G can run in parallel after A lands. Last.fm enrichment is script-only (not ingest fix).

> **Architecture decision (2026-05-12):** Phase 2 was originally planned around Item2Vec trained on public datasets. That approach was scrapped because separate per-service Item2Vec models produce incompatible vector spaces — cross-domain matching is not achievable that way. See `docs/brainstorm.md §ML Architecture Decisions` for the full reasoning. Item2Vec remains in the codebase as a future optional enhancement for when we have real multi-service user co-occurrence data.

> **No hard gate:** unlike the original plan, Phase 2 does not depend on offline training or public datasets. Semantic embeddings work from day one on existing item data.

> **Trigger gap:** syncing a service does NOT automatically trigger user embedding computation. `POST /api/embeddings/build` must be called explicitly after sync (or via `POST /api/me/recompute`). Auto-triggering post-sync is Block F.

### 2.0 Phase 2 Block A — Schema & Config

> **Status:** Complete ✅ (2026-05-20). `feat/phase2-schema` merged to master. 726 tests passing.
>
> Delivered:
> - `EMBEDDING_DIM` changed 128 → 384 (sentence-transformers `all-MiniLM-L6-v2`)
> - `UserItem.excluded: bool DEFAULT FALSE` — Phase 2 item exclusion column
> - `User.vibe_summary`, `User.archetype`, `User.key_themes`, `User.vibe_computed_at` — vibe synthesis columns
> - Migration `20260520_0010`: vector type widened, stale 128-dim embeddings cleared, IVFFlat index recreated
> - `Settings.embedding_model_name`, `Settings.llm_api_key`, `Settings.tmdb_api_key` added
> - `pyproject.toml [ml]`: `sentence-transformers>=3.0`, `implicit>=0.7`, `anthropic>=0.25`
> - `Item2Vec.TrainingConfig.vector_size` (128) is now explicitly decoupled from `EMBEDDING_DIM` (384)

### 2.1 Phase 2 Block B — Semantic Embedding Module

> **Status:** Complete ✅ (2026-05-21). `feat/phase2-semantic` merged via PR #14 — 785 tests passing.
>
> Delivered:
> - `syncup/embeddings/semantic.py` — lazy-loaded `SentenceTransformer` wrapper; `embed_text()` + `embed_batch()`, L2-normalized output; `_MODEL_NAME` cached at module load; double-checked locking for thread safety; per-element blank guard in `embed_batch`; zero-norm rows emit `logger.warning`
> - `syncup/embeddings/item_text.py` — `item_to_text(item)` serializer per roadmap §2.1 format table; handles game/artist/track/film/show/anime/manga/album/community + generic fallback; duck-typed; never raises; degenerate name+type emits `logger.warning`
> - `syncup/ingest/anilist.py` — `genres` field added to GraphQL query (both animeList and mangaList); stored as `metadata["genres"]` (list, defaults to []); `_graphql` `resp.json()` guarded against non-JSON 200 responses
> - Agent frontmatter: `tools:` + `model:` added to alembic-reviewer, ml-reviewer, oauth-security-reviewer
> - 59 new tests (test_semantic.py × 20, test_item_text.py × 42, test_anilist.py +3, manual_test_block_b.py script)

### 2.1 Dimension migration + semantic embedding module

**Status:** Complete — see Block B above.

**EMBEDDING_DIM: 128 → 384.** `all-MiniLM-L6-v2` (sentence-transformers) outputs 384-dim vectors. 384 captures more semantic nuance than 128 for text. Migration changes `items.embedding` and `user_embeddings.embedding` column types and recreates IVFFlat indexes.

New files:
- `syncup/embeddings/semantic.py` — lazy-loaded sentence-transformers wrapper; `embed_text()` and `embed_batch()`
- `syncup/embeddings/item_text.py` — `item_to_text(item)` builds the string to embed per service/item_type

Text format per item type:

| Type | Embedded text | Metadata source |
|------|--------------|-----------------|
| Steam game | `"{name} — game, {tags}"` | `metadata["genres"]` from enrichment script (see §2.2) |
| Music artist | `"{name} — music, {genres}"` | `metadata["genres"]` from Spotify; from Last.fm `artist.getInfo` tags after enrichment (see §2.2); name-only fallback if neither present |
| Music track | `"{name} by {artist} — music"` | `metadata["artists"]` from Spotify |
| Film | `"{name} ({year}) — film, {genres}"` | `metadata["genres"]` from TMDB lookup (see §2.2); name+year fallback |
| Show | `"{name} ({year}) — show, {genres}"` | `metadata["genres"]` from TMDB lookup; name+year fallback |
| Anime / manga | `"{name} — {item_type}, {genres}"` | `metadata["genres"]` from AniList ingest fix (see §2.2) |
| Album | `"{name} by {artist} — album, music"` | `metadata["artist_normalized"]`; no genre available from RYM |
| Reddit community | `"r/{name} — online community, {description[:100]}"` | `metadata["description"]` already stored ✅ |
| Manual obsession | `"{name} — {category}"` | category only; name is user-supplied |

`item_to_text()` must never fail — if a metadata key is missing, fall back gracefully to name + item_type only. Bare name + item_type is still better than no embedding.

New config: `Settings.embedding_model_name: str = "all-MiniLM-L6-v2"`.
New dep: `sentence-transformers>=3.0` in `pyproject.toml`.

### 2.2 Metadata enrichment + item population script + auto-embed post-sync

**Status:** Not started

**Metadata enrichment must run before embedding.** Embedding quality is directly limited by what's in `items.metadata`. Four enrichment fixes land in this block:

**Fix A — AniList genres (ingest fix):**
- `syncup/ingest/anilist.py`: the `MediaListCollection` GraphQL query already fetches media entries — add `genres` to the field list and store in `metadata["genres"]`
- One-line addition to the query and the metadata dict; no schema change needed
- All future AniList syncs automatically include genres; historical items get genres on the next user re-sync

**Fix B — Steam genre/tag enrichment script:**
- `scripts/enrich_steam_metadata.py`: queries Steam Store `appdetails` API (`https://store.steampowered.com/api/appdetails?appids={appid}&filters=genres,categories`) per game, stores `genres` (list of genre names) in `items.metadata`
- Rate-limited: ~200 requests per 5 minutes — script paces itself with `time.sleep(1.5)` between calls
- Incremental: skips games where `metadata["genres"]` already set; safe to re-run
- Run once after first sync; new items get genres on next enrichment pass
- Fallback: if Steam API returns no data for an appid (unreleased, removed), leave metadata as-is

**Fix C — Last.fm artist tag enrichment script:**
- `scripts/enrich_lastfm_metadata.py`: for all items with `item_type = 'artist'` sourced from Last.fm where `metadata["genres"]` is absent, calls Last.fm `artist.getInfo` API (`https://ws.audioscrobbler.com/2.0/?method=artist.getinfo&artist={name}&api_key=...`), stores the top tags as `metadata["genres"]`
- Uses the existing `LASTFM_API_KEY` config — no new credentials needed
- Rate-limited: Last.fm allows ~5 req/sec — script uses `time.sleep(0.2)` between calls
- Incremental: skips artists already enriched; safe to re-run
- Fallback: if artist not found or no tags returned, leave metadata as-is (embeds as `"artist_name — music"`)
- Note: Last.fm tracks are not enriched here — track embeddings use `"track_name by artist — music"` which is sufficient since genre is captured at the artist level

**Fix D — TMDB film/show genre enrichment:**
- `scripts/enrich_tmdb_metadata.py`: for all items with `item_type IN ('film', 'show')` where `metadata["genres"]` is absent, calls TMDB search API (`/search/movie` or `/search/tv` with `query=title_normalized&year=release_year`), takes the top result's genre list
- New dep: `httpx` (already present), new config: `Settings.tmdb_api_key: str | None = None`
- If `tmdb_api_key` is unset, script is skipped — films embed with name+year only (acceptable fallback)
- Incremental: skips items already enriched; safe to re-run

**Item population script:**
`scripts/populate_item_embeddings.py` — run AFTER enrichment scripts:
- Batches all `items WHERE embedding IS NULL` in chunks of 256
- Calls `embed_batch()`, writes 384-dim vectors + `embedding_computed_at`
- Incremental: safe to re-run, skips already-embedded items

**Auto-embed post-sync (Block F):**
- After `_do_sync_generic` completes, background task embeds any new items with `embedding IS NULL`
- New items from enrichment-less sources (RYM, manual obsessions) embed immediately with name-only text; quality improves if enrichment is run later

**Script execution order (one-time setup):**
```
1. python scripts/enrich_steam_metadata.py     # ~10 min for 300-game library
2. python scripts/enrich_lastfm_metadata.py    # ~5 min for 200 artists
3. python scripts/enrich_tmdb_metadata.py      # ~5 min for 200 films
4. python scripts/populate_item_embeddings.py  # embed everything
```

### 2.3 User embedding builder

**Status:** Not started

`POST /api/embeddings/build` — computes (or recomputes) the current user's `combined` taste vector.

The `combined` vector is the **primary match vector** — what ANN search and CF re-ranking operate on. It is built from the user's actual curated item data, not from LLM output.

Implementation:
1. Query `user_items JOIN items WHERE items.embedding IS NOT NULL AND user_items.excluded = false`
2. Apply `user_dimension_weights` as multipliers on `engagement_score`, then apply `preference_overrides.boost_multiplier` where set
3. Call `aggregate_vectors([(item.embedding, weighted_score), ...])` — log1p dampened weighted average, L2-normalised
4. Upsert to `user_embeddings` with `service = "combined"`
5. Returns 422 `NO_EMBEDDINGS_AVAILABLE` if no items have embeddings yet (not 500)

**Why item-average is information-preserving:**
- Uses `engagement_score` (already normalized 0–1 per service), not raw playtime/scrobbles
- `preference_overrides.boost_multiplier` directly amplifies underrepresented items (e.g. Disco Elysium at 20h can be boosted 3× and will dominate an Overwatch at 1500h)
- `excluded = true` items are skipped — misrepresentative items (e.g. games played purely with friends) don't pull the vector toward unwanted regions
- Log1p dampening prevents any single item from dominating regardless of raw engagement magnitude
- Dimension weights let the user decide which services contribute to their match profile

The information loss concern (low-playtime favourites, high-playtime items the user dislikes) is addressed by `preference_overrides` and `excluded` — these are direct controls on the match vector. The controls already exist in the API.

`aggregate_vectors()` is extracted from `user_embeddings.py` as a pure function taking pre-fetched `(vector, weight)` pairs directly — no model dependency.

### 2.4 LLM vibe synthesis

**Status:** Not started.

The component that delivers the "it actually understands me" feeling and generates taste card content. The LLM output is also embedded and stored as a **secondary match vector** that contributes 20% to the final match score (see §2.6 for the blending formula).

**What it does:** takes a user's top items across all connected services, sends them to an LLM (Claude API), receives back: `vibe_summary` (2-3 sentences), `archetype` (label like "The Patient Aesthete"), `key_themes` (list of 3-5 strings). The `vibe_summary` is embedded with sentence-transformers → stored as `user_embeddings` row with `service = "vibe"`.

**Role of the vibe embedding:**
- Primary purpose: user-facing taste card content (archetype label, description, what users read and share)
- Secondary purpose: contributes 20% to match score alongside the `combined` item-average vector (80%)
- The LLM synthesizes cross-domain patterns (the thread connecting Disco Elysium + Nick Cave + Tarkovsky) that item-averaging alone can miss
- Two users with similar cross-domain vibes but different surface items can score higher than item cosine alone would suggest

**Why the vibe embedding is secondary, not primary:**
- LLM summaries flatten nuance — two users with different niche tastes may get similar prose, embedding to nearly the same vector
- The item-average preserves more information because it operates in the full 384-dim item space, not in compressed prose
- The 80/20 blend is a tunable hyperparameter — vary it in the evaluation framework (§2.8) to find the empirically best ratio

**Item selection for LLM input:**
- Top items by `engagement_score`, not by rarity
- Cap at top 5 per service, up to 20 total (prevents one service dominating)
- Skip `user_items.excluded = true` items and apply `preference_overrides.boost_multiplier` before ranking
- Rarity weighting is explicitly NOT used here — mainstream favourites are valid signal

**New columns on `users`:**
- `vibe_summary: Text | None`
- `archetype: Text | None`
- `key_themes: ARRAY(Text) | None`
- `vibe_computed_at: DateTime | None`

**New file:** `syncup/embeddings/vibe_synthesizer.py`
- `synthesize_vibe(user_id, db) -> VibeProfile` — selects top items, calls LLM, parses response, stores result, upserts `user_embeddings` row with `service = "vibe"`
- Called after sync completes (background task) and on `POST /api/me/recompute`
- Mocked in tests — don't make real LLM calls in CI

**New config:** `Settings.llm_api_key: str | None = None`. If unset, vibe synthesis is skipped — match score falls back to 100% item-average (graceful degradation, no feature flag needed).

**Cost:** ~$0.01 per user synthesis call. Called once per sync, result stored in DB.

### 2.5 CF re-ranker

**Status:** Not started

Collaborative filtering re-ranker trained on our own `user_items` engagement data. This is the trainable component for the KI Challenge — it learns from our actual user data, not a pre-trained model.

`syncup/matching/cf_ranker.py`:
- Builds a user × item implicit feedback matrix from `user_items.engagement_score`
- Trains ALS model via the `implicit` library (~20 lines) — ALS is preferred over BPR for this use case (faster, more stable on sparse data)
- `CfRanker.train(db)` — called on a daily schedule; NOT per-user (trains on all user data at once)
- `CfRanker.rerank(user_id, candidate_user_ids) -> list[uuid]` — scores and sorts candidates
- Fallback: if `user_id` not in CF model (new user, sparse history), skip re-ranking silently

**How `rerank()` works (important implementation note):** ALS produces a user factor matrix (one latent vector per user) and an item factor matrix. To rank candidate *users* by CF similarity to a query user, extract the ALS user latent vectors and compute cosine similarity between `user_vector[query_user]` and `user_vector[candidate]` for each candidate. This is user-user CF in latent space — not item prediction. The `implicit` library's `model.user_factors` array holds these vectors after training; index into it by the internal integer user index (maintain a `user_id → row_index` mapping alongside the model).

**Training frequency:** train once daily on all data (not on every `POST /api/me/recompute`). `recompute` triggers embedding rebuild; CF retraining is a separate scheduled task. Separating these prevents expensive model retraining on every user action.

**Known limitation (document in evaluation):** ALS user-user similarity can only re-rank candidates already in the 50-candidate semantic pool. If the true best match is not in the top-50 semantic results (possible when metadata quality is low), CF cannot surface them. This is the cascade ceiling — it's a known trade-off, not a bug.

Why two stages instead of CF alone:
- CF needs sufficient history to produce signal — new users have none
- CF is single-domain (it learns co-occurrence, not semantics)
- Semantic handles cold start and cross-domain; CF improves ranking where real engagement patterns exist

### 2.6 Match endpoint upgrade + D14 IVFFlat index

**Status:** Not started (D14 was deferred from Branch 3)

Migration `20260513_0010_ivfflat_user_embeddings.py` — creates the IVFFlat index on `user_embeddings.embedding` (already defined in `models.py`, just needs the migration).

Updated `GET /api/matches` logic:
1. If user has `user_embeddings` row with `service = "combined"`: ANN cosine via pgvector `<=>` on `combined` vector → 50 candidates
2. Blend score: `final_score = 0.8 × cosine(combined_a, combined_b) + 0.2 × cosine(vibe_a, vibe_b)` (if both users have a `vibe` row; otherwise 100% combined). The 0.8/0.2 ratio is a tunable hyperparameter — vary it in the evaluation framework to find the empirically best value.
3. If user is in CF model: `CfRanker.rerank()` → top 10 from those 50 (re-ranks by CF user-latent-factor similarity)
4. Else: fall back to heuristic
5. Response includes `matching_mode: "heuristic" | "semantic" | "semantic+cf"`

The `matching_mode` field is intentional for the KI Challenge submission — it lets us compare modes scientifically and demonstrate self-critical assessment.

### Match Cache + Staleness (carried from original 2.4)

- Already partially implemented (hourly cleanup job, `POST /api/me/recompute`)
- `POST /api/me/recompute` now also triggers `POST /api/embeddings/build` + CF retraining
- Hard-expire after 24h (existing behaviour)
- Invalidate when either user's embedding updates

### 2.6 Recommendations Endpoint

**Status:** Not started. Unblocked by semantic embeddings (was deferred in Phase 1.8 pending Item2Vec).

`GET /api/me/recommendations?item_type=game&limit=10`

Implementation:
1. Load user's `combined` embedding from `user_embeddings`
2. ANN search on `items.embedding <=> user_embedding` WHERE item NOT IN user's `user_items`
3. Optional `item_type` filter (game, artist, track, film, anime, album, etc.)
4. Returns top N with `item_name`, `service`, `item_type`, `similarity_score`
5. Falls back 503 `NO_EMBEDDING_AVAILABLE` if user has no combined embedding yet

Cross-domain is automatic: combined taste vector spans all services, so asking for `item_type=film` surfaces recommendations informed by gaming and music taste too. This is the most user-visible AI feature — "here are 5 games you'd probably love" is the demo moment.

For the KI Challenge: recommendations are a compelling live demo. Connect Steam, run the endpoint, get back items you've never played but actually would love. More tangible to judges than matching scores.

### 2.7 Public taste card endpoint

**Status:** Not started. Backend data (`GET /api/me/taste`) already live; this adds a public unauthenticated version for shareable links.

`GET /api/users/{user_id}/taste-card`

- Unauthenticated — no session cookie required
- Returns the same shape as `GET /api/me/taste` but for any user
- Gate: only returns data if `users.is_matchable = true` (user has opted in to visibility)
- 404 if user doesn't exist or hasn't opted in

Unblocks the frontend shareable taste card (Phase 3.4). The visual rendering is the friend's job in Phase 3; this endpoint is the data layer it needs.

### 2.9 User-controlled taste profile (item exclusion)

**Status:** Not started.

`user_items.excluded: bool, default False` — new column + migration.

When `excluded = true`, the item is skipped in user vector computation, LLM item selection, and recommendations. This is different from `preference_overrides` (which adjusts weight); exclusion removes the item entirely.

API: `PATCH /api/me/items/{item_id}` — `{"excluded": true/false}`.

**UX decision:** import everything silently. Do NOT show a checkbox list at import time — overwhelming and creates false urgency. Users refine their profile anytime via their taste profile view. The feedback loop (exclude item → archetype updates → "this now feels right") is the core "it understands me" experience.

The three taste control levers (all exist in API):
- `excluded` on `user_items` — remove misrepresentative items
- `preference_overrides.boost_multiplier` — amplify underrepresented items  
- `user_dimension_weights` — weight services differently

Frontend unifies these in a "manage your taste" view (Phase 3, friend's job).

### 2.8 Evaluation framework

**Status:** Not started. Required for KI Challenge scientific rigor (criterion 7).

A standalone evaluation script and a small API endpoint that measures how well the AI is actually working. Without this, we can't answer "how do you know your recommendations are good?" in front of judges.

**Recommendation quality (offline holdout eval):**
- Hold out 20% of each user's `user_items` before embedding
- Train on the remaining 80%
- Check if held-out items rank in the top-K of recommendations vs. random items
- Metric: Precision@10, Recall@10 (how many held-out items appear in top 10 recommendations)

**Matching quality (A/B comparison):**
- `matching_mode` field already records which mode was used (`heuristic`, `semantic`, `semantic+cf`)
- Log scores per mode
- Report average scores per mode — does `semantic+cf` consistently outscore `heuristic`?
- **Caveat (document in report):** higher average cosine similarity ≠ better matches in absolute terms, only relative to baseline. The quantitative comparison is evidence of improvement, not proof of quality.

**Qualitative exhibit (required for KI demo — criterion 8):**
- Pre-compute match results for 3–5 real user profiles (your own accounts, your friend's accounts, or hand-crafted test profiles)
- For each: pick 2 matches that are intuitively correct ("yes, these people share a vibe") and 1 that is wrong or surprising
- For the wrong one: diagnose why the system got it wrong (sparse data? missing metadata? genre mismatch in semantic space?)
- This exhibit answers criterion 8 ("self-critical assessment") better than any number — judges will remember "the system recommended X because of Y, and here's where it failed and why" far longer than a precision score

**Blend ratio evaluation:**
- Run the eval at blend ratios 100/0, 80/20, 60/40, 50/50 (item-average / vibe)
- Report which ratio maximizes Precision@10 on the holdout set
- Use the best ratio in production; report this in the KI submission as a hyperparameter search

**Output:** `scripts/evaluate.py` prints a clean report:
```
Recommendation quality (holdout eval, N=X users):
  Precision@10: 0.34
  Recall@10:    0.21

Blend ratio sweep (Precision@10):
  combined only (100/0): 0.29
  80/20 blend:           0.34  ← best
  60/40 blend:           0.31
  50/50 blend:           0.28

Matching mode comparison:
  heuristic:    avg score 0.41
  semantic:     avg score 0.58  (+41%)
  semantic+cf:  avg score 0.63  (+54%)

Known failure modes:
  - Users with < 20 items: degraded recommendation quality (thin signal)
  - Steam-only users: no genre metadata pre-enrichment → lower embedding quality
  - Cascade ceiling: CF can only re-rank semantic top-50; misses outside that pool
```

This is the scientific evidence that the AI works. Show this to judges. The failure modes section is not a weakness — it is criterion 8.

---

## Phase 3 — Frontend

**Goal:** users can do everything through the browser.

Stack: **Next.js 15 (App Router)**, TypeScript, Tailwind CSS.

### 3.1 Project Setup

- `pnpm create next-app frontend --typescript --tailwind --app`
- Auth handled via `syncup_session` cookie (already set by backend)
- API calls proxied through Next.js route handlers (avoids CORS issues in production)

### 3.2 Auth Pages

- `/login` — email + password form
- `/signup` — create account
- Redirect to `/onboarding` after signup

### 3.3 Onboarding Flow

Multi-step wizard:
1. Display name
2. Languages + interests (populates `manual_obsessions`)
3. "Connect your first service" (or "Skip — I'll add 3 obsessions instead")
4. Taste card preview → "Enable matching"

### 3.4 Taste Card Page (`/me/taste`)

This is the **primary product during the cold-start phase**. It must be beautiful and shareable before anything else.

- Visual breakdown of the user's taste (games, music, film, etc.)
- Archetype label + description
- Shareable OG image (generate server-side with `@vercel/og` or similar)
- "Share to X" / "Copy link" buttons

See [product-strategy.md §Taste Card & Discovery Engine](product-strategy.md) for the full design rationale.

### 3.5 Service Connection UI

- "Connect Steam", "Connect Spotify", "Connect Last.fm" buttons (Phase 1 services)
- Sync status indicator per service
- Disconnect + resync actions

### 3.6 Match Feed (`/matches`)

- Card per match: avatar, display name, compatibility score, service breakdown, shared highlights
- Dimension weight sliders (real-time preview of how changing weights reorders matches)
- Reveal flow: click a match → see their Discord handle / social link

### 3.7 UX Decisions — Resolve Before Building

| Decision | Options | Leaning |
|----------|---------|---------|
| Match reveal flow | Show handle immediately vs. "request to connect" step | Immediate for MVP; add request step in V2 |
| Browse mode | Tinder-style swipe vs. scrollable feed | Feed for MVP (easier to build, less friction) |
| Activity feed | Bridge activity from connected services | Post-launch feature; don't build yet |

---

## Phase 4 — Launch Preparation

### 4.1 Taste Card Sharing (OG Images)

Generate a shareable image card from `/api/me/taste` data. People will post these on Twitter/X without being asked — each share is an organic acquisition targeting exactly the right demographic. Build this before the match feed.

### 4.2 Waitlist + Batch Invite

- `/join` page with email capture
- Group signups into batches of 50–100
- Email everyone in a batch on the same day so matches exist immediately at launch

### 4.3 Archetype Generation

Generate 10 predefined taste archetypes from public training data. Show them during onboarding as examples of what the matching engine sees. Also show a user's computed archetype on their taste card.

### 4.4 Community Launch Kit

Pick one target community (see [product-strategy.md §Phase 4](product-strategy.md)). Build:
- Custom invite codes per community
- A simple mod dashboard showing signup count
- Copy for the community announcement

---

## Phase 5 — Growth & Expansion

### 5.1 Discord Bot

After web MVP is stable. Priority features:
- Import taste card into server profile
- Show server-wide compatibility ("@sam and @alex are 89% compatible")
- Weekly vibe highlights in a channel

### 5.2 Recommendations Engine

Use service-native APIs first (Last.fm `artist.getSimilar`, Spotify recommendations), then item-to-item via Item2Vec once the model is trained. See [product-strategy.md §The "People Like You Also Like" Recommendation Layer](product-strategy.md).

### 5.3 Additional Services

Expand in this order once the MVP services (Spotify, Steam, Last.fm) are solid:

| Priority | Service | What to use | Access |
|----------|---------|-------------|--------|
| 1 | **Letterboxd** | Film ratings + diary | Unofficial API or scrape |
| 2 | **AniList** | Anime + manga ratings | GraphQL API (open) |
| 3 | **RateYourMusic** | Deep music ratings | Scrape / export |
| 4 | **Apple Music** | Listening history | MusicKit (limited scopes) |
| 5 | **Trakt.tv** | TV tracking | OAuth API |
| 6 | **Bandcamp** | Record purchases + follows | No public API — scrape |
| 7 | **itch.io** | Indie game ownership | No public API — scrape |
| 8 | **StoryGraph** | Book tracking | No public API — scrape |
| 9 | **Reddit** | Subreddit subscriptions | OAuth API |

For services without APIs: consider a "paste your export" flow (Letterboxd, RateYourMusic both offer data exports).

**Deferred — evaluate later:**
- PlayStation Network / Xbox Network — limited API access; priority if the user base skews console
- Tracker.gg — competitive game stats; niche but high signal for the gamer segment
- IMDB — overlaps with Letterboxd; low priority given Letterboxd's richer social data
- YouTube — vague signal (watch history is not taste data in the same way); skip for now
- GitHub — only useful for the feed/social layer, not for taste matching
- Social media (Instagram, Twitter, Bluesky) — following graph is noisy; wait until the core taste dimensions are solid

---

## Maintenance Checklist (before any public launch)

- [ ] Automated Spotify token refresh before each sync
- [ ] Session cleanup job (delete rows where `expires_at < now()`)
- [x] `CORS_ALLOWED_ORIGINS` driven from env, not hardcoded
- [ ] `SESSION_SECRET` generated and in `.env`
- [ ] Production DB: limited-privilege app user (not superuser)
- [ ] Rate limits on all write endpoints
- [ ] Error monitoring (Sentry or equivalent)
