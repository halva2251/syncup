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

---

## ML Architecture Decisions (2026-05-12)

Everything below is a record of the reasoning behind the Phase 2 pivot. Read this before changing the ML stack.

### Why we dropped Item2Vec as the foundation

Item2Vec is Word2Vec applied to items. It learns that items co-owned by many users are similar. We were going to train it on the UCSD Steam review dataset and the Last.fm public dataset, then use the resulting vectors as `items.embedding`.

The problem: Item2Vec trained on Steam data produces game vectors. Item2Vec trained on Last.fm data produces artist vectors. **These live in completely different vector spaces.** Cosine similarity between a game vector and an artist vector is mathematically meaningless — you can't compare them. The CLAUDE.md says "the innovation — the model learns that certain game aesthetics correlate with certain music aesthetics." That claim was never achievable with separate per-service Item2Vec models. There was no implementation path for cross-domain matching in the original plan.

Secondary problems:
- `min_count=5` filters out niche items — exactly the items with the highest taste signal
- Bag-of-words user vector averaging loses information (eclectic taste gets averaged into mush)
- Requires downloading large public datasets and running offline training before any matching works
- Gensim Word2Vec is CPU-bound, not GPU-accelerated — the 3090 wouldn't help anyway

Item2Vec is not deleted. It remains as an optional future enhancement: once we have 1000+ real users with multi-service connections, we can train a unified model where each user's sequence contains IDs from all their services concatenated. That's when cross-domain co-occurrence can actually be learned from real user behaviour. But it requires real users first, and is a second layer on top of semantic embeddings, not a replacement.

### Why we switched to semantic text embeddings

`sentence-transformers/all-MiniLM-L6-v2` embeds any text into a 384-dim semantic vector space. All items — games, artists, films, anime, subreddits — get embedded into the **same space** from day one. Cross-domain works immediately: "Disco Elysium — game, RPG narrative" and "Nick Cave and the Bad Seeds — music, gothic rock" end up geometrically close because the concepts are semantically related, not because users co-own them.

Advantages:
- Cross-domain matching works on day one with zero training data
- No offline training run needed — no dependency on public datasets or GPU hardware
- Works with sparse profiles (cold start is much better)
- Niche items still get embeddings (min_count problem gone)
- Explainable to judges and users

Limitations to be honest about:
- Embedding quality depends on how much genre/tag metadata is in `items.metadata`. A bare item name ("game 12345") produces a worse embedding than a rich description. Quality improves as metadata enriches over time.
- We're using someone else's pre-trained model for the base embeddings. The model didn't learn from our data. This is why we add the CF re-ranker.
- Semantic similarity ≠ taste similarity perfectly. "The Shining" and "The Room" are both horror films — semantically close, but very different taste signals.

**EMBEDDING_DIM changed from 128 → 384** to match `all-MiniLM-L6-v2` output. 384 captures meaningfully more semantic nuance than 128 for text embeddings. Migration required (safe: no real embeddings existed in DB yet at time of pivot).

### Why we added the CF re-ranker

This is for the KI Challenge (ki-challenge.ch, organized by ETH AI Center). One of the 8 judging criteria is "scientific rigor" — they want to see that the team understands the AI they're using and trained something on their own data. Using only a pre-trained sentence-transformers model is valid but thin: the model was trained by someone else.

The CF (collaborative filtering) re-ranker trains on our own `user_items` engagement data. It's a matrix factorization model (implicit feedback, BPR or ALS via the `implicit` library). It learns patterns like "users who engaged heavily with Disco Elysium, Hollow Knight, and Celeste also tend to engage with Hades and Planescape: Torment" — purely from co-occurrence in our own data, not from item descriptions.

Architecture: semantic ANN search produces 50 candidates → CF re-ranker scores those 50 → return top 10. The two-stage approach is intentional:
- Semantic handles cold start and cross-domain
- CF improves ranking for users with rich histories where real engagement patterns exist
- New users (not in CF model) skip the re-ranking step and get pure semantic results

This gives us a genuine scientific comparison: "semantic-only vs semantic+CF, here's when each wins and loses." That's the self-critical assessment criterion answered.

### The KI Challenge context

This project is our entry for the 2026 KI Challenge (Swiss, ages 13–19, organized by ETH AI Center). Judging criteria:
1. Eigenständigkeit (independence/originality)
2. Code functionality
3. Code readability
4. Difficulty level and effort
5. Originality / Creativity / Inventiveness
6. Practical relevance and insights gained
7. Scientific rigor — analyzing error sources, embedding in current research
8. Self-critical assessment of results

