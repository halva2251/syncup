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
| `enrich_steam_metadata.py` — Steam Store appdetails enrichment; incremental, rate-limited to ~200 req/5 min | `backend/scripts/enrich_steam_metadata.py` |
| `enrich_lastfm_metadata.py` — Last.fm `artist.getInfo` tag enrichment; incremental, 5 req/s | `backend/scripts/enrich_lastfm_metadata.py` |
| `enrich_tmdb_metadata.py` — TMDB search genre enrichment for films/shows; title-match guard; aborts if genre maps fail | `backend/scripts/enrich_tmdb_metadata.py` |
| `populate_item_embeddings.py` — batch-embeds all items `WHERE embedding IS NULL` in chunks of 256; degenerate text guard | `backend/scripts/populate_item_embeddings.py` |
| 831 passing tests | `backend/tests/` |
| `GET /api/me/recommendations` — cross-domain item recs from combined taste vector; `item_type` filter allowlist (9 types); `NOT EXISTS` ownership check; `similarity_score = 1 - cosine_distance` clamped to `[0, 1]`; 422 `NO_EMBEDDING_AVAILABLE` guard | `syncup/api/routes/recommendations.py` |
| Block J review fixes — **service-aware user embedding** (`combine_service_vectors`: per-service mean-pool then linear dim-weight so the slider is authoritative over item count), semantic-authoritative match refresh (no heuristic churn), in-flight refresh guard, drift-tolerant highlight parsing, honest log1p docstring, centroid-collapse eval probe, `Item(meta)` genre-persistence fix | `syncup/embeddings/user_embeddings.py`, `syncup/api/routes/{embeddings,matches}.py`, `scripts/evaluate.py` |
| 987 passing tests | `backend/tests/` |
| Recommendations cross-service dedup — excludes any title the user owns on *any* service (`normalize_title` + `item_type`, not just `item_id`); same title never returned twice (highest-similarity copy wins); franchise variants preserved; oversample raised to `limit*5` (cap 200) | `syncup/api/routes/recommendations.py` |
| `scripts/qa_sweep.py` — autonomous, self-cleaning QA harness: seeds a catalog, drives the live HTTP API as a throwaway user, asserts dedup/exclusion/score/filter/limit/cross-domain/smoke invariants (22/22 pass) | `backend/scripts/qa_sweep.py` |
| `scripts/seed_catalog.py` — seeds ~170 curated, taste-distinctive items (45 games, 45 artists, 35 films, 25 albums, 20 anime) with production-consistent embeddings (`item_to_text` + `embed_batch`), solving the recommendations cold-start for single/few-user instances; idempotent (`seed-<slug>` external_ids), reversible (`--wipe`), `--dry-run` preview | `backend/scripts/seed_catalog.py` |
| 998 passing tests | `backend/tests/` |
| External code review (Kimi) pass — fixed lossless cursor encoding (`repr()` not `:.6f`) in keyset pagination, bulk `pg_insert(...).on_conflict_do_update(...)` upsert for match cache writes (replacing N×`db.merge()`), proxy-host allowlist for `ProxyHeadersMiddleware` (`TRUSTED_PROXY_HOSTS` env var, was `"*"`), stripped `input` field from validation-error responses, conditional HSTS header, `raw_type`/`engagement_score` CHECK constraints on `user_items`, signup timing-safe constant-time fix, avatar URL scheme allowlisting, query limits on obsessions/auto-embed, removed unused `lastfm_shared_secret` config, unified OAuth cookie-deletion options across all 4 callbacks, narrowed match-cache write exception to `SQLAlchemyError`. **Deferred to issue #23**: OAuth state/verifier cookies aren't deleted on callback *failure* paths (low-severity — httpOnly/secure/10-min TTL) | `backend/CODE_REVIEW_REPORT.md`, PR #22, [issue #23](https://github.com/halva2251/syncup/issues/23) |
| Second full-scope swarm review (2026-06-11, 5 parallel agents: oauth-security, bounty-style security, ML correctness, Python quality, test/lint verification) — zero CRITICAL/HIGH; all 8 Phase 2 ML invariants re-confirmed. Fixed: Spotify OAuth callback now raises `409 SPOTIFY_CONNECT_CONFLICT` on connect race instead of silently swallowing `IntegrityError` (matches AniList/Trakt/Reddit contract); non-finite CSV ratings (`inf`/`nan`/`1e400`) rejected with `SyncClientError` in Letterboxd + RYM parsers; `format_vec` raises `ValueError` on non-finite vector elements (clear error instead of opaque pgvector DB error); `evaluate.py` `_format_vec` delegates to production `syncup.db.pgvector.format_vec` (drift elimination). Deferred: OAuth state-to-session binding (defense-in-depth), recompute in-flight-guard release edge, vibe top-item tiebreaker, Reddit User-Agent placeholder fallback, `(service, external_user_id)` non-uniqueness | `syncup/api/routes/connect.py`, `syncup/ingest/{letterboxd,rateyourmusic}.py`, `syncup/db/pgvector.py`, `backend/scripts/evaluate.py` |
| 1009 passing tests | `backend/tests/` |
| ML-pipeline validation pass (2026-06-11) — full re-review (ml-reviewer: all 8 Phase 2 invariants re-confirmed, zero CRITICAL/HIGH; python-reviewer: zero CRITICAL/HIGH) + 9/9 independent fake-data probes (dimension-weight authority incl. 50-vs-5-item slider invariance, boost, exclusion, engagement lean, cross-domain artist ranking) + 22/22 qa_sweep. Fixed eval–production drift: `evaluate.py` `_ann_item_query` now mirrors `recommendations.py` owned-by-title + title-dedup filtering (`filter_candidates_production_style`, oversample `limit*5`), holdout hits counted by normalized-title equivalence; Hit Rate@10 re-baselined 0.80 (empty catalog) → 0.50 (403-item catalog) — see §2.8 catalog-sensitivity note | `backend/scripts/evaluate.py`, `backend/tests/test_evaluate.py` |
| 1015 passing tests | `backend/tests/` |
| Category-aware autocomplete for obsessions — `GET /api/items/search` (Steam Store, TMDB, AniList, MusicBrainz, Open Library) + frontend `Autocomplete` component; selecting a suggestion links the obsession to a canonical `items` row via `external_id` + `service` | `syncup/ingest/search/`, `syncup/api/routes/search.py`, `frontend/components/ui/autocomplete.tsx`, `frontend/lib/actions/obsession-actions.ts`, `backend/syncup/api/routes/obsessions.py` |
| 1069 passing tests | `backend/tests/` |

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

