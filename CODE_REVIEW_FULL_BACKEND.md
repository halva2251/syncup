# Full Backend Code Review — SyncUp Phase 1 Complete

**Review date:** 2026-05-02
**Scope:** Entire `backend/` directory — all source files, tests, migrations, config, Docker, and documentation consistency.
**Skills consulted:** `api-design`, `backend-patterns`, `coding-standards`, `postgres-patterns`, `python-patterns`, `security-review`, `docker-patterns`.

---

## Executive Summary

**Verdict: Production-ready for cold-start launch (0–500 users), with a short hardening checklist before any public deployment.**

The codebase is well-architected, thoroughly tested (~380+ tests), and follows consistent patterns. The separation of concerns is clean (routes → models → ingest clients → embeddings → matching). Security fundamentals are solid (argon2, AES-GCM, timing-attack mitigation, rate limiting). The main gaps are operational (no Dockerfile, hardcoded CORS, empty session secret, no cleanup jobs) rather than architectural.

---

## 1. Documentation vs Code Consistency

### ✅ Accurate

| Document | Match |
|----------|-------|
| `roadmap.md` | Phase 1 fully implemented. All listed endpoints exist. |
| `dev-guide.md` | Live routes table matches actual code. Ingest layer docs match client signatures. |
| `db-schema.md` | Schema matches models.py and initial migration almost exactly. |
| `product-strategy.md` | Heuristic matcher implements the exact formula described. |

### ⚠️ Drift / Out of Date

| Issue | Doc | Code | Severity |
|-------|-----|------|----------|
| Onboarding response missing `has_languages` | `api-contract.md` §8 | `OnboardingStatusOut` has it | Low |
| Test count stale | `README.md`: "215 passing tests" | Actual: ~380+ tests across 20 files | Low |
| `api-contract.md` §3 lists `/me/connections/*` as planned | Sketch status | Not yet built | Expected per roadmap |
| `GET /me/taste/items?service=...&cursor=...` | `api-contract.md` §4 | Not implemented | Medium — pagination of raw taste items is not needed for MVP but is in the contract |

### 🔴 Missing Documentation

- No `DEPLOYMENT.md` or ops runbook. The `dev-guide.md` "Before you go to production" section exists but is buried inside a larger doc.
- No API changelog or versioning strategy documented beyond the contract sketch.

---

## 2. API Design (`api-design`)

### ✅ What's Right

- **Resource naming**: All URLs use nouns, plural where appropriate (`/matches`, `/obsessions`, `/dimensions`).
- **HTTP methods**: Correct semantics — GET for reads, POST for creates/actions, PATCH for partial updates, DELETE for removal.
- **Status codes**: Consistent and semantically correct:
  - `201 Created` for signup, obsession create, override create
  - `204 No Content` for logout, deletes, recompute
  - `401` for missing auth, `403` for matchability guard, `404` for missing resources, `409` for conflicts, `422` for validation errors
- **Error envelope**: Every error returns `{ "error": { "code": "...", "message": "..." } }`. The global exception handler in `app.py` enforces this uniformly.
- **Rate limiting**: Every write endpoint and every expensive read has a limit. Limits are documented in `dev-guide.md` and enforced in code.
- **Pagination**: `GET /matches` uses cursor pagination (base64 offset, acknowledged as temporary until ANN in Phase 2).
- **Auth**: Session cookie (`syncup_session`) with `HttpOnly`, `SameSite=lax`, secure in production.

### ⚠️ Notes

- **Response envelope**: Success responses return flat objects (not wrapped in `{ "data": ... }`). This is internally consistent but diverges from `api-design` skill's "Option A" recommendation for public APIs. If the API ever goes public, consider adding a `data` wrapper.
- **No API versioning**: URLs are `/api/*` without `/v1/`. Fine for MVP, but document the versioning decision.
- **Rate limit headers**: `slowapi` doesn't return `X-RateLimit-*` headers by default. The 429 responses work, but clients can't preemptively back off.
- **`/api/me/recompute` rate limit**: `1/hour` is per-IP, not per-user. A shared office IP could block multiple users. Consider switching to user-based limiting for authenticated routes.

---

## 3. Backend Patterns (`backend-patterns`)

### ✅ What's Right

- **Repository-ish pattern**: Routes query the DB directly. For a project this size, no separate repository layer is needed. The code stays readable without abstraction bloat.
- **Service separation**: Ingest clients (`spotify.py`, `steam.py`, `lastfm.py`) are pure HTTP clients with no DB knowledge. Sync tasks are background workers with their own sessions. Clean separation.
- **Background tasks**: `POST /api/sync/{service}` and `GET /api/matches` (cache miss) both use `BackgroundTasks`. Consistent pattern.
- **Cache-aside**: `match_cache` is loaded, computed on miss, and returned. Correct.
- **Session management**: `get_session()` handles rollback on exception and explicit close. `get_db()` wraps it for FastAPI dependency injection.
- **Upsert pattern**: `sync.py` uses PostgreSQL `INSERT ... ON CONFLICT` for atomic item/user_item upserts. Correct and efficient.
- **Token refresh**: Spotify sync checks expiry with a 60s buffer and refreshes automatically. Good operational detail.

