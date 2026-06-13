# Frontend Code Review: feat/onboarding

**Branch:** feat/onboarding  
**Scope:** frontend/ directory changes relative to master  
**Date:** 2026-06-13

---

## Summary

This PR implements the onboarding taste-review step, a reusable taste card component, an autocomplete UI component, a glossy button component, and refactors onboarding step layouts into shared `OnboardingStep`/`OnboardingActions` wrappers. It also adds client-side search API support, category icons, and updates service connection types to support OAuth-or-username flows.

Overall architecture is sound: Server Components fetch data, Client Components handle interactivity, Server Actions handle mutations. Most new components are well-structured and accessible. There are several HIGH and MEDIUM issues to address before merge, primarily around hard-coded colors in the glossy button, a missing `use client` directive, a potential null-deref in category icons, and some minor accessibility and type-safety gaps.

---

## CRITICAL Issues

_None found._

---

## HIGH Issues

### 1. `GlossyButton` / `GlossyButtonLink` hard-code hex colors outside the design system

**File:** `/home/reazn/Projects/syncup/frontend/components/ui/glossy-button.tsx`  
**Lines:** 21-22, 29-37

The `shellClasses` string and `bezelStyle` object use raw hex values (`#60A5FA`, `#1D4ED8`, `#9CA3AF`) and `rgba()` literals instead of the CSS design tokens defined in `DESIGN.md` and `globals.css`.

```tsx
const shellClasses =
  "... rounded-lg bg-gradient-to-b from-[#60A5FA] to-[#1D4ED8] ...";
```

**Why this matters:** The design system mandates all colors use CSS variables for light/dark parity and maintainability. Hard-coding blue shades will look wrong in dark mode and breaks the token contract.

**Fix:** Replace with `var(--color-accent-light)` and `var(--color-accent-hover)` or similar documented tokens. If a glossy gradient is an intentional one-off visual effect, document it in `DESIGN.md` as an exception. Also replace the `#9CA3AF` in `taste-service-carousel.tsx` line 95 with `var(--color-text-tertiary)`.

---

### 2. `TasteCard` is missing the `"use client"` directive

**File:** `/home/reazn/Projects/syncup/frontend/components/taste/taste-card.tsx`  
**Line:** 1

`TasteCard` imports `lucide-react` icons and renders them as JSX components. While it does not currently use hooks or browser APIs, it is a leaf presentational component that may be composed inside client components. More importantly, if any future edit adds interactivity (e.g., hover states, click handlers), the missing directive will cause a runtime error. Given that it is already imported by `TasteReviewStep` (a client component), the file should declare itself explicitly.

**Fix:** Add `"use client";` at the top of the file.

---

### 3. `CategoryIcon` can throw at runtime if category is unknown

**File:** `/home/reazn/Projects/syncup/frontend/components/onboarding/obsessions-step-form.tsx`  
**Lines:** 52-60

```tsx
function CategoryIcon({ category, ... }) {
  const Icon = CATEGORY_ICONS[category.toLowerCase()];
  return <Icon className={className} ... />;
}
```

If `category` is not in `CATEGORY_ICONS`, `Icon` is `undefined` and React will throw a runtime error when trying to render it. The same pattern exists in `taste-card.tsx` line 57 but there it falls back to `Heart`.

**Fix:** Add a fallback:

```tsx
const Icon = CATEGORY_ICONS[category.toLowerCase()] ?? HelpCircle;
```

---

### 4. `Autocomplete` does not expose the selected suggestion value to the form

**File:** `/home/reazn/Projects/syncup/frontend/components/ui/autocomplete.tsx`  
**Lines:** 206-228

The component renders an `<input name={name} type="text" value={query} ... />`. When the user selects a suggestion, `query` is set to `suggestion.name`. However, the actual selected item's `external_id` and `service` are lost. The parent `ObsessionsStepForm` submits this to `createObsessionAction`, which presumably only receives the text name. If the backend needs to link the obsession to a canonical item, the `external_id` and `service` are unavailable.

