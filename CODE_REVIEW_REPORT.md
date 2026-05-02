# Full Backend Code Review Report

## CRITICAL

### 1. `_refresh_match_cache` will OOM at scale
**Location:** `syncup/api/routes/matches.py:116-121`

```python
rows = db.execute(
    select(UserItem.user_id, UserItem.item_id, Item.service, Item.name)
    .join(Item, UserItem.item_id == Item.id)
    .join(User, UserItem.user_id == User.id)
    .where(User.is_matchable == True)
).all()
```

This loads **all** user items for **all** matchable users into memory in a single query. At 10k matchable users x 100 items = 1M rows. No batching, no streaming, no LIMIT.

**Fix:** Batch by user or use server-side cursor (`stream_scalars`). For now, add a TODO comment and cap the query.

---

## HIGH

### 2. `config.py` has dead code
**Location:** `syncup/config.py:16-19`

`cors_allowed_origins` is defined in `Settings` but `_cors_origins()` in `app.py` reads `os.environ` directly, bypassing Settings entirely. Two parsers for one env var.

**Fix:** Either remove the field from `config.py` or make `_cors_origins()` read from `settings.cors_allowed_origins`.

### 3. `dev-guide.md` "Known gaps" is stale
**Location:** `docs/dev-guide.md:293-294`

Still lists:
- *"CORS origins are hardcoded"* — **FIXED by your Fix 1**
- *"`SESSION_SECRET` not set"* — **DOCUMENTED by your Fix 8**

These are false alarms now. Remove them or move to a "Resolved" section.

### 4. No max length on Steam connect inputs
**Location:** `syncup/api/routes/connect.py:36-37`

```python
steam_id: str | None = Field(None, min_length=1)
vanity_url: str | None = Field(None, min_length=1)
```

No `max_length`. A malicious client could POST a 10MB string. FastAPI will accept it and pass it to Steam API.

**Fix:** Add `max_length=100` to both fields (Steam IDs are 17 digits, vanity URLs are short).

### 5. Rate limiter is IP-only
**Location:** `syncup/limiter.py:7`

```python
limiter = Limiter(key_func=get_remote_address)
```

All authenticated endpoints are rate-limited by IP, not by user. A bad actor with a botnet or proxy rotation can bypass per-user limits. For authenticated routes like `POST /api/me/recompute` (1/hour), this is a real gap.

**Fix:** For authenticated routes, use a composite key: `f"{ip}:{user.id}"` or just `user.id`.

---

## MEDIUM

### 6. Missing test coverage

| What | Why it matters |
|------|---------------|
| `_cors_origins()` parses env + fallback | Regression risk if someone refactors |
| Rate limit returns 429 | Can't prove limits work |
| Startup raises RuntimeError without key | Only tested in debug mode |
| Invalid cursor resets to page 0 | `matches.py:83` is uncovered |
| `updated_at` trigger with raw SQL | Migration exists but no test verifies it |
| Full sync pipeline end-to-end | Mocked tests don't catch integration bugs |

### 7. No CSRF tokens
**Location:** `syncup/auth/router.py:95-103`

Cookies are `samesite="lax"`, which mitigates CSRF for cross-site POSTs, but not same-site or relaxed browser policies. Since this is a stateful API with cookie auth, consider adding a CSRF token for non-GET routes before production.

**Mitigation:** `SameSite=Lax` + all mutations use POST/PATCH/DELETE (already true). Acceptable for MVP but document the gap.

### 8. `ManualObsession.created_at` relies on route, not DB
**Location:** `syncup/api/routes/obsessions.py:65`

```python
obs = ManualObsession(
    id=uuid.uuid4(),
    created_at=datetime.now(UTC),  # <-- set by Python, not DB
    ...
)
```

Other models use `_created_at()` which sets `server_default=func.now()`. If someone creates a `ManualObsession` outside the route (e.g., admin script), `created_at` will be NULL and crash.

**Fix:** Add `default=_now` to the `created_at` column in `ManualObsession`, same as other models.

---

