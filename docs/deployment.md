# Single-origin deployment

The root [`compose.yml`](../compose.yml) runs the complete SyncUp stack while
publishing only one host port:

```text
Caddy -> 127.0.0.1:8090 -> Next.js -> FastAPI -> configured PostgreSQL
                              |
                              +-> /api/* and /uploads/* are internal rewrites
```

FastAPI (`3020`) is exposed only inside the Compose network. PostgreSQL remains
at the `DATABASE_URL` configured in `backend/.env`; it is never routed through
Caddy. The browser therefore sees one HTTPS origin for pages, API requests,
uploads, session cookies, and OAuth callbacks.

## Configuration

1. Copy `.env.example` to `.env` and adjust the public origin or host port if
   needed.
2. Fill in `backend/.env` with `DATABASE_URL`, the service credentials, and a
   production `SYNCUP_TOKEN_ENCRYPTION_KEY`. Values related to the public
   origin, proxy trust, and OAuth callback URLs are supplied by `compose.yml`.
3. Register the callback URLs listed below with each provider:

```text
https://syncup.ruu.by/api/auth/spotify/callback
https://syncup.ruu.by/api/connect/steam/openid/callback
https://syncup.ruu.by/api/connect/lastfm/oauth/callback
https://syncup.ruu.by/api/connect/anilist/oauth/callback
https://syncup.ruu.by/api/connect/trakt/oauth/callback
https://syncup.ruu.by/api/connect/reddit/oauth/callback
```

If `PUBLIC_ORIGIN` changes, register the same paths on the new origin.

## Run

```bash
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:8090/api/health
```

The backend entrypoint applies database migrations before starting the API.
Uploaded avatars are kept in a named volume.
