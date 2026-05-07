# SyncUp

Match people by the vibe of their actual taste — not demographics, not dating.

Connect Steam, Last.fm, Spotify, and Letterboxd. A cross-domain embedding model learns what your library says about you. Find people who share your wavelength, with control over which dimensions matter.

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
| Service connect routes | done | Steam, Last.fm, Spotify OAuth, Letterboxd CSV import |
| Sync routes | done | `POST /api/sync/{service}` — background data pull |
| Taste profile endpoint | done | `GET /api/me/taste` — top items per service |
| Manual obsessions | done | `GET/POST/DELETE /api/me/obsessions` |
| Preference overrides | done | `GET/POST/PATCH/DELETE /api/me/overrides` |
| Dimension weights | done | `GET/PATCH /api/me/dimensions` |
| Profile edit | done | `PATCH /api/me` |
| Onboarding status | done | `GET /api/onboarding/status` |
| Rate limiting | done | per-endpoint limits on all routes |
| PostgreSQL + Docker | done | `docker compose up -d` in `backend/` |
| Heuristic matcher + matches API | done | rarity-weighted overlap, cache-aside, BackgroundTasks refresh |
| `ServiceClient` Protocol + `ServiceRegistry` | done | service-agnostic dispatch for ingest pipeline |
| `SyncClientError` | done | user-safe exception; sync task trusts its message |
| Letterboxd CSV import | done | `POST /api/connect/letterboxd/import` — wipe-and-replace |
| 420 passing tests | done | |
| ML training pipeline | not started | Phase 2 — Item2Vec on public datasets |
| Frontend | not started | Phase 3 — Next.js, deferred until after Phase 2 |

---

## Quickstart

