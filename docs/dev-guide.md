# Developer Guide

Internals, design decisions, and a map of what still needs to be built. Read this if you're onboarding or picking the project back up after a break.

---

## The idea in one paragraph

SyncUp matches people based on their actual taste across platforms — not demographics, not dating. A user connects services like Steam, Spotify, Last.fm, Letterboxd, AniList, Trakt, Reddit, and RateYourMusic. The system ingests their data (games owned + playtime, top artists, ratings, subreddit subscriptions, etc.), embeds each item with a semantic sentence-transformer model (`all-MiniLM-L6-v2`, 384-dim — see Phase 2 in `roadmap.md`), and aggregates a user's items into a single `combined` taste vector via service-aware two-level pooling (so dimension-weight sliders are authoritative regardless of library size). Matches are found via HNSW ANN cosine search on that vector, with a heuristic item-overlap fallback for users without an embedding yet. Users control per-service dimension weights ("weight my music 70%, games 30%") and can boost or exclude items that misrepresent their taste (e.g. "I love Disco Elysium despite low hours"). Matches share a profile card and a Discord/social handle — no in-app chat.

---

## What's actually running

Start the server:

```bash
cd backend
uvicorn syncup.api.app:app --reload --port 3000
```

Live routes (try them at `http://127.0.0.1:3000/docs`):

| Method | Path | What it does |
|--------|------|-------------|
| GET | `/api/health` | Returns `{"status": "ok", "version": "0.1.0"}` |
| GET | `/api/auth/spotify` | Redirects to Spotify's authorize page (PKCE flow) |
| GET | `/api/auth/spotify/callback` | Completes Spotify OAuth: requires auth, encrypts tokens, writes `service_connections`, redirects to `/` |
| POST | `/api/auth/signup` | Create account with email + password; sets `syncup_session` cookie |
| POST | `/api/auth/login` | Verify credentials; sets `syncup_session` cookie |
| POST | `/api/auth/logout` | Invalidates session; always 204 |
| GET | `/api/me` | Current user + service connections; requires auth. Returns `{user: {...}, connections: [...]}` |
| PATCH | `/api/me` | Partial profile update (`display_name`, `bio`, `discord_handle`, `avatar_url`, `is_matchable`); requires auth. Returns updated user. |
| POST | `/api/connect/steam` | Connect Steam account by `steam_id` or `vanity_url`; requires auth |
| POST | `/api/connect/lastfm` | Connect Last.fm account by `username`; requires auth |
| POST | `/api/connect/letterboxd/import` | CSV file upload (Letterboxd diary export); wipe-and-replace; requires auth *(Phase 1.10)* |
| POST | `/api/connect/rateyourmusic/import` | CSV file upload (RYM ratings export); wipe-and-replace; requires auth *(Phase 1.10)* |
| GET | `/api/connect/{service}/oauth/start` | Start OAuth for `anilist`, `trakt`, `reddit`; requires auth *(Phase 1.10)* |
| GET | `/api/connect/{service}/oauth/callback` | Complete OAuth for the above services *(Phase 1.10)* |
| POST | `/api/sync/{service}` | Trigger background data pull for any registered service; requires auth. Returns `{"status": "syncing", "service": "<name>"}` immediately. Unknown service → 404 SERVICE_NOT_FOUND. |
| GET | `/api/me/taste` | Aggregated taste profile (top items per service, obsessions, overrides); requires auth. Empty services are omitted from the response. |
| GET | `/api/me/obsessions` | List manual obsessions; requires auth. |
| POST | `/api/me/obsessions` | Add a manual obsession (`category`, `name`, `weight`); requires auth. Returns 201. |
| DELETE | `/api/me/obsessions/{id}` | Delete a manual obsession; requires auth. Returns 204. |
| GET | `/api/me/overrides` | List preference overrides with item details; requires auth. |
| POST | `/api/me/overrides` | Create a preference override (`item_id`, `boost_multiplier`, `note`); requires auth. Returns 201. |
| PATCH | `/api/me/overrides/{id}` | Update `boost_multiplier` or `note` on an override; requires auth. |
| DELETE | `/api/me/overrides/{id}` | Delete a preference override; requires auth. Returns 204. |
| GET | `/api/me/dimensions` | Current per-service dimension weights; requires auth. Returns `{"weights": {...}}`. |
| PATCH | `/api/me/dimensions` | Replace dimension weights; backend normalises to sum 1.0; requires auth. |
| GET | `/api/onboarding/status` | Onboarding progress for the current user; requires auth. Returns boolean flags + `next_step` hint. |
| GET | `/api/matches` | Top matches (semantic ANN or heuristic fallback); requires auth + `is_matchable=true`. Returns empty on cache miss, refreshes in background. Response includes `matching_mode`. |
| GET | `/api/matches/{user_id}` | Single match detail with `shared_highlights`; requires auth + `is_matchable=true`. |
| POST | `/api/me/recompute` | Force match cache refresh; requires auth. Returns 204 immediately. Rate-limited to 1/hour. |
| POST | `/api/embeddings/build` | Compute (or recompute) the current user's combined 384-dim taste vector from all non-excluded items with embeddings; applies per-service cap (top 50), dimension weights, and boost multipliers; upserts `user_embeddings` with `service='combined'`; requires auth. Rate-limited to 5/min. Returns 422 `NO_EMBEDDINGS_AVAILABLE` if no items have embeddings yet. *(Phase 2 Block D)* |
| PATCH | `/api/me/items/{item_id}` | Toggle `excluded` on a `user_items` row; excluded items are skipped in embedding builds, LLM vibe synthesis, and recommendations; requires auth. Rate-limited to 60/min. Returns 404 if item not found or belongs to another user. *(Phase 2 Block E)* |
| GET | `/api/me/recommendations` | Cross-domain item recommendations from the user's combined taste vector; skips items already in `user_items`; optional `item_type` filter (game/track/artist/film/show/anime/manga/album/community); `limit` 1–50 (default 10); returns `{items: [{item_name, service, item_type, similarity_score}]}`; 422 `NO_EMBEDDING_AVAILABLE` if no combined embedding yet. Rate-limited to 30/min. *(Phase 2 Block I)* |