> **Implementation plan confirmed 2026-05-19; updated 2026-06-04 after council review.** Phase 2 is split into blocks. Build order:
>
> | Block | Branch | Depends on | Delivers |
> |-------|--------|------------|----------|
> | A | ~~`feat/phase2-schema`~~ ✅ | — | EMBEDDING_DIM 128→384, `excluded` col, vibe cols, new deps/config |
> | B | ~~`feat/phase2-semantic`~~ ✅ | A | `semantic.py`, `item_text.py`, AniList ingest genres fix |
> | C | ~~`feat/phase2-enrichment`~~ ✅ | A | Steam/Last.fm/TMDB enrichment scripts + populate script |
> | D | ~~`feat/phase2-user-embeddings`~~ ✅ | A+B | `POST /api/embeddings/build`, `aggregate_vectors()` with catalog-size cap, auto-embed post-sync |
> | E | ~~`feat/phase2-item-exclusion`~~ ✅ | A | `PATCH /api/me/items/{id}` |
> | F | ~~`feat/phase2-vibe`~~ ✅ | D | `vibe_synthesizer.py`, archetype labels + vibe explanation text only (not a match score input) |
> | ~~G~~ | ~~`feat/phase2-cf-ranker`~~ | ~~A~~ | **CUT** — ALS requires real user-item interaction density we don't have; produces pretend rigor |
> | H | ~~`feat/phase2-match-upgrade`~~ ✅ | D+F | Semantic ANN path, cosine similarity score, `matching_mode` field |
> | I | ~~`feat/phase2-recommendations`~~ ✅ | D | `GET /api/me/recommendations` |
> | J | `feat/phase2-evaluation` | H | `scripts/evaluate.py`, synthetic cohort eval, failure mode report |
>
> C, E can run in parallel after A lands. Last.fm enrichment is script-only (not ingest fix).

