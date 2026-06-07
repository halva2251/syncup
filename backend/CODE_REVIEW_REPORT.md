# SyncUp Backend — Full Code Review Report

**Date:** 2026-06-07
**Reviewer:** Kimi Code (multi-agent + manual audit)
**Scope:** Full backend (`backend/syncup/`, `backend/tests/`), migrations, scripts
**Test Status:** 998 passing, 23 warnings
**Overall Verdict:** **WARNING** — 0 CRITICAL, 7 HIGH, 22 MEDIUM, 18 LOW. No active security breaches, but 3 HIGH issues are production blockers.

---

## Executive Summary

The SyncUp backend is a well-architected FastAPI application with strong security fundamentals (AES-GCM token encryption, argon2id password hashing, timing-safe comparisons, CSRF protection via state cookies). The codebase demonstrates mature patterns: Protocol-based ingest clients, service-aware two-level embedding aggregation, HNSW pgvector indexes, and comprehensive test coverage (~1000 tests).

However, several issues require attention before production:

1. **Data-integrity bug in match pagination** — cursor encoding rounds floats, causing duplicates and skipped rows.
2. **Security blockers** — validation errors leak raw passwords; `ProxyHeadersMiddleware` trusts all hosts, enabling rate-limit bypass; signup endpoint leaks email existence via timing side-channel.
3. **Schema drift** — `UserItem` model is missing a CHECK constraint that exists in migrations.
4. **Silent background task failures** — match cache refreshes, embedding builds, vibe synthesis, and auto-embed all swallow exceptions with only log messages.
5. **Unbounded queries** — several endpoints load unbounded result sets into Python memory.
6. **Code size** — `connect.py` at 1002 lines and `matches.py` at 661 lines exceed maintainability thresholds.

---

## Findings by Severity

### 🔴 HIGH

#### [HIGH-1] Match cursor truncates floats — data-integrity bug
**File:** `syncup/api/routes/matches.py:122-124`

```python
def _encode_cursor(score: float, user_a_id: uuid.UUID, user_b_id: uuid.UUID) -> str:
    return base64.b64encode(f"{score:.6f}:{user_a_id}:{user_b_id}".encode()).decode()
```

`score` is formatted with `:.6f`, which **rounds** the float. On decode, the paginated query uses the rounded value as a keyset boundary:
- A row with actual score `0.123456789` is encoded as `0.123457`
- The next page's `score < 0.123457` filter will **re-include** the already-seen row (duplicate)
- It will **permanently skip** any rows whose true score lies between `0.123456789` and `0.123457`

**Impact:** Pagination across match results can produce duplicates and skip rows.

**Fix:** Encode the score losslessly with `struct.pack("!d", score)`.

---

#### [HIGH-2] `ProxyHeadersMiddleware` trusts all hosts (`trusted_hosts="*"`)
**File:** `syncup/api/app.py:152`

```python
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
```

**Impact:** `slowapi.util.get_ipaddr` uses `request.client.host` for rate-limit keys. With `trusted_hosts="*"`, an attacker can spoof `X-Forwarded-For` to any IP and bypass all rate limits. This undermines brute-force protection on auth endpoints.

**Fix:** Restrict to actual upstream proxy IPs (read from env):
```python
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=settings.trusted_hosts.split(","))
```

---

#### [HIGH-3] Background task failures are silent — no alerting path
**Files:** `syncup/api/routes/matches.py`, `syncup/api/routes/sync.py`, `syncup/embeddings/vibe_synthesizer.py`

Multiple background tasks catch `Exception` broadly and only log:
- `_build_embedding_bg()` — catches `SyncUpError` and `Exception`, never re-raises
- `_refresh_match_cache()` — exceptions in read/compute/write phases are logged but swallowed
- `_embed_new_items()` — catches `Exception`, logs warning, continues
- `synthesize_vibe()` — catches `Exception`, logs, returns `None`
- `_cleanup_stale_match_cache()` — catches `Exception`, logs, rolls back

**Impact:** In production, a failing embedding build or match refresh is invisible unless logs are actively monitored.

**Fix:** Add a lightweight failure-tracking table and expose `GET /me/background-tasks`, or increment a Prometheus counter on failure.

---

