# SyncUp UI Design System

A clean, modern dashboard aesthetic inspired by the Duplicati reference screenshots. The interface should feel like a polished desktop/SaaS application: lots of white space, soft borders, rounded cards, a fixed sidebar, and a restrained blue accent palette.

---

## 1. Design Philosophy

- **Clarity first.** Every screen has one obvious job. Avoid visual noise.
- **Card-based layout.** Content lives inside rounded containers with subtle borders.
- **Restrained color.** Interface is mostly neutral; blue is reserved for primary actions, brand, and active states.
- **Consistent radius & spacing.** Rounded corners everywhere; generous internal padding.
- **Light + dark parity.** Both modes share the same layout; only the surface colors invert.

---

## 2. Color Palette

### Light mode

| Token | Hex | Usage |
|---|---|---|
| `--bg-page` | `#F9FAFB` | Main content background |
| `--bg-card` | `#FFFFFF` | Cards, sidebar, top bar |
| `--bg-sidebar` | `#FFFFFF` | Left navigation sidebar |
| `--border` | `#E5E7EB` | Card borders, dividers, input borders |
| `--border-subtle` | `#F3F4F6` | Section separators, table row borders |
| `--text-primary` | `#111827` | Headings, primary labels |
| `--text-secondary` | `#6B7280` | Descriptions, placeholders, metadata |
| `--text-tertiary` | `#9CA3AF` | Disabled, hints |
| `--accent` | `#2563EB` | Primary buttons, active nav item, links, brand |
| `--accent-hover` | `#1D4ED8` | Primary button hover |
| `--accent-soft` | `#EFF6FF` | Light blue badges, selected states |
| `--color-accent-light` | `#93C5FD` | Soft accent backgrounds, secondary buttons |
| `--color-bg-auth-card` | `#FAFAFA` | Auth card surface (slightly off-white) |
| `--success` | `#22C55E` | Online, ok, success status |
| `--warning` | `#F59E0B` | Warning, syncing, partial states |
| `--danger` | `#EF4444` | Offline, error, destructive actions |
| `--tag-green-bg` | `#DCFCE7` | Success tag background |
| `--tag-green-text` | `#166534` | Success tag text |
| `--tag-blue-bg` | `#DBEAFE` | Info/primary tag background |
| `--tag-blue-text` | `#1E40AF` | Info/primary tag text |
| `--tag-yellow-bg` | `#FEF9C3` | Warning tag background |
| `--tag-yellow-text` | `#854D0E` | Warning tag text |
| `--tag-purple-bg` | `#F3E8FF` | Generic tag background |
| `--tag-purple-text` | `#6B21A8` | Generic tag text |

### Dark mode

| Token | Hex | Usage |
|---|---|---|
| `--bg-page` | `#0A0A0A` | Main content background |
| `--bg-card` | `#141414` | Cards, elevated surfaces |
| `--bg-sidebar` | `#111111` | Left navigation sidebar |
| `--border` | `#262626` | Card borders, dividers |
| `--border-subtle` | `#1F1F1F` | Section separators |
| `--text-primary` | `#FAFAFA` | Headings, primary labels |
| `--text-secondary` | `#A3A3A3` | Descriptions, metadata |
| `--text-tertiary` | `#737373` | Disabled, hints |
| `--accent` | `#3B82F6` | Primary actions (slightly brighter in dark) |
| `--accent-hover` | `#2563EB` | Primary button hover |
| `--accent-soft` | `#172554` | Selected/dark blue backgrounds |
| `--color-accent-light` | `#60A5FA` | Soft accent backgrounds, secondary buttons |
| `--color-bg-auth-card` | `#141414` | Auth card surface |
| `--color-danger-soft` | `#450A0A` | Soft danger focus rings/backgrounds |
| `--success` | `#4ADE80` | Success indicators |
| `--warning` | `#FBBF24` | Warning indicators |
| `--danger` | `#F87171` | Error indicators |

### Radius tokens

Custom radius scale lives in `frontend/app/globals.css` under `@theme inline`.

