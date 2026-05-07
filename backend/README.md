# backend

Python 3.11+ · FastAPI · SQLAlchemy · PostgreSQL · uv

See the [root README](../README.md) for the full quickstart. This file covers backend-specific commands you'll use day to day.

---

## Daily commands

All commands run from `syncup/backend/`.

```bash
# Install / sync dependencies (run after any pyproject.toml or uv.lock change)
uv sync --extra dev

# Start the API server
uv run uvicorn syncup.api.app:app --reload --port 3000

# Run all tests
uv run pytest

# Run tests for a specific module
uv run pytest tests/test_letterboxd.py

# Run with coverage
uv run pytest --cov=syncup --cov-report=term-missing

# Apply new migrations
uv run alembic upgrade head

# Create a migration after changing models.py
uv run alembic revision --autogenerate -m "describe what changed"
uv run alembic upgrade head

# Lint
uv run ruff check syncup/

# Type check
uv run mypy syncup/
```

> `uv run <cmd>` runs the command inside the managed `.venv` without you needing to activate it. If you prefer an activated shell, run `source .venv/bin/activate` once and then use commands directly.

---

## Running a subset of tests

```bash
uv run pytest tests/test_connect.py                                    # one file
uv run pytest tests/test_connect.py::test_letterboxd_import_success    # one test
uv run pytest -k "letterboxd"                                          # name pattern
uv run pytest -x                                                       # stop on first failure
uv run pytest -q                                                       # quiet output
```

---

## DB container

```bash
docker compose up -d      # start PostgreSQL + pgvector
docker compose down       # stop
docker compose down -v    # stop and wipe volume (destructive)
```

`test_db_schema.py` requires the container to be running — it reflects the live schema. All other tests use mocks and work offline.

---

## Layout

```
syncup/
├── api/
│   ├── app.py          FastAPI app, lifespan, exception handlers, Spotify OAuth
│   ├── routes/         one file per route group (connect, sync, me, taste, …)
│   └── schemas.py      shared Pydantic output models
├── auth/               signup, login, session cookie middleware
├── ingest/
│   ├── protocol.py     ServiceClient Protocol, RawItem TypedDict, SyncClientError
│   ├── registry.py     ServiceRegistry — maps service names to client instances
│   ├── steam.py        SteamClient
│   ├── spotify.py      SpotifyClient (OAuth PKCE)
│   ├── lastfm.py       LastfmClient
│   ├── letterboxd.py   LetterboxdClient (CSV import)
│   ├── _text.py        normalize_title() — cross-service title dedup
│   └── crypto.py       AES-GCM token encryption/decryption
├── embeddings/         item2vec.py — Item2Vec model; user_embeddings.py — user vectors
├── matching/           engine.py — cosine similarity; heuristic.py — overlap scorer
├── db/                 models.py — SQLAlchemy models; session.py — DB session helpers
├── config.py           pydantic-settings Settings class
├── exceptions.py       SyncUpError — app-level exception with code + status
└── limiter.py          slowapi rate limiter instance
```