#### [HIGH-4] Missing CHECK constraint on `user_items.raw_type` — schema drift
**File:** `syncup/db/models.py:251-255`

Migration `20260503_0006` creates `ck_user_items_raw_type_values` (`raw_type IN ('consumption', 'rating')`), but the `UserItem` model omits it from `__table_args__`. A fresh `Base.metadata.create_all()` or future Alembic autogenerate will drop this constraint.

**Fix:** Add the `CheckConstraint` to `UserItem.__table_args__`.

---

#### [HIGH-5] Spotify OAuth callback has no rate limit
**File:** `syncup/api/routes/connect.py:912`

The OAuth callback lacks `@limiter.limit()`. An attacker can hammer it to exhaust Spotify API quota, connection pool, or race the DB commit.

**Fix:** Add `@limiter.limit("10/minute")` consistent with other OAuth callbacks.

---

#### [HIGH-6] RequestValidationError handler leaks raw input values
**File:** `syncup/api/app.py:199-213`

The global `_validation_error_handler` returns `exc.errors()` directly. In Pydantic v2, every error dict contains an `input` key with the **raw submitted value**. A user submitting a password to `/api/auth/signup` gets it echoed back in the JSON error body.

**Fix:** Strip the `input` field before returning:
```python
safe_errors = [{k: v for k, v in e.items() if k != "input"} for e in exc.errors()]
```

---

#### [HIGH-7] Signup leaks email existence via timing side-channel
**File:** `syncup/api/routes/auth/router.py:136-138`

`signup()` returns immediately without computing `hash_password()` if the email exists. Argon2id is slow (~50-100 ms). An attacker with timing precision can distinguish "email exists" (fast) from "new email" (slow), enabling account enumeration.

**Fix:** Always run the expensive hash before checking existence, or call `verify_password_dummy()` on the existing-email path to consume equivalent time.

---

### 🟡 MEDIUM

#### [MEDIUM-1] ANN queries use f-string SQL construction for `EMBEDDING_DIM`
**Files:** `syncup/api/routes/matches.py:361-369`, `syncup/api/routes/recommendations.py:110-129`

`EMBEDDING_DIM` is a module constant (384), not user input, so this is not an active SQL injection vector. However, it breaks the parameterized-query invariant and creates a maintenance hazard.

**Fix:** Use a module-level query template or validate `EMBEDDING_DIM` at load and add `# noqa: S608`.

---

#### [MEDIUM-2] `connect.py` is 1002 lines — violates file-size heuristic
**File:** `syncup/api/routes/connect.py`

Handles OAuth start/callback for 4 services, CSV import for 2 services, and shared upsert helpers. At 1000+ lines it exceeds the project's own 800-line soft limit.

**Fix:** Split by service or flow type into a subpackage.

---

#### [MEDIUM-3] Route-to-route import (`_format_vec` from matches.py)
**File:** `syncup/api/routes/recommendations.py:16`

```python
from syncup.api.routes.matches import _format_vec
```

Private helpers should not be imported across route modules.

**Fix:** Move `_format_vec` to `syncup/db/pgvector.py` as a shared utility.

---

#### [MEDIUM-4] `_write_match_results` uses `db.merge()` in a loop
**File:** `syncup/api/routes/matches.py:313-327`

`merge()` issues a `SELECT` then `INSERT`/`UPDATE` per row. For 500 candidates × 2 users = 1000 rows, this is 1000 round-trips in a single transaction.

**Fix:** Use `insert(...).on_conflict_do_update(...)` with a batch of dicts.

---

#### [MEDIUM-5] `UserEmbedding` upsert in `build_user_embedding` uses `merge()`
**File:** `syncup/api/routes/embeddings.py:155`

Same `merge()` anti-pattern. For a single row it's acceptable, but document the expectation.

---

#### [MEDIUM-6] `Settings()` instantiated at module load in `semantic.py`
**File:** `syncup/embeddings/semantic.py:34`

```python
_MODEL_NAME: str = Settings().embedding_model_name
```

This executes at import time, breaking isolated unit tests that just want to import the module.

**Fix:** Move `_MODEL_NAME` initialization into `_get_model()` (lazy).

---

#### [MEDIUM-7] `lastfm_shared_secret` loaded but never used
**File:** `syncup/config.py:36`

