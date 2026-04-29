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
| POST | `/api/connect/steam` | Connect Steam account by `steam_id` or `vanity_url`; requires auth |
| POST | `/api/connect/lastfm` | Connect Last.fm account by `username`; requires auth |
| POST | `/api/sync/{service}` | Trigger background data pull for `spotify`, `steam`, or `lastfm`; requires auth. Returns `{"status": "syncing"}` immediately. |
| GET | `/api/me/taste` | Aggregated taste profile (top items per service, obsessions, overrides); requires auth. Empty services are omitted from the response. |

All error responses use the envelope `{"error": {"code": "...", "message": "..."}}`.

Rate limits: signup 5/min, login 10/min, sync 5/min, taste 30/min (all per IP).

The rest of the planned API surface is in [api-contract.md](api-contract.md).

---

## Ingest layer (`syncup/ingest/`)

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

Last.fm returns its own error envelope (`{"error": 6, "message": "..."}`) even on HTTP 200. The client checks for this and raises `ValueError`.

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
pytest                        # all 197 tests
pytest tests/test_spotify.py  # one module
pytest --cov=syncup           # with coverage report
```

Ingest client tests use `httpx`'s mock transport — no live API calls. Auth route tests use FastAPI's `TestClient` with `dependency_overrides` for the DB session (no real DB required). The DB schema test (`test_db_schema.py`) uses SQLAlchemy reflection against the live PostgreSQL container — make sure `docker compose up -d` is running.

---

## What to build next

See **[roadmap.md](roadmap.md)** for the full phased build order, current status, and open UX decisions. That document is the single source of truth for implementation priority.

The immediate next step is **Phase 1.3: Manual Obsessions** (`POST/GET/DELETE /api/me/obsessions`).

---

## Known gaps and sharp edges

- **Expired session cleanup**: `sessions.expires_at` is indexed but nothing deletes stale rows. Add a `pg_cron` job or a background task before production.
- **CORS origins are hardcoded in `app.py`**: `Settings.cors_allowed_origins` already exists in `config.py` (overridable via env), but `app.py` still passes a hardcoded list to `CORSMiddleware` instead of reading from settings. Fix before any non-local deployment.
- **`SESSION_SECRET` not set**: `.env` has an empty `session_secret`. Generate before building any signed-cookie features.

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
