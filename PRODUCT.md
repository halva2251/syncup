# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

SyncUp is built for people who want to compare taste across media and communities, and for hackathon viewers evaluating how the project works. The public homepage should help a first-time visitor understand the project before they enter the app.

## Product Purpose

SyncUp connects a person's activity from games, music, film, anime, and online communities into one taste profile. It uses that profile to find people with compatible taste and surface recommendations across domains.

## Positioning

The project matches people by the signal in what they actually play, watch, listen to, read, and follow—not by demographics or a dating profile.

## Operating Context

People can connect Steam, Spotify, Last.fm, Letterboxd, AniList, Trakt, Reddit, and RateYourMusic. They can review their synced taste, add manual obsessions, exclude misleading items, adjust per-service importance, view matches, and explore recommendations.

## Capabilities and Constraints

- Session-based signup and login, onboarding, service connections, taste profiles, match feeds, recommendations, and settings are implemented in the web app.
- Item metadata is serialized and embedded into 384-dimensional semantic vectors.
- User vectors aggregate item embeddings with engagement and user-controlled dimension weights.
- Matching currently supports rarity-weighted overlap, with semantic cosine matching represented as the intended cross-domain mechanism.
- Optional LLM-generated taste archetypes are explanatory only and do not affect match scores.
- The public homepage must link to login and registration while remaining primarily descriptive rather than conversion-driven.

## Brand Commitments

The product name is SyncUp. Voice is direct, curious, and technically honest. Avoid corporate language, startup hype, dating language, and aggressive calls to action. The established visual system uses DM Sans, neutral card-based surfaces, restrained blue accents, generous whitespace, rounded corners, and full light/dark parity.

## Evidence on Hand

- The implementation and current feature inventory live in `README.md`, `backend/`, and `frontend/`.
- The established interface system is documented in `DESIGN.md`.
- No testimonials, customer logos, adoption metrics, or commercial claims are available and none should be fabricated.

## Product Principles

- Explain the mechanism with concrete project details.
- Treat taste as personal, editable data rather than a fixed identity label.
- Keep user control visible alongside automation.
- Prefer honest project status over promotional claims.
- Make cross-domain connections legible.

