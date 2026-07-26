#!/bin/sh
set -eu

uv run alembic upgrade head
exec uv run uvicorn syncup.api.app:app --host 0.0.0.0 --port 3020