> **Architecture decision (2026-05-12):** Phase 2 was originally planned around Item2Vec trained on public datasets. That approach was scrapped because separate per-service Item2Vec models produce incompatible vector spaces — cross-domain matching is not achievable that way. See `docs/brainstorm.md §ML Architecture Decisions` for the full reasoning. Item2Vec remains in the codebase as a future optional enhancement for when we have real multi-service user co-occurrence data.

> **No hard gate:** unlike the original plan, Phase 2 does not depend on offline training or public datasets. Semantic embeddings work from day one on existing item data.

> **Trigger gap (resolved in Block F):** `POST /api/sync/{service}` now auto-embeds new items and auto-synthesizes vibe (if `llm_api_key` is set) as background tasks after sync completes. User embedding (`POST /api/embeddings/build`) still requires an explicit call or `POST /api/me/recompute`.

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

> **Status:** Complete ✅ (2026-05-21). `feat/phase2-semantic` merged via PR #14 — 785 tests passing. UMAP embedding validation run 2026-06-04: 51 items across Steam/music/anime; cross-domain same-vibe similarity 0.273 vs diff-vibe 0.225 (delta +0.049) — architecture validated. See `backend/notebooks/embedding_validation.py`.
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

**Status:** Scripts complete ✅ (2026-06-04). `feat/phase2-enrichment` — 831 tests passing. Auto-embed post-sync lands in Block F.

**Metadata enrichment must run before embedding.** Embedding quality is directly limited by what's in `items.metadata`. Four enrichment fixes land in this block:

**Fix A — AniList genres (ingest fix):**
- `syncup/ingest/anilist.py`: the `MediaListCollection` GraphQL query already fetches media entries — add `genres` to the field list and store in `metadata["genres"]`
- One-line addition to the query and the metadata dict; no schema change needed
- All future AniList syncs automatically include genres; historical items get genres on the next user re-sync

**Fix B — Steam genre/tag enrichment script:**
- `scripts/enrich_steam_metadata.py`: queries Steam Store `appdetails` API (`https://store.steampowered.com/api/appdetails?appids={appid}&filters=genres`) per game, stores `genres` (list of genre names) in `items.metadata`; Steam `categories` (e.g. "Single-player", "Achievements") are not fetched — they are not genre signals and do not improve embedding quality
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
- `scripts/enrich_tmdb_metadata.py`: for all items with `item_type IN ('film', 'show')` where `metadata["genres"]` is absent, calls TMDB search API (`/search/movie` or `/search/tv` with `query=item.name&year=release_year`), takes the top result's genre list; a title-match guard (`_normalize_for_match`) rejects false positives
- New dep: `httpx` (already present), new config: `Settings.tmdb_api_key: str | None = None`
- If `tmdb_api_key` is unset, script is skipped — films embed with name+year only (acceptable fallback)
- Search uses `metadata["title_normalized"]` when present, falling back to `item.name`; TMDB search is case-insensitive and handles punctuation — do NOT pass the fully-lowercased normalized form as that degrades match quality
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

**Status:** Complete ✅ (2026-06-04). `feat/phase2-user-embeddings` — 868 tests passing.

`POST /api/embeddings/build` — computes (or recomputes) the current user's `combined` taste vector.

The `combined` vector is the **match vector** — what ANN search operates on. It is built from the user's actual curated item data, not from LLM output.

**Per-service representation — corrected during the Block J review (2026-06-07).** The original plan claimed a top-50/service cap alone gives "equal representation per service before dimension weights." That was **wrong**: a flat global weighted sum still lets a service with more items dominate the centroid by sheer count (verified — 50 games + 5 tracks at music=0.7/games=0.3 still leaned games 0.87 vs 0.16). The cap bounds the imbalance but does not remove it. **Fix shipped:** the builder is now **service-aware (two-level aggregation)** so the user's dimension-weight slider is authoritative regardless of library size.

