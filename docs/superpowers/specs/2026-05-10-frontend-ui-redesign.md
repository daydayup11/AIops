# Frontend UI Redesign Spec

**Date:** 2026-05-10  
**Status:** Approved

## Goal

Upgrade the frontend UI of the 校园网流量分析助手 from basic Tailwind to a polished "modern minimal + dashboard card" style (B+C), using shadcn/ui as the component foundation.

## Style Direction

- **Modern minimal white** (ChatGPT / Linear quality): clean white backgrounds, refined shadows, consistent spacing and border radius
- **Dashboard card feel** (Grafana / Notion): light gray page background, elevated card components, subtle visual hierarchy
- Color palette: neutral grays + blue accent (`hsl(221.2 83.2% 53.3%)` as primary)

## Dependencies to Add

| Package | Purpose |
|---|---|
| `@radix-ui/react-scroll-area` | Sidebar scroll area |
| `@radix-ui/react-tooltip` | Icon button tooltips in header |
| `@radix-ui/react-slot` | shadcn Button asChild |
| `lucide-react` | Icons (Settings, Moon, etc.) |
| `class-variance-authority` | shadcn component variants |
| `clsx` | Class merging utility |
| `tailwind-merge` | Tailwind class dedup |

shadcn components are added as source files (not npm packages) under `src/components/ui/`.

## File Changes

### `index.css`
- Add shadcn CSS variable tokens: `--background`, `--foreground`, `--primary`, `--muted`, `--card`, `--border`, `--radius`, etc.
- Set page background to `--background` (light gray, e.g. `hsl(210 20% 98%)`)

### `vite.config.ts`
- Add `resolve.alias`: `@` → `./src`

### `tsconfig.app.json`
- Add `paths`: `"@/*": ["./src/*"]`

### `src/lib/utils.ts` (new)
- `cn()` helper combining `clsx` + `tailwind-merge`

### `src/components/ui/` (new)
- `button.tsx` — shadcn Button with variants (default, ghost, outline)
- `input.tsx` — shadcn Input
- `scroll-area.tsx` — shadcn ScrollArea (wraps Radix)
- `tooltip.tsx` — shadcn Tooltip

### `App.tsx`
- Header: add right-side icon buttons (Settings gear icon + Moon icon as theme placeholder) using ghost Button + Tooltip
- Header: subtle bottom border + `backdrop-blur` for glass effect

### `SessionSidebar.tsx`
- Use `ScrollArea` for the session list
- Each session item: add formatted timestamp below title (e.g. `今天 14:32`)
- Active item: stronger visual indicator (left border accent + bg)
- "新对话" button: use shadcn Button

### `ChatPanel.tsx`
- User bubble: refined radius, slightly deeper blue
- Clarify bubble: card-style with border instead of flat gray bg
- Result card: use `card` token bg + `shadow-md` + stronger border
- Error: use `destructive` color token

### `InputBar.tsx`
- Use shadcn `Input` + `Button`
- Add subtle `⏎` hint text inside input when idle

## Constraints

- Tailwind v4 is in use; shadcn CLI init differs from v3. CSS variables must be injected manually into `index.css` using the `@theme` block syntax for Tailwind v4, not `tailwind.config.js`.
- No additional routing or state management changes.
- No dark mode implementation (theme button is placeholder only).

## Out of Scope

- Backend changes
- Dark mode
- Mobile/responsive layout
- ChartRenderer restyling