A 2025 finalist built NextRead (single-domain book recommendations). SyncUp does cross-domain matching across 8 services simultaneously. The technical complexity (719 tests, production-grade API, pgvector ANN, 8 OAuth integrations) significantly exceeds typical entries.

The framing for judges: "We built a cross-domain taste matching system. We use pre-trained semantic embeddings for cold-start and cross-domain matching, then re-rank with collaborative filtering trained on real user engagement data. Here's where semantic alone fails, here's where CF improves it, here's where both fail."

### KI Challenge demo strategy

The finals are at ETH AI Center on August 29, 2026. You need to demo live in front of judges. This is what the demo should look like:

1. **"Let me show you what the AI learned about me."** Open the taste card. It shows top games, top artists, top films — all pulled from real connected accounts. The AI has profiled you from actual data across 8 platforms.

2. **"Now watch this."** Hit the recommendations endpoint with `item_type=game`. The system returns games you've never played but are close to your taste vector. Point out one you actually know and love (you'll have checked this in advance). "It recommended Pathologic 2 — I've wanted to play that for years and never touched it. The AI figured that out from my Steam library and Last.fm."

3. **"Here's the science."** Show the evaluation report: precision@10, recall@10, matching mode comparison. "We measured it. Semantic+CF outperforms the heuristic baseline by X%. Here's where it still fails: users with fewer than 20 items get worse recommendations because the signal is too thin."

4. **"Here's where it gets interesting."** Show a cross-domain recommendation: "I asked for film recommendations. It surfaced The Tree of Life and Stalker — atmospheric, slow-burn, philosophical films. It inferred that from my games and music, not my Letterboxd."

Point 3 is what wins criterion 7 and 8. Every other team will show their app working. You will show evidence that it works and honest analysis of where it doesn't.

### Corrected: rarity weighting is wrong for LLM input selection

Early in the architecture discussion, I proposed weighting items by rarity (niche items first) when selecting which items to send the LLM for taste synthesis. This was wrong and the user caught it.

Rarity weighting makes sense for **comparing two users** (heuristic matcher) — if both users like CS2, that shared item doesn't differentiate them, so it scores low. But for **describing one user**, rarity is irrelevant. If someone's actual favourite artist is Taylor Swift and favourite game is Fortnite, those ARE the signal. Filtering them out because they're popular gives the LLM a distorted, unrepresentative picture.

**Correct approach for LLM item selection: top items by engagement score, period.** Cap per-service representation (top 5 per service, up to 20 total) so one service doesn't dominate. No popularity filter.

The LLM handles mainstream taste just fine. "Top artists: Taylor Swift, Drake, The Weeknd" is a coherent profile and deserves an accurate archetype just as much as an obscure one.

### User-controlled taste profile (item exclusion)

The user identified a key problem: someone might have 2000 hours in Overwatch because they played it with friends for years, not because it represents their taste. Importing it and centering their profile around it would break the "this understands me" feeling.

**The feature:** `user_items.excluded` boolean. When true, the item is skipped in:
- User vector computation
- LLM item selection for vibe synthesis
- Recommendations

API: `PATCH /api/me/items/{item_id}` with `{"excluded": true/false}`.

**The UX decision:** do NOT do this at import time. Showing 400 games at import and asking the user to review them all is overwhelming and creates false urgency. The correct pattern: **import everything silently, let users refine anytime.**

The user sees their taste card and archetype first. Then they think "hmm, Overwatch doesn't feel right here." They find it in their profile, exclude it, and the archetype updates immediately. That feedback loop — seeing the system respond to their input in real time — IS the "it actually understands me" moment. The control shapes the understanding.

This is distinct from `preference_overrides` (which boosts item weight, for items you love despite low engagement). Exclusion is "don't use this at all." Keep them separate — different semantics.

**The product principle this embodies:** the user collaborates with the AI to define themselves. The system is not a black box that analyzes you — it's a tool you shape. For the KI Challenge framing: "human-AI collaboration."

The three tuning levers users have:
1. **Exclude items** — remove misrepresentative items entirely
2. **Boost items** — existing preference_overrides, increase weight of underrepresented items
3. **Dimension weights** — existing, weight services differently (70% music, 30% games)

All three already exist in the API. The frontend just needs a unified "manage your taste profile" view. Your friend's job in Phase 3.

### What "matching mode" means in the response

`GET /api/matches` returns a `matching_mode` field:
- `"heuristic"` — user has no embedding yet, using rarity-weighted item overlap
- `"semantic"` — user has a combined embedding, using pgvector ANN cosine search
- `"semantic+cf"` — user is in the CF model, semantic candidates re-ranked by CF

The heuristic is never removed. It's the permanent fallback for new users and a useful baseline for evaluating the other modes.