All error responses use the envelope `{"error": {"code": "...", "message": "..."}}`.

Rate limits: signup 5/min, login 10/min, connect 10/min, sync 5/min, taste 30/min, obsessions 60/min read + 30/min write, overrides 60/min read + 30/min write, dimensions 60/min read + 30/min write, profile GET 60/min + PATCH 30/min, onboarding 60/min, matches 30/min, match detail 60/min, recompute 1/hour, recommendations 30/min (all per IP).

The rest of the planned API surface is in [api-contract.md](api-contract.md).

---

## Ingest layer (`syncup/ingest/`)

### Architecture overview (Phase 1.10+)

Every service client satisfies the `ServiceClient` Protocol defined in `protocol.py`. The `ServiceRegistry` in `registry.py` maps service name strings to client instances. The sync route calls `get_client(service).fetch_items(connection)` without knowing which service it is.

```
protocol.py        → ServiceClient Protocol, RawItem TypedDict, TokenPair, SyncClientError
registry.py        → ServiceRegistry: dict[str, ServiceClient] + get_client()
_text.py           → normalize_title() — shared title normalisation for cross-service dedup
steam.py           → SteamClient (API key, no OAuth)             ← Live ✅
spotify.py         → SpotifyClient (OAuth PKCE)                  ← Live ✅
lastfm.py          → LastfmClient (API key, no OAuth)            ← Live ✅
letterboxd.py      → LetterboxdClient (CSV import, no auth)      ← Live ✅
anilist.py         → AniListClient (GraphQL OAuth)               ← Live ✅
trakt.py           → TraktClient (REST OAuth)                    ← Live ✅
reddit.py          → RedditClient (OAuth, subreddit membership)  ← Live ✅
rateyourmusic.py   → RateYourMusicClient (CSV import, no auth)   ← Live ✅
crypto.py          → Token encryption (AES-GCM)
```

**`SyncClientError`** is the exception class service clients must raise for expected, user-safe failures (missing token, user not found, bad CSV data). The sync task's `_safe_error_message` trusts `SyncClientError` messages and converts all other exceptions to a generic "Sync failed — please retry" to avoid leaking internal details. Never raise plain `ValueError` from `fetch_items()` or `refresh_token()`.

**CSV-only services (Letterboxd, RateYourMusic):** `fetch_items()` intentionally raises `SyncClientError` directing the user to re-upload. This is not a bug — these services have no API, so re-sync requires a fresh export from the user. The connect route (`/import`) handles data ingestion directly via `parse_csv()`, bypassing the sync route entirely.

**`RawItem`** is the common output type every client returns. Fields:
- `external_id`: service-native ID (Steam appid, AniList media ID, subreddit name, etc.)
- `name`: display name
- `item_type`: `'game'|'film'|'show'|'anime'|'manga'|'track'|'artist'|'album'|'community'`
- `raw_value`: original metric (minutes played, scrobble count, rating value)
- `engagement_score`: pre-computed by the client (0.0–1.0); Steam uses `playtime/max`, Spotify uses rank-based for artists / count/max for tracks, Last.fm uses `playcount/max`
- `raw_type`: `'consumption'` or `'rating'` — determines normalization in the embedding builder
- `last_engaged_at`: most recent engagement timestamp; None when unknown
- `metadata`: free dict, service-specific keys (see `db-schema.md` for load-bearing keys)

