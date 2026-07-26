FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --extra ml --no-install-project

COPY . .
RUN uv sync --locked --no-dev --extra ml \
    && chmod +x /app/docker-entrypoint.sh

EXPOSE 3020

ENTRYPOINT ["/app/docker-entrypoint.sh"]
