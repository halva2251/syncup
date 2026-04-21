# Service API Credentials

Each service needs its own registration. Both developers should register independently — that way you each have dev credentials and the team isn't blocked on one account.

Put all secrets in `backend/.env` (never commit). Use the variable names listed in each section.

---

## 1. Steam

Steam uses a **single API key** (no OAuth for our needs — user just enters their Steam ID or we resolve it from a vanity URL).

### Steps

1. Sign in to your Steam account at [steamcommunity.com](https://steamcommunity.com/).
2. Go to [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey).
3. Register a **domain name** — for local dev, use `localhost` (Steam accepts this).
4. Copy the generated key.

### What you can fetch

- `GetOwnedGames` — full library with playtime per game
- `GetPlayerSummaries` — profile info (name, avatar, real name if public)
- `GetRecentlyPlayedGames` — last 2 weeks of activity

### Env

```
STEAM_API_KEY=your_key_here
```

### Docs

- [Steam Web API reference](https://steamcommunity.com/dev)
- [steamapi community docs](https://steamapi.xpaw.me/)

---

## 2. Last.fm

Last.fm uses an **API key + shared secret** pair. For our use case (read-only listening history), no OAuth is strictly required — you can fetch public data by username.

### Steps

1. Create a Last.fm account at [last.fm](https://www.last.fm/).
2. Go to [last.fm/api/account/create](https://www.last.fm/api/account/create).
3. Fill in:
   - **Application name**: `SyncUp (dev - your_name)`
   - **Application description**: taste-based matching
   - **Callback URL**: `http://localhost:3000/api/auth/lastfm/callback` (only needed if doing full auth flow later)
4. Submit. You'll see your API key and shared secret on the next page.

### What you can fetch

- `user.getTopArtists` — top artists by play count over a period
- `user.getTopTracks` — top tracks
- `user.getTopTags` — taste tags (e.g. "post-punk", "shoegaze")
- `user.getRecentTracks` — scrobble history

### Env

```
LASTFM_API_KEY=your_key_here
LASTFM_SHARED_SECRET=your_secret_here
```

### Docs

- [Last.fm API](https://www.last.fm/api)
- [User methods](https://www.last.fm/api/intro)

---

## 3. Spotify

Spotify uses **OAuth 2.0** (Authorization Code flow). Users must explicitly grant access.

### Steps

1. Sign in at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard).
2. Click **Create app**.
3. Fill in:
   - **App name**: `SyncUp (dev - your_name)`
   - **App description**: taste-based matching service
   - **Redirect URIs**: `http://localhost:3000/api/auth/spotify/callback`
   - **APIs used**: check **Web API**
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
SPOTIFY_REDIRECT_URI=http://localhost:3000/api/auth/spotify/callback
```

### Docs

- [Spotify Web API](https://developer.spotify.com/documentation/web-api)
- [Authorization Code flow](https://developer.spotify.com/documentation/web-api/tutorials/code-flow)

---

## .env Template

Create `backend/.env` from this template (add to `.gitignore` if not already):

```dotenv
# Steam
STEAM_API_KEY=

# Last.fm
LASTFM_API_KEY=
LASTFM_SHARED_SECRET=

# Spotify
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
SPOTIFY_REDIRECT_URI=http://localhost:3000/api/auth/spotify/callback

# App
DATABASE_URL=postgresql://syncup:syncup@localhost:5432/syncup
SESSION_SECRET=
```

---

## Rate Limits (know before demo day)

| Service | Limit | Notes |
|---------|-------|-------|
| Steam | 100k req/day per key | generous; cache anyway |
| Last.fm | 5 req/sec | be polite, batch where possible |
| Spotify | ~180 req/min per token | app-level limits also apply |

**Golden rule for demo day**: never hit a live API during the presentation. Everything must be pre-fetched and cached in the database.