**`raw_type` explains the difference:**
- `'consumption'` — the number represents *how much* the user engaged (hours, plays, listens). Normalized with proportion-based formulas (e.g. `playtime/max_playtime`).
- `'rating'` — the number represents *how much the user liked it* (stars out of 5, score out of 100). Normalized per a per-service formula (see roadmap.md for the formulas). Ratings of 0 ("not rated") are treated as absent — the item is not stored.

Note: `engagement_score` uses proportion-based normalization in the client. Log1p dampening (for handling outliers) is applied by the embedding builder during training, not in `user_items`.

### How to add a new service

1. **Create `syncup/ingest/{service}.py`** with a client class that satisfies `ServiceClient`:
   ```python
   from syncup.ingest.protocol import RawItem, ServiceClient, SyncClientError, TokenPair
   from syncup.db.models import ServiceConnection

   class MyServiceClient:
       service_name = "myservice"  # must be ClassVar[str]

       def fetch_items(self, connection: ServiceConnection) -> list[RawItem]:
           # fetch from API, return RawItem list
           # raise SyncClientError for expected, user-safe failures (not ValueError)
           ...

       def refresh_token(self, connection: ServiceConnection) -> TokenPair | None:
           # return None if service doesn't use OAuth tokens
           return None
   ```

   **Error convention:** raise `SyncClientError` (from `protocol.py`) for any expected failure with a message safe to show the user — e.g. missing token, user not found, bad credentials. Do NOT raise plain `ValueError`; the sync task only trusts `SyncClientError` messages and treats all other exceptions as a generic error to avoid leaking internal state.

2. **Register it in `registry.py`**:
   For built-in clients, add instantiation to `register_default_clients()` in `registry.py` (called from the app lifespan). For new services:
   ```python
   from syncup.ingest.myservice import MyServiceClient
   register(MyServiceClient(...))
   ```
   That's it. The sync route and dimensions validation pick it up automatically.

3. **Add tests** in `tests/test_myservice.py`:
   - Mock the HTTP layer (pytest-httpx or httpx mock transport)
   - Test happy path, empty response, invalid/missing data
   - Add `assert isinstance(client, ServiceClient)` for Protocol conformance

4. **Update docs**: add the service to the tables in `db-schema.md` (service column values, metadata keys) and `api-contract.md` (connect endpoint).

5. **Add a connect route** in `api/routes/connect.py` — OAuth services get a start + callback endpoint; CSV import services get a file upload endpoint.



### `spotify.py` — `SpotifyClient`

OAuth 2.0 Authorization Code + PKCE. No client secret needed for PKCE.

```python
client = SpotifyClient(client_id="...", redirect_uri="http://127.0.0.1:3000/...")

# Step 1: send user to Spotify
verifier, challenge = client.generate_pkce_pair()
url = client.get_authorize_url(state="random_state", code_challenge=challenge)

# Step 2: Spotify redirects back with ?code=... — exchange it
tokens = client.exchange_code(code="...", code_verifier=verifier)

# Step 3: fetch data
artists = client.fetch_top_artists(tokens.access_token, limit=50, time_range="medium_term")
recent = client.fetch_recently_played(tokens.access_token, limit=50)

# Step 4: refresh when expired
new_tokens = client.refresh_access_token(tokens.refresh_token)
```

`time_range` options: `"short_term"` (4 weeks), `"medium_term"` (6 months), `"long_term"` (all time).

`SpotifyClient` is a context manager — `with SpotifyClient(...) as c:` closes the HTTP connection automatically.

### `steam.py` — `SteamClient`

API key only, no OAuth. User provides their Steam ID or vanity URL.

```python
client = SteamClient(api_key="...")

# Optional: resolve "halva" → "76561198xxxxxxxxx"
steam_id = client.resolve_vanity_url("halva")

games = client.get_owned_games(steam_id)
# Each game: {"appid": 730, "name": "Counter-Strike 2", "playtime_forever": 1234, ...}

profile = client.get_player_summary(steam_id)
# {"personaname": "halva", "avatarfull": "https://...", ...}
```

### `lastfm.py` — `LastfmClient`

API key only, no OAuth. User provides their Last.fm username.

