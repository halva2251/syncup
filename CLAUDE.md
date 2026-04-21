# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**VibeMatch** — a people-matching service that connects users based on their actual taste across platforms (Steam, Last.fm, Spotify, etc.), not demographics. Users connect their accounts via OAuth, the system trains user embeddings from their real data, and matches them with others who share their vibe — with control over *which dimensions* matter and *how similar* matches should be.

Not dating. Finding your people.

## Architecture (to be built)

```
vibe-match/
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
