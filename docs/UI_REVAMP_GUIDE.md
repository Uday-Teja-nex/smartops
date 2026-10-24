# UI Design System — Premium Dark Glassmorphism

Direction: **enterprise calm**. Dark, minimal, layered glass, one restrained
accent, purposeful motion. Not cyberpunk, not gaming UI, no scanlines, no
neon grids.

## Tokens (`src/app/globals.css`)

| Token | Value | Use |
|---|---|---|
| `--bg` | `#05070d` | page background (single subtle ambient gradient on body) |
| `--bg-raised` | `#0a0e18` | sidebar / chrome |
| `--glass` / `--glass-strong` | white @ 4% / 7% | panel fills |
| `--glass-border(-strong)` | white @ 8% / 14% | 1px panel borders |
| `--accent` / `--accent-strong` / `--accent-soft` | teal `#5eead4` family | live indicators, active nav, primary buttons — sparingly |
| `--accent-safety/housekeeping/occupancy/security/queue/system` | category hues | category badges & charts only |
| `--sev-low/medium/high/critical` | slate→rose ramp | severity everywhere |
| `--radius-sm/md/lg` | 10/14/20px | corners |
| `--shadow-panel/float` | inset highlight + deep drop | depth |

Utility classes: `.glass-panel`, `.glass-panel-strong`, `.pulse-dot`.

## Component library (`src/components/ui/`)

- `GlassPanel` (`strong`, `padded`) — the base surface. Everything sits on it.
- `Button` — `primary | outline | ghost | danger`, `sm | md`, optional icon.
- `Skeleton` / `SkeletonPanel` — every async surface's loading state.
- `EmptyState` / `ErrorState` — icon + title + description + optional action.

Legacy components (EventTable, charts, KpiCard, drawers) remain and inherit
the tokens; migrate them to `ui/*` primitives opportunistically.

## Layout principles

- Fixed 240px glass sidebar (icon + label nav, role-aware), glass topbar with
  live-status chip, building & time-range selectors, search.
- Content max-width free, 24px page padding, `gap-6` section rhythm.
- Responsive floor: usable at 1280×800; sidebar collapses to horizontal pill
  nav below `lg`.

## Motion rules (framer-motion)

- Page transitions: `template.tsx` — 0.28s rise-and-fade, custom ease
  `[0.22, 1, 0.36, 1]`. Nothing flashier.
- Live arrivals (incidents, candidate rows): 4–8px slide + fade on mount.
- Status changes: `pulse-dot` keyframe on live/online indicators only.
- Always respect `prefers-reduced-motion` (`useReducedMotion`, CSS media query).
- Never animate layout-critical properties on large lists; keep durations
  ≤0.3s; no parallax, no continuous background animation.

## Accessibility expectations

- Visible `:focus-visible` ring (`--ring`) on all interactive elements.
- Form fields always have labels; icon-only buttons get `title`/`aria-label`.
- Drawers/dialogs: `role="dialog"`, ESC to close, focus moves in.
- Color is never the only signal — status pills pair color with text.

## Honesty in UI

- The Connected / Offline status reflects API/SSE connectivity. It does not
  claim camera liveness. Offline state hides data and actions; no mock fallback.
- Evidence player draws only persisted detections; otherwise it states
  "No detection overlay available".
- Model metadata (provider/model/confidence) is shown on incident detail —
  operators always know what produced a classification.

## Key screens

Overview (`/`), Live Ops (`/live-ops`), Sources (`/sources`), Monitoring
(`/monitoring`), Incident Detail (`/incidents/[id]`), Safety, Housekeeping,
Occupancy & Security (`/occupancy`), Reports, Settings (`/settings`,
supervisor+), Login (`/login`).