### ⚠️ Notes

- **No centralized service layer**: This is a choice, not a bug. But as the codebase grows, consider extracting repeated query patterns (e.g., "get user's service connection by name") into small functions to reduce duplication.
- **No event bus**: Background tasks are fine for MVP, but at scale, `BackgroundTasks` runs in the same process. If the server restarts, pending tasks are lost. Document this limitation.
- **No request ID logging**: `app.py` logs exceptions but doesn't attach a request-scoped UUID. Debugging production issues across multiple requests is harder without this.

---

## 4. Postgres Patterns (`postgres-patterns`)

### ✅ What's Right

- **Extensions**: `uuid-ossp`, `citext`, `pgvector` all created in initial migration.
- **Data types**: `UUID` for IDs, `CITEXT` for email (case-insensitive), `TIMESTAMPTZ` for timestamps, `JSONB` for metadata/breakdown/highlights, `Vector(128)` for embeddings.
- **Constraints**: Check constraints on `sync_status`, `boost_multiplier > 0`, `weight` range, `user_a_id < user_b_id`, category enum.
- **Indexes**: All foreign keys indexed. Partial index on `users.is_matchable = true`. IVFFlat index on `items.embedding` (where not null) and `user_embeddings` (where service='combined'). Composite indexes on `match_cache` for both user directions.
- **Migrations**: Alembic setup is correct. `env.py` reads `DATABASE_URL` from environment. `compare_type=True` ensures type changes are detected.
- **Migration chain**: Linear chain (0001 → 0002 → 0003 → 0004), no branches. Each migration is safe (adds nullable columns or check constraints).

### ⚠️ Notes

- **Migration 0002 adds a check constraint on existing data**: If `manual_obsessions` already has rows with invalid categories, this migration will fail. Since the app validates categories at the API layer, this is unlikely, but worth noting for deployments with existing data.
- **No index on `sessions.expires_at` + automatic cleanup**: The index exists, but no cron job deletes stale sessions. Table will grow indefinitely. **Action item:** Add a `pg_cron` job or application-level cleanup task.
- **No index on `match_cache.computed_at`**: The `_load_cached_matches` query filters by `computed_at >= cutoff`. Currently it relies on the `user_a_id`/`user_b_id` indexes plus a filter. With large caches, adding an index on `computed_at` or a composite `(user_a_id, computed_at)` could help. Low priority for MVP.
- **No GIN index on `match_cache.highlights`**: Not needed until you query highlights directly (e.g., "find all matches with shared Steam games"). Fine for now.

---

## 5. Python Patterns (`python-patterns`)

### ✅ What's Right

- **`__future__` annotations**: Used in every file.
- **Type hints**: Comprehensive annotations on all functions, including `Annotated[DbSession, Depends(get_db)]`.
- **Dataclasses**: `TokenResponse`, `SharedHighlight`, `SpotifyClient`, `SteamClient`, `LastfmClient` all use dataclasses appropriately.
- **Context managers**: All HTTP clients are context managers (`with SpotifyClient(...) as client:`).
- **EAFP**: Code follows Pythonic exception handling (e.g., `try/except` around token decryption, hash verification).
- **Generators**: `get_session()` is a generator-based context manager.
- **No mutable default arguments**: Safe patterns throughout.
- **Comprehensions**: Used judiciously (e.g., `_to_steam_game` converters).

### ⚠️ Notes

- **`type: ignore` comments**: Present in `sync.py` (line 67, 79, 91, 101) and ingest clients. Most are for SQLAlchemy's typed `Table` operations and `resp.json()` returns. Acceptable given the current state of SQLAlchemy/httpx typing, but should be revisited as stubs improve.
- **`Any` usage**: Minimal. `taste.py` uses `Any` for row converters, which is pragmatic given the dynamic nature of SQLAlchemy row proxies.

---

## 6. Coding Standards (`coding-standards`)

### ✅ What's Right

- **Naming**: Functions are verb-noun (`get_taste`, `trigger_sync`, `hash_password`). Constants are `UPPER_SNAKE_CASE`. Classes are `PascalCase`.
- **Constants extracted**: `_OBSESSIONS_THRESHOLD`, `_CACHE_MAX_AGE_HOURS`, `_VALID_SERVICES`, `_TOKEN_REFRESH_BUFFER`, API fetch limits.
- **KISS**: No over-engineering. Each route does one thing. No unnecessary abstractions.
- **DRY**: `_upsert_connection` shared between Steam and Last.fm. `_upsert_item` and `_upsert_user_item` shared across all sync tasks. `_safe_error_message` shared across sync error handling.
- **File organization**: Routes grouped by domain (auth, me, connect, sync, taste, obsessions, overrides, dimensions, matches, onboarding). Models in one file (justified by size — 420 lines is manageable).

