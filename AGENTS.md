# Agent Instructions

## Frontend Design

All frontend work must follow the design system defined in [`DESIGN.md`](./DESIGN.md).

Key points:

- Use the color tokens, typography, spacing, and component patterns documented there.
- **Use DM Sans** as the interface typeface. It is loaded via `next/font/google` in `frontend/app/layout.tsx`.
- The frontend has been stripped to scaffold shells — implement components against `DESIGN.md`, not the old content.
- Tailwind CSS v4 is configured; prefer CSS variables/design tokens over hard-coded values.
- Maintain both light and dark mode parity.

## Frontend Documentation

For page plan, API integration patterns, and build order, see [`docs/frontend.md`](./docs/frontend.md).

## Project Context

- Backend: Python/FastAPI in `backend/`.
- Frontend: Next.js 16 + React 19 + TypeScript in `frontend/`.
- Database migrations live in `backend/alembic/versions/`.
