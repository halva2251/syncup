# SyncUp

Match people by the vibe of their actual taste, not demographics, not dating.

Connect Steam, Last.fm, Spotify, Letterboxd, AniList, Trakt, Reddit, and RateYourMusic. A cross-domain semantic embedding model learns what your library says about you. Find people who share your wavelength, with control over which dimensions matter.

---

## What's been built

### Phase 1: Sync and Taste Profile (complete)

| Layer | Notes |
|-------|-------|
| Spotify OAuth + PKCE client | token exchange, refresh, top artists, recent tracks |
| Steam API client | owned games, player summary, vanity URL resolution |
| Last.fm API client | top artists, top tracks with period filtering |
| AniList GraphQL OAuth client | anime + manga ratings, genre metadata |
| Trakt OAuth client | watched movies and shows |
| Reddit OAuth client | subscribed subreddits, niche scoring |
| Letterboxd CSV import | diary export, wipe-and-replace |
| RateYourMusic CSV import | album ratings CSV, wipe-and-replace |
| AES-GCM token encryption | for storing OAuth tokens at rest |
| SQLAlchemy schema + Alembic migrations | users, items, user_items, embeddings, matches, overrides |
| Auth routes | signup, login, logout, session-based auth |
| Service connect routes | OAuth for all services + CSV imports |
| Sync routes | `POST /api/sync/{service}` background data pull |
| Taste profile endpoint | `GET /api/me/taste` top items per service |
| Manual obsessions | `GET/POST/DELETE /api/me/obsessions` |
| Preference overrides | `GET/POST/PATCH/DELETE /api/me/overrides` boost or demote items |
| Dimension weights | `GET/PATCH /api/me/dimensions` per-service match contribution |
| Item exclusion | `PATCH /api/me/items/{item_id}` remove misrepresentative items |
| Profile edit | `PATCH /api/me` display name, bio, Discord handle, avatar |
| Onboarding status | `GET /api/onboarding/status` |
| Heuristic matcher | rarity-weighted item overlap, match cache, background refresh |
| Rate limiting | per-endpoint limits across all routes |
| PostgreSQL + pgvector + Docker | `docker compose up -d` in `backend/` |
| Security hardening | CSP headers, timing-safe OAuth state, proxy trust, encryption key guard |

### Phase 2: ML Pipeline (in progress)

| Block | What | Status |
|-------|------|--------|
| A: Schema and config | EMBEDDING_DIM 128 to 384, vibe cols, excluded col, new deps | done |
| B: Semantic embeddings | `semantic.py` (sentence-transformers), `item_text.py` serializer | done |
| C: Metadata enrichment | Steam/Last.fm/TMDB enrichment scripts + populate script | done |
| D: User embeddings | `POST /api/embeddings/build`, `aggregate_vectors()`, per-service cap | done |
| E: Item exclusion API | `PATCH /api/me/items/{item_id}` | done |
| F: Vibe synthesis | LLM taste archetype + auto-embed post-sync | done |
| H: Semantic match upgrade | ANN cosine via pgvector `<=>`, `matching_mode` field | not started |
| I: Recommendations | `GET /api/me/recommendations`, public taste card | not started |
| J: Evaluation framework | `scripts/evaluate.py`, synthetic cohort eval | not started |

**908 passing tests.**

---

## Quickstart

