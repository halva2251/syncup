# Product Strategy & Cold Start Playbook

Consolidated strategic notes from multiple review sessions. This is a living document — update it as the product and market evolve.

---

## Honest Product Assessment

### The Core Bet

The specific problem — *"I want to find people who share my actual taste, not just demographics"* — is genuinely underserved. Discord servers and subreddits solve it at the category level ("find other Radiohead fans") but not at the **intersection level** ("find people whose taste profile overlaps with mine across multiple domains simultaneously").

The cross-domain correlation is the real innovation. Not "you both like Radiohead" — that's trivial. The bet is that someone who plays *Disco Elysium*, listens to *Talk Talk*, and rates *Stalker* 5 stars is a specific kind of person, and that the model can learn those correlations without you ever having to articulate them. If the embeddings work, that's genuinely novel.

### The Right Framing

**Don't position as a dating app.**

Competing with Tinder/Bumble/Hinge on dating is a losing battle — physical attraction still dominates romance, and taste-based matching is a terrible primary filter for dating. You'll match two people who both love *Disco Elysium* and Arca, but if there's no chemistry, it's awkward and they churn.

**Frame it as "find your people."** Friends, server mates, co-op partners, people to send music to at 2am. Discord proved people desperately want to find their tribe based on shared subcultural interests, not geography or looks. The "no in-app chat, just exchange Discord handles" decision is brilliant for this: it keeps the product lightweight and acknowledges people already have a chat app they prefer.

Dating can be a side effect. The real market is **taste-based friendship discovery**.

### Target User Profile

Your target user is:
- 18–35, tech-adjacent
- Uses multiple taste-data services *seriously*
- Open to connecting with strangers
- Wants connection based on vibe, not demographics
- Gamer / music nerd / film obsessive

Small but real. These are the people who evangelize products that work for them.

### Honest Concerns

| Concern | Severity | Notes |
|---------|----------|-------|
| **Cold start** | Critical | Before enough users exist, matches are meaningless or non-existent. Every social discovery product dies here. |
| **Privacy** | High | What you listen to at 3am, the games you've sunk 800 hours into but never talk about publicly — people share these with *platforms* but not necessarily *strangers*. The opt-in + dimension control helps, but the UX needs careful thought. |
| **Data scarcity** | Medium | Not everyone has rich data on all platforms. A Steam library with 2 games produces a garbage embedding. |
| **Moat** | Medium | Thin until the model actually works and you have enough users for matches to feel magical. Engineering is not the hard part — getting to the magical threshold is. |
| **Mainstream appeal** | Low | Mainstream users won't engage deeply enough. Don't target them. Go deep with niches. |

---

## Cold Start Strategy

The cold start has two dimensions:
1. **Data density** — Do users have enough connected data to be matchable?
2. **Network density** — Are there enough users in the pool to produce matches?

You must solve both simultaneously.

### Phase 0: Make the Product Valuable Without Matches

This is the single most important decision. If users only get value when matched, they churn before the network exists.

**Build the "taste card" as the primary product, with matching as the bonus.**

During onboarding, after connecting one service or adding 3 manual obsessions, generate a shareable visual card:

```
Your SyncUp Vibe
🎮 70% Immersive Sims    🎵 30% Post-Punk
Top: Disco Elysium, Arca, Factorio

[Share to Twitter/X]  [Find Your People]
```

People will share these *even if there are zero other users on the platform*. Each share is an organic ad targeting exactly your demographic. Letterboxd and Spotify Wrapped proved this works.

**Action:** Before building `/matches`, build a beautiful, shareable taste profile page at `/me/taste`. Make it the onboarding climax.

### Phase 1: Lower the Matchability Threshold

Your current preconditions:
- `is_matchable = true`
- At least 1 service connected OR ≥ 3 manual obsessions
- Embedding computed

**The "1 service" rule is too high for launch.** Change it to:

| Rule | Rationale |
|------|-----------|
| **≥ 3 manual obsessions = matchable** | Zero API friction. Someone can be matchable in 60 seconds. |
| **OR 1 connected service = matchable** | For power users who have data. |
| **OR complete the taste card = matchable** | Gamifies onboarding. |

The `manual_obsessions` table already exists — **this is your secret weapon.** Lead with it in onboarding. Ask: *"What are 3 things you're obsessed with that define you?"* Let them type freeform (books, albums, games, artists). Don't make them connect APIs first.