Last.fm API signing requires the secret for some methods, but it's never computed. If authenticated Last.fm methods are needed, this will silently fail.

**Fix:** Either implement signing in `LastfmClient` or remove the config field.

---

#### [MEDIUM-8] `_USER_AGENT` placeholder in Reddit client
**File:** `syncup/ingest/reddit.py:26`

```python
_USER_AGENT = "web:syncup:0.1.0 (by /u/REDDIT_DEV_USERNAME)"
```

Reddit's API rules require a descriptive User-Agent. A placeholder causes API rejections.

**Fix:** Make `reddit_user_agent` a required setting or validate at startup.

---

#### [MEDIUM-9] `Item2VecModel` and `build_user_vector` are orphaned code
**Files:** `syncup/embeddings/item2vec.py`, `syncup/embeddings/user_embeddings.py:136-186`

Superseded by sentence-transformers semantic embeddings. Dead code increases maintenance burden.

**Fix:** Delete or move to an `archive/` folder.

---

#### [MEDIUM-10] PKCE code_verifier stored in browser cookie instead of server-side
**File:** `syncup/api/routes/connect.py:908`

The PKCE verifier is stored in an httpOnly cookie (`spotify_verifier`). While cookie flags are correct, it still travels over the wire and is vulnerable to cookie-based attacks.

**Fix:** Store the verifier server-side (short-lived Redis/cache or DB row keyed by `state`).

---

#### [MEDIUM-11] OAuth state / verifier cookies not deleted on callback failures
**File:** `syncup/api/routes/connect.py:388-950`

Cookies are only deleted on **successful** completion. If the flow fails, valid cookies remain in the browser for their 10-minute TTL, widening the replay window.

**Fix:** Delete cookies in a `try/finally` block immediately after reading them.

---

#### [MEDIUM-12] `avatar_url` accepts arbitrary strings without URL validation
**File:** `syncup/api/routes/me.py:29`

```python
avatar_url: str | None = Field(default=None, max_length=500)
```

Accepts any string. If the frontend renders this unescaped, it opens XSS (`javascript:`) or SSRF vectors.

**Fix:** Use `pydantic.HttpUrl` instead of `str`.

---

#### [MEDIUM-13] Unbounded query without LIMIT: manual obsessions
**File:** `syncup/api/routes/taste.py:273-277`

`get_taste` fetches all `ManualObsession` rows for the user without a LIMIT. A prolific user could cause memory pressure.

**Fix:** Add `.limit(100)`.

---

#### [MEDIUM-14] Unbounded query without LIMIT: new items for auto-embedding
**File:** `syncup/api/routes/sync.py:153-163`

`_embed_new_items` selects all items where `embedding IS NULL` with no LIMIT. A large initial sync could load thousands of rows.

**Fix:** Add `.limit(100)` and process in batches.

---

#### [MEDIUM-15] N+1 write pattern in sync upsert loop
**File:** `syncup/api/routes/sync.py:217-235`

`_do_sync_generic` loops over `raw_items` and executes one upsert pair per item. A 500-item sync = 500 item upserts + 500 user_item upserts in a single transaction.

**Fix:** Batch using `pg_insert(...).values([...]).on_conflict_do_update(...)`.

---

#### [MEDIUM-16] Unbounded query: semantic candidate item loading
**File:** `syncup/api/routes/matches.py:382-388`

`_read_semantic_data` loads all `UserItem` + `Item` rows for up to 51 users with no LIMIT. Large libraries can materialize tens of thousands of rows.

**Fix:** Cap with a per-user LIMIT (e.g., top 200 items per user).

---

#### [MEDIUM-17] Non-deterministic heuristic user sampling
**File:** `syncup/api/routes/matches.py:213-218`

```python
select(User.id).where(User.is_matchable == True).limit(500)
```

No `ORDER BY`. Repeated refreshes may process different subsets and produce unstable match results.

**Fix:** Add `.order_by(User.created_at)`.

---

#### [MEDIUM-18] Sensitive token columns over-fetched in public routes
**File:** `syncup/api/routes/me.py:52-54`, `syncup/api/routes/sync.py:280-304`

`get_me` and `trigger_sync` load full `ServiceConnection` rows including encrypted tokens just to return status.

**Fix:** Use `select(ServiceConnection.service, ServiceConnection.sync_status, ...)`.