Implementation (as built):
1. Query `user_items JOIN items WHERE items.embedding IS NOT NULL AND user_items.excluded = false`, LEFT JOIN dimension weights + overrides
2. **Per-service cap:** keep top 50 by `engagement_score` per service
3. **Within each service** → `aggregate_vectors([(embedding × boost, engagement_score), …])`: log1p-dampened weighted sum, L2-normalised to a unit *service taste direction*. `boost` amplifies an item relative to its service peers.
4. **Across services** → `combine_service_vectors([(service_unit_vec, dim_weight), …])`: a **linear** weighted sum (no log1p), L2-normalised. Because each service was mean-pooled to unit mass first, `dim_weight` maps directly to contribution (0.7 vs 0.3 → exactly 0.7:0.3) — item count no longer overrides the slider.
5. Upsert to `user_embeddings` with `service = "combined"`
6. Returns 422 `NO_EMBEDDINGS_AVAILABLE` if no items have embeddings / all weights zero

**Why this is information-preserving:**
- Uses `engagement_score` (already normalized 0–1 per service), not raw playtime/scrobbles
- `preference_overrides.boost_multiplier` amplifies underrepresented items *within their service*
- `excluded = true` items are skipped entirely
- `dim_weight` is now the authoritative cross-service lever (per-service mean-pool before weighting)

**Honest note on log1p (corrected 2026-06-07):** log1p runs on `engagement_score ∈ [0,1]` (already normalised by every ingest client), where it is *near-linear* — a mild concave reweighting, NOT the order-of-magnitude raw-play-count dampener the old docstring described (that work happens upstream in each client). The module docstring now states this honestly.

**Known limitation — centroid collapse (now *measured*, not just asserted):** a user whose library spans unrelated domains produces an averaged vector that matches neither cluster well. Block J's eval now includes a mixed-domain probe quantifying it: a mixed RPG+EDM user sits at cos≈0.79 to the RPG centroid vs 0.99 for a pure RPG user (a ~0.20 collapse). See §2.8.

`aggregate_vectors()` and `combine_service_vectors()` live in `user_embeddings.py` as pure functions taking pre-fetched `(vector, weight)` pairs — no model dependency.

### 2.4 LLM vibe synthesis (explanation layer only)

**Status:** Not started.

**Scope change (2026-06-04):** The LLM is an explanation layer, not a match score contributor. The previous plan had LLM output contributing 20% to the final match score — this has been cut. A 20% blend weight with no empirical basis is indefensible to KI Challenge judges, and LLM summaries flatten nuance in ways that degrade match quality. The match score is purely cosine similarity on the `combined` vector.

**What it now does:** takes a user's top items across all connected services, sends them to an LLM (Claude API), receives back: `vibe_summary` (2-3 sentences), `archetype` (label like "The Patient Aesthete"), `key_themes` (list of 3-5 strings). These are stored on the `users` table and displayed on the taste card. No `vibe` row is written to `user_embeddings`.

**Role of the LLM output:**
- Taste card content — archetype label, description, what users read and share
- Match explanation — "you both favor atmospheric melancholic aesthetics with high narrative density" shown alongside the cosine score
- The synthesis captures cross-domain patterns the item vector can't articulate (e.g. the thread connecting Disco Elysium + Nick Cave + Tarkovsky)
- It does NOT influence which users are ranked as matches — that is purely the `combined` vector

**Item selection for LLM input:**
- Top items by `engagement_score`, not by rarity
- Cap at top 5 per service, up to 20 total (prevents one service dominating)
- Skip `user_items.excluded = true` items and apply `preference_overrides.boost_multiplier` before ranking

**New columns on `users` (already added in Block A):**
- `vibe_summary: Text | None`
- `archetype: Text | None`
- `key_themes: ARRAY(Text) | None`
- `vibe_computed_at: DateTime | None`

**Status:** Complete ✅ (2026-06-06). `feat/phase2-vibe` — 898 tests passing.