| Token | Value | Tailwind class |
|---|---|---|
| `--radius-xs` | `0.15rem` | `rounded-xs` |
| `--radius-sm` | `0.3rem` | `rounded-sm` |
| `--radius-md` | `0.45rem` | `rounded-md` |
| `--radius-lg` | `0.6rem` | `rounded-lg` |
| `--radius-xl` | `0.9rem` | `rounded-xl` |
| `--radius-2xl` | `1.2rem` | `rounded-2xl` |
| `--radius-3xl` | `1.8rem` | `rounded-3xl` |
| `--radius-4xl` | `2.4rem` | `rounded-4xl` |

Use these tokens for all rounded corners instead of hard-coded pixel values.

### Status colors

Use small solid dots for status:
- Online / Ok / Connected → green dot `#22C55E`
- Syncing / Pending / Away → amber dot `#F59E0B`
- Offline / Error → red dot `#EF4444`
- Unknown / Not connected → gray dot `#9CA3AF`

---

## 3. Typography

- **Font family:** `DM Sans` (Google Fonts) with a system fallback: `"DM Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- **Weights used:** `400` (regular), `500` (medium), `600` (semibold), `700` (bold)
- **Base size:** `14px`
- **Line height:** `1.5`

### Type scale

| Element | Size | Weight | Color |
|---|---|---|---|
| Page title | `24px` | `600` | `--text-primary` |
| Section title | `18px` | `600` | `--text-primary` |
| Card title | `16px` | `600` | `--text-primary` |
| Body / label | `14px` | `400` | `--text-primary` |
| Description / meta | `13px` | `400` | `--text-secondary` |
| Caption / small | `12px` | `400` | `--text-tertiary` |
| Nav item | `14px` | `500` | `--text-secondary` |
| Nav item active | `14px` | `500` | `--text-primary` |

---

## 4. Layout

### Shell

- **Left sidebar:** fixed, `240px` wide, full height, vertical stack.
- **Top bar:** optional; when used it sits above main content and shows context, status, and primary actions.
- **Main area:** `padding: 24px–32px`, scrolls independently.
- **Max content width:** none; cards and tables fill the available width.

### Sidebar

- White/light in light mode; very dark in dark mode.
- Logo block at top: icon + wordmark.
- Navigation as vertical list with left icon + label.
- Active item: subtle background (`--accent-soft`), left accent border or text color change.
- Hover item: light gray background (`#F3F4F6` light / `#1F1F1F` dark).
- Bottom section: utility links and user/device metadata.

### Cards

- Background: `--bg-card`
- Border: `1px solid --border`
- Border radius: `var(--radius-xl)` (`0.9rem` / `rounded-xl`)
- Padding: `20px–24px`
- Shadow: none or very subtle `0 1px 2px rgba(0,0,0,0.03)`
- Optional small icon/illustration in top-left corner of promotional cards.

### Spacing scale

| Token | Value |
|---|---|
| `space-1` | `4px` |
| `space-2` | `8px` |
| `space-3` | `12px` |
| `space-4` | `16px` |
| `space-5` | `20px` |
| `space-6` | `24px` |
| `space-8` | `32px` |

---

## 5. Components

### Buttons

**Primary**
- Background: `--accent`
- Text: white
- Padding: `8px 14px`
- Radius: `8px`
- Hover: `--accent-hover`

**Secondary / Outline**
- Background: transparent
- Border: `1px solid --border`
- Text: `--text-primary`
- Hover: subtle background (`--bg-page` in light)

**Ghost**
- Background: transparent
- Text: `--text-secondary`
- Hover: `--bg-page`

**Icon button**
- `32px × 32px` or `36px × 36px`
- Radius: `8px`
- Border only when in a toolbar

### Inputs

- Background: `--bg-card`
- Border: `1px solid --border`
- Radius: `8px`
- Height: `38px`
- Padding: `8px 12px`
- Placeholder: `--text-tertiary`
- Focus ring: `2px --accent-soft` or border `--accent`

### Tags / Badges

