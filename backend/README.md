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
uv run uvicorn vibe_match.api.main:app --reload
```

## Layout

- `vibe_match/ingest/` — OAuth flows + Steam/Last.fm/Spotify API clients
- `vibe_match/embeddings/` — item2vec training + user vector builders
- `vibe_match/matching/` — cosine similarity + dimension weighting
- `vibe_match/api/` — FastAPI routes
- `tests/` — pytest suite