## LOW / OBSERVATIONS

### 9. `MatchCache` refresh has no deduplication guard
**Location:** `syncup/api/routes/matches.py:157-183`

If a user triggers recompute twice quickly (before first background task finishes), two `_refresh_match_cache` tasks run concurrently. They both read the same data and both write to `match_cache`. `db.merge()` with the same PK prevents duplicates, but it's wasted work.

**Fix:** Add a `syncing` lock in `match_cache` or use a distributed lock before Phase 2.

### 10. `_safe_error_message` truncates generic errors too aggressively
**Location:** `syncup/api/routes/sync.py:118-126`

```python
return "Sync failed -- please retry"
```

For debugging, this is opaque. Consider logging the full exception before sanitizing.

**Note:** You already do -- `logger.exception()` is called at each catch site. So this is fine.

### 11. `item2vec.py` uses `os.cpu_count()` for workers
**Location:** `syncup/embeddings/item2vec.py:39`

In containerized environments, `os.cpu_count()` may return the host CPU count, not the container limit. Could oversubscribe.

**Fix:** Use `min(os.cpu_count() or 4, 8)` or read from env.

### 12. `me.py` PATCH allows `display_name: null` as no-op
**Location:** `syncup/api/routes/me.py:62-63`

```python
if "display_name" in fields and body.display_name is not None:
    user.display_name = body.display_name
```

Sending `{"display_name": null}` is silently ignored. This is documented behavior (`null` is a no-op for NOT NULL fields), but could confuse API consumers who expect it to clear the field. Consider returning 422 instead.

---

## SECURITY CHECKLIST

| Check | Status | Notes |
|-------|--------|-------|
| No hardcoded secrets | PASS | All from env |
| Password hashing | PASS | argon2id, OWASP defaults |
| Session cookies | PASS | HttpOnly, Secure in prod, SameSite=Lax |
| Timing-safe auth | PASS | `verify_password_dummy()` on unknown emails |
| Token encryption | PASS | AES-GCM, key from env, cached |
| SQL injection prevention | PASS | Parameterized queries throughout |
| Input validation | PASS | Pydantic schemas on all routes |
| Rate limiting | PASS | All write endpoints limited |
| Error sanitization | PASS | `_safe_error_message()` strips upstream details |
| CSRF protection | WARN | SameSite=Lax only; no tokens |
| CORS | PASS | Env-driven with fallback |
| Secret key validation | PASS | Startup rejects missing key in prod |

---

## FIXES VERIFICATION SUMMARY (8 Fixes)

| # | Fix | Verdict | Issue |
|---|-----|---------|-------|
| 1 | CORS env var | PASS | Remove dead `cors_allowed_origins` from `config.py` |
| 2 | Rate limits | PASS | Add 429 enforcement tests |
| 3 | Startup validation | PASS | Add non-debug test |
| 4 | Key caching | PASS | Clean |
| 5 | Popularity scope | PASS | Clean |
| 6 | Cursor warning | PASS | Add invalid cursor test |
| 7 | Rename | PASS | Fully consistent |
| 8 | session_secret | PASS | Update dev-guide.md known gaps |
| 9 | Migration | PASS | Clean |
| 10 | Docs | WARN | **dev-guide.md lines 293-294 need update** |

---

## RECOMMENDED ACTIONS (in order)

1. **Add `max_length` to Steam connect inputs** (`connect.py:36-37`) -- 1 line
2. **Update `dev-guide.md` known gaps** -- remove CORS and SESSION_SECRET lines -- 2 lines
3. **Remove dead `cors_allowed_origins` from `config.py`** or wire it up -- 1 line
4. **Add batching/streaming to `_refresh_match_cache`** -- protect against OOM
5. **Add user-ID to rate limit key for authenticated routes** -- security hardening
6. **Fix `ManualObsession.created_at` default** in `models.py` -- 1 line
7. **Add tests for:** invalid cursor, CORS parsing, rate limit 429, non-debug startup

**Total estimated lines to touch:** ~20 lines + 4-6 new tests.