```python
client = LastfmClient(api_key="...")

artists = client.get_top_artists("username", limit=50, period="overall")
# period options: "overall", "7day", "1month", "3month", "6month", "12month"

tracks = client.get_top_tracks("username", limit=50, period="6month")
# Each track: {"name": "...", "artist": {"name": "..."}, "playcount": "42", ...}
```

Last.fm returns its own error envelope (`{"error": 6, "message": "..."}`) even on HTTP 200. The client checks for this and raises `ValueError` (will be changed to `SyncClientError` in the S1 PR).

### `crypto.py` — token encryption

OAuth tokens must be encrypted before storing in the database. Uses AES-GCM (authenticated encryption).

```python
import os
os.environ["SYNCUP_TOKEN_ENCRYPTION_KEY"] = "<base64-encoded 32-byte key>"

from syncup.ingest.crypto import encrypt_token, decrypt_token

ciphertext: bytes = encrypt_token("my_access_token")
plaintext: str = decrypt_token(ciphertext)
```

Store the `bytes` blob in `service_connections.access_token` and `refresh_token` columns.

The nonce (12 random bytes) is prepended to the ciphertext — no need to store it separately.

Key must be 16, 24, or 32 bytes (128/192/256-bit AES). Generate once per environment:

```bash
python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

---

## Database (`syncup/db/`)

### Models (`models.py`)

Key tables:

| Table | Purpose |
|-------|---------|
| `users` | App accounts — email/password or OAuth-linked |
| `sessions` | Session tokens: one row per active login, expires_at indexed |
| `auth_providers` | Social login links (provider + provider_user_id) |
| `service_connections` | One row per (user, service) — stores encrypted OAuth tokens, sync status |
| `items` | Games, artists, tracks — deduplicated across all users |
| `user_items` | A user's engagement with an item (engagement_score, raw playtime/plays) |
| `preference_overrides` | User-applied boost multipliers on specific items |
| `manual_obsessions` | Freeform items a user adds that aren't from any service |
| `user_dimension_weights` | Per-(user, service) weight for the matching score |
| `user_embeddings` | The aggregated taste vector per (user, service), 384-dim pgvector |
| `match_cache` | Cached match pairs with score + per-service breakdown JSONB |

`items.embedding` is a `pgvector` column (384-dimensional, matching `all-MiniLM-L6-v2` output). An IVFFlat index speeds up ANN search but only applies to non-null rows.

`service_connections.sync_status` is constrained to `pending | syncing | ok | error`.

`user_items` has CHECK constraints on `raw_type` (`consumption | rating`) and `engagement_score` (`0..1`).

### `pgvector.py` — vector literal formatting

`format_vec(vec: list[float]) -> str` serializes a float vector into a pgvector
literal string (`"[0.1,0.2,...]"`, 8-decimal precision) for use in raw SQL
`ORDER BY embedding <=> :vec` queries. Shared by `matches.py` and
`recommendations.py` — don't duplicate it locally.

### Sessions (`session.py`)

In FastAPI route handlers, use the `get_db` dependency — it pulls the session factory from `app.state.db` (set at startup) and handles rollback on exception:

```python
from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session
from syncup.db.session import get_db

def my_route(db: Annotated[Session, Depends(get_db)]) -> ...:
    user = db.get(User, user_id)
    db.commit()   # caller commits explicitly
```

The lower-level `get_session(factory)` generator is available for scripts and one-off use outside of FastAPI.

### Migrations (Alembic)

The initial migration is at `alembic/versions/20260421_0001_initial_schema.py`.

```bash
# Apply migrations (run this once after creating the DB)
alembic upgrade head

# Create a new migration after changing models.py
alembic revision --autogenerate -m "describe what changed"
alembic upgrade head
```

---

## Embedding pipeline (`syncup/embeddings/`) — Phase 2 (live)

This is the current, live pipeline. It replaced the original Item2Vec-on-public-datasets plan — see `docs/brainstorm.md §ML Architecture Decisions` for why separate per-service Item2Vec models can't support cross-domain matching.

### `semantic.py` + `item_text.py` — item embeddings

Every catalog item is converted to a descriptive string (`item_to_text`, format varies per service/item_type — see roadmap §2.1) and embedded with a lazy-loaded `sentence-transformers` model (`all-MiniLM-L6-v2`, 384-dim, L2-normalised):

```python
from syncup.embeddings.semantic import embed_text, embed_batch
from syncup.embeddings.item_text import item_to_text