**New file:** `syncup/embeddings/vibe_synthesizer.py`
- `synthesize_vibe(db_factory, user_id, llm_api_key, llm_base_url, llm_model) -> VibeResult | None`
- Selects top 5 items per service (up to 20 total), applies `boost_multiplier` before ranking, skips `excluded=true` items
- Calls DeepSeek (or any OpenAI-compatible provider) via `httpx` with tool-use forced JSON
- Returns and persists `VibeResult(vibe_summary, archetype, key_themes)` to `users` row
- Called after sync completes (background task via `_do_sync_generic`) and on `POST /api/me/recompute`
- Mocked in tests — no real LLM calls in CI

**Auto-embed post-sync (also Block F):**
- `_embed_new_items(session, user_id, service)` added to `sync.py`
- After successful sync commit, embeds any `items WHERE embedding IS NULL` for that service
- Embedding failure is logged but does NOT roll back the sync commit

**New config:** `Settings.llm_api_key: str | None = None` (existing). `Settings.llm_base_url: str = "https://api.deepseek.com"`, `Settings.llm_model: str = "deepseek-chat"` added. Provider-agnostic: point `llm_base_url` at any OpenAI-compatible endpoint. If `llm_api_key` is unset, vibe synthesis is skipped and taste card shows items only (graceful degradation, no feature flag needed).

**Cost:** ~$0.01 per user synthesis call with DeepSeek. Called once per sync, result stored in DB.

### 2.5 CF re-ranker — CUT ❌

**Status:** Permanently cut (2026-06-04).

ALS collaborative filtering requires a meaningful user × item interaction matrix to learn latent factors. With no real users at demo time, any trained model reflects synthetic or hand-seeded data — judges with ML knowledge will identify this immediately. This block produced pretend rigor, not evidence.

The `implicit` dependency remains in `pyproject.toml [ml]` for future use when real user data exists post-launch. Block H no longer depends on this block.

### 2.6 Match endpoint upgrade + ANN index

**Status:** ✅ Complete (2026-06-06, PR `feat/phase2-match-upgrade`, 931 tests passing)

Migration `20260606_0011_phase2_match_upgrade.py`:
- Adds `matching_mode TEXT NOT NULL DEFAULT 'heuristic'` column to `match_cache`
- Recreates the ANN index on `user_embeddings.embedding WHERE service='combined'` as **HNSW** (not IVFFlat — HNSW requires no lists-tuning and performs well from single-digit to millions of rows)

`_refresh_match_cache` path selection:
1. If user has a `user_embeddings` row with `service='combined'`: runs HNSW ANN search via pgvector `<=>` → 50 candidates → `score = 1 - cosine_distance`, candidates with `score <= 0` filtered (antipodal vectors) → `matching_mode="semantic"`
2. Else: falls back to heuristic item-overlap scorer → `matching_mode="heuristic"`

`POST /api/me/recompute` now queues `_build_embedding_bg` before `_refresh_match_cache` so the embedding is always up-to-date before matching runs.

Response field `matching_mode: "heuristic" | "semantic"` on `GET /api/matches` and `GET /api/matches/{id}`.

**Score formula:** pure cosine similarity on the `combined` vector — reproducible, empirically evaluable, defensible to judges. Candidates with negative cosine similarity (distance > 1.0) are filtered out rather than floored to 0, preventing antipodal users from appearing in match results.

**Addressed in the Block J review (2026-06-07):**
- **Semantic mode is now authoritative.** Once a user has a combined embedding, `_refresh_match_cache` no longer falls through to the heuristic path even when every ANN neighbour scores ≤ 0. This removes the mode-churn that previously let a heuristic refresh overwrite a semantic row for a symmetric pair.
- **In-flight refresh guard.** Repeated empty-page `GET /api/matches` requests no longer stack redundant concurrent `_refresh_match_cache` runs for the same user (`_try_acquire_refresh` / `_release_refresh`), reducing write contention.
- **Match list is drift-tolerant.** Highlights are parsed via `_parse_highlights` (`model_validate` + skip-and-log) so a malformed/legacy cache row degrades gracefully instead of 500-ing the whole list.

**Known issues / deferred (still open):**
- `_write_match_results` uses `db.merge()` in a loop (not atomic). Concurrent refreshes of the same user pair can still unique-violate. Fix: bulk `ON CONFLICT DO UPDATE` upsert. (The in-flight guard reduces, but does not eliminate, the window — recompute and matches paths can still overlap.)
- Semantic `pop_rows` are computed over 51 users (self + 50 candidates) vs 500 in heuristic. `top_shared_highlights` rarity weighting is slightly inconsistent between modes.

