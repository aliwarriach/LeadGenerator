# Frontend — Senior React Architect

Scope: `frontend/` only. Ignore backend rules here. Root rules still apply.

## Directives
- Ultra-concise, code-first. ≤2 lines explanation unless real trade-off.
- 1 precise question if ambiguity changes implementation (state scope, unlisted variant).
- Flow: Plan → Verify → Implement. Skip ceremony for trivial changes.
- Use available MCP/design tools for specs before asking user to describe visuals.

## Stack
React (functional, hooks) · Tailwind (utility only) · Zustand (global state) · Apisauce (API)

## Architecture
```
components/  pure UI, no logic, no API calls
features/    feature logic, composition
store/       Zustand slices
services/    Apisauce API layer
hooks/       reusable/data-fetching logic
utils/       pure helpers
constants/   static values/config
```
No mixed concerns. Component fetching data directly → extract a hook.

## Components
- Fully reusable — no hardcoded copy/structure.
- Props-driven only. No static inline data — use `constants/` or props.
- Small, composable. Prefer composition/children over unbounded variant props.
- DRY, but extract only on 2nd real occurrence, not the 1st.
- **Use `.map()` for rendering lists/repeated elements wherever applicable — avoid manual/hardcoded repetition of JSX.**

## Libraries — prefer over manual implementation
Don't hand-roll what a best-in-class library already solves:
- **Forms/validation:** React Hook Form + Zod (or Formik + Yup if repo already uses it) — never manual per-field `useState` forms.
- **Carousels/sliders:** Swiper.
- **Dates:** date-fns (or dayjs) — never manual date math.
- **Icons:** lucide-react.
- **Server-state caching/re-fetching (beyond raw Apisauce calls):** TanStack Query.
- **Drag-and-drop:** dnd-kit.
- **Virtualized long lists:** TanStack Virtual.
Hand-roll only if trivial (few static items) or no well-maintained library fits. Name the library in 1 line if it's not already a repo dependency.

## Code Quality
- Minimal, no dead code, no leftover console.log.
- No pass-through wrapper components with zero added behavior.
- Comments only for non-obvious why, never restating the code.
- Explicit loading/error/empty states for all data-driven UI — no happy-path-only components.

## Data & State
- All API calls via `services/` (Apisauce) — never fetch/axios in components/hooks directly.
- Zustand: global/cross-feature. useState: local. Promote to global only on 2nd real consumer.
- API / state / UI stay in separate layers.

## Testing
- Required for `services/`, `hooks/` (data-fetching/logic), `store/` slices, and any API integration — mock the network layer, test success/error/loading paths.
- Not required for pure presentational `components/` — visual correctness is verified by the user, not a test suite.
- Feature logic in `features/` → test if it contains branching/business logic; skip if it's pure composition/layout.

## Styling
- Tailwind only, no inline styles. Global theme (colors/spacing/type) via `tailwind.config` — no ad hoc values.

## Performance
- Memoize only with real/predictable re-render cost, not by default.
- Keep state local where possible; split store subscriptions narrowly.
- Lazy-load routes/heavy components where it meaningfully helps load time.

## Output
1. Plan (1-3 lines, non-trivial only)
2. Verify (1 question, if needed)
3. Implement (clean, complete, production code)

## Rules
- No hardcoding — props/constants/config only.
- Split components once >1 concern mixes (fetch + layout + logic = split).
- No cross-feature imports of internals — go through shared components/hooks/store.
- Don't break folder structure to save lines.
- Production-level always: real error boundaries, loading states, accessibility (semantic HTML, labeled inputs, keyboard nav).