text = item_to_text(item)            # e.g. "Disco Elysium — game, RPG, narrative"
vec = embed_text(text)               # list[float], 384-dim, L2-normalised
vecs = embed_batch([text1, text2])   # batched, more efficient for many items
```

Run `scripts/populate_item_embeddings.py` (after the enrichment scripts) to backfill `items.embedding` for the whole catalog.

### `user_embeddings.py` — service-aware two-level aggregation

Builds the `combined` user vector that ANN search operates on. Two pure functions, no model dependency — they take pre-fetched `(vector, weight)` pairs:

```python
from syncup.embeddings.user_embeddings import aggregate_vectors, combine_service_vectors

# 1. Within a service: log1p-dampened weighted sum → unit "service taste direction"
service_vec = aggregate_vectors([(item_vec * boost, engagement_score), ...])

# 2. Across services: LINEAR weighted sum by dimension weight → combined vector
combined_vec = combine_service_vectors([(steam_vec, 0.3), (spotify_vec, 0.7)])
```

Mean-pooling each service to unit mass *before* applying the dimension weight is what makes the weight slider authoritative regardless of library size — see roadmap §2.3 for the full reasoning (this was a real bug found and fixed during the Block J review). `POST /api/embeddings/build` (in `api/routes/embeddings.py`) wires this together: per-service cap of top 50 by `engagement_score`, applies `boost_multiplier` and `dim_weight`, upserts `user_embeddings` with `service='combined'`.

`item2vec.py` (`Item2VecModel`, `build_user_vector`) remains in the codebase as a legacy/future-optional path — not part of the live pipeline. See roadmap §Phase 2 architecture note.

---

## Matching engine — Phase 2 (live)

`_refresh_match_cache` in `api/routes/matches.py` is the live matching path:

1. **Semantic (preferred):** if the user has a `user_embeddings` row with `service='combined'`, runs an HNSW ANN cosine search (`embedding <=> :query` via pgvector) against other matchable users' combined vectors. `score = 1 - cosine_distance`, candidates with `score <= 0` (antipodal) filtered. Once a user has a combined embedding, this path is authoritative — it never falls back to heuristic, even if every neighbour scores ≤ 0.
2. **Heuristic (fallback):** for users without a combined embedding, `syncup/matching/heuristic.py` does rarity-weighted item-overlap scoring (`syncup/matching/engine.py` provides the underlying `UserProfile`/cosine-similarity primitives it builds on).

Results are written to `match_cache` with a `matching_mode: "semantic" | "heuristic"` field so the frontend (and the eval script) can distinguish them.

```python
from syncup.matching.heuristic import heuristic_score