---

#### [MEDIUM-19] Runtime `cast()` masks invalid DB enum values
**File:** `syncup/api/routes/matches.py:600`, `syncup/api/routes/matches.py:636`

```python
matching_mode=cast(Literal["heuristic", "semantic"], row.matching_mode)
```

`cast()` is a runtime no-op. If DB drift writes an invalid value, it propagates until a Pydantic validation error elsewhere.

**Fix:** Replace with explicit validation against `{"heuristic", "semantic"}`.

---

#### [MEDIUM-20] Untyped `dict[str, Any]` kwargs bypass cookie security attributes
**File:** `syncup/api/routes/connect.py` (multiple cookie set/delete calls)

`_cookie_opts: dict[str, Any]` is unpacked into `set_cookie`/`delete_cookie`. A typo or wrong type (e.g., `secure="False"`) won't be caught statically and could weaken cookie security.

**Fix:** Define a `CookieOpts(TypedDict)` or use explicit keyword arguments.

---

#### [MEDIUM-21] Background task schedules sync without timeout guard
**File:** `syncup/api/routes/matches.py:574`

```python
background_tasks.add_task(_refresh_match_cache, request.app.state.db, user.id)
```

FastAPI `BackgroundTasks` runs in the same threadpool. If the task hangs (e.g., DB deadlock), it starves the pool.

**Fix:** Add an explicit `timeout` parameter, or move heavy work to a proper task queue (Celery, RQ, arq).

---

#### [MEDIUM-22] Duplicated OAuth and CSV import logic
**File:** `syncup/api/routes/connect.py`

Each OAuth callback (~70-115 lines) and CSV import (~120 lines) repeats the same sequence. This violates DRY and means a security fix must be applied in 4+ places.

**Fix:** Extract `_finish_oauth()` and `_import_csv()` generic helpers.

---

### 🟢 LOW

#### [LOW-1] `except Exception:` in `_cleanup_stale_match_cache` too broad
**File:** `syncup/api/routes/matches.py:522-537`

Catches all exceptions including `KeyboardInterrupt`. Should catch `SQLAlchemyError` specifically.

---

#### [LOW-2] `engagement_score` clamp happens in Python, not at DB level
**File:** `syncup/api/routes/sync.py:230`

```python
max(0.0, min(1.0, raw_item["engagement_score"]))
```

Client-side guard with no DB `CHECK` constraint. A buggy client could store values outside [0, 1].

**Fix:** Add `CheckConstraint("engagement_score >= 0 AND engagement_score <= 1")` to `UserItem`.

---

#### [LOW-3] `MatchCache.score` uses `Float(precision=53)` which is a no-op in PostgreSQL
**File:** `syncup/db/models.py:379`

PostgreSQL ignores `precision=53` and uses `double precision` regardless. Harmless but misleading.

**Fix:** Use plain `Float()` and add a comment.

---

#### [LOW-4] `_parse_highlights` logs at `warning` level for every malformed entry
**File:** `syncup/api/routes/matches.py:95-109`

If a cache row has many malformed highlights, this could spam logs. `info` or `debug` is more appropriate.

---

#### [LOW-5] `get_match_detail` queries `User` table after already having the match row
**File:** `syncup/api/routes/matches.py:607-637`

Extra DB round-trip. The user data could be fetched in the same query.

---

#### [LOW-6] `get_taste` subquery could use `LATERAL` or a CTE for clarity
**File:** `syncup/api/routes/taste.py:214-239`

The window-function subquery is correct but the outer query is harder to `EXPLAIN`. Not a bug.

---

#### [LOW-7] `normalize_title` strips all non-word characters including hyphens
**File:** `syncup/ingest/_text.py:23`

```python
s = re.sub(r"[^\w\s]", "", s)
```

"Spider-Man" and "Spiderman" normalize to the same thing (likely intended), but "Rock & Roll" becomes "Rock Roll". Document explicitly.

---

#### [LOW-8] `register_default_clients` does not validate required settings
**File:** `syncup/ingest/registry.py:61-113`

Steam and Last.fm clients are registered even if `api_key` is empty. Failing fast is better.

**Fix:** Skip registration with a log warning if required credentials are missing.

---

