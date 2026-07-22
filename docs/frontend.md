# SyncUp Frontend Documentation

A living guide for the SyncUp Next.js frontend. Covers the current scaffold state, design system, page plan, API integration patterns, and conventions for anyone continuing the build.

---

## Current Status

The frontend is actively built out on top of the Phase 2 backend (semantic matching, recommendations, and vibe synthesis). It follows the shared design system and keeps the profile, taste controls, and discovery experiences in the authenticated app shell.

| Area | Status |
|------|--------|
| Project setup | ✅ Next.js 16.2.7 + React 19 + TypeScript + Tailwind CSS v4 |
| Design system | ✅ `DESIGN.md` at repo root |
| Typeface | ✅ DM Sans loaded in `frontend/app/layout.tsx` |
| App-style icons | ✅ `AppIcon` utility in `frontend/components/ui/app-icon.tsx` |
| Shared UI primitives | ✅ Cards, controls, page headers, avatars, AppIcon, feedback states |
| Auth / login / signup | ✅ Built |
| Onboarding | ✅ 4-step wizard built (languages, services, obsessions, taste preview) |
| Profile / taste card | ✅ Built at `/feed/[id]`; the signed-in user can preview and edit their own profile there |
| Home dashboard (`/home`) | ✅ Built |
| Matches feed | ✅ Built (`/feed` + `/feed/[id]`) |
| Recommendations | ✅ Built (filters, cross-domain cards, taste-vector empty state) |
| Settings (hub + profile/privacy/dimensions/taste/services) | ✅ Built |
| Connections (`/connections`) | ✅ Built (reuses `ServiceConnectGrid`); disconnect action live |
| Avatar upload | ✅ Built (frontend + `POST /api/me/avatar`) |

---

## Stack