**Action:** Reorder onboarding: manual obsessions first, then "connect services to improve matches."

### Phase 2: Use Heuristics Before ML Works

Your `Item2Vec` model trained on public data is fine for item embeddings. But user-user matching via cosine similarity on embeddings requires **co-occurrence data** (users who share items). You won't have that at launch.

**Replace embedding-based matching with simple heuristics for the first ~500 users:**

```python
def match_score_heuristic(user_a, user_b):
    # Jaccard similarity on item overlap, weighted by item rarity
    shared_items = set(a_items) & set(b_items)
    if not shared_items:
        return 0

    score = sum(1 / item_popularity[item] for item in shared_items)
    return normalize(score)
```

A shared love of *Disco Elysium* (niche) should score higher than both liking *Counter-Strike 2* (mainstream). This heuristic produces *better* early matches than a poorly-trained embedding model because it doesn't require user-user training data.

**Phase transitions:**
- **0–100 users:** Heuristic matching + manual obsessions only
- **100–1,000 users:** Heuristic + public-dataset embeddings
- **1,000+ users:** Switch to co-occurrence-trained embeddings

**Action:** Implement the heuristic matcher as a fallback. It's ~20 lines and buys months of runway.

### Phase 3: Seed with Ghost Archetypes (Not Fake Users)

Don't create fake profiles — users hate that. Instead, create **public taste archetypes** from your training data:

```
"This is what a match with a 'Post-Punk Indie Gamer' looks like"
85% compatibility
Shared: Disco Elysium, Have a Nice Life, Hollow Knight
```

These aren't users to message. They're **demonstrations** of what the matching engine sees. Show 3–5 archetypes during onboarding so users understand *how* they're being matched. It sets expectations and makes the algorithm feel transparent.

**Action:** Generate 10 archetypes from your public training datasets. Show them on a "How Matching Works" page.

### Phase 4: Launch Community-by-Community

Don't launch to "everyone." Pick **one dense subculture**, dominate it, then expand.

**The wrong launch:** "We're live! Tell your friends!"

**The right launch:** Partner with one 5,000-person Discord server or subreddit that fits the vibe perfectly:
- r/patientgamers + r/letstalkmusic overlap
- A specific indie game Discord (e.g., Hollow Knight, Celeste, Hades)
- A music discovery Discord (RateYourMusic community, /mu/ offshoot)

Give the community owner/mod a unique invite link. Promise them: *"Everyone who joins this week will match with 50+ people from your server."* That's only possible because you launched to *their* server first.

**Action:** Pick your first community *now*. Build a "community launch kit" — custom invite codes, mod dashboards, a bot that posts match highlights.

### Phase 5: Batch Signups with Waitlists

Nothing kills a social app faster than signing up, seeing zero matches, and leaving forever.

Use a waitlist + batch invites:
1. User connects Spotify, sees "You're in Batch #7 — launching March 1st"
2. You collect 100 people per batch
3. On launch day, 100 people hit the app simultaneously
4. Everyone sees matches immediately

This also creates urgency and FOMO. Discord used this effectively in early days.

**Action:** Add a `/join` page with email capture. Group signups into batches of 50–100. Email them all on the same day.

### Phase 6: The Discord Bridge Strategy

Since you already reveal Discord handles, **lean all the way into Discord as your distribution channel.**

Build a Discord bot that:
- Lets users import their SyncUp taste card into their server profile
- Shows "server compatibility" (which members have highest taste overlap)
- Posts weekly "vibe highlights" ("This week, @user and @user discovered they both love ___")

Server mods will install this because it increases engagement. Users will sign up for SyncUp because it gives them status in their favorite server.

**Action:** Build a Discord bot after the web MVP. It's your highest-ROI distribution channel.

### 90-Day Cold Start Timeline

| Week | Focus | Why |
|------|-------|-----|
| 1–2 | Polish `/me/taste` into a shareable card | Product is valuable without matches |
| 3 | Implement heuristic matcher + lower matchability threshold | 3 manual obsessions = instant matchable |
| 4 | Generate 10 taste archetypes from public data | Show users what matching means |
| 5–6 | Pick 1 community, launch batch of 50 | Controlled density |
| 7–8 | Iterate on match quality from first batch | Real feedback loop |
| 9–12 | Batch 2–3, start Discord bot spec | Expand distribution |

