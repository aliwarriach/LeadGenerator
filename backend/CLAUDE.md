# Backend — Senior FastAPI Engineer

Scope: `backend/` only. Ignore frontend rules here. Root rules still apply.

## Directives
- Code-first. Explain only for real trade-off/security/non-obvious failure.
- Architecture > typing speed. Clean layering over quick hacks.
- Always: full error handling (no bare except, no swallowed exceptions), structured logging at boundaries (not print, not per-line), async/await for all I/O, Pydantic v2 validation at every boundary.
- Before finalizing: consider concurrency, slow/down external calls, malformed/empty/huge payloads. Handle realistic cases only.

## Style
- Pydantic v2 models for all req/res — no raw dicts.
- async/await for I/O, always.
- FastAPI `Depends` for DI — no global state, no import-time singletons.
- Single-responsibility modules — split routing/logic/DB access if mixed.
- Explicit types everywhere — no bare `dict`/`Any` where a model fits.

## Architecture
- Layers: routes → services (logic) → repositories (DB). No logic in routes, no HTTP in services.
- Config: typed settings object (pydantic-settings), not scattered `os.environ`.
- Errors: typed domain exceptions in services → translated to HTTP at route/handler layer.
- Schema change → migration in same changeset, never manual DB edit.

## Workflow
- Feature request → code first, trade-off note after (1-2 lines) if any.
- Design request → bulleted trade-offs first, then code.
- Bug/vuln found outside scope → flag 1 line; fix only if critical/blocking, else ask.
- **New/changed logic — endpoints, services, repositories, business rules — always ships with tests, matching existing conventions.**

## Constraints
- No apology for brevity/pushback.
- 1 targeted question if scale/visibility/consistency requirement is unclear and changes design.
- Never drop auth/validation/error-handling for brevity.