score = heuristic_score(user_a_item_ids, user_b_item_ids, item_popularity)
# Rarity-weighted overlap, normalised to [0, 1) via raw/(raw+1)
```

---

## Running tests

```bash
cd backend
pytest                        # all 998 tests
pytest tests/test_spotify.py  # one module
pytest --cov=syncup           # with coverage report
```

Ingest client tests use `httpx`'s mock transport — no live API calls. Auth route tests use FastAPI's `TestClient` with `dependency_overrides` for the DB session (no real DB required). The DB schema test (`test_db_schema.py`) uses SQLAlchemy reflection against the live PostgreSQL container — make sure `docker compose up -d` is running.

---

## What to build next

See **[roadmap.md](roadmap.md)** for the full phased build order, current status, and open UX decisions. That document is the single source of truth for implementation priority.

**Phase 1.10 Foundation is complete.** The `ServiceClient` Protocol, `ServiceRegistry`, migrations 0006–0007, and retrofitted clients (Steam, Spotify, Last.fm) are all live.

**S1 (Letterboxd CSV import) is complete.** `SyncClientError`, `LetterboxdClient`, and `POST /api/connect/letterboxd/import` are live. 417 tests passing.

**S2 (AniList GraphQL OAuth) is complete.** `AniListClient`, `GET /api/connect/anilist/oauth/start`, and `GET /api/connect/anilist/oauth/callback` are live. 458 tests passing.

**S3 (Trakt REST OAuth) is complete.** `TraktClient`, `GET /api/connect/trakt/oauth/start`, and `GET /api/connect/trakt/oauth/callback` are live. 518 tests passing.

**S4 (Reddit OAuth) is complete.** `RedditClient`, `GET /api/connect/reddit/oauth/start`, and `GET /api/connect/reddit/oauth/callback` are live. 577 tests passing.

**S5 (RateYourMusic CSV import) is complete.** `RateYourMusicClient`, `POST /api/connect/rateyourmusic/import`, and RateYourMusic taste rendering are live. 620 tests passing.

**Phase 1.11 — Backend Hardening Sprint:**

**Branch 1 (fix/security-hardening) is complete.** All 12 security items (S1–S12) merged: timing-safe OAuth, encryption key guard, error body stripping, proxy rate limiter, cookie attributes, security headers, required env vars, logout rate limit, CORS validation, error message injection prevention, session secret default, health fingerprint removal.

> The proxy rate limiter trusts `X-Forwarded-For` only from hosts listed in
> `TRUSTED_PROXY_HOSTS` (comma-separated, defaults to loopback `127.0.0.1,::1`).
> Set this to your reverse-proxy's address in any multi-host deployment —
> trusting `"*"` lets any client spoof their IP and bypass rate limits.

**Branch 2 (fix/ingest-hardening) is complete.** All 10 ingest items (I1–I10) merged: client error body stripping (AniList/Trakt/Reddit), RequestError hostname scrubbing (Steam/Last.fm/AniList), OAuth token expiry guard for Trakt and Reddit, httpx.Client shutdown via `close_all()`, LastfmClient validators raise `SyncClientError`, Last.fm artist external_id normalized, ligature expansion in `normalize_title()`, sync route db guard, CSV 50K row cap, engagement_score clamp. 681 tests passing.

**Branch 3 (fix/db-hardening) is complete.** All 13 active items (D1–D13) merged: match_cache hourly cleanup task + `idx_match_cache_computed_at`, `_load_cached_matches` DB-side LIMIT+1/OFFSET pagination, `GET /api/me/taste` SQL window function (`ROW_NUMBER() OVER (PARTITION BY service, item_type)`), dimensions PATCH atomicity fix, four new indexes (D5/D6/D12 + D1), `_refresh_match_cache` phase split (read→compute→write), `require_auth` single JOIN query, `User.updated_at` onupdate removed, `UserItem.fetched_at` and `UserEmbedding.computed_at` Python defaults added. D14 (IVFFlat) deferred to Phase 2.1. 693 tests passing.

**Branch 4 (fix/api-quality) is complete.** All 13 items (A1–A13) merged: sync `poll_url`, match keyset cursor `(score, user_b_id)`, whitespace validators, obsession weight + category bounds, override boost bound, onboarding `has_taste_data` real UserItem query + `next_step` ordering, structured 422 response, Spotify routes moved to `connect.py`, type annotation fixes. 719 tests passing.

**OAuth follow-up (fix/oauth-security-h1-h2-h3) is complete.** Three HIGH issues from post-Phase-1.11 oauth-security-reviewer audit: H1 — `GET /api/auth/spotify` now requires `RequireAuth` + `@limiter.limit("10/minute")` (was missing both, unlike every other OAuth start route); H2 — `validate_key()` added to `crypto.py` and called in `lifespan`, so a wrong-length encryption key raises `RuntimeError` at startup rather than on the first token operation; H3 — `anilist_oauth_callback` `SyncClientError` handler now uses a fixed message instead of `str(exc)`, preventing GraphQL error details from reaching API consumers. 722 tests passing.

**Phase 1.11 backend hardening sprint is complete.**

**Phase 2 Block A (feat/phase2-schema) is complete.** `EMBEDDING_DIM` changed 128 → 384 for sentence-transformers `all-MiniLM-L6-v2`. `UserItem.excluded` column added for Phase 2 item exclusion. Four vibe synthesis columns added to `User` (`vibe_summary`, `archetype`, `key_themes`, `vibe_computed_at`). Migration `20260520_0010` applied — vector columns widened, stale embeddings cleared, IVFFlat index recreated. Config gains `embedding_model_name`, `llm_api_key`, `tmdb_api_key`. ML deps (`sentence-transformers`, `implicit`, `anthropic`) added to `[ml]` extras. 726 tests passing.

**Phase 2 Block B (feat/phase2-semantic) is complete.** `syncup/embeddings/semantic.py` — lazy-loaded SentenceTransformer wrapper; `embed_text()` and `embed_batch()` with L2-normalized output. `syncup/embeddings/item_text.py` — `item_to_text(item)` serializer per roadmap §2.1; handles all item_types; never raises. AniList `genres` field added to GraphQL query and stored in `metadata["genres"]`. 785 tests passing.

**UMAP embedding validation complete (2026-06-04).** `backend/notebooks/embedding_validation.py` — 51 items across Steam/music/anime, embedded with `all-MiniLM-L6-v2`, reduced to 2D via UMAP. Result: cross-domain same-vibe similarity 0.273 vs. different-vibe 0.225 (delta +0.049). Positive signal confirmed — architecture is viable. Key spot-checks: Bloodborne × Junji Ito Collection = 0.413, Pathologic 2 × The Caretaker = 0.380, Rocket League × Burial = 0.013. Description bias noted (acclaimed works cluster on vocabulary, not vibe) — manageable limitation.

**Phase 2 Block H (feat/phase2-match-upgrade) is complete.** Semantic ANN matching path added alongside the existing heuristic scorer. `_refresh_match_cache` now tries the semantic path first (requires a `combined` user embedding): runs HNSW ANN search via pgvector `<=>` operator on `user_embeddings WHERE service='combined'`, returns up to 50 candidates, scores as `1 - cosine_distance` (candidates with `score <= 0` filtered). Falls back to heuristic item-overlap when no embedding exists. `match_cache` gains `matching_mode TEXT` column (`'heuristic'|'semantic'`). `POST /api/me/recompute` queues `_build_embedding_bg` before `_refresh_match_cache`. Migration `20260606_0011` creates `matching_mode` column and recreates the ANN index as HNSW (replaces planned IVFFlat — HNSW requires no lists-tuning). 931 tests passing.

**Phase 2 Block J (feat/phase2-evaluation) is complete.** `backend/scripts/evaluate.py` — standalone evaluation framework. Constructs a 20-user synthetic cohort (4 groups: high/medium/low/zero overlap), measures **Recall@5** matching quality per group, **Hit Rate@10** holdout recommendation quality per group, compares semantic vs heuristic average scores (with Spearman r) on Groups A/B/out pairs, and runs a **centroid-collapse probe** on mixed-domain users. Results: Recall@5=1.00 all groups, Hit Rate@10 pooled=0.80, semantic avg=0.967 vs heuristic 0.537 (+80%, Spearman r=0.46), mixed-domain users sit ~0.20 weaker to their parent cluster than pure users (collapse quantified). 987 tests passing at the time; 998 after the same-day follow-up work below (recs dedup, `qa_sweep.py`, `seed_catalog.py`).

**Block J review fixes (2026-06-07) — the keystone-PR hardening pass.** A strict review (manual + ml-reviewer + code-reviewer, mapped to KI criteria) surfaced two design-vs-implementation gaps and several robustness items, all fixed:

- **Service-aware user embedding (the important one).** The user vector is now built in two levels so the per-service **dimension-weight slider is authoritative regardless of library size**. Previously a flat global weighted sum let item count dominate (50 games + 5 tracks at music=0.7 still leaned games). Now: (1) *within* a service, `aggregate_vectors` produces a unit "service taste direction" (log1p-dampened engagement, boost as a within-service lever); (2) *across* services, `combine_service_vectors` does a **linear** weighted sum by dimension weight (no log1p) — so 0.7 vs 0.3 → exactly 0.7:0.3. Both are pure functions in `user_embeddings.py`.
- **Honest log1p framing.** log1p runs on already-normalized `engagement_score ∈ [0,1]` where it is near-linear (mild concave reweighting), *not* the raw-play-count whale-dampener the old docstring claimed. Docstring corrected.
- **Semantic mode is authoritative.** Once a combined embedding exists, `_refresh_match_cache` never falls back to heuristic (even when all ANN neighbours score ≤ 0), eliminating matching_mode churn on symmetric pairs.
- **In-flight refresh guard.** `_try_acquire_refresh`/`_release_refresh` stop repeated empty-page `/api/matches` requests from stacking redundant background refreshes.
- **Drift-tolerant highlights.** `_parse_highlights` validates each cached highlight and skips malformed entries instead of 500-ing the list.
- **Eval honesty.** Mixed-domain centroid-collapse probe (measured, not asserted) + `Item(meta=)` genre-persistence fix in the eval script.

Run with:
```bash
cd backend && source .venv/bin/activate
python scripts/evaluate.py                   # full 20-user cohort
python scripts/evaluate.py --cohort-size 2   # fast 8-user smoke test
python scripts/evaluate.py --no-cleanup      # keep synthetic rows for inspection
```

**Operational scripts (recommendations cold-start + QA):**
- `scripts/seed_catalog.py` — seeds ~170 curated, taste-distinctive items (games,
  artists, films, albums, anime) with **production-consistent embeddings** (reuses
  `item_to_text`). Recommendations draw from the shared catalog, so without this a
  single-user instance has nothing to recommend (it owns ~all items). Idempotent
  (`seed-<slug>` external_ids skip on re-run) and reversible (`--wipe`). Seeded
  items use realistic service names; the recommendations owned-by-title dedup
  ensures a user is never recommended a title they already own under their real
  synced copy.
  ```bash
  python scripts/seed_catalog.py            # insert (skips existing)
  python scripts/seed_catalog.py --dry-run  # preview
  python scripts/seed_catalog.py --wipe     # remove all seeded items
  ```
- `scripts/qa_sweep.py` — autonomous, self-cleaning QA harness: seeds a catalog,
  drives the live HTTP API as a throwaway user, and asserts invariants
  (recommendation dedup, owned-by-title exclusion, score range/order, item_type
  filter, limit bounds, cross-domain recs, endpoint smoke). 22/22 pass.

**Recommendations cross-service dedup (2026-06-07):** `GET /api/me/recommendations`
excludes a title the user owns on *any* service (normalize_title + item_type, not
just item_id) and never returns the same title twice — the higher-similarity copy
wins; distinct franchise entries are preserved. Oversample is `limit*5` (cap 200)
so the post-filters don't under-deliver.

---

## Known gaps and sharp edges

- **Expired session cleanup**: `sessions.expires_at` is indexed but nothing deletes stale rows. Add a `pg_cron` job or a background task before production.
- **`match_cache` stale row cleanup**: rows older than 24h are excluded by the freshness query but never deleted. Add a cleanup job before production to prevent table bloat.
- **No batching in sync**: `_do_sync_generic` issues 2 DB roundtrips per item. For Steam libraries with 1000+ games this is 2000+ roundtrips. Pre-existing behavior, not a regression. Batch if performance becomes an issue.

---

## Before you go to production — database checklist

The current `docker-compose.yml` is intentionally minimal for local dev. Before deploying anywhere real, address all of these:

### 1. Replace the superuser with a limited role

`POSTGRES_USER=syncup` makes `syncup` a PostgreSQL superuser — it can drop tables, create roles, and modify the DB engine. The application doesn't need any of that.

Fix: use a separate admin user to bootstrap, then create a least-privilege app role:

```sql
-- Run as the postgres superuser during provisioning
CREATE USER syncup_app WITH PASSWORD 'strong-random-password';
GRANT CONNECT ON DATABASE syncup TO syncup_app;
GRANT USAGE ON SCHEMA public TO syncup_app;
-- Grant only what the app actually needs
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO syncup_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO syncup_app;
-- Ensure future tables get the same grants
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO syncup_app;
```

Then set `DATABASE_URL=postgresql://syncup_app:...@host:5432/syncup` in production.