- Small rounded pills or rounded rectangles.
- Background: soft tint (green, blue, yellow, purple).
- Text: matching darker shade.
- Padding: `4px 10px`.
- Font size: `12px`.
- Examples:
  - `Work` → purple
  - `Projects` → blue
  - `Essential` → yellow
  - `Archive` → teal/green
  - `Personal` → green

### Tables

- Header: small uppercase or title-case labels, `--text-secondary`, `13px`.
- Row bottom border: `--border-subtle`.
- Row hover: `--bg-page`.
- Action column: text button or `⋯` menu.
- Progress/status can use colored segmented bars or simple dots.

### Toggles

- Track: gray when off, `--accent` when on.
- Thumb: white.
- Use for binary settings like "Remote control enabled" or "is_matchable".

---

## 6. Iconography

### UI icons

- Use **Lucide React** for all interface icons.
- Stroke width: `1.5px–2px`.
- Size in nav: `18px–20px`.
- Size in buttons/cards: `16px–18px`.
- Keep icons muted (`--text-secondary`) unless active/primary.

### App-style icons

For feature cards, service tiles, or brand markers, use the `AppIcon` utility in `components/ui/app-icon.tsx`.

- It renders a rounded-square container with a top-light to bottom-dark gradient background.
- Supports Lucide icons and **Simple Icons** brand icons.
- Available gradients: `blue`, `purple`, `green`, `orange`, `red`, `brand`.
- Includes a glossy highlight and a subtle dark-top/light-bottom bezel.
- Border width scales down on small sizes (`xs`–`lg`).

```tsx
import { ShieldCheck } from "lucide-react";
import { siSpotify } from "simple-icons";
import { AppIcon } from "@/components/ui/app-icon";

<AppIcon icon={ShieldCheck} size="lg" gradient="blue" />
<AppIcon brand={siSpotify} size="md" gradient="brand" />
```

### Navigation icon mapping (SyncUp)

| Route | Icon suggestion |
|---|---|
| Home | `Home` |
| Taste | `Heart` or `Sparkles` |
| Matches | `Users` |
| Recommendations | `Compass` or `Lightbulb` |
| Settings | `Settings` |
| Log out | `LogOut` |

---

## 7. Page Patterns

### Dashboard / Home

- Page title + short description at top left.
- Optional top-right primary action button.
- Top row of stat/overview cards (4 across on large screens).
- Below: sectioned cards or lists.
- Empty states use a dashed-border card with a CTA button.

### List views (Matches, Machines, Backups)

- Title bar with search input and filter dropdowns.
- Data table or card list below.
- Status shown as colored dot + text or segmented bar.
- Actions aligned right.

### Detail / Settings pages

- Page title + description.
- Stacked cards, each with a section title and description on the left, controls on the right.
- Horizontal divider between sections.
- Save/change action buttons aligned with the control area.

### Onboarding

- Step progress indicator as a row of pills/links.
- One focus card per step.
- Clear primary CTA at the bottom of each card.

---

## 8. Dark Mode Notes

- Do not just invert colors; darken each surface by a consistent amount.
- Cards should still be visually distinct from the page background.
- Accent blue can be slightly brighter (`#3B82F6`) for contrast.
- Borders become very subtle; rely on background separation.
- Tags/badges keep the same semantic hues but darken backgrounds.

---

## 9. Accessibility

- Minimum contrast ratio: `4.5:1` for body text.
- Interactive elements must have visible focus rings.
- Do not rely on color alone for status; pair dots/icons with text.
- Buttons should have clear hover/active states.

---

## 10. Implementation Notes

- This project uses **Tailwind CSS v4**. Define tokens in `globals.css` via `@theme inline` or CSS variables.
- **DM Sans is loaded via `next/font/google`** in `frontend/app/layout.tsx`. Do not add a separate `<link>` to Google Fonts.
- Avoid hard-coding colors in components; always reference the design tokens.
- Keep the existing stripped component shells and implement them against these guidelines.
- Prefer server components; keep client interactivity minimal and localized.