### Match Cache + Staleness (carried from original 2.4)

- Already partially implemented (hourly cleanup job, `POST /api/me/recompute`)
- `POST /api/me/recompute` now also triggers `POST /api/embeddings/build` before cache refresh
- Hard-expire after 24h (existing behaviour)
- Invalidate when either user's embedding updates

### 2.6 Recommendations Endpoint

**Status:** ✅ Complete (2026-06-06, branch `feat/phase2-match-upgrade`, 947 tests passing).

`GET /api/me/recommendations?item_type=game&limit=10`

Implementation:
1. Load user's `combined` embedding from `user_embeddings`
2. ANN search on `items.embedding <=> user_embedding` WHERE item NOT IN user's `user_items`
3. Optional `item_type` filter (game, artist, track, film, anime, album, etc.)
4. Returns top N with `item_name`, `service`, `item_type`, `similarity_score`
5. Returns 422 `NO_EMBEDDING_AVAILABLE` if user has no combined embedding yet

Cross-domain is automatic: combined taste vector spans all services, so asking for `item_type=film` surfaces recommendations informed by gaming and music taste too. This is the most user-visible AI feature — "here are 5 games you'd probably love" is the demo moment.

For the KI Challenge: recommendations are a compelling live demo. Connect Steam, run the endpoint, get back items you've never played but actually would love. More tangible to judges than matching scores.

**Cross-service dedup + cold-start seeding (added 2026-06-07, after live manual testing surfaced both issues):**
- **Dedup:** a title the user owns on *any* service is excluded — matched via `normalize_title(name)` + `item_type`, not just `item_id` — so a game owned on Steam isn't re-recommended from another service's catalog row under a different id. The same title is never returned twice (highest-similarity copy wins, distinct franchise entries like *Avatar* vs *Avatar: The Way of Water* are kept). Oversample raised to `limit*5` (cap 200) so the extra filtering doesn't under-deliver.
- **Cold start:** recommendations draw from the *shared* item catalog. A near-empty catalog (e.g. a single real user who owns ~all of it) has nothing left to recommend — this looked like a bug ("only 5 recommendations") but was confirmed to be cold-start by `scripts/qa_sweep.py`. `scripts/seed_catalog.py` solves it by seeding ~170 curated, taste-distinctive items across games/artists/films/albums/anime with **production-consistent embeddings** (reuses `item_to_text` + `embed_batch`, so seeded items live in the same vector space as real synced items). Idempotent (`seed-<slug>` external_ids skip on re-run), reversible (`--wipe`). Verified end-to-end: recommendations went from 5 → 15 meaningful, on-taste items for a real account.
- `scripts/qa_sweep.py` is an autonomous, self-cleaning QA harness — seeds a catalog, drives the live HTTP API as a throwaway user, and asserts dedup/exclusion/score-range/item_type-filter/limit/cross-domain/smoke invariants (22/22 pass). Run it after any change to the recommendations path.

### 2.7 Public taste card endpoint

**Status:** Not started. Backend data (`GET /api/me/taste`) already live; this adds a public unauthenticated version for shareable links.

`GET /api/users/{user_id}/taste-card`

- Unauthenticated — no session cookie required
- Returns the same shape as `GET /api/me/taste` but for any user
- Gate: only returns data if `users.is_matchable = true` (user has opted in to visibility)
- 404 if user doesn't exist or hasn't opted in

Unblocks the frontend shareable taste card (Phase 3.4). The visual rendering is the friend's job in Phase 3; this endpoint is the data layer it needs.

### 2.9 User-controlled taste profile (item exclusion)

**Status:** Complete ✅ (2026-06-06). `feat/phase2-item-exclusion` — 880 tests passing.

`user_items.excluded: bool, default False` — new column + migration.

When `excluded = true`, the item is skipped in user vector computation, LLM item selection, and recommendations. This is different from `preference_overrides` (which adjusts weight); exclusion removes the item entirely.