Additionally, there is no hidden input tracking the actual selected suggestion, so free-text entries and selected suggestions are indistinguishable on the server.

**Fix:** Add a hidden input (or a second controlled input) that stores the selected `external_id` and `service` when a suggestion is chosen, and clears it when the user types freely. Alternatively, expose an `onSelect` callback so the parent can manage the selection state.

---

### 5. `OnboardingStep` wraps `children` inside a card but `ProfileStepForm` places the `<form>` outside it

**File:** `/home/reazn/Projects/syncup/frontend/components/onboarding/profile-step-form.tsx`  
**Lines:** 27-57

```tsx
<form action={formAction} className="space-y-5">
  <OnboardingStep ... continueButton={{ type: "submit" }}>
    ...
  </OnboardingStep>
</form>
```

The `OnboardingStep` renders a card `div` with `OnboardingActions` at the bottom. The `continueButton` is rendered inside that card. The `<form>` wraps the entire card, which is semantically unusual — the submit button is visually inside the card but the form scope is broader. This works functionally but is structurally odd. More importantly, the `OnboardingActions` continue button is rendered as a `GlossyButton` with `type="submit"`, which is correct, but the `OnboardingStep` card itself is not a form element.

This is not a bug, but it is an architectural inconsistency compared to `ObsessionsStepForm` where the `<form>` is inside `OnboardingStep` and the continue action is a `ButtonLink` (navigation, not submission).

**Recommendation:** Either move `<form>` inside `OnboardingStep` (and have `OnboardingStep` accept an `action` prop for Server Actions), or keep the current pattern but document it. The current approach is acceptable but slightly confusing.

---

## MEDIUM Issues

### 6. `TasteServiceCarousel` auto-advances without pause/resume for keyboard users

**File:** `/home/reazn/Projects/syncup/frontend/components/taste/taste-service-carousel.tsx`  
**Lines:** 37-42

The carousel auto-advances every 10 seconds via `setInterval`, but only pauses on mouse hover. Keyboard users who tab into the carousel or use the prev/next buttons do not get the timer paused, which can cause focus loss or unexpected content changes while reading.

**Fix:** Also pause the timer when any element inside the carousel has focus. Add a `focus`/`blur` listener or check `document.activeElement` inside the container.

---

### 7. `AccordionSelect` chip remove button changed from `<button>` to `<span role="button">`

**File:** `/home/reazn/Projects/syncup/frontend/components/ui/accordion-select.tsx`  
**Lines:** 194-211

The diff shows the remove control was changed from a `<button type="button">` to a `<span role="button" className="cursor-pointer">`. While it has `aria-label` and `role="button"`, it is no longer keyboard-focusable or activatable with Enter/Space unless additional handlers are added. This is an accessibility regression.

**Fix:** Revert to `<button type="button">` for the remove control. The same pattern exists in `language-select.tsx` (lines 84-92 in the diff).

---

### 8. `searchItems` uses `fetch` directly instead of a typed API helper

**File:** `/home/reazn/Projects/syncup/frontend/lib/api/search.ts`  
**Lines:** 15-38

The function calls `fetch("/api/items/search?...")` directly with inline type assertions. The project convention (per `CLAUDE.md`) is that client components call relative `/api/...` endpoints, which is being followed, but there is no shared error-handling pattern or retry logic. The `as` casts on `response.json()` bypass type safety.

**Fix:** This is acceptable for a thin client helper, but consider centralizing the `response.json()` parsing pattern used elsewhere. Not a blocker.

---

### 9. `TasteItemList` uses `item.id` as React key, but `id` may not be unique across buckets

**File:** `/home/reazn/Projects/syncup/frontend/components/taste/taste-item-list.tsx`  
**Line:** 58

```tsx
<li key={item.id} ...>
```

If the same item appears in multiple buckets (e.g., a track in both "top_tracks" and "top_albums"), React will warn about duplicate keys. The parent `TasteServiceSection` slices items per bucket, so duplicates within a single list are unlikely, but not guaranteed by the type system.

