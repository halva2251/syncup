# SyncUp Frontend

Next.js 16.2.7 + React 19 + TypeScript + Tailwind CSS v4.

## Docs

- Design system: [`../DESIGN.md`](../DESIGN.md)
- Frontend plan & conventions: [`../docs/frontend.md`](../docs/frontend.md)
- Backend API spec: [`../docs/api-contract.md`](../docs/api-contract.md)

## Getting started

```bash
cd frontend
pnpm install
pnpm dev         # runs on localhost:3000 by default
```

> The backend already uses port `3000`. Run the frontend on a different port to avoid conflicts:
> ```bash
> PORT=3001 pnpm dev
> ```

## Checks

```bash
npx tsc --noEmit
pnpm lint
```

## Project notes

- Auth is cookie-based via the backend's `syncup_session` cookie.
- All backend routes live under `/api` on `http://127.0.0.1:3000`.
- Prefer Server Components; keep Client Components small and localized.
- Use the `AppIcon` utility in `components/ui/app-icon.tsx` for app-style feature/service icons.