API: `PATCH /api/me/items/{item_id}` — `{"excluded": true/false}`.

**UX decision:** import everything silently. Do NOT show a checkbox list at import time — overwhelming and creates false urgency. Users refine their profile anytime via their taste profile view. The feedback loop (exclude item → archetype updates → "this now feels right") is the core "it understands me" experience.

The three taste control levers (all exist in API):
- `excluded` on `user_items` — remove misrepresentative items
- `preference_overrides.boost_multiplier` — amplify underrepresented items  
- `user_dimension_weights` — weight services differently

Frontend unifies these in a "manage your taste" view (Phase 3, friend's job).

### 2.8 Evaluation framework ✅

**Status:** Complete. `backend/scripts/evaluate.py` — 987 tests passing when Block J review fixes landed (2026-06-07); 998 passing after the follow-up recommendations cross-service dedup fix, `qa_sweep.py`, and `seed_catalog.py` landed the same day (see §2.6 and the Done table above).

A standalone evaluation script that measures how well the AI is actually working — without requiring real users. Without this, we can't answer "how do you know your matching works?" in front of judges.

**Synthetic cohort evaluation (primary method — no real users needed):**
Construct synthetic user profiles with known overlap levels:
- Group A: 5 users sharing 80%+ of items (should rank each other highest)
- Group B: 5 users sharing ~50% of items (should rank within-group above out-group)
- Group C: 5 users sharing ~10% of items (should rank near-random)
- Out-group: 5 users with 0% overlap (should rank lowest)

For each group-A user, check how many group-A users appear in their top-5 semantic matches. Report as Precision@5. This is ground truth — we constructed it. It requires no real users and no user feedback.

**Holdout item prediction (recommendation quality):**
- Hold out 20% of each synthetic user's items before embedding
- Build user vector on remaining 80%
- Check if held-out items rank in top-K of `GET /api/me/recommendations`
- Metric: Precision@10, Recall@10

**Matching mode comparison:**
- `matching_mode` field records which mode was used (`heuristic` vs `semantic`)
- Report average scores per mode — does `semantic` consistently outscore `heuristic`?
- **Caveat (document in report):** higher cosine similarity ≠ better matches in absolute terms, only relative to baseline.

**Qualitative exhibit (required for KI demo — criterion 8):**
- Pre-compute match results for 3–5 real user profiles (your own accounts, friends)
- For each: pick 2 intuitively correct matches and 1 that is wrong or surprising
- For the wrong one: diagnose why (sparse data? missing metadata? genre mismatch?)
- This exhibit answers criterion 8 ("self-critical assessment") better than any number.

**Actual output** (`python scripts/evaluate.py`, refreshed 2026-06-11 after the eval–production filtering alignment, on a 403-item catalog incl. the 170-item seed):
```
Synthetic cohort evaluation (N=20 synthetic users):
  Group A recall@5: 1.00  (high-overlap users correctly ranked)
  Group B recall@5: 1.00  (medium-overlap users ranked)
  Group C recall@5: 1.00  (low-overlap users ranked)
  Group out recall@5: 1.00  (zero-overlap out-group ranked)

Holdout recommendation quality (N=20 users, k=10):
  Hit Rate@10 (pooled): 0.50
  Hit Rate@10 by group:
    Group A: 1.00  (high overlap — sanity check)
    Group B: 0.20  (medium overlap)
    Group C: 0.40  (unique holdout per user — hardest group)
    Group out: 0.40  (cross-domain — sanity check)

Matching mode comparison (Groups A/B/out, 30 pairs):
  heuristic:  avg score 0.537  (rarity-weighted overlap, cohort-wide popularity)
  semantic:   avg score 0.967  (+80% vs heuristic)
  Spearman r (heuristic vs semantic rankings): 0.461
  Per-group breakdown:
    Group A: heuristic 0.583  semantic 0.983  (+69%)  n=10 pairs
    Group B: heuristic 0.444  semantic 0.943  (+112%) n=10 pairs
    Group out: heuristic 0.583 semantic 0.975  (+67%)  n=10 pairs

Centroid-collapse probe (mixed-domain users, N=3):
  pure RPG user → RPG centroid:   0.993  (within-cluster baseline)
  mixed user    → RPG centroid:   0.792
  mixed user    → EDM centroid:   0.805
  → blending two domains pulls the vector to a midpoint: it matches the RPG
    cluster +0.201 weaker than a pure RPG user does (centroid collapse,
    measured not assumed).

Evaluation caveats (self-critical assessment):
  - Synthetic cohort uses seeded engagement scores (0.2–1.0); log1p dampening
    is exercised but items are still from a narrow eval vocabulary.
  - Hit Rate@k pooled across groups is not directly comparable: Group C uses
    unique holdouts per user (hardest), Out-group items cluster tightly (easy).
    Group A/B hit rate is the most informative signal.
  - Recall@5 for Out-group is trivially 1.0 (same EDM cluster). It
    validates domain separation, not intra-domain ranking quality.
Known failure modes (production):
  - Users with < 20 items: degraded recommendation quality (thin signal)
  - Steam-only users: no genre metadata pre-enrichment → lower embedding quality
  - Centroid collapse: users whose items span unrelated clusters produce
    averaged vectors that match neither cluster well (now quantified above)
```

This is the scientific evidence that the AI works. Show this to judges. The caveats and failure modes section is not a weakness — it is criterion 8.

> **Metric naming (corrected 2026-06-07):** the matching metric is **Recall@5** (fraction of same-group peers surfaced — ceiling 1.0, vs P@5's structural ceiling of 4/5) and the holdout metric is **Hit Rate@10** (single held-out item per user → binary). The centroid-collapse failure mode is now *measured* by a dedicated mixed-domain probe, not merely asserted.

> **Hit Rate@10 is catalog-sensitive (found + fixed 2026-06-11).** The originally documented pooled 0.80 was measured on a near-empty catalog and is not reproducible after `seed_catalog.py` populated 170 curated items: re-running gave 0.10 because `_ann_item_query` excluded owned items only by `item_id` while production (`recommendations.py`) also filters owned titles (any service) and dedups repeated titles — seeded title-twins of the user's own items crowded the holdout out of the top-10. Fix: the eval now mirrors production filtering exactly (`filter_candidates_production_style`, oversample `limit*5` cap 200) and counts a hit by `(normalize_title, item_type)` equivalence, since production legitimately returns a different catalog copy of the same title. Result on the 403-item catalog: pooled 0.50 (A=1.00, B=0.20, C=0.40, out=0.40). The drop from 0.80 is honest, not a regression: the holdout now competes against hundreds of taste-adjacent real items instead of a handful — report Hit Rate@k only alongside the catalog size it was measured on.

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

**Onboarding improvement — autocomplete for obsessions:**
- `GET /api/items/search` provides category-aware suggestions from Steam Store (games), TMDB (films/shows), AniList (anime/manga), MusicBrainz (artists), and Open Library (books).
- Frontend `Autocomplete` component in the obsessions step prefills the name field from a suggestion while still allowing free-text entry.
- When a suggestion is selected, the component stores the suggestion's `external_id` and `service` in hidden inputs and forwards them to `POST /api/me/obsessions`; the backend resolves the canonical `items` row and stores `items.id` in `manual_obsessions.item_id`. Free-text entries or unmatched suggestions keep `item_id` null.

### 3.4 Taste Card Page (`/me/taste`)

This is the **primary product during the cold-start phase**. It must be beautiful and shareable before anything else.

- Visual breakdown of the user's taste (games, music, film, etc.)
- Archetype label + description
- Shareable OG image (generate server-side with `@vercel/og` or similar)
- "Copy link" button (copies public profile URL)
- Toast notification system for user feedback
- Item exclusion controls (remove items with trash icon, add back via "add one more")
- Service management and settings access

**Recent improvements (2026-07-19):**
- Added toast notification system with bottom-right positioning, auto-dismiss, and type-appropriate styling
- Fixed taste page UI by removing duplicate "Copy link" and "Share on X" buttons
- Improved item exclusion behavior - removed items now appear in "add one more" section for easy recovery
- Simplified taste page subtitle to "Your taste profile used for matching"

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