### ⚠️ Notes

- **Long functions**: `sync.py` has three sync task functions (~100 lines each) and the route handler. These are long but linear (no deep nesting). Acceptable given they orchestrate complex external API calls.
- **`matches.py` `_refresh_match_cache`**: 80+ lines. Could be split into smaller helpers (`_build_user_data`, `_compute_popularity`, `_compute_pair`), but the current structure is readable.
- **Comments**: Good module-level docstrings. Minimal inline comments, but the code is self-documenting.

---

## 7. Security Review (`security-review`)

### ✅ Pass

| Check | Status | Evidence |
|-------|--------|----------|
| No hardcoded secrets | Pass | All secrets from env vars via `pydantic-settings` |
| Password hashing | Pass | argon2id with OWASP defaults (`auth/hashing.py`) |
| Timing attack mitigation | Pass | `verify_password_dummy()` runs on unknown email (`auth/router.py:169`) |
| Token encryption | Pass | AES-GCM with random nonce (`ingest/crypto.py`) |
| Session cookies | Pass | `HttpOnly`, `SameSite=lax`, `secure=not debug` |
| SQL injection prevention | Pass | SQLAlchemy ORM + parameterized queries everywhere |
| Input validation | Pass | Pydantic schemas on all request bodies |
| Rate limiting | Pass | All write routes and expensive reads limited |
| Auth required on sensitive routes | Pass | `RequireAuth` on all `/me/*`, `/matches`, `/sync`, `/connect` |
| Authorization checks | Pass | Users can only access their own resources (user_id filters in queries) |
| Error messages don't leak internals | Pass | Generic messages to client; details logged server-side |
| CORS | Partial | Hardcoded origins (see below) |

### ⚠️ Notes

- **CORS hardcoded**: `app.py:105` hardcodes `["http://127.0.0.1:3001", "http://localhost:3001"]`. `config.py` has `cors_allowed_origins` but `app.py` ignores it. This is a known gap listed in `dev-guide.md`. **Fix before non-local deployment.**
- **`.env` `SESSION_SECRET` is empty**: The session cookie is signed with an empty secret in local dev. In production, this must be a strong random string. The `config.py` default is also `str = ""`. If `DEBUG=false` and `SESSION_SECRET` is empty, sessions are technically signed with an empty key. **Action:** Add a startup check that raises if `session_secret` is empty in non-debug mode.
- **Rate limiter is IP-based only**: `limiter.py` uses `get_remote_address`. For authenticated routes, this means all users behind the same NAT (corporate office, mobile carrier) share a rate limit bucket. Consider a hybrid approach: IP for anonymous, user ID for authenticated.
- **No CSRF tokens**: The API uses cookies for auth but doesn't implement CSRF tokens. However, all state-changing operations use `POST`/`PATCH`/`DELETE` with `Content-Type: application/json`, which makes simple CSRF attacks harder (browsers block cross-origin JSON requests without CORS). Still, for defense-in-depth, consider adding a `X-Requested-With` check or CSRF tokens if you ever accept form-encoded requests.
- **No Content Security Policy headers**: Not applicable to a JSON API without HTML responses, but worth noting if you serve any static content.
- **OAuth state cookie**: `spotify_state` and `spotify_verifier` cookies have `max_age=600` (10 min). Good — short-lived reduces replay window.

---

## 8. Docker Patterns (`docker-patterns`)

### ✅ What's Right

- **`docker-compose.yml` healthcheck**: `pg_isready` with retries and start period.
- **Port binding restricted to localhost**: `127.0.0.1:5432:5432` prevents external access to the DB.
- **Named volume**: `pgdata` persists across container restarts.
- **`restart: unless-stopped`**: Good for local dev.

### 🔴 Missing / Needs Hardening

- **No Dockerfile**: The project has no `Dockerfile` for the Python app. Only `docker-compose.yml` for PostgreSQL. **Action:** Add a multi-stage Dockerfile for the FastAPI app.
- **Floating image tag**: `pgvector/pgvector:pg18` is a floating tag. Per `dev-guide.md`, pin to a digest for reproducibility.
- **DB password in compose**: `POSTGRES_PASSWORD: syncup` is fine for local dev but documented as a placeholder. For production, inject via env or secrets.
- **DB runs as superuser**: `POSTGRES_USER=syncup` creates a superuser. `dev-guide.md` has the correct least-privilege SQL. **Action:** Apply before production.
- **No `.dockerignore`**: Not critical without a Dockerfile, but should be added when the Dockerfile is created.
- **No app service in compose**: The compose only defines the DB. For local dev, this is fine (developers run `uvicorn` directly), but a complete dev stack would include the app service.