> **This project uses [uv](https://docs.astral.sh/uv/) for dependency management.** Do not use `pip install` or `python -m venv` — they won't pick up the lockfile and you'll get missing module errors when running tests or the server.
>
> Install uv if you don't have it:
> ```bash
> curl -LsSf https://astral.sh/uv/install.sh | sh
> ```

### 1. Clone and enter the backend

```bash
git clone <repo>
cd syncup/backend
```

### 2. Install dependencies

```bash
uv sync --extra dev
```

This reads `uv.lock` and creates a `.venv` inside `backend/` automatically. To also install ML dependencies (PyTorch, gensim — only needed for embedding training):

```bash
uv sync --extra dev --extra ml
```

### 3. Set up environment variables

Copy this template to `backend/.env` and fill in the blanks:

```dotenv
# Set to true in local dev — skips the encryption key startup check
DEBUG=true

# Steam
STEAM_API_KEY=

# Last.fm
LASTFM_API_KEY=
LASTFM_SHARED_SECRET=

# Spotify
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
SPOTIFY_REDIRECT_URI=http://127.0.0.1:3000/api/auth/spotify/callback

# PostgreSQL (matches docker-compose.yml defaults)
DATABASE_URL=postgresql://syncup:syncup@localhost:5432/syncup

# Session secret — any random string
SESSION_SECRET=change-me-in-prod

# AES-GCM key for encrypting OAuth tokens at rest
SYNCUP_TOKEN_ENCRYPTION_KEY=   # generate one with the command below
```

Generate the encryption key:

```bash
uv run python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

See [docs/api-keys.md](docs/api-keys.md) for how to register each service and get credentials.

### 4. Start PostgreSQL and run migrations

```bash
# Start the DB container (from backend/)
docker compose up -d

# Apply all migrations
uv run alembic upgrade head
```

### 5. Run the server

```bash
# From backend/
uv run uvicorn syncup.api.app:app --reload --port 3000
```

Open `http://127.0.0.1:3000/docs` for the Swagger UI with try-it-out on every route.

> **Always use `http://127.0.0.1:3000`, not `http://localhost:3000`.** Spotify's OAuth redirect URI must match the dashboard registration exactly, and session cookies don't survive a host change mid-redirect.

### 6. Run tests

```bash
# From backend/ — the DB container must be running (needed for schema tests)
uv run pytest
```

Useful variants:

```bash
uv run pytest tests/test_letterboxd.py                          # single file
uv run pytest tests/test_connect.py::test_letterboxd_import_success  # single test
uv run pytest -x                                                # stop at first failure
uv run pytest --cov=syncup --cov-report=term-missing            # with coverage
uv run pytest -q                                                # quiet output
```

> **If you get `ModuleNotFoundError` or `command not found: pytest`** you're hitting the system Python instead of the project venv. Always prefix with `uv run`, which runs inside the managed venv without needing to activate it. Alternatively, activate once with `source .venv/bin/activate` and then use `pytest` directly.

---

## Structure

```
syncup/
├── backend/
│   ├── syncup/
│   │   ├── api/
│   │   │   ├── app.py          FastAPI app + lifespan + exception handlers
│   │   │   ├── routes/         one file per route group
│   │   │   └── schemas.py      shared Pydantic output models
│   │   ├── auth/               signup, login, session middleware
│   │   ├── ingest/
│   │   │   ├── protocol.py     ServiceClient Protocol, RawItem, SyncClientError
│   │   │   ├── registry.py     ServiceRegistry — service-agnostic dispatch
│   │   │   ├── steam.py        SteamClient
│   │   │   ├── spotify.py      SpotifyClient
│   │   │   ├── lastfm.py       LastfmClient
│   │   │   ├── letterboxd.py   LetterboxdClient (CSV import)
│   │   │   ├── _text.py        normalize_title() — cross-service dedup
│   │   │   └── crypto.py       AES-GCM token encryption
│   │   ├── embeddings/         item2vec.py, user_embeddings.py
│   │   ├── matching/           engine.py, heuristic.py
│   │   └── db/                 models.py, session.py
│   ├── alembic/                migrations (one per schema change)
│   ├── tests/                  one file per module, pytest
│   ├── docker-compose.yml      PostgreSQL + pgvector
│   ├── .env                    secrets (never commit)
│   └── pyproject.toml
├── frontend/                   Next.js (not started)
└── docs/
    ├── api-contract.md         route shapes, status codes, live vs planned
    ├── api-keys.md             how to register each service
    ├── db-schema.md            full database schema
    ├── dev-guide.md            internals, patterns, what to build next
    ├── roadmap.md              phased build plan and current status
    └── product-strategy.md     cold start, positioning, target user
```

---

## Environment variables reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DEBUG` | no | Set `true` in dev to skip encryption key startup check |
| `SPOTIFY_CLIENT_ID` | yes | from Spotify developer dashboard |
| `SPOTIFY_CLIENT_SECRET` | yes | from Spotify developer dashboard |
| `SPOTIFY_REDIRECT_URI` | yes | must match dashboard exactly |
| `STEAM_API_KEY` | for Steam | from steamcommunity.com/dev/apikey |
| `LASTFM_API_KEY` | for Last.fm | from last.fm/api/account/create |
| `LASTFM_SHARED_SECRET` | for Last.fm | same registration |
| `DATABASE_URL` | yes | `postgresql://user:pass@host:port/dbname` |
| `SESSION_SECRET` | yes | random string, keep secret |
| `SYNCUP_TOKEN_ENCRYPTION_KEY` | yes (non-debug) | base64-encoded 16/24/32-byte AES key |

---

## Docs

- [docs/api-keys.md](docs/api-keys.md) — how to register each service and get credentials
- [docs/api-contract.md](docs/api-contract.md) — API surface: routes, request/response shapes, live vs planned
- [docs/db-schema.md](docs/db-schema.md) — full database schema
- [docs/dev-guide.md](docs/dev-guide.md) — internals, design decisions, what to build next
- [docs/roadmap.md](docs/roadmap.md) — phased build plan and current status
- [docs/product-strategy.md](docs/product-strategy.md) — cold start strategy, positioning, target user

---

## License

MIT — see [LICENSE](LICENSE).
