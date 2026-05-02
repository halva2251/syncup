# SyncUp

Match people by the vibe of their actual taste — not demographics, not dating.

Connect Steam, Last.fm, and Spotify. A cross-domain embedding model learns what your library says about you. Find people who share your wavelength, with control over which dimensions matter.

---

## What's been built

| Layer | Status | Notes |
|-------|--------|-------|
| Spotify OAuth + PKCE client | done | token exchange, refresh, top artists, recent tracks |
| Steam API client | done | owned games, player summary, vanity URL resolution |
| Last.fm API client | done | top artists, top tracks with period filtering |
| AES-GCM token encryption | done | for storing OAuth tokens at rest |
| SQLAlchemy schema + Alembic migrations | done | full schema: users, items, embeddings, matches |
| Item2Vec embedding model | done | gensim Word2Vec wrapper, train from play sequences |
| User taste vectors | done | weighted average of item embeddings |
| Matching engine | done | cosine similarity with per-service dimension weights |
| Auth routes | done | signup, login, logout, session-based auth |
| Service connect routes | done | Steam (steam_id/vanity), Last.fm, Spotify OAuth |
| Sync routes | done | `POST /api/sync/{service}` — background data pull |
| Taste profile endpoint | done | `GET /api/me/taste` — top items per service |
| Manual obsessions | done | `GET/POST/DELETE /api/me/obsessions` |
| Preference overrides | done | `GET/POST/PATCH/DELETE /api/me/overrides` |
| Dimension weights | done | `GET/PATCH /api/me/dimensions` |
| Profile edit | done | `PATCH /api/me` |
| Onboarding status | done | `GET /api/onboarding/status` |
| Rate limiting | done | per-endpoint limits on all routes |
| PostgreSQL + Docker | done | `docker compose up -d` in `backend/` |
| Heuristic matcher + GET /api/matches | done | Phase 1.9 — rarity-weighted overlap, cache-aside, BackgroundTasks refresh |
| 338 passing tests | done | |
| ML training pipeline | not started | Phase 2 — Item2Vec on public datasets |
| Frontend | not started | Phase 3 — Next.js, deferred until after Phase 2 |

---

## Quickstart

### 1. Clone and enter the backend

```bash
git clone <repo>
cd syncup/backend
```

### 2. Create a virtual env and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev,ml]"
```

Or with uv (faster):

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev,ml]"
```

### 3. Set up environment variables

Copy this template to `backend/.env` and fill in the blanks:

```dotenv
# Steam
STEAM_API_KEY=

# Last.fm
LASTFM_API_KEY=
LASTFM_SHARED_SECRET=

# Spotify
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
SPOTIFY_REDIRECT_URI=http://127.0.0.1:3000/api/auth/spotify/callback

# PostgreSQL
DATABASE_URL=postgresql://syncup:syncup@localhost:5432/syncup

# App secrets
SESSION_SECRET=
SYNCUP_TOKEN_ENCRYPTION_KEY=   # base64-encoded 32-byte AES key (see below)
```

For the encryption key, generate one:

```bash
python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

See [docs/api-keys.md](docs/api-keys.md) for how to register each service and get its credentials.

### 4. Start PostgreSQL and run migrations

```bash
# Start the DB container (from backend/)
docker compose up -d

# Run migrations (use the venv alembic, not the system one)
.venv/bin/alembic upgrade head
```

### 5. Run the server

```bash
# From backend/
uvicorn syncup.api.app:app --reload --port 3000
```

Or with uv:

```bash
uv run uvicorn syncup.api.app:app --reload --port 3000
```

Open `http://127.0.0.1:3000/docs` — Swagger UI with all routes and try-it-out.

> **Important:** Always use `http://127.0.0.1:3000`, not `http://localhost:3000`. Spotify's OAuth redirect requires the exact URI registered in the dashboard, and session cookies won't survive the redirect if the host doesn't match.

### 6. Run tests

```bash
cd backend
pytest
```

---

## Structure

```
syncup/
├── backend/
│   ├── syncup/
│   │   ├── api/         app.py — FastAPI routes + lifespan
│   │   ├── ingest/      spotify.py, steam.py, lastfm.py, crypto.py
│   │   ├── embeddings/  item2vec.py, user_embeddings.py
│   │   ├── matching/    engine.py
│   │   └── db/          models.py, session.py, base.py
│   ├── alembic/         migrations
│   ├── tests/           one file per module
│   ├── .env             secrets (never commit)
│   └── pyproject.toml
├── frontend/            Next.js (not started)
└── docs/
    ├── api-contract.md  planned API surface
    ├── api-keys.md      how to register each service
    ├── db-schema.md     schema reference
    └── dev-guide.md     internals, design decisions, what to build next
```

---

## Environment variables reference

| Variable | Required | Description |
|----------|----------|-------------|
| `SPOTIFY_CLIENT_ID` | yes | from Spotify developer dashboard |
| `SPOTIFY_CLIENT_SECRET` | yes | from Spotify developer dashboard |
| `SPOTIFY_REDIRECT_URI` | yes | must match dashboard exactly |
| `STEAM_API_KEY` | for Steam routes | from steamcommunity.com/dev/apikey |
| `LASTFM_API_KEY` | for Last.fm routes | from last.fm/api/account/create |
| `LASTFM_SHARED_SECRET` | for Last.fm routes | same registration |
| `DATABASE_URL` | for DB | `postgresql://user:pass@host:port/dbname` |
| `SESSION_SECRET` | for sessions | random string, keep secret |
| `SYNCUP_TOKEN_ENCRYPTION_KEY` | for token storage | base64-encoded 16/24/32-byte key |

---

## Docs

- [docs/api-keys.md](docs/api-keys.md) — how to register each service and get credentials
- [docs/api-contract.md](docs/api-contract.md) — API surface: routes, request/response shapes
- [docs/db-schema.md](docs/db-schema.md) — full database schema
- [docs/dev-guide.md](docs/dev-guide.md) — internals, design decisions, what to build next
- [docs/roadmap.md](docs/roadmap.md) — phased build plan and current status
- [docs/product-strategy.md](docs/product-strategy.md) — cold start strategy, positioning, target user

---

## License

MIT — see [LICENSE](LICENSE).