---

## 9. Deployment Readiness Checklist

### Must Fix Before Production

- [ ] **Add Dockerfile** (multi-stage: deps → dev → production)
- [ ] **Fix CORS** to read from `Settings.cors_allowed_origins` instead of hardcoded list
- [ ] **Generate and set `SESSION_SECRET`** — add startup validation that fails if empty in prod
- [ ] **Pin `pgvector` image digest** in `docker-compose.yml`
- [ ] **Create least-privilege DB user** (see `dev-guide.md` §1)
- [ ] **Add session cleanup job** (`DELETE FROM sessions WHERE expires_at < NOW()`)
- [ ] **Add `match_cache` cleanup job** (`DELETE FROM match_cache WHERE computed_at < NOW() - INTERVAL '24 hours'`)
- [ ] **Switch rate limiter to per-user for authenticated routes** (or add user-based tier)
- [ ] **Set `debug: false`** and verify error handlers don't leak stack traces
- [ ] **HTTPS enforcement**: Ensure `secure` cookie flag works (requires TLS termination)

### Should Fix Soon After Launch

- [ ] **Health check endpoint**: `/api/health` exists but only returns static JSON. Add DB connectivity check and dependency status.
- [ ] **Structured logging**: Replace basic `logging` with structured JSON logs (e.g., `python-json-logger`).
- [ ] **Request ID propagation**: Add middleware to generate and attach `X-Request-ID` to all logs.
- [ ] **Observability**: Add Prometheus metrics or OpenTelemetry tracing.
- [ ] **API versioning**: Document the decision to not version yet, and plan for `/api/v1/` prefix when breaking changes arrive.
- [ ] **Test coverage target**: Current tests are mocked unit tests. Add a small integration test suite that runs against a real PostgreSQL container in CI.

---

## 10. Test Quality Assessment

### ✅ Strengths

- **Coverage**: 20 test files covering all routes, all ingest clients, crypto, embeddings, matching engine, heuristic scorer, DB schema, and auth.
- **Mock strategy**: FastAPI `dependency_overrides` + `unittest.mock.patch` for external APIs. No live network calls in tests.
- **Auth testing**: Exhaustive — signup, login, logout, session expiry, orphaned sessions, timing attack mitigation, transparent rehash.
- **Edge cases**: Boundary tests for pagination, empty pools, cache expiry, duplicate emails, race conditions.
- **Schema tests**: `test_db_schema.py` verifies table registration, embedding dimension consistency, and index existence without a live DB.
- **Builder pattern**: `_make_user`, `_make_connection`, `_make_obsession`, `_make_cache_row` keep tests DRY.

### ⚠️ Gaps

- **No integration tests against real DB**: All DB interactions are mocked. The `test_db_schema.py` smoke tests are good but don't exercise actual SQL execution.
- **No E2E tests**: No Playwright or similar tests for critical user flows.
- **Coverage report unavailable**: `pytest --cov` is configured but I couldn't run it (missing env). Verify 80%+ coverage before launch.
- **No load tests**: The BackgroundTasks pattern and match cache refresh should be load-tested with synthetic data.

---

## 11. Architecture Observations

### What's Well-Designed

- **Layered architecture**: Ingest → DB → Embeddings → Matching → API. Clear data flow.
- **Phase-aware design**: Heuristic matcher is a clean fallback for the cold-start phase. Item2Vec engine is ready for Phase 2. The transition path is documented.
- **Configurable by env**: `Settings` class with `.env` file support. All service credentials, DB URL, and secrets are externalized.
- **Forward-compatible models**: `users.languages`, `match_cache.highlights`, and `items.metadata` all have room for future features without schema changes.

### Future Technical Debt

- **`BackgroundTasks` scalability ceiling**: At ~1000 users, the process-based background task queue will become a bottleneck. Plan to migrate to Celery/Arq/RQ before then.
- **Offset pagination in matches**: Will break under concurrent cache refreshes. Cursor pagination (stable score+id cursor) is needed for Phase 2.
- **Single embedding dimension**: All services share 128-dim vectors. If one service needs a different dimension later, this will require a migration.

---

## Final Verdict

**Approve for cold-start deployment with the "Must Fix Before Production" checklist completed.**

The codebase is production-quality for its intended scope. The team has made smart architectural choices (heuristic first, background tasks, pure ingest clients) that defer complexity until it's needed. The test suite gives confidence to refactor. The main blockers are operational, not structural.

**Reviewer confidence: High.**
