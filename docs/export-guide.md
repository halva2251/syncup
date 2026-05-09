# Service Export Guide

How to connect each service to SyncUp. Covers what the user needs to do, what format the data arrives in, and any gotchas.

---

## Steam

**Method:** Enter your Steam ID or vanity URL — no export needed.

1. Go to your Steam profile page.
2. Copy the URL. If it's `https://steamcommunity.com/id/halva`, your vanity URL is `halva`. If it's `https://steamcommunity.com/profiles/76561198...`, use the number directly.
3. POST to `/api/connect/steam` with either `{"steam_id": "..."}` or `{"vanity_url": "..."}`.

**Gotcha:** Your Steam profile must be public (Settings → Privacy → Profile Status: Public). SyncUp can't read private libraries.

---

## Last.fm

**Method:** Enter your Last.fm username — no export needed.

1. Log in at last.fm.
2. Your username is in the URL: `https://www.last.fm/user/halva` → username is `halva`.
3. POST to `/api/connect/lastfm` with `{"username": "halva"}`.

**Gotcha:** Last.fm scrobbles need to be enabled in your music player. The API reads your all-time top artists and tracks, not a CSV.

---

## Spotify

**Method:** OAuth flow — fully automatic.

1. Navigate to `GET /api/connect/spotify/oauth/start` (or hit it in the browser once the frontend exists).
2. Authorize SyncUp on the Spotify consent screen.
3. Redirects back automatically.

No manual export. Spotify pulls your top artists and recently played tracks via the API.

---

## Letterboxd

**Method:** Export your diary as CSV, then upload it.

1. Go to [letterboxd.com/settings/data](https://letterboxd.com/settings/data).
2. Click **Export your data** → download the ZIP.
3. Inside the ZIP, find `diary.csv` (not `ratings.csv` — the diary includes dates).
4. Upload via `POST /api/connect/letterboxd/import` with the CSV as multipart form data.

**Expected columns:** `Name`, `Year`, `Rating` (plus others that are ignored).

**Gotcha:** Entries with no rating are silently skipped. If you've watched films without rating them, they won't appear.

**Scale:** Letterboxd uses 0.5–5.0 half-star ratings stored as decimals (`4.5`, `5.0`, etc.). Our formula: `(rating - 0.5) / 4.5`.

---

## AniList

**Method:** OAuth flow — fully automatic.

1. Navigate to `GET /api/connect/anilist/oauth/start`.
2. Authorize SyncUp on the AniList consent screen.
3. Redirects back automatically.

AniList pulls all anime and manga from your lists with their scores. Entries with score = 0 (not rated) are skipped.

**Rating scale:** AniList lets each user choose their preferred score format. SyncUp reads the format from your account and normalizes correctly:

| AniList format | Raw range | Normalization |
|---------------|-----------|---------------|
| POINT_100 | 1–100 | `score / 100` |
| POINT_10 | 1–10 (integers) | `score / 10` |
| POINT_10_DECIMAL | 1.0–10.0 | `score / 10` |
| POINT_5 | 1–5 (stars) | `score / 5` |
| POINT_3 | 1–3 (smileys) | `score / 3` |

All formats are handled automatically — no user action needed.

---

## Trakt

**Method:** OAuth flow — fully automatic.

1. Navigate to `GET /api/connect/trakt/oauth/start`.
2. Authorize SyncUp on the Trakt consent screen.
3. Redirects back automatically.

Trakt pulls your watched movies and shows (play count / episode count). No rating data — Trakt signals are engagement-based (plays, not stars).

**Token expiry:** Trakt tokens expire every 90 days. SyncUp will auto-refresh when syncing.

---

## Reddit

**Method:** OAuth flow — fully automatic.

1. Navigate to `GET /api/connect/reddit/oauth/start`.
2. Authorize SyncUp on the Reddit consent screen (scopes: `identity mysubreddits`).
3. Redirects back automatically.

Reddit pulls your subscribed subreddits. Mainstream subreddits (> 1M subscribers) are filtered out — only niche communities count as taste signals. Scoring: `1 / ln(subscribers + 2)` (smaller subreddits score higher).

**Prerequisite:** Your Reddit developer app must be approved. Register at [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) with redirect URI `http://127.0.0.1:3000/api/connect/reddit/oauth/callback`.

---

## RateYourMusic

**Method:** Export your ratings as CSV, then upload it.

1. Log in at [rateyourmusic.com](https://rateyourmusic.com).
2. Click your username → **Your data** → **Export your data** → download the CSV.
3. Upload via `POST /api/connect/rateyourmusic/import` with the CSV as multipart form data.

**Expected columns:** `Title`, `Release_Date`, `Rating` (plus artist columns `First Name` / `Last Name` and others that are used automatically).

**Gotcha:** Entries with no rating are silently skipped. Unrated albums in your collection won't appear.

**Scale:** RYM exports ratings as integers 1–10 (not 0.5–5.0). `10` = 5 stars, `9` = 4.5 stars, etc. Our formula: `(rating - 1) / 9.0`. This is different from Letterboxd despite both using a 5-star visual display.

**Artist deduplication:** If the export includes `First Name` / `Last Name` columns (it always does for full exports), the artist is incorporated into the album's ID to prevent "Greatest Hits" from different artists colliding.

---

## Quick reference

| Service | Method | Data type | Manual step |
|---------|--------|-----------|-------------|
| Steam | API lookup | Games + playtime | Enter Steam ID/URL |
| Last.fm | API lookup | Artists + tracks | Enter username |
| Spotify | OAuth | Top artists + recent tracks | Click authorize |
| Letterboxd | CSV upload | Film ratings | Export diary.csv from settings |
| AniList | OAuth | Anime + manga ratings | Click authorize |
| Trakt | OAuth | Films + shows watched | Click authorize |
| Reddit | OAuth | Subreddit subscriptions | Click authorize |
| RateYourMusic | CSV upload | Album ratings | Export ratings CSV from settings |