#### [LOW-9] `db-schema.md` mentions IVFFlat but migrations use HNSW
**File:** `docs/db-schema.md:103-104`

Stale docs mislead future developers.

**Fix:** Update `db-schema.md` to reflect HNSW indexes.

---

#### [LOW-10] `vibe_synthesizer.py` `_call_llm` has no retry logic
**File:** `syncup/embeddings/vibe_synthesizer.py:146-187`

A single transient network error fails vibe synthesis permanently. LLM providers can return 502/503 during high load.

**Fix:** Add retry with exponential backoff (max 3 attempts).

---

#### [LOW-11] `build_user_embedding` uses Python-side sorting instead of DB `ORDER BY ... LIMIT`
**File:** `syncup/api/routes/embeddings.py:104-109`

```python
capped = sorted(service_rows, key=...)[:_SERVICE_CAP]
```

For users with 1000+ items per service, this fetches all rows to Python.

**Fix:** Apply the per-service cap in SQL using `ROW_NUMBER() OVER (...)`.

---

#### [LOW-12] `sessions.expires_at` is never cleaned up
**File:** `syncup/db/models.py:400-414`

Expired rows accumulate forever. The index makes them cheap to find, but nothing deletes them.

**Fix:** Add a daily cleanup job or use `pg_cron`.

---

#### [LOW-13] Session token lookup does not use timing-safe comparison
**File:** `syncup/auth/router.py:256-265`

Validated via SQL `WHERE sessions.token == <input>`. SQL string equality typically short-circuits on first mismatched byte. While token entropy (256 bits) makes brute-force infeasible, `secrets.compare_digest` is the documented requirement.

**Fix:** Fetch by user or token prefix, then compare in Python with `secrets.compare_digest`.

---

#### [LOW-14] Token encryption key validation accepts 16/24 bytes
**File:** `syncup/ingest/crypto.py:20-24`

The documented requirement is 32-byte AES-256. `validate_key()` accepts 16 and 24 bytes (AES-128/192).

**Fix:** Enforce exactly 32 bytes.

---

#### [LOW-15] Missing `Strict-Transport-Security` header
**File:** `syncup/api/app.py:162-172`

The `security_headers` middleware omits HSTS. In production, this prevents SSL-stripping protection.

**Fix:** Add `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload` when `not settings.debug`.

---

#### [LOW-16] Database engine does not enforce SSL in production
**File:** `syncup/db/session.py:31-37`

`create_engine(database_url)` is called without SSL parameters. If the DB host is remote, traffic may be unencrypted.

**Fix:** Append `?sslmode=require` when not in debug mode, or document that the DSN must include SSL.

---

#### [LOW-17] Token encryption reads directly from `os.environ`
**File:** `syncup/ingest/crypto.py:19`

`_get_key()` reads `os.environ[_KEY_ENV]` directly. If the key is ever injected into `Settings` programmatically (e.g., in tests), the crypto layer ignores it.

**Fix:** Accept the key as an argument, or have `validate_key()` accept a string parameter.

---

#### [LOW-18] Race condition in sync status transition
**File:** `syncup/api/routes/sync.py:280-304`

`trigger_sync` reads `sync_status`, checks it in Python, then updates it. Two concurrent requests can both read `ok`, both set `syncing`, and both spawn background tasks.

**Fix:** Use `SELECT FOR UPDATE`, or an atomic `UPDATE ... WHERE sync_status != 'syncing'`.

---

## Security Audit

