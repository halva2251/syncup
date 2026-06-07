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
  Validation errors (422) include a `details` array:
  ```json
  { "error": { "code": "VALIDATION_ERROR", "message": "Validation failed", "details": [...] } }
  ```
- Paginated endpoints use cursor pagination:
  ```json
  { "items": [...], "next_cursor": "opaque_string_or_null" }
  ```
  Match pagination uses a keyset cursor encoding `(score, user_a_id, user_b_id)` — stable across cache refreshes.

---

## 1. Auth — Live ✅

### `POST /auth/signup`
Email/password signup.
```json
// req
{ "email": "me@example.com", "password": "...", "display_name": "alex" }
// res
{ "user": { "id": "...", "email": "...", "display_name": "alex" } }
// display_name is stripped; whitespace-only → 422
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

Returns a nested envelope:
```json
{
  "user": {
    "id": "uuid",
    "email": "me@example.com",
    "display_name": "alex",
    "avatar_url": null,
    "bio": null,
    "discord_handle": null,
    "is_matchable": false,
    "onboarded": true,
    "created_at": "2026-04-21T12:00:00Z",
    "updated_at": "2026-04-21T12:00:00Z"
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

### `PATCH /me` — Live ✅

Partial update — only fields present in the body are written. Returns the updated user object (same shape as the `user` field in `GET /me`).

```json
// req — all fields optional
{
  "display_name": "alex",
  "bio": "gamer and music nerd",
  "discord_handle": "alex#1234",
  "avatar_url": "https://example.com/avatar.png",
  "is_matchable": true
}
```

- `display_name`: min 1, max 200 chars; sending `null` is a no-op (field is NOT NULL)
- `bio`, `discord_handle`, `avatar_url`: nullable; sending `null` clears the field
- `is_matchable`: strict bool — `"yes"` and `"true"` are rejected (422)

### `DELETE /me` — Sketch
Hard-delete; cascades to all user data.

---

## 3. Service connections — Sketch

### `POST /connect/steam` and `POST /connect/lastfm` are **Live ✅** (at `/api/connect/steam`, `/api/connect/lastfm`).

### `POST /connect/letterboxd/import` — Live ✅
Multipart file upload. Accepts Letterboxd diary CSV export.
```
Content-Type: multipart/form-data
field: file — the CSV file (max 10 MB)
```
- Parses `Name`, `Year`, `Rating` columns; skips rows with empty `Rating`
- **Wipe-and-replace**: deletes all existing Letterboxd items for this user, then inserts from the CSV, all in a single DB transaction (rollback on failure preserves old data)
- Creates/replaces a `service_connections` row with `sync_status = 'ok'`
- Returns 201 `{"imported": N}` on success; 413 if file exceeds 10 MB; 422 if CSV is malformed

### `POST /connect/rateyourmusic/import` — Live ✅
Same pattern as Letterboxd import. Accepts RateYourMusic ratings export CSV (`Title`, `Release_Date`, `Rating` columns required). Returns `{"imported": N}` on 201. Wipe-and-replace per import; 10 MB cap.
- Parses `Title`, `Release_Date` (year), `Rating` columns
- Same wipe-and-replace, 10 MB cap, 201/413/422 responses

### `GET /connect/anilist/oauth/start` — Live ✅
Redirects (302) to AniList's authorization page. Sets `anilist_state` cookie (httpOnly, 10 min TTL). Returns 503 if `ANILIST_CLIENT_ID` / `ANILIST_CLIENT_SECRET` are not configured.

### `GET /connect/anilist/oauth/callback?code=...&state=...` — Live ✅
Validates state cookie, exchanges code for access token, encrypts token, upserts `service_connections` row (`sync_status = 'pending'`), redirects to `/`. Returns 400 on state mismatch.

### `GET /connect/trakt/oauth/start` — Live ✅
Redirects (302) to Trakt's authorization page. Sets `trakt_state` cookie (httpOnly, 10 min TTL). Returns 503 if `TRAKT_CLIENT_ID` / `TRAKT_CLIENT_SECRET` are not configured.

### `GET /connect/trakt/oauth/callback?code=...&state=...` — Live ✅
Validates state cookie, exchanges code for access + refresh token, encrypts tokens, upserts `service_connections` row (`sync_status = 'pending'`, `token_expires_at` set 90 days out), redirects to `/`. Returns 400 on state mismatch.

### `GET /connect/reddit/oauth/start` — Live ✅
Redirects (302) to Reddit's authorization page. Sets `reddit_state` cookie (httpOnly, 10 min TTL). Requests scopes `identity mysubreddits` with `duration=permanent`. Returns 503 if `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` are not configured.

### `GET /connect/reddit/oauth/callback?code=...&state=...` — Live ✅
Validates state cookie, exchanges code for access + refresh token, encrypts tokens, upserts `service_connections` row (`sync_status = 'pending'`, `token_expires_at` set 1 hour out), redirects to `/`. Returns 400 on state mismatch, 400 on user denial (`error=access_denied`), 400 on missing code.

### The `/me/connections/*` sub-routes below are planned.

### `GET /me/connections`
Same shape as `connections` in `/me`.

### `POST /me/connections/{service}/start`
- For OAuth services (Spotify): returns `{ "authorize_url": "..." }`.
- For Steam: `{ "steam_id_or_vanity": "..." }` → resolves and stores.

### `GET /me/connections/{service}/callback?code=...`
OAuth callback for the data connection (distinct from login OAuth callback).

### `DELETE /me/connections/{service}`
Disconnects + purges pulled data for that service.

### `POST /sync/{service}` — Live ✅
Triggers a fresh pull. Returns immediately; actual work runs in background.
```json
// res
{ "status": "syncing", "service": "spotify", "poll_url": "/api/me" }
```
Poll `poll_url` to check `connections[].sync_status` for `"ok"` or `"error"`.

---

## 4. Taste profile

### `GET /me/taste` — Live ✅
Aggregated view. Services with no items are omitted from the response entirely (not returned as `null`).
```json
{
  "services": {
    "steam":   { "top_games":   [{ "id": "...", "name": "Disco Elysium", "hours": 50 }, ...] },
    "lastfm":  { "top_artists": [...], "top_tags": [] },   // top_tags not yet synced — placeholder for later
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

### `GET /me/obsessions` — Live ✅
### `POST /me/obsessions` — Live ✅
```json
// req
{ "category": "book", "name": "Blindsight", "weight": 1.5 }
// category ∈ game | music | film | book | show | anime | manga | community | other
// (anime, manga, community added in migration 0007 for AniList and Reddit support)
// weight defaults to 1.0, must be > 0 and ≤ 10.0
// name is stripped of leading/trailing whitespace; blank-after-strip → 422
```
### `DELETE /me/obsessions/{id}` — Live ✅

### `GET /me/overrides` — Live ✅
### `POST /me/overrides` — Live ✅
```json
// req
{ "item_id": "...", "boost_multiplier": 2.5, "note": "my favourite despite low hours" }
// item_id must reference an existing items row
// boost_multiplier must be > 0 and ≤ 10.0
// duplicate override for same item returns 409
```
### `PATCH /me/overrides/{id}` — Live ✅ — update `boost_multiplier` or `note`; sending `note: null` clears it
### `DELETE /me/overrides/{id}` — Live ✅

---

## 5. Recommendations — Live ✅

### `GET /me/recommendations` — Live ✅ (Phase 2 Block I)

Cross-domain item recommendations powered by the user's `combined` taste vector.

Query params:
- `item_type` (optional): one of `game | track | artist | film | show | anime | manga | album | community`. Omit for all types. Unknown values → 422.
- `limit` (optional, default 10, max 50): number of results. `limit < 1` or `limit > 50` → 422.

```json
// GET /api/me/recommendations?item_type=game&limit=5
// res
{
  "items": [
    { "item_name": "Planescape: Torment", "service": "steam", "item_type": "game", "similarity_score": 0.87 },
    { "item_name": "Disco Elysium",       "service": "steam", "item_type": "game", "similarity_score": 0.84 }
  ]
}
```

- `similarity_score` = `1 - cosine_distance`, clamped to `[0.0, 1.0]`. Items with `score <= 0` (antipodal vectors) are excluded.
- Only items NOT already in `user_items` are returned.
- Cross-domain by default: the combined vector spans all services, so `item_type=film` returns films informed by gaming and music taste.
- 422 `NO_EMBEDDING_AVAILABLE` if the user has no `combined` embedding yet — build one via `POST /api/embeddings/build`.
- Rate-limited: 30/min per IP.

---

## 6. Dimension weights

### `GET /me/dimensions` — Live ✅
```json
{ "weights": { "steam": 0.3, "lastfm": 0.5, "spotify": 0.2 } }
```
Returns `{"weights": {}}` when no weights have been set yet.

### `PATCH /me/dimensions` — Live ✅
Send the full weights object. Backend normalises to sum to 1.0. Full replacement — omitted services are removed.
```json
// req
{ "weights": { "steam": 7, "spotify": 3 } }
// → stored as { "steam": 0.7, "spotify": 0.3 }
```
Valid services: any service registered in `ServiceRegistry` (currently `steam`, `lastfm`, `spotify`; expands automatically as new services are added). Unknown service keys → 422. All-zero → 422. Empty dict → 422.

---

## 7. Embeddings — Live ✅

### `POST /embeddings/build` — Live ✅ *(Phase 2 Block D)*

Compute (or recompute) the current user's combined 384-dim taste vector. Aggregates all non-excluded `user_items` that have item embeddings using **two-level, service-aware aggregation** (per-service cap of top 50 by `engagement_score`), then writes a single L2-normalised vector to `user_embeddings` with `service='combined'`.

Rate-limited to 5/min per user.

```json
// res 200
{
  "service": "combined",
  "item_count": 42,
  "computed_at": "2026-06-04T20:00:00Z"
}

// res 422 — no items have embeddings yet
{ "error": { "code": "NO_EMBEDDINGS_AVAILABLE", "message": "No embedded items found. Run the enrichment and populate scripts first, or sync a connected service." } }
```

**Aggregation (service-aware, corrected 2026-06-07):**
- **Within a service:** `service_direction = L2_normalize( Σ embedding × boost_multiplier × log1p(engagement_score) )`. `boost_multiplier` amplifies an item relative to its service peers; log1p is a mild concave reweighting on the already-normalized `engagement_score ∈ [0,1]` (not a raw-count dampener).
- **Across services:** `combined = L2_normalize( Σ service_direction × dim_weight )` — a **linear** weighted sum. Mean-pooling each service to unit mass first makes `dim_weight` authoritative: a 0.7 vs 0.3 split yields exactly a 0.7:0.3 contribution **regardless of how many items each service has**. (Before this fix, a large library could override the user's slider by sheer item count.)
- `dim_weight` defaults to 1.0 if no `user_dimension_weights` row exists for the service
- `boost_multiplier` defaults to 1.0 if no `preference_overrides` row exists for the item
- `excluded = true` items are skipped entirely

---

## 8. Item exclusion — Live ✅ *(Phase 2 Block E)*

### `PATCH /me/items/{item_id}` — Live ✅

Toggle the `excluded` flag on a `user_items` row. Excluded items are skipped in embedding builds (`POST /embeddings/build`), LLM vibe synthesis, and recommendations. Rate-limited to 60/min.

`{item_id}` is the `user_items.id` UUID (not `items.id`). Returns 404 whether the row doesn't exist or belongs to another user.

```json
// req body
{ "excluded": true }

// res 200
{
  "id": "<user_items.id>",
  "excluded": true,
  "engagement_score": 0.85,
  "item": {
    "id": "<items.id>",
    "name": "Disco Elysium",
    "service": "steam",
    "item_type": "game"
  }
}

// res 404
{ "error": { "code": "NOT_FOUND", "message": "Item not found" } }
```

Setting `excluded: false` re-includes the item. Both directions are idempotent.

---

## 9. Matches — Live ✅

**Preconditions:**
- `is_matchable = true`
- At least 1 `ok`-status service connection **or** ≥ 3 manual obsessions

> Block H (2026-06-06): semantic ANN path active. `matching_mode` field added to all match responses.

### `GET /matches?limit=20&cursor=...` — Live ✅
Top matches for the current user. Returns empty immediately on cache miss; match cache is refreshed in the background.

`matching_mode` is `"semantic"` when the user has a `combined` embedding (HNSW ANN cosine search on 384-dim vector, score = 1 − cosine_distance, candidates with score ≤ 0 filtered). Falls back to `"heuristic"` (item-overlap Jaccard) when no embedding exists.
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
      "breakdown": { "combined": 0.87 },
      "shared_highlights": [
        { "service": "steam",  "item_name": "Disco Elysium" },
        { "service": "lastfm", "item_name": "Arca" }
      ],
      "computed_at": "...",
      "matching_mode": "semantic"
    }
  ],
  "next_cursor": "..."
}
```

`breakdown` is `{"combined": score}` in semantic mode, per-service Jaccard in heuristic mode.

### `GET /matches/{user_id}` — Live ✅
Single match detail — same shape as one `items` entry above, including `matching_mode`.

### `POST /me/recompute` — Live ✅
Forces refresh of the user's match cache **and** (if `LLM_API_KEY` is set) triggers vibe synthesis. Rate-limited to 1/hour. Returns 204 immediately; all tasks run in background.

Background tasks triggered (in order):
1. `_build_embedding_bg` — rebuilds the user's `combined` embedding (no-op if no item embeddings; silent)
2. `_refresh_match_cache` — semantic ANN search if embedding exists, else heuristic
3. `synthesize_vibe` — regenerates `vibe_summary`, `archetype`, `key_themes` on `users` row (skipped if `LLM_API_KEY` unset)

---

## 10. Onboarding helpers — Sketch

### `GET /onboarding/status` — Live ✅
What the user still needs to do before becoming matchable.
```json
{
  "has_display_name": true,
  "has_languages": false,
  "has_connection_or_obsessions": false,
  "has_taste_data": false,
  "has_set_matchable": false,
  "next_step": "connect_service"
}
// next_step progression: "set_display_name" → "connect_service" → "set_matchable" → null
```

- `has_display_name`: `true` when `users.display_name` is non-blank
- `has_languages`: `true` when `users.languages` is set; skippable — does not block `next_step`
- `has_connection_or_obsessions`: ≥1 `ok`-status service connection OR ≥3 manual obsessions
- `has_taste_data`: `true` when the user has ≥1 synced `UserItem` rows (real item count, independent of connections)
- `next_step`: `"set_display_name"` → `"connect_service"` → `"set_matchable"` → `null` (fully onboarded)

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

- **Match reveal flow** — ~~Decide before building `/matches`.~~ **Decided:** show full profile + discord handle immediately for MVP. "Request to connect" step deferred to V2. Already implemented in `GET /matches`.
- **Background jobs** — sync triggers are async; frontend needs to poll `/me/connections` or we add a WebSocket/SSE endpoint. Start with polling.
- **Rate limits on `/me/recompute`** — initial target: 1/hour per user.
