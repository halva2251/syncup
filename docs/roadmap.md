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

> **Status:** Branch 1 (fix/security-hardening) complete ✅ (2026-05-09). Branch 2 (fix/ingest-hardening) complete ✅ (2026-05-09). 678 tests passing. Branches 3–4 pending.

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

### Branch 3: fix/db-hardening (pending)

Background cleanup jobs, unbounded queries, atomicity, index maintenance.

### Branch 4: fix/api-quality (pending)

Sync visibility, response schemas, cursor pagination, input validation, onboarding fixes.

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

**Goal:** replace the heuristic matcher with learned embeddings once there's enough data.

> **Hard gate:** Phase 2.2–2.4 are blocked until Item2Vec training is complete (2.1). Training requires downloading public datasets, running training scripts offline, and populating `items.embedding` in the database. This is hours-to-days of work, not a route to implement. Plan accordingly.

> **Trigger gap:** Currently, syncing a service does NOT automatically trigger user embedding computation. `POST /api/embeddings/build` (2.3) must be called explicitly after sync. Decide whether to trigger it automatically post-sync before building the match endpoint.

### 2.1 Train Item2Vec on Public Datasets

Public datasets to start with:
- **Steam:** [Steam review dataset](https://cseweb.ucsd.edu/~jmcauley/datasets.html#steam_data) — play sequences per user
- **Music:** [Million Song Dataset](http://millionsongdataset.com/) or Last.fm public dataset

Training produces item vectors (128-dim). These feed into `user_embeddings` via the existing `build_user_vector()` function.

The training script does not need to be a FastAPI route — a one-off `python train_item2vec.py` is fine.

### 2.2 Build User Embedding Endpoint

`POST /api/embeddings/build` — compute (or recompute) a user's embedding from their `user_items`.

Stores result in `user_embeddings`. Sets the user as potentially matchable.

### 2.3 Match Endpoint

`GET /api/matches?limit=20&cursor=...` — top matches for the current user.

Implementation:
1. Load requesting user's `combined` embedding from `user_embeddings`
2. Query `user_embeddings` for all other matchable users (ANN via IVFFlat index)
3. Apply dimension weights
4. Sort by score, paginate
5. Cache results in `match_cache`

`GET /api/matches/{user_id}` — detailed match view with shared highlights.

### 2.4 Match Cache + Staleness

- Invalidate cached matches when either user's embedding updates
- Hard-expire after 24h
- `POST /api/me/recompute` — force recompute; rate-limit to 1/hour

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
