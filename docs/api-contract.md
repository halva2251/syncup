# API Contract (Sketch)

REST + JSON. FastAPI backend on `http://127.0.0.1:3000`, Next.js frontend on `http://127.0.0.1:3001`.

> **Path prefix:** all backend routes are served under `/api`. So `/me` in this document maps to `http://127.0.0.1:3000/api/me`. The prefix is omitted throughout for readability.

Routes are marked **Live** (implemented) or **Sketch** (planned, shape may change).

---

## Conventions

- All auth'd endpoints require a session cookie (`syncup_session`) set by `/auth/*` endpoints.
- All timestamps are RFC 3339 (`2026-04-21T12:34:56Z`).
- All IDs are UUID strings.
- Errors follow:
  ```json
  { "error": { "code": "NOT_FOUND", "message": "..." } }
  ```
- Paginated endpoints use cursor pagination:
  ```json
  { "items": [...], "next_cursor": "opaque_string_or_null" }
  ```

---

## 1. Auth — Live ✅

### `POST /auth/signup`
Email/password signup.
```json
// req
{ "email": "me@example.com", "password": "...", "display_name": "alex" }
// res
{ "user": { "id": "...", "email": "...", "display_name": "alex" } }
```

### `POST /auth/login`
```json
// req
{ "email": "me@example.com", "password": "..." }
// res
{ "user": { ... } }
```
Sets `syncup_session` cookie.

### `GET /auth/oauth/{provider}/start`
`provider` ∈ `discord`, `google`, `spotify`, `steam`.
Returns 302 redirect to provider's authorize URL, or:
```json
{ "authorize_url": "https://..." }
```

### `GET /auth/oauth/{provider}/callback?code=...&state=...`
Completes the OAuth handshake, creates/links `auth_providers` row, sets session, redirects to `/onboarding` or `/home`.

### `POST /auth/logout`
Clears session. Returns 204.

---

## 2. Current user

### `GET /me` — Live ✅

**Live** — returns a nested envelope:
```json
{
  "user": {
    "id": "uuid",
    "email": "me@example.com",
    "display_name": "alex",
    "is_matchable": false,
    "onboarded": true,
    "created_at": "2026-04-21T12:00:00Z"
  },
  "connections": [
    {
      "service": "steam",
      "external_user_id": "76561198...",
      "sync_status": "ok",
      "last_synced_at": "...",
      "token_expires_at": null,
      "sync_error": null
    }
  ]
}
```

> `avatar_url`, `bio`, and `discord_handle` are in the `users` table but not yet in `UserOut`. They'll be exposed once `PATCH /me` is built.
```

### `PATCH /me` — Sketch
Fields: `display_name`, `bio`, `discord_handle`, `is_matchable`, `avatar_url`.

### `DELETE /me` — Sketch
Hard-delete; cascades to all user data.

---

## 3. Service connections — Sketch

### `POST /connect/steam` and `POST /connect/lastfm` are **Live ✅** (at `/api/connect/steam`, `/api/connect/lastfm`). The `/me/connections/*` sub-routes below are planned.

### `GET /me/connections`
Same shape as `connections` in `/me`.

### `POST /me/connections/{service}/start`
- For OAuth services (Spotify): returns `{ "authorize_url": "..." }`.
- For Steam: `{ "steam_id_or_vanity": "..." }` → resolves and stores.

### `GET /me/connections/{service}/callback?code=...`
OAuth callback for the data connection (distinct from login OAuth callback).

### `DELETE /me/connections/{service}`
Disconnects + purges pulled data for that service.

### `POST /me/connections/{service}/sync`
Triggers a fresh pull. Returns `{ "status": "syncing" }`; actual work runs in background.

---

## 4. Taste profile — Sketch

### `GET /me/taste`
Aggregated view:
```json
{
  "services": {
    "steam":   { "top_games":   [{ "id": "...", "name": "Disco Elysium", "hours": 50 }, ...] },
    "lastfm":  { "top_artists": [...], "top_tags": ["post-punk", "shoegaze"] },
    "spotify": { "top_artists": [...], "top_tracks": [...] }
  },
  "manual_obsessions": [
    { "id": "...", "category": "game", "name": "Disco Elysium", "weight": 2.0 }
  ],
  "overrides": [
    { "id": "...", "item": { "name": "Overwatch" }, "boost_multiplier": 0.3 }
  ]
}
```

### `GET /me/taste/items?service=steam&item_type=game&cursor=...`
Paginated raw items for a service/type.

### `POST /me/overrides`
```json
// req
{ "item_id": "...", "boost_multiplier": 2.5, "note": "my favourite despite low hours" }
```

### `PATCH /me/overrides/{id}` — update `boost_multiplier` or `note`
### `DELETE /me/overrides/{id}`

### `GET /me/obsessions`
### `POST /me/obsessions`
```json
// req
{ "category": "book", "name": "Blindsight", "weight": 1.5 }
```
### `DELETE /me/obsessions/{id}`

---

## 5. Dimension weights — Sketch

### `GET /me/dimensions`
```json
{
  "weights": {
    "steam":   0.3,
    "lastfm":  0.5,
    "spotify": 0.2
  }
}
```

### `PATCH /me/dimensions`
Send the full weights object. Backend normalises to sum to 1.0.

---

## 6. Matches — Sketch

**Preconditions for any `/matches` endpoint:**
- `is_matchable = true`
- At least 1 service connected **or** ≥ 3 manual obsessions
- User's combined embedding has been computed

### `GET /matches?limit=20&cursor=...`
Top matches for the current user.
```json
{
  "items": [
    {
      "user": {
        "id": "...",
        "display_name": "sam",
        "avatar_url": "...",
        "bio": "...",
        "discord_handle": "sam#9999"
      },
      "score": 0.87,
      "breakdown": { "steam": 0.72, "lastfm": 0.94, "spotify": 0.81 },
      "shared_highlights": [
        { "service": "steam",  "item_name": "Disco Elysium" },
        { "service": "lastfm", "item_name": "Arca" }
      ],
      "computed_at": "..."
    }
  ],
  "next_cursor": "..."
}
```

### `GET /matches/{user_id}`
Detailed view of a specific match — same shape as one `items` entry above, plus a fuller `shared_highlights` list and per-service top overlaps.

### `POST /me/recompute`
Forces re-compute of the user's embedding and invalidates their cached matches. Rate-limited.

---

## 7. Onboarding helpers — Sketch

### `GET /onboarding/status`
What the user still needs to do before becoming matchable.
```json
{
  "has_display_name": true,
  "has_connection_or_obsessions": false,
  "has_reviewed_taste": false,
  "has_set_matchable": false,
  "next_step": "connect_service"
}
```

---

## Status codes

- `200 OK` — success with body
- `201 Created` — resource created
- `204 No Content` — success, no body
- `400 Bad Request` — validation error
- `401 Unauthorized` — no session
- `403 Forbidden` — session but not allowed (e.g. not matchable)
- `404 Not Found`
- `409 Conflict` — e.g. already connected
- `429 Too Many Requests` — rate-limited
- `5xx` — server errors

---

## Open questions

- **Match reveal flow** — current design shows full profile + discord immediately. Do we want a "request to connect" step before revealing discord handle? Decide before building `/matches`.
- **Background jobs** — sync triggers are async; frontend needs to poll `/me/connections` or we add a WebSocket/SSE endpoint. Start with polling.
- **Rate limits on `/me/recompute`** — initial target: 1/hour per user.