> **This project uses [uv](https://docs.astral.sh/uv/) for dependency management.** Do not use `pip install` or `python -m venv` -- they won't pick up the lockfile and you'll get missing module errors when running tests or the server.
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

This reads `uv.lock` and creates a `.venv` inside `backend/` automatically. To also install ML dependencies (PyTorch, sentence-transformers -- needed for embedding):

```bash
uv sync --extra dev --extra ml
```

### 3. Set up environment variables

Copy this template to `backend/.env` and fill in the blanks:

```dotenv
# Set to true in local dev -- skips the encryption key startup check
DEBUG=true

# Steam
STEAM_API_KEY=

# Last.fm
LASTFM_API_KEY=

# Spotify
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
SPOTIFY_REDIRECT_URI=http://127.0.0.1:3000/api/auth/spotify/callback

# AniList
ANILIST_CLIENT_ID=
ANILIST_CLIENT_SECRET=

# Trakt
TRAKT_CLIENT_ID=
TRAKT_CLIENT_SECRET=

# Reddit
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_REDIRECT_URI=http://127.0.0.1:3000/api/connect/reddit/oauth/callback

# TMDB (optional -- for film/show genre enrichment)
TMDB_API_KEY=

# LLM vibe synthesis (optional -- any OpenAI-compatible provider)
# If unset, vibe synthesis is skipped and taste cards show items only.
# Defaults point at DeepSeek (~$0.01 per synthesis call).
LLM_API_KEY=
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat

# PostgreSQL -- use postgresql+psycopg:// (psycopg3), not postgresql:// (psycopg2)
DATABASE_URL=postgresql+psycopg://syncup:syncup@localhost:5432/syncup

# Session secret -- any random string
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
# From backend/ -- the DB container must be running (needed for schema tests)
uv run pytest
```

Useful variants:

```bash
uv run pytest tests/test_vibe_synthesizer.py       # single file
uv run pytest tests/test_sync.py::test_embed_new_items_happy_path   # single test
uv run pytest -x                                   # stop at first failure
uv run pytest --cov=syncup --cov-report=term-missing  # with coverage
uv run pytest -q                                   # quiet output
```

> **If you get `ModuleNotFoundError` or `command not found: pytest`** you're hitting the system Python instead of the project venv. Always prefix with `uv run`, which runs inside the managed venv without needing to activate it. Alternatively, activate once with `source .venv/bin/activate` and then use `pytest` directly.

### 7. Run metadata enrichment (one-time setup for Phase 2)

After syncing at least one service, run these scripts in order to enrich item metadata before computing embeddings:

```bash
# Enrich Steam games with genre tags (~10 min for a 300-game library)
uv run python scripts/enrich_steam_metadata.py

# Enrich Last.fm artists with genre tags (~5 min for 200 artists)
uv run python scripts/enrich_lastfm_metadata.py

# Enrich films and shows with genres from TMDB (requires TMDB_API_KEY)
uv run python scripts/enrich_tmdb_metadata.py

# Embed all items (batch-processes everything with embedding IS NULL)
uv run python scripts/populate_item_embeddings.py
```

All scripts are incremental -- safe to re-run. New items are also auto-embedded after each sync.

### 8. Build your user embedding and compute matches

```bash
# Build your taste vector (required before semantic matching works)
curl -X POST http://127.0.0.1:3000/api/embeddings/build \
  -H "Cookie: syncup_session=<your-session>"

# Trigger a match recompute
curl -X POST http://127.0.0.1:3000/api/me/recompute \
  -H "Cookie: syncup_session=<your-session>"
```

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
│   │   │   ├── registry.py     ServiceRegistry -- service-agnostic dispatch
│   │   │   ├── steam.py        SteamClient
│   │   │   ├── spotify.py      SpotifyClient (OAuth PKCE)
│   │   │   ├── lastfm.py       LastfmClient
│   │   │   ├── letterboxd.py   LetterboxdClient (CSV import)
│   │   │   ├── anilist.py      AniListClient (GraphQL OAuth)
│   │   │   ├── trakt.py        TraktClient (REST OAuth)
│   │   │   ├── reddit.py       RedditClient (OAuth)
│   │   │   ├── rateyourmusic.py  RateYourMusicClient (CSV import)
│   │   │   ├── _text.py        normalize_title() cross-service dedup
│   │   │   └── crypto.py       AES-GCM token encryption
│   │   ├── embeddings/
│   │   │   ├── semantic.py     sentence-transformers wrapper, embed_text/embed_batch
│   │   │   ├── item_text.py    item_to_text() serializer per service/item_type
│   │   │   ├── item2vec.py     Item2Vec model (future use)
│   │   │   ├── user_embeddings.py  aggregate_vectors(), user taste vector builder
│   │   │   └── vibe_synthesizer.py  LLM taste archetype synthesis (explanation only)
│   │   ├── matching/
│   │   │   ├── heuristic.py    rarity-weighted overlap scorer
│   │   │   └── engine.py       cosine similarity utilities
│   │   └── db/                 models.py, session.py
│   ├── alembic/                migrations (one per schema change)
│   ├── scripts/
│   │   ├── enrich_steam_metadata.py     Steam Store genre enrichment
│   │   ├── enrich_lastfm_metadata.py    Last.fm artist tag enrichment
│   │   ├── enrich_tmdb_metadata.py      TMDB film/show genre enrichment
│   │   └── populate_item_embeddings.py  batch-embed all items with embedding IS NULL
│   ├── tests/                  one file per module, pytest (908 tests)
│   ├── docker-compose.yml      PostgreSQL + pgvector
│   ├── .env                    secrets (never commit)
│   └── pyproject.toml
├── frontend/                   Next.js (not started -- Phase 3)
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
| `SPOTIFY_CLIENT_ID` | for Spotify | from Spotify developer dashboard |
| `SPOTIFY_CLIENT_SECRET` | for Spotify | from Spotify developer dashboard |
| `SPOTIFY_REDIRECT_URI` | for Spotify | must match dashboard exactly |
| `STEAM_API_KEY` | for Steam | from steamcommunity.com/dev/apikey |
| `LASTFM_API_KEY` | for Last.fm | from last.fm/api/account/create |
| `ANILIST_CLIENT_ID` | for AniList | from anilist.co/settings/developer |
| `ANILIST_CLIENT_SECRET` | for AniList | same registration |
| `TRAKT_CLIENT_ID` | for Trakt | from trakt.tv/oauth/applications |
| `TRAKT_CLIENT_SECRET` | for Trakt | same registration |
| `REDDIT_CLIENT_ID` | for Reddit | from reddit.com/prefs/apps |
| `REDDIT_CLIENT_SECRET` | for Reddit | same registration |
| `REDDIT_REDIRECT_URI` | for Reddit | must match app settings exactly |
| `TMDB_API_KEY` | optional | from themoviedb.org/settings/api -- enables film/show genre enrichment |
| `LLM_API_KEY` | optional | API key for vibe synthesis (any OpenAI-compatible provider) |
| `LLM_BASE_URL` | optional | defaults to `https://api.deepseek.com` |
| `LLM_MODEL` | optional | defaults to `deepseek-chat` |
| `DATABASE_URL` | yes | `postgresql+psycopg://user:pass@host:port/dbname` (psycopg3 scheme) |
| `SESSION_SECRET` | yes | random string, keep secret |
| `SYNCUP_TOKEN_ENCRYPTION_KEY` | yes (non-debug) | base64-encoded 16/24/32-byte AES key |

---

## How the matching works

1. **Sync your services** -- `POST /api/sync/{service}` pulls your data in the background and embeds new items automatically.
2. **Build your taste vector** -- `POST /api/embeddings/build` computes a 384-dim `combined` embedding from your items, weighted by engagement score and dimension weights. Items you've excluded are skipped.
3. **Compute matches** -- `POST /api/me/recompute` scores you against all matchable users. Currently uses rarity-weighted item overlap (heuristic); Block H upgrades this to pgvector cosine ANN.
4. **View matches** -- `GET /api/matches` returns paginated results with per-service breakdown and shared highlights.
5. **Vibe synthesis** -- if `LLM_API_KEY` is set, an archetype label and 2-3 sentence taste summary are generated after each sync and stored on your profile. This is display-only and does not affect match scores.

---

## Docs

- [docs/api-keys.md](docs/api-keys.md) -- how to register each service and get credentials
- [docs/api-contract.md](docs/api-contract.md) -- API surface: routes, request/response shapes, live vs planned
- [docs/db-schema.md](docs/db-schema.md) -- full database schema
- [docs/dev-guide.md](docs/dev-guide.md) -- internals, design decisions, what to build next
- [docs/roadmap.md](docs/roadmap.md) -- phased build plan and current status
- [docs/product-strategy.md](docs/product-strategy.md) -- cold start strategy, positioning, target user

---

## License

MIT -- see [LICENSE](LICENSE).