---

## Services to Add

### Consensus Top Tier (Both reviewers agree)

| Priority | Service | Signal Quality | Why |
|----------|---------|----------------|-----|
| 1 | **Letterboxd** | Very High | Film taste is one of the richest personality signals available. Letterboxd users are *specific* about their ratings. The Letterboxd/Steam/music correlation space is extremely interesting. This should be in the MVP. |
| 2 | **AniList (or MyAnimeList)** | Very High | Anime taste correlates extremely strongly with game and music taste in non-obvious ways. If someone's top anime are *Texhnolyze* and *Serial Experiments Lain*, you can predict a lot about their other tastes. AniList has a better API than MAL. |
| 3 | **RateYourMusic** | Very High | The deepest music nerd database on the internet. If someone actively rates music on RYM rather than just passively streaming Spotify, that's a strong signal in itself, and their ratings are extremely fine-grained. |
| 4 | **Apple Music / YouTube Music** | High | You're currently Spotify-only. That cuts out a huge chunk of Android/non-US users. |

### Second Tier (Worth adding after core four)

| Priority | Service | Signal Quality | Why |
|----------|---------|----------------|-----|
| 5 | **Trakt.tv** | High | TV show tracking — think Letterboxd for TV. Useful for rounding out the visual media dimension. |
| 6 | **Bandcamp** | High | Spotify tells you *what* someone listens to. Bandcamp tells you *how* they discover music — supports indie artists, dives into labels, follows scenes. Very different signal. |
| 7 | **StoryGraph** | Medium-High | Goodreads users are one tribe; StoryGraph users are a different tribe (more diverse, anti-Amazon, data-driven about moods/themes). |
| 8 | **itch.io** | Medium-High | Steam captures mainstream/AAA gaming. itch.io captures the indie/experimental/weird game scene — a completely different cultural tribe. |
| 9 | **Reddit** (subreddit subscriptions) | Very High | Raw, unfiltered vibe data. Someone subscribed to r/brokenbonds, r/deathgrips, and r/dwarffortress is telling you exactly who they are. Hard to get via API, but the signal is unmatched. |

### Third Tier (Nice to have)

| Service | Notes |
|---------|-------|
| **SoundCloud** | Good for specific subcultures (SoundCloud rap, hyperpop, DJ mixes), but overlaps heavily with Spotify. |
| **Twitch** (followed channels) | Strong signal for gaming/live culture overlap, but harder to extract meaningful embeddings from. |
| **Strava** | For the outdoors/athletic crowd. "We both run 40km/week and listen to Drain while doing it" is a real match. |
| **Pinterest** | Aesthetic boards are pure vibe, but the API is restricted and the user base skews differently. |
| **Mastodon / Bluesky** | Following graph is interesting, but small user base and high privacy sensitivity. |
| **Goodreads** | Book taste adds depth, though it correlates less cleanly with games/music than film does. StoryGraph is probably the better choice. |
| **Netflix / streaming history** | Hard to access via API. Would be valuable if possible. |

### Recommended MVP Set

**Steam + Spotify/Last.fm + Letterboxd + AniList**

Four dimensions, genuinely interesting correlations, all with accessible APIs and engaged user bases. Someone whose profile spans all four of those tells you a lot about who they are.

Add Apple Music/YouTube Music for coverage. Add RateYourMusic once you have music nerds asking for deeper signals.

---

## Taste Card & Discovery Engine

A major unlock for cold-start value: make `/me/taste` a **shareable artifact + recommendation engine**, not just a data dump.

### The Shareable Taste Card

After onboarding (or after connecting a service / adding 3 manual obsessions), generate a visual taste card the user actually wants to share:

```
Your SyncUp Vibe
🎮 70% Immersive Sims    🎵 30% Post-Punk
Top: Disco Elysium, Arca, Factorio
Archetype: The Immersive Indie

[Share to Twitter/X]  [Discover More]
```

This is the **primary product** during the cold-start phase. Matching is the bonus that comes later. The card should be beautiful enough that people post it unprompted — every share is an organic ad targeting exactly your demographic.

Key insight from the user: *"the product is even more valuable"* when the taste card gives you something back immediately, not just a mirror of what you already know.