| Layer | Choice |
|-------|--------|
| Framework | [Next.js](https://nextjs.org) 16.2.7 (App Router) |
| Runtime | React 19.2.4 |
| Language | TypeScript 5 |
| Styling | Tailwind CSS v4 |
| UI icons | [Lucide React](https://lucide.dev) |
| Brand icons | [Simple Icons](https://simpleicons.org) |
| Package manager | pnpm |

> **Note:** The backend runs on port `3000`. The frontend dev server should run on a different port (e.g. `3001`) to avoid conflicts.

---

## Project Structure

```
frontend/
├── app/                  # Next.js App Router pages
│   ├── (app)/            # Authenticated app shell routes
│   │   └── home/
│   │       └── page.tsx  # Currently an empty shell
│   ├── globals.css       # Tailwind entry + design tokens
│   ├── layout.tsx        # Root layout: DM Sans + metadata
│   └── page.tsx          # Redirects / → /home
├── components/           # React components (all shells except AppIcon)
│   └── ui/
│       └── app-icon.tsx  # Implemented app-style icon renderer
├── hooks/                # Custom React hooks (scaffold)
├── lib/                  # Utilities, fetch helpers, types (scaffold)
├── types/                # Shared TypeScript types (scaffold)
├── public/               # Static assets
├── next.config.ts
├── package.json
└── tsconfig.json
```

---

## Design System

All frontend work must follow the design system in [`DESIGN.md`](./DESIGN.md) at the repo root.

Highlights:

- **Aesthetic:** clean, card-based dashboard/SaaS look with rounded corners, soft borders, and generous whitespace.
- **Color:** mostly neutral surfaces; blue (`#2563EB`) is reserved for primary actions and brand. A lighter accent variant (`--color-accent-light`) is available for completed/inactive states.
- **Typography:** DM Sans, base `14px`, weights 400–700.
- **Layout:** fixed `240px` left sidebar, scrollable main area with `24px–32px` padding.
- **Dark mode:** supported with inverted surface colors and a slightly brighter accent.
- **Icons:** Lucide for UI, `AppIcon` for feature/service/brand icons.

Root `AGENTS.md` enforces these rules for automated agents.

---

## Implemented Primitive: `AppIcon`

`frontend/components/ui/app-icon.tsx` renders polished, app-style icons for feature cards, service tiles, and brand markers.

### Features

- Rounded-square container with a top-light → bottom-dark gradient background.
- Inner raised bezel / gradient border.
- Optional glossy highlight overlay.
- SVG gradient fill/stroke for the icon itself.
- Scales from `xs` (`32px`) to `4xl` (`160px`); border width scales with size.
- Works with both Lucide icons and Simple Icons brand objects.
- Implemented as a **Server Component** so it can accept React component props.

### Usage

```tsx
import { ShieldCheck, Home } from "lucide-react";
import { siSpotify, siSteam, siLetterboxd } from "simple-icons";
import { AppIcon } from "@/components/ui/app-icon";

// Lucide icon
<AppIcon icon={ShieldCheck} size="lg" gradient="blue" />

// Simple Icons brand
<AppIcon brand={siSpotify} size="md" gradient="brand" />
```

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `icon` | `LucideIcon` | — | Lucide icon component (mutually exclusive with `brand`). |
| `brand` | `SimpleIcon` | — | Simple Icons object (`{ title, path }`) (mutually exclusive with `icon`). |
| `size` | `"xs" \| "sm" \| "md" \| "lg" \| "xl" \| "2xl" \| "3xl" \| "4xl"` | `"md"` | Container size. |
| `gradient` | `"blue" \| "purple" \| "green" \| "orange" \| "red" \| "brand"` | `"blue"` | Background gradient key. |
| `iconSize` | `number` | Derived from `size` | Override the inner glyph size without changing the container; useful for compact tag icons. |
| `glossy` | `boolean` | `true` | Render the glossy highlight. |
| `className` | `string` | — | Additional Tailwind classes. |

### Suggested service-to-gradient mapping

| Service | Gradient | Brand icon |
|---------|----------|------------|
| Steam | `blue` | `siSteam` |
| Spotify | `green` | `siSpotify` |
| Last.fm | `red` | — (use Lucide `AudioLines` or similar) |
| Letterboxd | `orange` | `siLetterboxd` |
| AniList | `purple` | — (use Lucide `Tv` or similar) |
| Trakt | `red` | — (use Lucide `Clapperboard` or similar) |
| Reddit | `orange` | — (use Lucide `MessageCircle` or similar) |
| RateYourMusic | `purple` | — (use Lucide `Disc` or similar) |

---

## Implemented Component: `ServiceConnectGrid`

`frontend/components/connections/service-connect-grid.tsx` renders the full service-connection grid (OAuth, API-key, and CSV flows) plus live sync polling. It was extracted from the onboarding step so both `/onboarding/services` and `/connections` can share the same UI.

### Props

| Prop | Type | Description |
|------|------|-------------|
| `initialConnections` | `ServiceConnection[]` | Connections seeded from `GET /api/me` (server-fetched and passed in). |
| `onActivity?` | `(serviceId: string) => void` | Optional callback fired when a connect/sync/import cycle starts. |
| `className?` | `string` | Extra classes on the grid container. |

> **Note on disconnect:** `DELETE /api/me/connections/{service}` is live and exposed as a confirmed disconnect action on `/connections` and the signed-in user's profile.

---

## Shared UI Primitives

Small reusable building blocks used across pages. Prefer these over re-rolling the same markup.

### `PageHeader`

`frontend/components/ui/page-header.tsx` — the standard page header (`AppIcon` + title + description, with an optional right-aligned `actions` slot). Used by `/home`, `/settings`, `/feed`, and `/connections`. Server Component.

| Prop | Type | Description |
|------|------|-------------|
| `icon` | `LucideIcon` | Icon rendered in an `AppIcon` tile next to the title. |
| `title` | `string` | Page title (`24px` semibold). |
| `description?` | `string` | Subtitle in `--text-secondary`. |
| `actions?` | `ReactNode` | Optional right-aligned slot (buttons/links). |

### `StatCard`

`frontend/components/ui/stat-card.tsx` — compact stat tile (`AppIcon` + label + value + hint) for dashboard overview rows per the DESIGN.md "Dashboard / Home" pattern. Server Component.

| Prop | Type | Description |
|------|------|-------------|
| `icon` | `LucideIcon` | Lucide icon passed to `AppIcon`. |
| `gradient?` | `AppIconGradient` | `AppIcon` gradient key (default `"blue"`). |
| `label` | `string` | Uppercase label above the value. |
| `value` | `ReactNode` | Prominent stat value. |
| `hint?` | `ReactNode` | Muted hint below the value. |

> `AppIconGradient` is exported from `components/ui/app-icon.tsx` so pages no longer need to redefine the gradient union locally.

### `Avatar`

`frontend/components/ui/avatar.tsx` — circular avatar with a `UserRound` fallback when no `src` is given. Renders a plain `<img>` (no remote-image domain config needed), matching the existing profile-form pattern. Server Component.

| Prop | Type | Description |
|------|------|-------------|
| `src?` | `string \| null` | Avatar image URL. Falls back to the icon when absent. |
| `alt` | `string` | Alt text (used for both `<img>` and fallback). |
| `size?` | `"sm" \| "md" \| "lg" \| "xl"` | Container size (default `"md"`). |
| `className?` | `string` | Extra classes. |

### Feed components (`components/matches/*`)

Used by `/feed` and `/feed/[id]`:

| Component | File | Description |
|-----------|------|-------------|
| `MatchCard` | `match-card.tsx` | One feed entry: avatar, name, score pill, highlights, mode tag. Links to `/feed/[id]`. |
| `MatchList` | `match-list.tsx` | **Client.** Cursor-paginated feed ("Load more") with cache-miss auto-polling and loading/empty states. |
| `MatchDetail` | `match-detail.tsx` | Full match profile: identity header, compatibility bar, per-service breakdown, shared highlights, Discord handle. |
| `MatchScore` | `match-score.tsx` | Reusable compatibility display. `variant="compact"` (pill) for cards, `"detail"` (bar) for detail. |
| `MatchHighlights` | `match-highlights.tsx` | Shared-taste highlight chips with service brand icons. `compact` (truncated) vs. `detail` (full). |

---

## Page Plan

The frontend implements the routes defined in GitHub issue #21 ("DESIGN: frontend").

> **Route prefix note:** the routes below are documented as `/me/...` for parity with the backend (`/api/me/...`), but the **actual frontend URLs drop the `/me` prefix** — e.g. `/settings`, `/connections`, `/recommendations`. The onboarding flow lives at `/onboarding/...`.

### Auth pages

Routes: `/login` and `/signup`.

Design specifics:

- **Logo:** `AppIcon` with `Sparkles` icon + "SyncUp" wordmark, centered above the card.
- **Card background:** `#FAFAFA` (`--color-bg-auth-card`) — a warm off-white that separates the form from the `#F9FAFB` page background.
- **Card shape:** `rounded-2xl`, border `var(--color-border)`, soft shadow.
- **Title:** `28px` semibold, tight tracking.
- **Subtitle:** `15px`, `--text-secondary`.
- **Inputs:** `42px` height, `15px` label with medium weight, `8px` rounded corners, accent focus ring.
- **Primary CTA:** full-width button.
- **Footer link:** centered, accent color.

Both pages use Server Actions (`lib/auth.ts`) that call the backend, forward the `syncup_session` cookie, and redirect on success.

**Client-side validation:**
- Email: required, validated against a simple email regex. Shows a red `X` (Lucide) when invalid and a green checkmark when valid.
- Password (signup): minimum 8 characters, maximum 128. Shows a red `X` while below 8 characters and a green checkmark once valid.
- Display name (signup): required, max 100 characters.
- Validation icons render inside the input field on the right side.

### Public routes

| Route | Purpose |
|-------|---------|
| `/login` | Email + password login. |
| `/signup` | Create account; redirect to `/onboarding` on success. |
| `/how-it-works` | Static algorithm explainer + demo archetypes. |
| `/join` | Waitlist email capture. |
| `/users/[id]/taste-card` | Public shareable taste card (data from `GET /api/users/{id}/taste-card`). |

### Authenticated routes

| Route | Purpose | Key endpoints |
|-------|---------|---------------|
| `/onboarding` | 4-step wizard: languages → connect services → manual obsessions → taste card preview. Display name is collected at `/signup`. | `GET /api/onboarding/status`, `POST /api/me/obsessions`, `PATCH /api/me` |
| `/home` | Dashboard landing after onboarding. Stat overview (services, taste items, obsessions, matching status), vibe summary, quick links, connected-services status, and recommendations teaser. | `GET /api/me`, `GET /api/me/taste` |
| `/me/connections` | Service grid, sync status, OAuth + CSV upload flows. | `GET /api/me`, `POST /api/sync/{service}`, connect endpoints |
| `/me/settings` | Hub linking to the settings sub-pages. | `GET /api/me` |
| `/me/settings/profile` | Profile editor: display name, bio, Discord, avatar photo upload, and languages. Connected services with public profiles are linked automatically. | `PATCH /api/me`, `POST /api/me/avatar` |
| `/me/settings/privacy` | Discoverable-matching toggle. | `PATCH /api/me` |
| `/me/settings/taste` | Preference overrides editor (boost/dampen specific items). | `GET/POST/PATCH/DELETE /api/me/overrides` |
| `/me/settings/dimensions` | Per-service taste weight sliders. | `GET /api/me`, `GET /api/me/dimensions`, `PATCH /api/me/dimensions` |
| `/me/settings/services` | Sync-status readout for connected services; links to `/connections` for connect/sync flows. | `GET /api/me` |
| `/me/recommendations` | Cross-domain recommendations with item-type filters. | `GET /api/me/recommendations` |
| `/feed` | Discovery feed: scrollable list of matched users ranked by compatibility (not swipe). Includes a "Refresh matches" action. | `GET /api/matches`, `POST /api/me/recompute` |
| `/feed/[id]` | A user's profile. Other profiles show compatibility, shared taste, public taste card, and social/service links. Your own profile adds preview/edit modes for services, obsessions, and taste controls. | `GET /api/matches/{id}`, `GET /api/users/{id}/taste-card`, `GET /api/me/taste` |

> **Build order recommendation:** login/signup → onboarding → `/me/connections` → `/feed` → recommendations/settings/dimensions.

---

## Backend API Integration

### Base URL

The backend is assumed to run at `http://127.0.0.1:3000` in development. All backend routes are prefixed with `/api`, so the frontend proxies or calls `http://127.0.0.1:3000/api/...`.

> **Cookie note:** Auth uses the `syncup_session` cookie set by `/api/auth/login` and `/api/auth/signup`. Requests to the backend must include credentials (`fetch(..., { credentials: "include" })`) so the session cookie is sent.

### Error shape

All backend errors follow:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "..."
  }
}
```

Validation errors (422) also include `details`:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": [...]
  }
}
```

### Key endpoints summary

See [`api-contract.md`](./api-contract.md) for the full spec. Relevant frontend endpoints:

- `POST /api/auth/signup`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/me`
- `PATCH /api/me`
- `GET /api/onboarding/status`
- `GET /api/me/taste`
- `GET /api/me/recommendations`
- `GET /api/matches/summary`
- `GET /api/matches`
- `GET /api/matches/{user_id}`
- `POST /api/me/recompute`
- `GET /api/me/dimensions`
- `PATCH /api/me/dimensions`
- `GET/POST/DELETE /api/me/obsessions`
- `GET/POST/PATCH/DELETE /api/me/overrides`
- `PATCH /api/me/items/{item_id}`
- `POST /api/sync/{service}`
- Service-specific connect endpoints (OAuth redirects + CSV uploads)

### Proxy strategy

In production, route `/api/*` requests through Next.js rewrites to the backend to avoid CORS. During local development you can either:

1. Run the frontend on a different port and call the backend directly with `credentials: "include"` (backend CORS must allow `http://localhost:3001`).
2. Use a Next.js rewrite in `next.config.ts`:

```ts
async rewrites() {
  return [
    {
      source: "/api/:path*",
      destination: "http://127.0.0.1:3000/api/:path*",
    },
  ];
}
```

---

## State & Data Fetching Conventions

- Prefer **Server Components** by default.
- Fetch session-gated data in Server Components with `{ credentials: "include" }` (or rely on the proxy rewrite keeping cookies).
- Use **React Server Actions** for mutations (login, signup, form submissions) so cookies flow naturally.
- Keep Client Components small and localized (e.g. sliders, dropdowns, copy-to-clipboard).
- Use `useId()` when generating unique SVG gradient IDs (already done in `AppIcon`).

---

## Onboarding Flow

The onboarding wizard is documented in detail in [`docs/frontend-onboarding.md`](./frontend-onboarding.md). The summary below describes the user flow; the dedicated doc covers the component architecture, data fetching, and carousel behavior.

From `docs/roadmap.md` / `api-contract.md`:

1. **Display name** — set at signup; `GET /api/onboarding/status` reports `has_display_name`.
2. **Languages** — optional languages via a searchable multi-select with ~70 real languages, each shown with a country flag via `flag-icons` (fake/made-up codes rejected by backend).
3. **Connect services** — OAuth or CSV upload to pull real library data. The page shows a tile per service (Spotify, Steam, Last.fm, Letterboxd, AniList, Trakt, Reddit, RateYourMusic) with status, username forms, CSV imports, and OAuth links. Skippable.
4. **Obsessions** — freeform things the user is obsessed with (games, albums, books, etc.). Each gets a category and is stored as a `manual_obsession`. ≥ 3 satisfies the `has_connection_or_obsessions` gate.
5. **Taste card preview** — call `GET /api/me/taste`, render the `TasteCard` component, let the user review, then `PATCH /api/me { is_matchable: true }`.

The frontend stepper shows four steps: **Languages → Services → Obsessions → Taste**. The old `/onboarding/matchable` route now redirects to `/onboarding/taste`; enabling matchability is the primary CTA on the taste preview page.

`next_step` progression from the backend:

```
"set_display_name" → "connect_service" → "set_matchable" → null (fully onboarded)
```

---

## Service Connection UX

### OAuth services

Spotify, AniList, Trakt, Reddit.

- Link/button opens `/api/connect/{service}/oauth/start` in the same tab.
- Backend redirects to the provider; user authorizes.
- Callback returns to `/` (or a frontend route) and sets `service_connections.sync_status = "pending"`.
- Frontend polls `GET /api/me` until `sync_status` is `"ok"` or `"error"`.
- `POST /api/sync/{service}` triggers a fresh background pull.

### API-key services

Steam, Last.fm.

- User enters Steam ID / vanity URL or Last.fm username.
- Frontend `POST /api/connect/steam` or `POST /api/connect/lastfm`.
- Connection row is created with `sync_status = "ok"`.
- `POST /api/sync/{service}` pulls data.

### CSV services

Letterboxd, RateYourMusic.

- Show an inline export guide (see [`export-guide.md`](./export-guide.md)).
- File input accepts `.csv`.
- `POST /api/connect/letterboxd/import` or `POST /api/connect/rateyourmusic/import` as `multipart/form-data`.
- Returns `{ imported: N }` on success.

---

## Taste Card Design Notes

The taste card is the **primary product during cold start** (see [`product-strategy.md`](./product-strategy.md)). The reusable `TasteCard` component is used by onboarding and by `/feed/[id]`; there is no separate `/taste` route.

Current behavior:

- Show the user's archetype label and vibe summary (if LLM key is configured).
- Display top items per connected service in a carousel (`TasteServiceCarousel`):
  - Auto-advances every 10 seconds; pauses on hover.
  - Service icons act as dot-style controls (current in color, others muted).
  - Prev/next arrow controls at the bottom right.
  - Slides move left/right inside a fixed border card.
  - Each bucket shows up to 5 items.
  - Single-bucket services use the full card width; multi-bucket services use two columns.
  - RYM albums render as `Album - Artist` and show the raw CSV rating instead of a rank number.
- Show manual obsessions and preference overrides below the carousel.
- Include an empty state when no taste data exists.

The signed-in user's profile includes a copy-link action and an edit mode. Edit mode exposes service management, item exclusions, manual obsessions, and a link to the taste controls settings page.

---

## Feed Design Notes

The discovery feed lives at `/feed` (formerly `/matches`). It is a scrollable card list, **not** a swipe interface (MVP decision).

- Each `MatchCard`: avatar, display name, compatibility score pill, shared-highlight chips, matching-mode tag.
- Clicking a card opens `/feed/[id]` and reveals the Discord handle immediately (MVP decision).
- `MatchList` (client) handles cursor pagination via "Load more", plus auto-polling when the match cache is being rebuilt after a cache miss.
- A "Refresh matches" action calls `POST /api/me/recompute` (rate-limited to 1/hour server-side).
- `matching_mode` field shows `"heuristic"` (taste overlap) or `"semantic"` (embedding-based).
- `/feed/[id]` detail shows the compatibility score bar, per-service breakdown bars, shared highlights, Discord handle, and the public taste card.
- A viewer's own `/feed/[id]` profile has preview and edit modes. The preview represents the public profile; the edit surface enables service, obsession, and item-control management.
- The profile's **Links & social** section uses Simple Icons and service-color gradients. In profile edit mode, users can add GitHub, X, Instagram, TikTok, YouTube, Twitch, Bluesky, Mastodon, or SoundCloud by choosing a platform and entering a username. Last.fm, Steam, Spotify, AniList, Trakt, and Reddit links appear automatically when those services are connected.

---

## Recommendations Design Notes

The authenticated `/recommendations` page uses `GET /api/me/recommendations` to surface cross-domain suggestions: games informed by music, films informed by games, and similar combinations.

- Filter chips cover every supported `item_type`, with a default cross-domain "Everything" view.
- Recommendation cards show the service marker, item type, and similarity percentage.
- `NO_EMBEDDING_AVAILABLE` renders a focused empty state with a "Build taste vector" action. It calls the existing recompute workflow and refreshes the page after the background job has started.
- A normal empty result explains that the shared catalog may not yet contain a fresh recommendation and invites the user to try another category later.

---

## Development Workflow

```bash
cd frontend
pnpm install       # if not already done
pnpm dev           # starts on localhost:3000 by default
```

> **Port conflict:** the backend already uses `3000`. Run the frontend on a different port, e.g. `pnpm dev -- -p 3001` or set `PORT=3001`.

### Type checking

```bash
cd frontend
npx tsc --noEmit
```

Run this after any TypeScript or component change.

### Linting

```bash
cd frontend
pnpm lint
```

---

## Conventions

1. **No hard-coded colors.** Reference design tokens from `DESIGN.md` / `globals.css`.
2. **Use DM Sans everywhere.** Already applied via `layout.tsx`; do not add another Google Fonts link.
3. **Prefer Server Components.** Client components are for interactivity only.
4. **Keep shells intact until implementing.** Don't add real content to a page until you're ready to build it fully.
5. **Update this doc when adding pages or changing patterns.** Stale docs mislead the next session.

---

## Open Questions / Decisions

These are documented in the project docs and should be revisited before building the related feature:

- **Match reveal flow:** show Discord handle immediately for MVP; "request to connect" deferred to V2.
- **Browse mode:** scrollable feed for MVP; swipe mode is post-launch.
- **Activity feed:** do not build until the match feed is solid.
- **Chat:** no in-app chat; matches exchange Discord handles.

---

## Related Docs

- [`DESIGN.md`](../DESIGN.md) — full design system.
- [`AGENTS.md`](../AGENTS.md) — agent-facing frontend rules.
- [`docs/api-contract.md`](./api-contract.md) — backend API spec.
- [`docs/frontend-onboarding.md`](./frontend-onboarding.md) — detailed onboarding wizard docs.
- [`docs/product-strategy.md`](./product-strategy.md) — cold-start strategy and taste-card rationale.
- [`docs/roadmap.md`](./roadmap.md) — phased build plan.
- [`docs/dev-guide.md`](./dev-guide.md) — backend internals.
- [`docs/export-guide.md`](./export-guide.md) — how users export CSVs from each service.

---

*Last updated: 2026-07-22 (feed)*