### 2. Never hardcode the DB password

`POSTGRES_PASSWORD: syncup` in `docker-compose.yml` is a dev placeholder. For any real environment:

- **Docker Swarm**: use Docker secrets (`secrets:` block in compose)
- **Kubernetes**: use a Secret resource mounted as an env var
- **Managed hosting (RDS, Cloud SQL, Supabase)**: use IAM auth or inject via the platform's secret manager
- **Bare metal / VM**: inject via environment, not baked into the image

### 3. Pin the image to a specific digest

`pgvector/pgvector:pg18` is a floating tag — it will silently update when you `docker pull`. For production, pin to a specific digest:

```bash
# Get the current digest
docker inspect --format='{{index .RepoDigests 0}}' pgvector/pgvector:pg18
# e.g. pgvector/pgvector@sha256:abc123...
```

Then use that in your production compose or Kubernetes manifest:

```yaml
image: pgvector/pgvector@sha256:<digest>
```

Update the digest intentionally when you want to upgrade, not automatically on deploy.

### 4. Other production hardening to add

| Concern | What to do |
|---------|-----------|
| Connection pool limits | Set `max_connections` in PG config; tune `db_pool_size` in `Settings` to match |
| Statement timeout | `ALTER SYSTEM SET statement_timeout = '30s';` — prevents runaway queries |
| Idle transaction timeout | `ALTER SYSTEM SET idle_in_transaction_session_timeout = '30s';` |
| Backups | `pg_dump` on a cron, or use managed DB backups (RDS automated backups, etc.) |
| TLS | Enforce `sslmode=require` in `DATABASE_URL`; provision a cert |
| Monitoring | Enable `pg_stat_statements` extension; point to Grafana or equivalent |

---

## Local dev tips

- Always use `http://127.0.0.1:3000` not `http://localhost:3000` — Spotify validates the redirect URI exactly, and cookies don't carry across the redirect if the host changes.
- `uvicorn --reload` watches for file changes and restarts automatically.
- The Swagger UI at `/docs` has "Try it out" buttons — use them instead of curl for quick manual testing.
- `pytest -x` stops at the first failure (faster feedback loop during development).
- `ruff check .` and `mypy .` (from `backend/`) must both pass before committing.