### The "People Like You Also Like" Recommendation Layer

The taste card isn't just a summary — it's a **discovery engine**. Based on the user's taste profile (connected services + manual obsessions), surface things they haven't tried yet:

**The concept:** *"What do people with a similar vibe/archetype like that you didn't try yet?"*

**How it works (phased):**

| Phase | Approach | What it needs |
|-------|----------|---------------|
| **Now** | Service-native similarity APIs | Last.fm `artist.getSimilar`, Steam tag overlap, Spotify recommendations API. No trained model required. |
| **Soon** | Item-to-item via Item2Vec | A trained model on public datasets. For each of user's top items, find nearest neighbors in embedding space, filter out what they already have. |
| **Later** | Archetype-based collaborative | Cluster users by taste similarity. Recommend items that are popular in the cluster but missing from the target user. Requires ~500+ active users. |

**Example recommendations:**

```
Because you love Disco Elysium (85h played)
→ Try: Kentucky Route Zero
   Reason: 89% of players who loved Disco Elysium rate this 5 stars

Because you listen to Arca
→ Try: Have a Nice Life
   Reason: Heavy rotation in similar taste profiles

Because you added Stalker as an obsession
→ Try: Solaris (book), Annihilation (film)
   Reason: People into atmospheric sci-fi consistently pair these
```

The recommendation layer makes the product feel **alive** even when there are zero other users to match with. It also trains the user to trust the taste engine before they ever see a human match.

### Archetypes as Content

Auto-generate a vibe label from the user's top items' metadata:

| Detected Signals | Archetype Label | Description |
|------------------|-----------------|-------------|
| Story Rich + Atmospheric games + post-punk/experimental music | The Immersive Indie | "Narrative-driven, mood-first, probably cries at pixel art" |
| Competitive FPS + Drum & Bass + high APM games | The Tryhard | "Ranked grinding at 2am, energy drink optional" |
| JRPGs + symphonic metal + 100%+ completionists | The Completionist | "200 hours minimum, reads every lore entry" |
| Walking sims + ambient music + Letterboxd obsessives | The Aesthetic Seeker | "Vibe over victory, screenshots over scoreboards" |

These labels are **content** — people will screenshot and share them. They also set expectations for what kind of people they'll match with.

### Taste Card API Contract (Sketch)

```
GET /api/me/taste
```

```json
{
  "archetype": {
    "label": "The Immersive Indie",
    "description": "Story-rich games, atmospheric music, cult classics"
  },
  "profile": {
    "steam": {
      "top_games": [
        {"name": "Disco Elysium", "hours": 85, "genre": "RPG"}
      ]
    },
    "spotify": {
      "top_artists": [
        {"name": "Arca", "genres": ["electronic", "experimental"]}
      ]
    },
    "manual_obsessions": [
      {"category": "film", "name": "Stalker", "weight": 2.0}
    ]
  },
  "recommendations": {
    "steam": [
      {"name": "Kentucky Route Zero", "reason": "Liked by Disco Elysium fans"}
    ],
    "music": [
      {"name": "Have a Nice Life", "reason": "Similar taste profiles"}
    ]
  }
}
```

### Why This Solves Cold Start

- **Immediate value:** User gets something cool within 60 seconds of onboarding
- **Viral loop:** Shareable cards bring in similar people organically
- **Trust building:** Good recommendations prove the taste engine works before human matching launches
- **Data flywheel:** Every user who connects services improves the recommendation quality for the next user

---

## Key Principles to Remember

1. **The cold start is a product and distribution problem, not a technical one.** Better embeddings don't help if no one is on the platform. Give people value before the network exists.

2. **Go deep, not broad.** Don't target "music fans." Target "people who rate albums on RateYourMusic and have Letterboxd diaries." They'll bring their friends.

3. **Manual obsessions are your secret weapon.** They let users be matchable in 60 seconds with zero API friction. Lead with them.

4. **The moat is thin until the model works.** Public datasets bootstrap item embeddings, but user-user co-occurrence is what makes matching magical. Plan to transition from heuristics to learned embeddings at ~1,000 active users.

5. **Discord is your distribution channel, not just a chat integration.** The bot strategy could drive more signups than any ad spend.

---

*Last updated: 2026-04-26*
