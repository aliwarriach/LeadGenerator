# Monorepo Root

`backend/CLAUDE.md` loads in `backend/`. `frontend/CLAUDE.md` loads in `frontend/`. Never cross-apply. Cross-cutting change → read both, apply separately, don't blend.

## Map
```
/backend   FastAPI — see backend/CLAUDE.md
/frontend  React — see frontend/CLAUDE.md
/shared    cross-cutting types/contracts
```

## Mindset
- Plan silently before non-trivial code; state plan in 1-3 lines only if complex.
- Push back on flawed specs (e.g. "skip validation") — propose fix, don't comply silently.
- State trade-off in 1 line only when a real fork exists (sync/async, cache strategy, client/server state). Skip for obvious choices.
- Brevity = prose only. Never cut error handling, validation, auth, edge cases.
- No speculative abstraction — build for current requirement, not imagined future one.
- 1 targeted question if a missing assumption changes the design. Don't ask what's inferable.
- Security/correctness bug spotted outside scope → flag in 1 line. Fix only if critical; else ask.
- Testing scope differs by domain — see backend/frontend files.

## Conventions
- JSON: camelCase. Python: snake_case. Convert at boundary only.
- Commits: `type(scope): imperative msg`.
- Never commit secrets/.env — flag if about to happen.
- No apologies for brevity or pushback.
