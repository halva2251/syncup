# Brainstorm / Vibe Dump

Rough ideas, half-baked thoughts, stuff we want to remember. No structure required.
When something solidifies into a real decision, it moves to roadmap.md or product-strategy.md.

---

## Onboarding / UX ideas

- **In-app export tutorial**: each CSV service (Letterboxd, RateYourMusic) needs a "here's exactly where to click" walkthrough inside the connect flow. Screenshots or a short animated GIF per service. The export paths are non-obvious and differ per site — without a guide, users will export the wrong file (e.g. Letterboxd has `diary.csv`, `ratings.csv`, `reviews.csv` — we want `diary.csv`). See `docs/export-guide.md` for the current developer-facing version; this needs to become UI copy.
- **Rating scale note for RateYourMusic**: RYM shows 0.5–5.0 stars in the UI but exports as integers 1–10. Worth surfacing this in the connect flow so users aren't confused why their "4.5 star" album shows `score: 0.89` in the API.
- **"What will SyncUp see?" preview**: before confirming the OAuth or CSV upload, show the user what data SyncUp is about to read (e.g. "We'll read your 342 subreddit subscriptions and filter to niche communities"). Builds trust.

---

## The core vibe

find your people based on actual taste, not demographics. not dating. not "add me on discord because we're both in this server". more like — i want to meet the person who also has 300 hours in disco elysium AND listens to arca AND rated stalker 5 stars. that specific intersection is a person. find that person.

---

## Features (dump)

- find like-minded people
- recommendations for activities, games, songs, movies etc
- profile page
- _activity feed → bridge activity from services (what are your matches currently playing/listening to)_
- tinder swipe style? not sure if this is the best UX tho
- taste card that people actually want to share (letterboxd diary energy)
- archetype labels ("the immersive indie", "the tryhard", etc.) — people will screenshot these

---

## Services we want (wishlist, no filter)

**Music**
- Last.fm ✅ (done)
- Spotify ✅ (done)
- Apple Music
- Deezer
- SoundCloud
- RateYourMusic (the real ones use this)

**Games**
- Steam ✅ (done)
- Tracker.gg (valorant/rocket league stats)
- PlayStation Network
- Xbox Network

**Social**
- Reddit → subreddit subscriptions (huge vibe signal)
- Twitter / X
- Bluesky
- Instagram
- DAJIA.LOL (BEST WEBSITE)

**Media**
- Letterboxd (film nerd essential)
- AniList / MyAnimeList
- IMDB
- _YouTube — not sure, watch history is weird_
- Trakt.tv (TV tracking)

**Books**
- StoryGraph
- Goodreads (less cool but bigger)

**Dev / other**
- GitHub → projects / repos (probably only useful for the activity feed)
- itch.io (indie game ownership — completely different crowd from Steam)
- Bandcamp (how people discover music, not just what they listen to)

---

## Onboarding thoughts

- name
- _age, gender — not sure → probably just make it skippable_
- languages you speak
- likes / dislikes / interests → cool for the profile and as a quick way to be matchable before connecting any service
- connect your services

the first thing they see after onboarding should make them go "woah this actually knows me". the taste card needs to slap.

---

## Random ideas to maybe explore

- "compatibility report" between two friends — like "here's how similar you and @sam are and why"
- let users see what archetype their matches are before seeing full profiles
- a "vibe check" mode — answer 5 questions about what you're in the mood for and get temporary matches
- import your RateYourMusic / Letterboxd data via CSV export for services without APIs
- weekly email: "3 new people joined who match your vibe this week"
- let users write a short "looking for" blurb — not romantic, more like "co-op partner for CRPGs" or "someone to send music to"

---

## What makes a good match notification feel exciting vs creepy

thinking about this a lot. showing "you and @user both love disco elysium and arca" = exciting.
showing "we noticed you listened to this song 47 times this week" = creepy.
the framing matters as much as the data.

---

## Stuff we still haven't decided

- do we ever add in-app messaging or is discord handle forever?
- do we show match % as a number or just relative ordering?
- public profiles or invite-only / opt-in visibility?
- do matches expire if you haven't interacted?