| Check | Status | Notes |
|-------|--------|-------|
| AES-GCM nonce unique per call | ✅ | `secrets.token_bytes(12)` |
| Token encryption key validated at startup | ✅ | `validate_key()` in lifespan |
| Plaintext tokens in logs/errors | ✅ | None found |
| Session cookie httpOnly + secure | ✅ | `secure=not debug`, `httponly=True` |
| OAuth state validated with `compare_digest` | ✅ | All 4 flows |
| PKCE verifier random | ✅ | `secrets.token_bytes(32)` → base64url |
| Rate limits on auth endpoints | ✅ | signup 5/min, login 10/min, logout 30/min |
| Timing-safe password check | ✅ | `verify_password_dummy()` for unknown emails |
| CORS from env | ✅ | `_cors_origins()` parses `CORS_ALLOWED_ORIGINS` |
| Security headers middleware | ✅ | CSP, X-Frame-Options |
| Error message stripping | ✅ | `_safe_error_message()` trusts only `SyncClientError` |
| Proxy-aware rate limiting | ❌ | `trusted_hosts="*"` bypasses all limits [HIGH-2] |
| Validation error redaction | ❌ | `input` field leaks raw passwords [HIGH-6] |
| Signup timing side-channel | ❌ | Early return skips argon2id on duplicate [HIGH-7] |
| OAuth callback rate limits | ⚠️ | Spotify callback unprotected [HIGH-5] |
| PKCE verifier storage | ⚠️ | Stored in cookie, not server-side [MEDIUM-10] |
| OAuth cookie cleanup | ⚠️ | Not deleted on failure [MEDIUM-11] |
| `avatar_url` validation | ⚠️ | No URL scheme check [MEDIUM-12] |
| Session timing compare | ⚠️ | SQL equality, not `compare_digest` [LOW-13] |
| HSTS header | ⚠️ | Missing [LOW-15] |
| DB SSL enforcement | ⚠️ | Not configured [LOW-16] |

## Database Audit

| Check | Status | Notes |
|-------|--------|-------|
| FK columns indexed | ✅ | All FKs have explicit indexes |
| Partial indexes | ✅ | D5, D6, D12 present |
| HNSW for ANN | ✅ | Migrations 0011, 0012 |
| CHECK constraints | ⚠️ | `ck_user_items_raw_type_values` missing from model [HIGH-4] |
| `timestamptz` used | ✅ | All datetime columns use `DateTime(timezone=True)` |
| JSONB for flexible metadata | ✅ | `meta` on `Item`, `breakdown`/`highlights` on `MatchCache` |
| N+1 in `get_taste` | ✅ | Single query with window function |
| N+1 in `get_matches` | ⚠️ | Extra `SELECT ... WHERE id IN (...)` for users, but batched |
| Raw SQL in ANN | ⚠️ | f-string for `EMBEDDING_DIM` [MEDIUM-1] |
| Unbounded queries | ❌ | Manual obsessions, new items, semantic candidates [MEDIUM-13..16] |
| N+1 writes in sync | ❌ | One upsert per item [MEDIUM-15] |
| Unbounded DELETE | ⚠️ | Stale cache cleanup deletes all in one statement |
| Non-deterministic sampling | ⚠️ | Heuristic user sample has no ORDER BY [MEDIUM-17] |
| UUID v4 for PKs | ⚠️ | Causes index bloat at scale [MEDIUM-?] |

## API Design Audit

| Check | Status | Notes |
|-------|--------|-------|
| RESTful URLs | ✅ | Nouns, plural, kebab-case |
| HTTP methods correct | ✅ | GET/POST/PATCH/DELETE used semantically |
| Status codes | ✅ | 201 for creates, 204 for deletes, 422 for validation |
| Pydantic validation | ✅ | All routes use typed request bodies |
| Error envelope | ✅ | `{"error": {"code", "message"}}` |
| Rate limiting | ⚠️ | Most endpoints covered; Spotify callback gap [HIGH-5] |
| Cursor pagination | ⚠️ | Keyset cursor works but rounds floats [HIGH-1] |
| Auth dependency | ✅ | `RequireAuth` used consistently |
| Response models | ✅ | `response_model=` on most routes |
| Sub-resource nesting | ⚠️ | `/api/me/items/{id}` is a `user_items` row, not an `items` row |

## ML / Embedding Audit

| Check | Status | Notes |
|-------|--------|-------|
| L2 normalization | ✅ | `_normalize()` in `semantic.py` |
| Two-level aggregation | ✅ | `aggregate_vectors` + `combine_service_vectors` |
| Per-service cap | ✅ | `_SERVICE_CAP = 50` |
| Dimension weights normalize to 1.0 | ✅ | `_normalise()` in `dimensions.py` |
| Semantic mode authoritative | ✅ | No heuristic fallback once embedding exists |
| Cross-service dedup in recs | ✅ | `normalize_title` + `item_type` dedup |
| Score clamped to [0, 1] | ✅ | `max(0.0, min(1.0, 1.0 - distance))` |
| `NO_EMBEDDING_AVAILABLE` guard | ✅ | 422 when no combined embedding |
| Item2Vec dead code | ⚠️ | `item2vec.py` and `build_user_vector()` unused [MEDIUM-9] |
| LLM timeout | ✅ | `timeout=30.0` |
| LLM retry | ❌ | No retry on transient failures [LOW-10] |

