# Developer Guide

Internals, design decisions, and a map of what still needs to be built. Read this if you're onboarding or picking the project back up after a break.

---

## The idea in one paragraph

SyncUp matches people based on their actual taste across platforms — not demographics, not dating. A user connects their Steam, Spotify, and Last.fm accounts. The system ingests their data (games owned + playtime, top artists, top tracks), builds a per-user embedding vector from item-level embeddings trained on public datasets, then finds other users whose vectors are close in cosine space. Users control per-service dimension weights ("weight my music 70%, games 30%") and can boost items that underrepresent their taste (e.g. "I love Disco Elysium despite low hours"). Matches share a profile card and a Discord/social handle — no in-app chat.

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
| GET | `/api/matches` | Top matches (heuristic scorer); requires auth + `is_matchable=true`. Returns empty on cache miss, refreshes in background. |
| GET | `/api/matches/{user_id}` | Single match detail with `shared_highlights`; requires auth + `is_matchable=true`. |
| POST | `/api/me/recompute` | Force match cache refresh; requires auth. Returns 204 immediately. Rate-limited to 1/hour. |

All error responses use the envelope `{"error": {"code": "...", "message": "..."}}`.

Rate limits: signup 5/min, login 10/min, connect 10/min, sync 5/min, taste 30/min, obsessions 60/min read + 30/min write, overrides 60/min read + 30/min write, dimensions 60/min read + 30/min write, profile GET 60/min + PATCH 30/min, onboarding 60/min, matches 30/min, match detail 60/min, recompute 1/hour (all per IP).

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
| `user_embeddings` | The aggregated taste vector per (user, service), 128-dim pgvector |
| `match_cache` | Cached match pairs with score + per-service breakdown JSONB |

`items.embedding` is a `pgvector` column (128-dimensional by default). An IVFFlat index speeds up ANN search but only applies to non-null rows.

`service_connections.sync_status` is constrained to `pending | syncing | ok | error`.

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

## Embedding pipeline (`syncup/embeddings/`)

### Item2Vec (`item2vec.py`)

A Word2Vec model where "words" are item IDs and "sentences" are play sequences (games a user has played, or tracks a user has listened to). Items that appear together in many users' histories end up near each other in vector space.

```python
from pathlib import Path
from syncup.embeddings.item2vec import TrainingConfig, Item2VecModel

config = TrainingConfig(vector_size=128, min_count=5, epochs=10)

# sequences: list of lists of item IDs (strings)
# e.g. [["730", "570", "271590"], ["730", "4000"], ...]
model = Item2VecModel.train(sequences, config)

vec = model.vector("730")            # list[float] for CS2
similar = model.most_similar("730", k=10)
model.save(Path("path/to/model.bin"))

# Later:
model2 = Item2VecModel.load(Path("path/to/model.bin"))
```

### User embeddings (`user_embeddings.py`)

Takes a trained Item2Vec model + a user's item interactions and builds a single weighted-average vector for that user.

```python
from syncup.embeddings.user_embeddings import build_user_vector

# item_id → engagement weight (playtime in minutes, play count, etc.)
interactions = {
    "730": 100.0,   # CS2, 100 hours
    "570": 50.0,    # Dota 2, 50 hours
}

user_vec = build_user_vector(interactions, model)  # list[float], L2-normalised
```

Weight is typically playtime (minutes) for games, play count for tracks, or the user's explicit boost value. Weights are log1p-dampened internally so no single item dominates.

---

## Matching engine (`syncup/matching/engine.py`)

Cosine similarity between user vectors, with optional per-service dimension weighting.

```python
from syncup.matching.engine import UserProfile, match_score, rank_matches

profile_a = UserProfile(user_id="uuid-a", vectors={"steam": vec_a_steam, "spotify": vec_a_spotify})
profile_b = UserProfile(user_id="uuid-b", vectors={"steam": vec_b_steam, "spotify": vec_b_spotify})

# per-service weights — renormalised automatically over shared services
weights = {"steam": 0.3, "spotify": 0.7, "lastfm": 0.0}

score = match_score(profile_a, profile_b, weights)
# Returns float in [-1, 1]. Higher = more similar.

top_k = rank_matches(profile_a, [profile_b, profile_c], weights, k=10)
# Returns list of (UserProfile, score) sorted highest-first.
```

---

## Running tests

```bash
cd backend
pytest                        # all 620 tests
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

**Branch 2 (fix/ingest-hardening) is complete.** All 10 ingest items (I1–I10) merged: client error body stripping (AniList/Trakt/Reddit), RequestError hostname scrubbing (Steam/Last.fm/AniList), OAuth token expiry guard for Trakt and Reddit, httpx.Client shutdown via `close_all()`, LastfmClient validators raise `SyncClientError`, Last.fm artist external_id normalized, ligature expansion in `normalize_title()`, sync route db guard, CSV 50K row cap, engagement_score clamp. 681 tests passing.

**Branch 3 (fix/db-hardening) is complete.** All 13 active items (D1–D13) merged: match_cache hourly cleanup task + `idx_match_cache_computed_at`, `_load_cached_matches` DB-side LIMIT+1/OFFSET pagination, `GET /api/me/taste` SQL window function (`ROW_NUMBER() OVER (PARTITION BY service, item_type)`), dimensions PATCH atomicity fix, four new indexes (D5/D6/D12 + D1), `_refresh_match_cache` phase split (read→compute→write), `require_auth` single JOIN query, `User.updated_at` onupdate removed, `UserItem.fetched_at` and `UserEmbedding.computed_at` Python defaults added. D14 (IVFFlat) deferred to Phase 2.1. 693 tests passing.

**Next: Branch 4 (fix/api-quality)** — sync visibility, response schemas, cursor pagination, input validation, onboarding fixes. See `docs/roadmap.md §Phase 1.11 Branch 4` for the full item list.

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
