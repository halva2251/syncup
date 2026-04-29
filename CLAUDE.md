# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SyncUp** — a people-matching service that connects users based on their actual taste across platforms (Steam, Last.fm, Spotify, etc.), not demographics. Users connect their accounts via OAuth, the system trains user embeddings from their real data, and matches them with others who share their vibe — with control over *which dimensions* matter and *how similar* matches should be.

Not dating. Finding your people.

## Architecture (to be built)

```
syncup/
├── backend/          # Python FastAPI — ML pipeline + REST API
│   ├── ingest/       # OAuth flows + service API clients
│   ├── embeddings/   # Item & user embedding model training
│   ├── matching/     # Similarity engine + dimension weighting
│   └── api/          # FastAPI routes
├── frontend/         # Next.js — profile, connect services, see matches
└── data/             # Training datasets (gitignored)
```

## Key Design Decisions

- **Embedding model**: Item2Vec-style embeddings trained on public datasets (Steam reviews, Million Song Dataset), then user profiles built as weighted averages of item embeddings. Cosine similarity for matching.
- **Preference overrides**: Users can manually boost items that underrepresent their actual taste (e.g. "I love Disco Elysium despite low hours") — these boosts increase item weight in the user vector.
- **Dimension weighting**: Users control per-service contribution to their match score (e.g. "weight my music taste 70%, games 30%").
- **Cross-domain correlation**: The innovation — the model learns that certain game aesthetics correlate with certain music aesthetics, enabling cross-platform vibe matching.

## Services Supported

MVP: Steam, Last.fm, Spotify
Future: Letterboxd, Trakt, Anilist

## Stack

- Backend: Python, FastAPI, SQLAlchemy, PyTorch (embeddings)
- Frontend: Next.js, TypeScript
- DB: PostgreSQL
- Auth: OAuth per service + session-based user auth

## Post-Match Interaction

Profile card + user-provided Discord/social handle. No in-app chat. Users connect off-platform.

# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
