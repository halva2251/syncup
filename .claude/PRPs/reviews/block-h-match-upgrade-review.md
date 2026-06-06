# PR Review: feat/phase2-match-upgrade — Block H Semantic ANN Matching

**Reviewed**: 2026-06-06
**Branch**: feat/phase2-match-upgrade → master
**Decision**: APPROVE (after fixes)

## Summary

Semantic ANN matching path added alongside the existing heuristic scorer. `_refresh_match_cache` tries semantic first (HNSW ANN on `user_embeddings` combined vector), falls back to heuristic when no embedding exists. `match_cache` gains `matching_mode` field. `POST /api/me/recompute` queues embedding build before cache refresh. All 932 tests pass.

## Reviewers

- ml-reviewer agent
- code-reviewer agent
- security-reviewer agent

## Findings

### CRITICAL — Fixed before merge

| # | Issue | File | Fix |
|---|-------|------|-----|
| 1 | **Missing `EMBEDDING_DIM` import** — `_read_semantic_data` f-string referenced `EMBEDDING_DIM` but it wasn't imported. `NameError` was swallowed by `except Exception`, silently disabling the entire semantic matching path. | `matches.py:19` | Added `EMBEDDING_DIM` to import |
| 2 | **ANN query leaked non-matchable users** — Semantic candidates weren't filtered by `users.is_matchable = true`. Users who opted out could still appear as matches. | `matches.py:317–330` | Added `AND user_id IN (SELECT id FROM users WHERE is_matchable = true)` |

### HIGH — Fixed before merge

| # | Issue | File | Fix |
|---|-------|------|-----|
| 3 | **No heuristic fallback when semantic returns empty** — If all 50 ANN candidates were filtered out, `_refresh_match_cache` returned early without writing anything and never fell back to heuristic. | `matches.py:447–453` | Only `return` early when semantic results are actually written |
| 4 | **`_read_semantic_data` happy path untested** — All tests mocked `scalar_one_or_none()` to return `None`. The ANN query branch was never executed. | `tests/test_matches_semantic.py` | Added `test_read_semantic_data_happy_path` |

### HIGH — Deferred to next release

| # | Issue | File | Reason |
|---|-------|------|--------|
| 5 | **Race condition on composite PK writes** — `_write_match_results` uses `db.merge(row)` in a loop (SELECT-then-INSERT/UPDATE, not atomic). Concurrent refreshes can unique-violate. | `matches.py:278–284` | Pre-existing Phase 1 pattern. Requires bulk `ON CONFLICT DO UPDATE` refactor. |
| 6 | **Heuristic refresh overwrites semantic rows** — Symmetric cache means B's heuristic can overwrite A's semantic row for pair (A,B). | `matches.py:437–464` | Product decision needed on mode precedence. |

### MEDIUM — Acknowledged

- **Popularity computed over wrong population in semantic mode** — `pop_rows` aggregated over 51 users vs 500 in heuristic. Acceptable for now; `top_shared_highlights` rarity weighting is intentionally heuristic-biased.
- **No cold-start guard for semantic mode** — Single-item embeddings can produce noisy ANN matches. Mitigated by 50-candidate limit and `score <= 0` filter.
- **No staleness check on combined embedding** — Weeks-old embeddings used silently. Mitigated by `POST /api/me/recompute` rebuilding embedding before refresh.

### LOW — Fixed

- `MatchOut.matching_mode` typed as `Literal["heuristic", "semantic"]` instead of plain `str`
- Migration docstring corrected (said IVFFlat, code creates HNSW)
- Test renamed to `test_compute_semantic_scores_filters_non_positive_similarity` with `distance=1.0` boundary case

## Correctness Spot-checks

- **L2 normalization chain**: `semantic.py` normalizes item embeddings; `aggregate_vectors` normalizes the aggregated user vector. pgvector `<=>` computes true cosine distance.
- **Dimension consistency**: `EMBEDDING_DIM = 384` used in model, SQL query, and pgvector cast.
- **Score math**: `score = 1.0 - distance` correctly converts cosine distance to similarity. `<= 0.0` filter and `min(1.0, ...)` clamp are defensive.
- **HNSW choice**: Migration and model both use `hnsw` with `vector_cosine_ops`. No lists-tuning required.
- **Background task ordering**: `_build_embedding_bg` added before `_refresh_match_cache`, so embedding is committed before cache refresh reads it.
- **Security**: No SQL injection (f-string only contains hardcoded constant; user inputs are bound parameters). Rate limiting applied. Authorization enforced.

## Validation Results

- **Tests**: 932 passed
- **mypy**: clean on modified source files
- **ruff**: clean on modified lines (4 pre-existing E501 untouched)
