# Service API Credentials

Each service needs its own registration. Both developers should register independently — that way you each have dev credentials and the team isn't blocked on one account.

Put all secrets in `backend/.env` (never commit). Use the variable names listed in each section.

**Letterboxd and RateYourMusic need no credentials** — they're CSV-import services (`POST /api/connect/{service}/import`). Users upload their data export directly; see `docs/export-guide.md` for where to find it.

---

## 1. Steam

Steam uses **OpenID 2.0** to discover the user's Steam ID, plus a **Steam Web API key** to fetch library data. Users can also enter a Steam ID or vanity URL manually as a fallback.

### Steps

1. Sign in to your Steam account at [steamcommunity.com](https://steamcommunity.com/).
2. Go to [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey).
3. Register a **domain name** — for local dev, use `localhost` (Steam accepts this).
4. Copy the generated key.
5. (Optional) Register this callback URL in the OpenID realm settings:
   - `http://127.0.0.1:3000/api/connect/steam/openid/callback`

### What you can fetch

- `GetOwnedGames` — full library with playtime per game
- `GetPlayerSummaries` — profile info (name, avatar, real name if public)
- `GetRecentlyPlayedGames` — last 2 weeks of activity

### Env

```
STEAM_API_KEY=your_key_here
# STEAM_OPENID_RETURN_TO=http://127.0.0.1:3000/api/connect/steam/openid/callback
# STEAM_OPENID_REALM=http://127.0.0.1:3000
```

### Docs

- [Steam Web API reference](https://steamcommunity.com/dev)
- [Steam OpenID provider](https://steamcommunity.com/dev)
- [steamapi community docs](https://steamapi.xpaw.me/)

---

## 2. Last.fm

Last.fm issues an **API key + shared secret** pair. The shared secret is required for the optional web-auth flow; the existing username-only fallback still works with just the API key.

### Steps

1. Create a Last.fm account at [last.fm](https://www.last.fm/).
2. Go to [last.fm/api/account/create](https://www.last.fm/api/account/create).
3. Fill in:
   - **Application name**: `SyncUp (dev - your_name)`
   - **Application description**: taste-based matching
   - **Callback URL**: `http://127.0.0.1:3000/api/connect/lastfm/oauth/callback`
4. Submit. Copy both the **API key** and the **shared secret**.

### What you can fetch

- `user.getTopArtists` — top artists by play count over a period
- `user.getTopTracks` — top tracks
- `user.getTopTags` — taste tags (e.g. "post-punk", "shoegaze")
- `user.getRecentTracks` — scrobble history

### Env

```
LASTFM_API_KEY=your_key_here
LASTFM_SHARED_SECRET=your_shared_secret_here
# LASTFM_REDIRECT_URI=http://127.0.0.1:3000/api/connect/lastfm/oauth/callback
```

### Docs

- [Last.fm API](https://www.last.fm/api)
- [Last.fm web authentication](https://www.last.fm/api/webauth)
- [User methods](https://www.last.fm/api/intro)

---

## 3. Spotify

Spotify uses **OAuth 2.0** (Authorization Code flow). Users must explicitly grant access.

> **Note on the redirect URI:** Spotify no longer accepts `http://localhost` — use `http://127.0.0.1` instead (or HTTPS). This means during development, open the app at `http://127.0.0.1:3000` rather than `http://localhost:3000`, otherwise session cookies won't persist across the Spotify redirect.

### Steps

1. Sign in at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard).
2. Click **Create app**.
3. Fill in:
   - **App name**: `SyncUp (dev - your_name)`
   - **App description**: taste-based matching service
   - **Redirect URIs**: `http://127.0.0.1:3000/api/auth/spotify/callback`, then click **Add** (typing alone doesn't save it)
   - **APIs used**: check **Web API** — note this section stays greyed out until a valid redirect URI has been added
4. Accept the ToS and save.
5. Copy **Client ID** and **Client Secret** from the app settings.

### Required OAuth scopes

- `user-top-read` — top artists and tracks
- `user-library-read` — saved albums and tracks
- `user-read-recently-played` — recent listening

### Env

```
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:3000/api/auth/spotify/callback
```

### Docs

- [Spotify Web API](https://developer.spotify.com/documentation/web-api)
- [Authorization Code flow](https://developer.spotify.com/documentation/web-api/tutorials/code-flow)

---

## 4. AniList

AniList uses **OAuth 2.0** (Authorization Code flow). Tokens do not expire, so no refresh flow is needed.

### Steps

1. Sign in at [anilist.co](https://anilist.co).
2. Go to **[anilist.co/settings/developer](https://anilist.co/settings/developer)**.
3. Click **Create New Client**.
4. Fill in:
   - **Name**: `SyncUp (dev - your_name)`
   - **Redirect URL**: `http://127.0.0.1:3000/api/connect/anilist/oauth/callback`
   - (The description field is optional)
5. Submit. You'll see a **Client ID** (an integer) and **Client Secret** immediately.

### What you can fetch

- `MediaListCollection` — full ANIME and MANGA list with scores and timestamps

### Env

```
ANILIST_CLIENT_ID=123456
ANILIST_CLIENT_SECRET=your_secret_here
# ANILIST_REDIRECT_URI is optional — default is correct for local dev
```

> **Note on the Client ID:** AniList issues integer IDs, not UUID strings. Paste it as-is.

> **Without credentials configured:** the `/api/connect/anilist/oauth/start` endpoint returns `503 SERVICE_NOT_CONFIGURED`. The rest of the app (Steam, Spotify, Last.fm, Letterboxd) continues to work normally.

### Docs

- [AniList API documentation](https://docs.anilist.co)
- [OAuth guide](https://docs.anilist.co/guide/auth)

---

## 5. Trakt.tv

Trakt uses **OAuth 2.0** (Authorization Code flow). Tokens expire after 90 days; the client will automatically refresh them.

### Steps

1. Sign in at [trakt.tv](https://trakt.tv).
2. Go to **[trakt.tv/oauth/applications](https://trakt.tv/oauth/applications)**.
3. Click **New Application**.
4. Fill in:
   - **Name**: `SyncUp (dev - your_name)`
   - **Redirect uri**: `http://127.0.0.1:3000/api/connect/trakt/oauth/callback`
   - **Javascript (cors) origins**: leave blank for local dev
   - Uncheck **Checkin** and **Scrobble** — SyncUp only needs read access
5. Submit. Copy the **Client ID** and **Client Secret**.

### What you can fetch

- `/users/me/watched/movies` — watched films with play counts
- `/users/me/watched/shows` — watched shows with episode counts

### Env

```
TRAKT_CLIENT_ID=your_client_id
TRAKT_CLIENT_SECRET=your_client_secret
# TRAKT_REDIRECT_URI=http://127.0.0.1:3000/api/connect/trakt/oauth/callback  ← default, only set if overriding
```

> **Without credentials configured:** `/api/connect/trakt/oauth/start` returns `503 SERVICE_NOT_CONFIGURED`. All other services continue to work normally.

### Docs

- [Trakt API documentation](https://trakt.docs.apiary.io/)
- [OAuth guide](https://trakt.docs.apiary.io/#reference/authentication-oauth)

---

## 6. Reddit

Reddit uses **OAuth 2.0** (Authorization Code flow) with `duration=permanent` to receive a long-lived refresh token. Access tokens expire after 1 hour.

> **Reddit requires a `User-Agent` header** identifying the application and developer. The hardcoded value in `reddit.py` is `web:syncup:0.1.0 (by /u/REDDIT_DEV_USERNAME)`. Update it if project ownership changes.

### Steps

1. Sign in at [reddit.com](https://www.reddit.com).
2. Go to **[reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)**.
3. Click **Create Another App** (or **Create App** if first time).
4. Fill in:
   - **Name**: `SyncUp (dev - your_name)`
   - **Type**: select **web app**
   - **Redirect URI**: `http://127.0.0.1:3000/api/connect/reddit/oauth/callback`
   - Description and about URL are optional
5. Submit. Copy the **client id** (shown under the app name) and the **secret**.

### Required OAuth scopes

- `identity` — read the authenticated user's username
- `mysubreddits` — list subscribed subreddits

### What you can fetch

- `/subreddits/mine/subscriber` — paginated list of subscribed communities (up to ~10,500 per account)

### Env

```
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
# REDDIT_REDIRECT_URI=http://127.0.0.1:3000/api/connect/reddit/oauth/callback  ← default, only set if overriding
```

> **Without credentials configured:** `/api/connect/reddit/oauth/start` returns `503 SERVICE_NOT_CONFIGURED`. All other services continue to work normally.

### Docs

- [Reddit OAuth2 guide](https://github.com/reddit-archive/reddit/wiki/OAuth2)
- [Reddit API documentation](https://www.reddit.com/dev/api/)

---

## .env Template

Create `backend/.env` from this template (add to `.gitignore` if not already):

```dotenv
# Steam
STEAM_API_KEY=
# STEAM_OPENID_RETURN_TO=http://127.0.0.1:3000/api/connect/steam/openid/callback
# STEAM_OPENID_REALM=http://127.0.0.1:3000

# Last.fm
LASTFM_API_KEY=
LASTFM_SHARED_SECRET=
# LASTFM_REDIRECT_URI=http://127.0.0.1:3000/api/connect/lastfm/oauth/callback

# Spotify
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
SPOTIFY_REDIRECT_URI=http://127.0.0.1:3000/api/auth/spotify/callback

# AniList
ANILIST_CLIENT_ID=
ANILIST_CLIENT_SECRET=
# ANILIST_REDIRECT_URI=http://127.0.0.1:3000/api/connect/anilist/oauth/callback  ← default, only set if overriding

# Trakt
TRAKT_CLIENT_ID=
TRAKT_CLIENT_SECRET=
# TRAKT_REDIRECT_URI=http://127.0.0.1:3000/api/connect/trakt/oauth/callback  ← default, only set if overriding

# Reddit
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
# REDDIT_REDIRECT_URI=http://127.0.0.1:3000/api/connect/reddit/oauth/callback  ← default, only set if overriding

# TMDB (optional — used for film/show genre enrichment and autocomplete)
TMDB_API_KEY=

# MusicBrainz (optional — used for music artist autocomplete)
# Set a descriptive User-Agent. No API key required.
MUSICBRAINZ_USER_AGENT=SyncUp/0.1.0 (your-email@example.com)

# Google Books (optional — used for faster book autocomplete)
GOOGLE_BOOKS_API_KEY=

# App
DATABASE_URL=postgresql://syncup:syncup@localhost:5432/syncup
SESSION_SECRET=

# Optional: frontend origin to land users on after OAuth/web-auth/OpenID callbacks.
# In dev, set this when the frontend runs on a different port than the backend.
# FRONTEND_URL=http://127.0.0.1:3001
```

---

## Rate Limits (know before demo day)

| Service | Limit | Notes |
|---------|-------|-------|
| Steam | 100k req/day per key | generous; cache anyway |
| Last.fm | 5 req/sec | be polite, batch where possible |
| Spotify | ~180 req/min per token | app-level limits also apply |
| AniList | 90 req/min | tokens never expire; GraphQL — we fetch everything in one request |
| Trakt | 1,000 req/5 min per user | tokens expire after 90 days; refresh handled automatically |
| Reddit | 100 req/min per OAuth client | tokens expire after 1 hour; refresh handled automatically |

## Autocomplete search APIs

The obsession autocomplete feature uses the following public search APIs. Only TMDB requires an API key; the others are free with rate-limit etiquette.

### MusicBrainz (music artists)

No API key required, but a descriptive `User-Agent` header is mandatory.

1. Create an account at [musicbrainz.org](https://musicbrainz.org).
2. Set `MUSICBRAINZ_USER_AGENT` to something like `SyncUp/0.1.0 (youremail@example.com)`.
3. Respect the 1 request/second limit (the backend enforces this).

### Google Books (books) — recommended for speed

Free API key required, but responses are much faster than Open Library.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a project.
3. Enable the **Books API**.
4. Create an API key under **Credentials**.
5. Set `GOOGLE_BOOKS_API_KEY` in `backend/.env`.

If `GOOGLE_BOOKS_API_KEY` is not set, book autocomplete falls back to Open Library.

### Open Library (books) — fallback

No API key or account required.

- [Open Library Search API docs](https://openlibrary.org/dev/docs/api/search)
- Be polite and do not hammer the endpoint.
- Response times can be slow (>3s); use Google Books if autocomplete feels sluggish.

### Steam Store (games)

No API key required beyond the `STEAM_API_KEY` already used for library sync.

---

**Golden rule for demo day**: never hit a live API during the presentation. Everything must be pre-fetched and cached in the database.