**Fix:** Use a composite key if available: `key={\`\${item.id}-\${index}\`}` or ensure backend IDs are globally unique.

---

### 10. `services-step-form.tsx` uses `grid-rows-subgrid` which may not be widely supported

**File:** `/home/reazn/Projects/syncup/frontend/components/onboarding/services-step-form.tsx`  
**Line:** 154

```tsx
<div className="... grid row-span-2 grid-rows-subgrid h-full ...">
```

`grid-rows-subgrid` is a CSS Grid Level 2 feature. As of mid-2026, it is supported in modern browsers but may still have edge cases in Safari or older Chromium versions. Given the project targets a modern Next.js stack, this is acceptable but worth noting.

**Fix:** No action required unless browser support matrix is broader. Add a comment if concerned.

---

### 11. `useActionState` in `TasteReviewStep` has an unnecessary async wrapper

**File:** `/home/reazn/Projects/syncup/frontend/components/onboarding/taste-review-step.tsx`  
**Lines:** 17-19

```tsx
const [state, formAction, pending] = useActionState(async () => {
  return await enableMatchingAction();
}, null);
```

The wrapper adds no value; `useActionState` accepts the action directly:

```tsx
const [state, formAction, pending] = useActionState(enableMatchingAction, null);
```

**Fix:** Simplify to pass the action reference directly.

---

### 12. `radius` tokens in `globals.css` are not referenced in `DESIGN.md`

**File:** `/home/reazn/Projects/syncup/frontend/app/globals.css`  
**Lines:** 7-14

The new radius scale (`--radius-xs` through `--radius-4xl`) is added to `@theme inline` but `DESIGN.md` still documents `rounded-xl` as `12px` and does not mention the custom radius tokens. This creates a documentation drift risk.

**Fix:** Update `DESIGN.md` to reference the new radius tokens, or remove the custom scale if it is not needed (Tailwind v4 already provides default radius utilities).

---

## LOW Issues

### 13. `OnboardingActions` uses template-string class concatenation

**File:** `/home/reazn/Projects/syncup/frontend/components/onboarding/onboarding-actions.tsx`  
**Line:** 29

```tsx
<div className={`mt-8 flex items-center gap-3 ${justifyClass}`}>
```

Prefer `cn()` / `clsx`-style utility for conditional classes, though this is a minor stylistic issue.

---

### 14. `GlossyButton` `bezelStyle` uses vendor-prefixed CSS properties that may be unnecessary in Tailwind v4

**File:** `/home/reazn/Projects/syncup/frontend/components/ui/glossy-button.tsx`  
**Lines:** 29-37

