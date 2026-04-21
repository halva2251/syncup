# backend

Python 3.11+ / FastAPI / SQLAlchemy / PyTorch.

## Setup

Install [uv](https://docs.astral.sh/uv/) if you don't have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then from this directory:

```bash
uv venv
uv pip install -e ".[ml,dev]"
```

Copy `.env.example` to `.env` and fill in service credentials (see [../docs/api-keys.md](../docs/api-keys.md)).

## Running

Not yet wired up. Will be:

```bash
uv run uvicorn syncup.api.main:app --reload
```

## Layout

- `syncup/ingest/` — OAuth flows + Steam/Last.fm/Spotify API clients
- `syncup/embeddings/` — item2vec training + user vector builders
- `syncup/matching/` — cosine similarity + dimension weighting
- `syncup/api/` — FastAPI routes
- `tests/` — pytest suite
