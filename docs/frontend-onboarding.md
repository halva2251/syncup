# Frontend Onboarding Wizard

Detailed documentation for the SyncUp onboarding flow implemented in `frontend/app/(app)/onboarding`.

---

## Overview

The onboarding wizard collects the minimum taste signal needed before a user can enable matching:

1. **Languages** — spoken languages for matching filters.
2. **Services** — OAuth or CSV connections to platforms where taste lives.
3. **Obsessions** — freeform manual obsessions when no service data exists.
4. **Taste preview** — review the generated taste card and enable matching.

The stepper shows four steps: **Languages → Services → Obsessions → Taste**. The legacy `/onboarding/matchable` route redirects to `/onboarding/taste`; enabling `is_matchable` is the final CTA on the taste preview page.

---

## Routes

| Route | File | Purpose |
|-------|------|---------|
| `/onboarding` | `app/(app)/onboarding/page.tsx` | Redirects to `/onboarding/profile`. |
| `/onboarding/profile` | `app/(app)/onboarding/profile/page.tsx` | Languages step. |
| `/onboarding/services` | `app/(app)/onboarding/services/page.tsx` | Connect services step. |
| `/onboarding/obsessions` | `app/(app)/onboarding/obsessions/page.tsx` | Manual obsessions step. |
| `/onboarding/taste` | `app/(app)/onboarding/taste/page.tsx` | Taste card preview + enable matching. |
| `/onboarding/matchable` | `app/(app)/onboarding/matchable/page.tsx` | Redirects to `/onboarding/taste`. |

All routes are wrapped by `app/(app)/onboarding/layout.tsx`, which renders `OnboardingStepper` above the step content.

---

## Shared Components

### `OnboardingStep`

`components/onboarding/onboarding-step.tsx`

Shell for each step: title, description, icon, content area, and bottom actions via `OnboardingActions`. It is a Client Component because steps may contain interactive forms.

Props:

| Prop | Description |
|------|-------------|
| `icon` | Lucide icon rendered in an `AppIcon`. |
| `title` | Step heading. |
| `description` | Short explanation under the title. |
| `children` | Step form/content. |
| `backHref` / `backLabel` | Optional back link. |
| `continueHref` | Renders a glossy link button. |
| `continueButton` | Renders a glossy submit button; supports `loading` for spinner replacement. |

### `OnboardingActions`

`components/onboarding/onboarding-actions.tsx`

Renders the bottom button bar. If `continueButton` is provided it uses `GlossyButton`; if `continueHref` is provided it uses `GlossyButtonLink`. Passes the `loading` prop through to `GlossyButton` so the spinner replaces the label while keeping button width.

### `OnboardingStepper`

`components/onboarding/stepper.tsx`

Displays four pills: Languages, Services, Obsessions, Taste. Highlights the current step and marks previous steps complete. Uses `usePathname`.

---

## Steps

### 1. Profile / Languages

**Page:** `app/(app)/onboarding/profile/page.tsx`  
**Form:** `components/onboarding/profile-step-form.tsx`  
**Action:** `lib/actions/profile-actions.ts`

- Fetches current user and onboarding status.
- Renders `LanguageSelect` with the user’s existing languages.
- On submit, calls `updateProfile({ languages })` and redirects to `/onboarding/services`.

### 2. Services

**Page:** `app/(app)/onboarding/services/page.tsx`  
**Form:** `components/onboarding/services-step-form.tsx`  
**Actions:** `lib/actions/connection-actions.ts`

- Renders a grid of service cards from `lib/constants/services.ts`.
- Each card shows the service brand icon, name, description, and connection status.
- Supports OAuth links, username inputs (Steam / Last.fm), and CSV uploads (Letterboxd / RateYourMusic).
- Polls `GET /api/me` every 2 seconds while any connection is `pending` or `syncing`.
- Back link goes to `/onboarding/profile`; Continue link goes to `/onboarding/obsessions`.

### 3. Obsessions

**Page:** `app/(app)/onboarding/obsessions/page.tsx`  
**Form:** `components/onboarding/obsessions-step-form.tsx`  
**Actions:** `lib/actions/obsession-actions.ts`

- Lists existing `manual_obsessions` as removable chips.
- Add new obsessions via category select (`AccordionSelect`) + autocomplete (`Autocomplete`).
- Uses optimistic UI for deletes.
- Back link goes to `/onboarding/services`; Continue link goes to `/onboarding/taste`.

### 4. Taste Preview