## Silent Failure Audit

| Location | Failure Mode | Visibility | Risk |
|----------|-------------|------------|------|
| `_build_embedding_bg` | Exception swallowed | Log only | User thinks embedding built; it didn't |
| `_refresh_match_cache` | Exception in any phase swallowed | Log only | Empty match list persists |
| `_embed_new_items` | `embed_batch` failure swallowed | Log only | New items never get embeddings |
| `synthesize_vibe` | LLM/network failure swallowed | Log only | Taste card never updates |
| `_cleanup_stale_match_cache` | DB error swallowed | Log only | `match_cache` table bloat |
| `close_all()` | Client close errors swallowed | Log only | httpx connection leaks on shutdown |
| `trigger_sync` | Race condition — dual sync possible | Log only | Duplicate background tasks |

---

## Recommendations (Prioritized)

### Immediate (before production)

1. **[HIGH-1]** Fix match cursor to use lossless float encoding (`struct.pack("!d", score)`).
2. **[HIGH-2]** Restrict `ProxyHeadersMiddleware` to configurable trusted hosts.
3. **[HIGH-4]** Add missing `CheckConstraint("raw_type IN ('consumption', 'rating')")` to `UserItem` model.
4. **[HIGH-5]** Add `@limiter.limit("10/minute")` to Spotify OAuth callback.
5. **[HIGH-6]** Redact `input` field from `RequestValidationError` responses.
6. **[HIGH-7]** Burn CPU on duplicate-email signup path to close timing side-channel.
7. **[MEDIUM-1]** Refactor ANN queries to avoid f-string SQL (use module-level template).
8. **[MEDIUM-4]** Replace `db.merge()` loop in `_write_match_results` with bulk `INSERT ... ON CONFLICT DO UPDATE`.

### Short-term (next sprint)

9. **[HIGH-3]** Add background task failure tracking (table or metrics endpoint).
10. **[MEDIUM-2]** Split `connect.py` into a subpackage.
11. **[MEDIUM-3]** Extract `_format_vec` to a shared utility module.
12. **[MEDIUM-6]** Move `Settings()` instantiation out of `semantic.py` module load.
13. **[MEDIUM-10]** Move PKCE verifier storage server-side (Redis/short-lived DB row).
14. **[MEDIUM-11]** Wrap OAuth callbacks in `try/finally` to always delete state/verifier cookies.
15. **[MEDIUM-12]** Change `avatar_url` to `pydantic.HttpUrl`.
16. **[MEDIUM-13..16]** Add LIMITs to unbounded queries.
17. **[MEDIUM-15]** Batch sync upserts with `pg_insert(...).values([...]).on_conflict_do_update(...)`.
18. **[MEDIUM-19]** Replace `cast()` with explicit validation for `matching_mode`.
19. **[MEDIUM-20]** Define `CookieOpts(TypedDict)` for cookie kwargs.
20. **[MEDIUM-21]** Add timeout to background tasks or move to a task queue.

### Nice-to-have

21. **[LOW-2]** Add `CHECK` constraint on `user_items.engagement_score`.
22. **[LOW-10]** Add retry logic to LLM calls.
23. **[LOW-12]** Add expired session cleanup job.
24. **[LOW-13]** Use `secrets.compare_digest` for session token comparison.
25. **[LOW-15]** Add HSTS header in production.
26. **[LOW-16]** Enforce DB SSL in production.
27. **[LOW-18]** Fix sync status race with `SELECT FOR UPDATE`.
28. Update `db-schema.md` to reflect HNSW indexes.

---

## Stats

| Metric | Value |
|--------|-------|
| Total backend `.py` files | ~55 |
| Lines of application code | ~5,500 |
| Test count | 998 passing |
| Test coverage | Not measured in this review |
| Migrations | 11 |
| CRITICAL issues | 0 |
| HIGH issues | 7 |
| MEDIUM issues | 22 |
| LOW issues | 18 |
| **Verdict** | **WARNING** — address HIGH + top 10 MEDIUM before production |
