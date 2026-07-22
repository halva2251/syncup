# Database Schema (Sketch)

PostgreSQL 15+ with the [`pgvector`](https://github.com/pgvector/pgvector) extension for embedding similarity search.

This is a **sketch** — expect it to change during implementation. The purpose is to lock down entity relationships and agree on what data flows through the system.

---

## Design principles

1. **Privacy-first.** `users.is_matchable` defaults to `false`. Users opt in after reviewing their taste profile.
2. **Raw + aggregated.** We store the raw per-service data (hours per game, scrobbles per artist) *and* computed embeddings. If we change the algorithm, we re-aggregate without re-fetching.
3. **Canonical items.** A Steam game or Last.fm artist is stored once in `items` and referenced by many users. Item embeddings are shared.
4. **Cached embeddings + cached matches.** User vectors live in `user_embeddings`. Match scores are cached in `match_cache` with a freshness stamp; we recompute on demand when stale.
5. **Multiple login methods.** `auth_providers` lets a user sign in via email, Discord, Google, Spotify, or Steam. Data collection (`service_connections`) is separate — you might log in with Discord but connect Steam for data.

---

## Schema

```sql
-- =============================================================
-- Extensions
-- =============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================
-- Users: core identity
-- =============================================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           CITEXT UNIQUE,              -- nullable (OAuth-only users)
    password_hash   TEXT,                       -- nullable (OAuth-only users)
    display_name    TEXT NOT NULL,
    avatar_url      TEXT,
    bio             TEXT,
    discord_handle  TEXT,                       -- shown to matches after reveal
    social_links    JSONB NOT NULL DEFAULT '{}', -- manually added public social-profile URLs
    languages       TEXT[],                     -- nullable; skippable during onboarding
    is_matchable    BOOLEAN NOT NULL DEFAULT false,
    onboarded       BOOLEAN NOT NULL DEFAULT false,
    vibe_summary    TEXT,                       -- LLM-generated 2-3 sentence taste summary (Phase 2 Block F)
    archetype       TEXT,                       -- LLM-generated label, e.g. "The Patient Aesthete"
    key_themes      TEXT[],                     -- LLM-generated list of 3-5 cross-domain themes
    vibe_computed_at TIMESTAMPTZ,               -- set when vibe synthesis last ran; null if no llm_api_key configured
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()  -- auto-updated by trigger trg_users_updated_at
);

CREATE INDEX idx_users_matchable ON users(is_matchable) WHERE is_matchable = true;

-- =============================================================
-- Auth providers: login methods (can coexist per user)
-- =============================================================
CREATE TABLE auth_providers (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider          TEXT NOT NULL,    -- 'email' | 'discord' | 'google' | 'spotify' | 'steam'
    provider_user_id  TEXT NOT NULL,    -- their id on that provider
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_user_id)
);

CREATE INDEX idx_auth_providers_user ON auth_providers(user_id);

-- =============================================================
-- Service connections: OAuth tokens for data pulls
-- Separate from auth_providers because a user might log in with
-- Discord but connect Steam/Last.fm/Spotify for data.
-- =============================================================
CREATE TABLE service_connections (
    id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    service                  TEXT NOT NULL,    -- 'steam'|'lastfm'|'spotify'|'letterboxd'|'anilist'|'trakt'|'reddit'|'rateyourmusic'
    external_user_id         TEXT NOT NULL,
    access_token_encrypted   BYTEA,            -- nullable for services using plain API keys
    refresh_token_encrypted  BYTEA,
    token_expires_at         TIMESTAMPTZ,
    last_synced_at           TIMESTAMPTZ,
    sync_status              TEXT NOT NULL DEFAULT 'pending',  -- 'pending'|'syncing'|'ok'|'error'
    sync_error               TEXT,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, service)
);

CREATE INDEX idx_service_connections_user ON service_connections(user_id);

-- =============================================================
-- Items: canonical catalog (shared across users)
-- Item embeddings are computed from training datasets and reused.
-- =============================================================
CREATE TABLE items (
    id                     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service                TEXT NOT NULL,    -- 'steam'|'lastfm'|'spotify'|'letterboxd'|'anilist'|'trakt'|'reddit'|'rateyourmusic'
    item_type              TEXT NOT NULL,    -- 'game'|'track'|'artist'|'album'|'film'|'show'|'anime'|'manga'|'community'
    external_id            TEXT NOT NULL,
    name                   TEXT NOT NULL,
    metadata               JSONB NOT NULL DEFAULT '{}',  -- shape documented below
    embedding              vector(384),
    embedding_computed_at  TIMESTAMPTZ,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (service, item_type, external_id)
);

CREATE INDEX idx_items_service_type ON items(service, item_type);
CREATE INDEX idx_items_embedding ON items USING hnsw (embedding vector_cosine_ops);
-- Switched from IVFFlat to HNSW in migration 20260606_0012 (Phase 2 Block I):
-- no lists/probes tuning required, handles dynamic inserts gracefully.

-- =============================================================
-- User items: per-user engagement with catalog items
-- engagement_score is normalized (0-1); raw_value keeps the
-- original (hours, scrobbles) for debugging/future algorithms.
-- =============================================================
CREATE TABLE user_items (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id           UUID NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    engagement_score  REAL NOT NULL,    -- 0..1, normalized (see normalization formulas in roadmap.md)
    raw_value         REAL,             -- original metric: minutes (Steam), play count (Last.fm/Spotify), rating (Letterboxd/AniList/Trakt/RYM)
    raw_type          TEXT NOT NULL DEFAULT 'consumption'  -- 'consumption' | 'rating'
                          CHECK (raw_type IN ('consumption', 'rating')),
    excluded          BOOLEAN NOT NULL DEFAULT false,  -- user-controlled removal from vector/LLM/recs (Phase 2 Block E)
    last_engaged_at   TIMESTAMPTZ,
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, item_id)
);

-- raw_type distinguishes consumption signals (hours played, scrobble count) from
-- rating signals (star ratings). The embedding builder applies different normalization
-- logic for each type. Added in migration 0006.

CREATE INDEX idx_user_items_user ON user_items(user_id);
CREATE INDEX idx_user_items_item ON user_items(item_id);

-- =============================================================
-- Preference overrides: "I love this, ignore the data"
-- =============================================================
CREATE TABLE preference_overrides (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id           UUID NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    boost_multiplier  REAL NOT NULL CHECK (boost_multiplier > 0),  -- 2.0 = 2x, 0.1 = demote
    note              TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, item_id)
);

CREATE INDEX idx_overrides_user ON preference_overrides(user_id);

-- =============================================================
-- Manual obsessions: free-text taste entries
-- For things not in connected data (books, niche music, etc.)
-- Optional link to a canonical item if we can resolve it.
-- =============================================================
CREATE TABLE manual_obsessions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category    TEXT NOT NULL CHECK (category IN ('game','music','film','book','show','anime','manga','community','other')),
    -- anime/manga/community added in migration 0007 to match AniList and Reddit item_types
    name        TEXT NOT NULL,
    item_id     UUID REFERENCES items(id),  -- nullable: resolved if we can
    weight      REAL NOT NULL DEFAULT 1.0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_obsessions_user ON manual_obsessions(user_id);

-- =============================================================
-- Dimension weights: per-service contribution to match score
-- A row per (user, service) the user has connected.
-- =============================================================
CREATE TABLE user_dimension_weights (
    user_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    service  TEXT NOT NULL,
    weight   REAL NOT NULL DEFAULT 1.0 CHECK (weight >= 0 AND weight <= 1),
    PRIMARY KEY (user_id, service)
);

-- =============================================================
-- User embeddings: cached user vectors per service, plus a 'combined'
-- vector for single-query nearest-neighbour search.
-- =============================================================
CREATE TABLE user_embeddings (
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    service      TEXT NOT NULL,        -- 'steam'|'lastfm'|'spotify'|'letterboxd'|'anilist'|'trakt'|'reddit'|'rateyourmusic'|'combined'
    embedding    vector(384) NOT NULL,
    computed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, service)
);

-- Partial index for the combined-vector nearest-neighbour search.
-- Switched from IVFFlat to HNSW in migration 20260606_0011 (Phase 2 Block H):
-- no lists/probes tuning required, performs well from single-digit to millions of rows.
CREATE INDEX idx_user_embeddings_combined
    ON user_embeddings USING hnsw (embedding vector_cosine_ops)
    WHERE service = 'combined';

-- =============================================================
-- Match cache: top matches + per-dimension breakdown
-- Canonical ordering avoids duplicate (a,b) / (b,a) rows.
-- =============================================================
CREATE TABLE match_cache (
    user_a_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_b_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    score        REAL NOT NULL,        -- 0..1 heuristic/cosine similarity
    breakdown    JSONB NOT NULL,       -- {steam: 0.72, lastfm: 0.89, spotify: 0.81}
    highlights   JSONB NOT NULL DEFAULT '[]',  -- [{service, item_name}, ...] top shared items
    matching_mode TEXT NOT NULL DEFAULT 'heuristic',  -- 'heuristic' | 'semantic' (Phase 2 Block H, migration 20260606_0011)
    computed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_a_id, user_b_id),
    CHECK (user_a_id < user_b_id)
);

CREATE INDEX idx_match_cache_a ON match_cache(user_a_id, score DESC);
CREATE INDEX idx_match_cache_b ON match_cache(user_b_id, score DESC);

-- =============================================================
-- Sessions: server-side session tokens
-- Simpler than JWT for a project this size.
-- =============================================================
CREATE TABLE sessions (
    token       TEXT PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);
```

---

## Open questions (to resolve during implementation)

- **Embedding dimension** — resolved: `vector(384)`. `all-MiniLM-L6-v2` outputs 384-dim vectors. Migration `20260520_0010` applied this change.
- **ANN index type** — resolved: both `idx_items_embedding` and `idx_user_embeddings_combined` were switched from IVFFlat to **HNSW** (migrations `20260606_0011` and `20260606_0012`). HNSW requires no `lists`/`probes` tuning and performs well from single-digit to millions of rows — a better fit for an early-stage table with no representative row count to tune against.
- **Token encryption** — `BYTEA` columns assume symmetric encryption (AES-GCM) with a key from env. Decide key rotation strategy later.
- **Match cache TTL** — initial target: invalidate on any embedding update for either user; hard-expire after 24h.
- **`items.metadata` shape** — free JSONB, but the following keys are load-bearing and must stay stable:

  | service | item_type | key | type | source |
  |---------|-----------|-----|------|--------|
  | `steam` | `game` | `img_icon_url` | string | Steam owned-games response |
  | `lastfm` | `track` | `artist` | string | Last.fm top-tracks `artist.name` |
  | `spotify` | `artist` | `genres` | string[] | Spotify artist object |
  | `spotify` | `track` | `artists` | string[] | Spotify track `artists[].name` |
  | `letterboxd` | `film` | `title_normalized` | string | Lowercased/stripped film name |
  | `letterboxd` | `film` | `release_year` | int | Year column from Letterboxd CSV |
  | `trakt` | `film` | `title_normalized` | string | Lowercased/stripped film name |
  | `trakt` | `film` | `release_year` | int | Release year from Trakt API |
  | `trakt` | `show` | `title_normalized` | string | Lowercased/stripped show name |
  | `trakt` | `show` | `release_year` | int | First air year from Trakt API |
  | `anilist` | `anime` | `title_normalized` | string | Lowercased/stripped title |
  | `anilist` | `anime` | `release_year` | int | `startDate.year` from AniList |
  | `anilist` | `anime` | `format` | string | `TV`\|`MOVIE`\|`OVA`\|`ONA`\|`SPECIAL` |
  | `anilist` | `manga` | `title_normalized` | string | Lowercased/stripped title |
  | `anilist` | `manga` | `release_year` | int | `startDate.year` from AniList |
  | `reddit` | `community` | `subreddit_name` | string | Subreddit name (without r/) |
  | `reddit` | `community` | `subscribers` | int | Subscriber count at ingest time |
  | `reddit` | `community` | `description` | string | `public_description`, first 200 chars |
  | `rateyourmusic` | `album` | `title_normalized` | string | Lowercased/stripped album title |
  | `rateyourmusic` | `album` | `release_year` | int | Year extracted from `Release_Date` column |
  | `rateyourmusic` | `album` | `artist_normalized` | string | Normalized artist name (`First Name` + `Last Name`); empty string when absent. Load-bearing — included in `external_id` to prevent same-title album collisions across artists. |

  **Cross-service deduplication note:** Films and shows from different services (Letterboxd + Trakt) are stored as separate `items` rows (one per service). The heuristic matcher and embedding builder deduplicate media items by `(title_normalized, release_year)` when scoring — a film shared between two services counts as one shared item, not two. The `title_normalized` + `release_year` metadata keys are therefore load-bearing for all film/show/anime/manga `item_type` values.

  All other keys are optional/raw. Rename or remove load-bearing keys only with a migration.