**Page:** `app/(app)/onboarding/taste/page.tsx`  
**Form:** `components/onboarding/taste-review-step.tsx`  
**Action:** `lib/actions/taste-actions.ts`

- Fetches current user, onboarding status, and taste profile (`GET /api/me/taste`).
- Renders `TasteCard` with the user’s archetype, vibe summary, service carousel, obsessions, and overrides.
- Submit calls `enableMatchingAction()`, which patches `is_matchable: true` and redirects to `/home`.
- Back link goes to `/onboarding/obsessions`.

---

## Taste Card Components

### `TasteCard`

`components/taste/taste-card.tsx`

Reusable summary of a user’s taste. Sections:

- **Archetype / vibe header** — shown when the backend returns an archetype or vibe summary.
- **Service carousel** — `TasteServiceCarousel` rendering one connected service at a time.
- **Obsessions** — chips with category icons.
- **Preference overrides** — list of boosted/demoted items.
- **Empty state** — dashed card prompting the user to connect a service or add obsessions.

### `TasteServiceCarousel`

`components/taste/taste-service-carousel.tsx`

Client carousel for service sections:

- Auto-advances every 10 seconds.
- Pauses on hover.
- Slides move left/right inside a fixed border card.
- Bottom-right controls: service brand icons (current in color, others muted/grayscale), prev/next arrows.
- Each slide uses `TasteServiceSection bordered={false}`.

### `TasteServiceSection`

`components/taste/taste-service-section.tsx`

Renders one service’s data:

- Service brand icon + name header.
- One or two columns of item buckets (`top_games`, `top_artists`, etc.).
- Single-bucket services use full width; multi-bucket services use `sm:grid-cols-2`.
- `bordered` prop controls whether the outer card border is rendered.

### `TasteItemList`

`components/taste/taste-item-list.tsx`

Compact ranked list of up to 5 items per bucket. Supports:

- `rankMode="index"` — default; shows 1–5.
- `rankMode="rating"` — shows the item’s `rating` (used for RYM).
- `rankMode="score"` — shows the normalized `score`.
- `getLabel` — custom label formatter; used for `Album - Artist` on RYM and tracks.

---

## Data Fetching & Guards

Each onboarding page follows this pattern:

```tsx
export default async function OnboardingXPage() {
  let user;
  let status;
  // ...other data

  try {
    const me = await getCurrentUser();
    user = me.user;
    status = await getOnboardingStatus();
    // ...other fetches
  } catch {
    redirect("/login");
  }

  if (status.next_step === null) {
    redirect("/home");
  }

  return <StepForm ... />;
}
```

- Unauthenticated users are redirected to `/login`.
- Fully onboarded users (`next_step === null`) are redirected to `/home`.
- Data is fetched in Server Components; mutations use React Server Actions.

---

## Enabling Matching

The final action is `enableMatchingAction()` in `lib/actions/taste-actions.ts`:

```ts
await updateProfile({ is_matchable: true });
redirect("/home");
```

On success the user lands on `/home`. On error the action returns `{ error: string }`, which `TasteReviewStep` displays via `ErrorMessage`.

---

## Related Files

| File | Role |
|------|------|
| `app/(app)/onboarding/layout.tsx` | Stepper layout. |
| `components/onboarding/stepper.tsx` | Progress indicator. |
| `components/onboarding/onboarding-step.tsx` | Step card shell. |
| `components/onboarding/onboarding-actions.tsx` | Bottom action buttons. |
| `components/onboarding/profile-step-form.tsx` | Languages form. |
| `components/onboarding/services-step-form.tsx` | Service connection grid. |
| `components/onboarding/obsessions-step-form.tsx` | Obsessions form. |
| `components/onboarding/taste-review-step.tsx` | Taste preview + match enable. |
| `components/taste/taste-card.tsx` | Reusable taste card. |
| `components/taste/taste-service-carousel.tsx` | Service carousel. |
| `components/taste/taste-service-section.tsx` | Single service section. |
| `components/taste/taste-item-list.tsx` | Compact item list. |
| `lib/api/taste.ts` | `getTasteProfile()`. |
| `lib/actions/taste-actions.ts` | `enableMatchingAction()`. |
| `lib/constants/services.ts` | Service metadata. |
| `lib/constants/category-icons.ts` | Category → Lucide icon mapping. |
| `types/api.ts` | `TasteResponse`, `TasteItem`, etc. |

---

*Last updated: 2026-06-13*