The `WebkitMask` / `WebkitMaskComposite` / `maskComposite` properties are required for the border-box gradient trick, but this is a complex CSS workaround. The same visual effect could potentially be achieved with a simpler pseudo-element or border-image approach. Given the hard-coded colors issue (HIGH #1), this component may need redesign anyway.

---

### 15. `formatSuggestionExtra` in `Autocomplete` uses `String()` on potentially non-string values

**File:** `/home/reazn/Projects/syncup/frontend/components/ui/autocomplete.tsx`  
**Lines:** 30-31

```tsx
if (extra.year) parts.push(String(extra.year));
if (extra.author) parts.push(String(extra.author));
```

The `extra` object is typed as `Record<string, unknown>`, so `extra.year` is `unknown`. The `String()` call is safe, but the type guard `if (extra.year)` is truthy-checking `unknown`, which is fine in practice. Consider narrowing the type with a helper or Zod schema if the backend contract is stable.

---

## Positive Notes

- **Server Component data fetching is correct.** `OnboardingTastePage` fetches user, status, and taste profile in parallel (well, sequentially but cleanly) and redirects appropriately.
- **Accessibility in `Autocomplete` is strong.** Proper `aria-autocomplete`, `aria-controls`, `aria-activedescendant`, `role="listbox"`, `role="option"`, keyboard navigation, and scroll-into-view for highlighted items.
- **`OnboardingStep` / `OnboardingActions` refactor reduces duplication.** All four onboarding steps now share the same card shell and navigation button pattern.
- **`useOptimistic` + `useActionState` pattern in `ObsessionsStepForm` is correct.** Optimistic deletion with rollback on error is well-implemented.
- **`TasteServiceCarousel` gracefully handles single-service and empty states.**
- **File naming follows kebab-case convention.** New files are all correctly named.

---

## Checklist Results

### Next.js / React
- [x] Server Components do not use browser APIs or hooks.
- [x] Client Components declare `"use client"` (except `TasteCard` — see HIGH #2).
- [x] Hooks called unconditionally at top level.
- [x] `useEffect` dependency arrays are correct (noted one minor simplification in MEDIUM #11).
- [x] No `use client` just for data fetching.

### TypeScript
- [x] No implicit `any` in new code.
- [ ] Component props use interfaces (yes, all new components do).
- [ ] API response types are shared (yes, `TasteResponse`, `User`, `SearchSuggestion` are in `types/api.ts`).
- [ ] `null`/`undefined` handling is explicit (mostly yes; `CategoryIcon` is an exception — see HIGH #3).

### Tailwind CSS v4 + Design System
- [ ] Colors use CSS variables (mostly yes; `GlossyButton` and `taste-service-carousel` brandColor are exceptions — see HIGH #1).
- [ ] Spacing uses 4-pt scale (yes).
- [ ] Typography uses documented type scale (yes).
- [ ] Dark mode parity (tokens are defined, but `GlossyButton` hard-coding breaks it — see HIGH #1).
- [ ] No arbitrary Tailwind values without justification (a few `w-[200px]`, `w-[42px]` exist; acceptable for fixed-size UI elements).

### Components
- [x] UI components in `components/ui/` are reusable and controlled.
- [x] Feature components compose UI primitives.
- [x] Loading, empty, and error states handled.
- [x] Components accept `className` where appropriate.

### API Integration
- [x] Server Components call `apiFetch`.
- [x] Client Components call relative `/api/...` with `credentials: "include"`.
- [x] Mutations use Server Actions.
- [x] Loading/debounced states for autocomplete (yes, 300ms debounce + `useTransition`).
- [x] Errors surfaced to user (yes, `ErrorMessage` components and inline error text).

### Forms
- [x] Forms use Server Actions via `useActionState`.
- [x] Client-side validation (Zod schemas are project convention; not visible in this diff but actions likely use them).
- [ ] Controlled vs uncontrolled: `Autocomplete` is controlled but resets via `key` prop hack in `ObsessionsStepForm` — acceptable but slightly unusual.

### Accessibility
- [x] Interactive elements are keyboard accessible (except `AccordionSelect` chip remove — see HIGH #7).
- [x] Form inputs have associated `<label>` elements.
- [x] Autocomplete uses correct ARIA roles.
- [x] Focus states are visible and match design system.
- [ ] `div`-as-button: `OAuthConnect` and `OAuthOrUsernameConnect` use `<button>` and `<a>` correctly, but the `AccordionSelect` chip remove is a regression.

### Performance
- [x] Images use `next/image` (no images in this diff).
- [x] Data fetched as high in tree as possible.
- [x] Event handlers debounced (autocomplete, 300ms).
- [x] No prop drilling through many layers.

### File / Naming Conventions
- [x] Files are kebab-case.
- [x] Components exported as named exports.
- [x] Feature folders group related components.
- [x] Custom hooks live in `frontend/hooks/` (no new hooks in this diff).

---

## Recommendations

1. **Before merge:** Fix HIGH #1 (hard-coded colors in `GlossyButton`), HIGH #2 (missing `use client`), HIGH #3 (CategoryIcon null-deref), and HIGH #7 (revert chip remove to `<button>`).
2. **After merge:** Consider MEDIUM #4 (Autocomplete hidden input for `external_id`) if the backend needs canonical item linkage.
3. **Docs:** Update `DESIGN.md` with the new radius tokens if they are staying.
