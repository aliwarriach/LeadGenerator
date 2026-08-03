# Backend Audit Report

_Last full audit: 2026-08-03. Scope: `backend/app/` (routes, services, repositories, models, schemas, core config). Auth, discovery, leads/CRM, activity, outreach, outreach-drafts, chat/AI-audit modules covered._

## Summary
- Total Issues: 9
- Critical: 2
- Medium: 6
- Minor: 1

---

## Issues

### No authentication or authorization anywhere in the API
**Category:** Security
**Severity:** Critical
**Problem:** There is no auth module, no user/session model, no API key check, and no `Depends` auth guard on any router (`routes/leads.py`, `routes/discovery.py`, `routes/activities.py`, `routes/outreach.py`, `routes/outreach_drafts.py`, `routes/dashboard.py`). Every endpoint — read and write — is reachable by anyone who can hit the port.
**Impact:** Any network-adjacent caller can read/modify all CRM data (leads, pipeline stage, activity log, outreach drafts), trigger discovery scrape jobs, and invoke paid third-party calls (Groq, PageSpeed, Hunter) at will — a direct cost-abuse and data-integrity vector, not just theoretical exposure.
**Fix Options:**
1. Add a lightweight API-key/bearer-token dependency (`Depends(require_api_key)`) applied at the router or app level — minimal viable gate for a single-tenant internal tool.
2. Full user/session auth (JWT or session cookie) with a `users` table, if multi-user access is ever needed.
3. Restrict at the network layer only (firewall/VPN) and explicitly document this as a trusted-network-only tool — acceptable only if this will never be internet-exposed.
**Recommended Fix:** Option 1 now (cheap, closes the immediate gap); revisit option 2 if multiple people will use this CRM independently.

---

### Non-atomic multi-step writes leave inconsistent state on partial failure
**Category:** Logical Bug / Edge Case
**Severity:** Critical
**Problem:** Every repository write commits its own transaction independently (`session.commit()` inside `add_activity`, `create_draft`, `add_message`, `update_lead_pipeline`, etc.), and services chain several of these per logical operation without a shared transaction:
- `activity_service.change_lead_stage`: updates `pipeline_stage` (commit 1), then logs a `stage_change` activity (commit 2). If the second commit fails, the stage change is permanently persisted but the caller receives a 503 "failed" — the activity log silently loses that entry forever.
- `outreach_draft_service.create_draft`: `create_draft` (commit 1) then `add_activity` (commit 2) inside one `try` — same pattern, same failure mode (orphaned draft, no activity record, client told it failed).
- `chat_service.send_chat_message`: user message and assistant reply are added via two separate committed calls; if the second fails, a user message is persisted with no reply and the caller sees an unhandled exception (see next issue).
**Impact:** Silent, permanent data drift between what actually happened and what the CRM's audit trail (activities) shows — undermines the entire point of an append-only activity log.
**Fix Options:**
1. Wrap each multi-step operation in a single explicit transaction (`async with session.begin():`) and have repository functions stop calling `commit()` themselves, committing once at the service boundary instead.
2. Keep per-call commits but make the second step's failure roll back the first via a compensating action (messier, not recommended).
3. Accept eventual-consistency and reconcile activities from an event stream instead of an in-request write (over-engineered for this app's scale).
**Recommended Fix:** Option 1 — the repositories already sit on a single `AsyncSession` per request; removing per-function commits and committing once at the service layer is a small, low-risk change that fixes all three call sites at once.

---

### Blocking PDF generation on unbounded content stalls the event loop
**Category:** Performance
**Severity:** Medium
**Problem:** `pdf_service.render_proposal_pdf` (markdown parse + `xhtml2pdf.pisa.CreatePDF`) is pure synchronous/CPU-bound work, called directly (no `await`, no `asyncio.to_thread`) from `outreach_draft_service.generate_draft_pdf`, itself awaited from an async route. Meanwhile `OutreachDraftCreateRequest.content` / `OutreachDraftUpdateRequest.content` (`schemas/outreach_draft.py`) has `min_length=1` but **no `max_length`** — an arbitrarily large draft can be saved and later PDF-rendered.
**Impact:** A single large (or adversarial) proposal draft blocks the entire single-threaded async event loop for the whole render duration — every other concurrent request (including `/health`) stalls until it finishes.
**Fix Options:**
1. Cap `content` length in the schema (e.g. 50–100KB) to bound worst-case render time.
2. Run `render_proposal_pdf` via `await asyncio.to_thread(render_proposal_pdf, draft.content)` so it no longer blocks the loop.
3. Both — length cap for sanity, thread offload for correctness regardless of size.
**Recommended Fix:** Option 3 — cheap and directly addresses both the unbounded input and the blocking-call problem.

---

### Inconsistent DB-error handling across the service layer
**Category:** API Contract Problem
**Severity:** Medium
**Problem:** `lead_service`, `activity_service`, and `outreach_draft_service` wrap every repository call in `try/except Exception` and translate failures into `LeadServiceUnavailableError` → HTTP 503 with a clean message. `chat_service.send_chat_message`, `chat_service.get_chat_history`, `outreach_service.*`, `website_audit_service.audit_lead_website`, and `discovery_service.start_discovery` do **not** — a DB hiccup (e.g. connection drop) in any of these raises a raw, unhandled exception that FastAPI turns into a generic 500 with no structured error body, and isn't logged via the app's own logger call.
**Impact:** Callers (the frontend) can't rely on a consistent error shape/status code for the same failure class depending on which endpoint they hit — breaks the "typed domain exceptions → HTTP at route layer" convention `backend/CLAUDE.md` mandates.
**Fix Options:**
1. Apply the same `try/except Exception → LeadServiceUnavailableError` wrapper used in `lead_service` to the DB calls in `chat_service`, `outreach_service`, `website_audit_service`, and `discovery_service`.
2. Move the wrapping into a shared decorator/context manager used by all services, so new services get it for free.
3. Add a global FastAPI exception handler for unhandled `Exception` that returns the same `ApiError` shape as a last-resort net (doesn't fix the missing logging/503 semantics, only the response shape).
**Recommended Fix:** Option 1 for immediate consistency; option 2 if more services are added soon, to stop this from recurring.

---

### CPU-bound fuzzy dedup scan blocks the event loop, scales O(n²) per run
**Category:** Performance
**Severity:** Medium
**Problem:** `deduplicator_service._best_fuzzy_match` runs `rapidfuzz.fuzz.token_sort_ratio` synchronously, in-loop, against every existing lead in the same `search_location` (`lead_repository.list_by_search_location` has no limit), once per newly scraped lead (`resolve_dedupe_key`, called from the upsert path). This is sync CPU work on the async event loop, not offloaded.
**Impact:** For a city/niche with hundreds–thousands of already-saved leads, every new lead triggers an O(n) scan, making a full scrape run O(n²) and — because it's synchronous — blocking all other concurrent API traffic (health checks, dashboard polling, UI requests) for the duration of each comparison batch.
**Fix Options:**
1. Offload the fuzzy-match loop via `asyncio.to_thread` so it no longer blocks the loop.
2. Pre-filter candidates further (e.g. by first-letter/n-gram bucket, or cap candidate pool size) before the O(n) fuzzy pass.
3. Move dedup fuzzy-matching into the DB via `pg_trgm` similarity, avoiding the in-Python scan entirely.
**Recommended Fix:** Option 1 now (minimal change, removes the blocking problem); option 3 is the right long-term fix if lead volume per location grows significantly.

---

### Unescaped `%`/`_` wildcards in ILIKE search filters
**Category:** Edge Case Failure
**Severity:** Medium
**Problem:** `lead_repository._apply_lead_filters` builds `Lead.name.ilike(f"%{name_contains}%")` and the same for `search_location_contains` with no escaping of literal `%`/`_` characters in user-supplied query params (`routes/leads.py` `name`, `search_location`).
**Impact:** Not a SQL-injection risk (parameterized), but a correctness bug: searching for a name that genuinely contains `%` or `_` behaves as a wildcard instead of a literal, producing wrong/surprising result sets (e.g. `name=50%_Off` matches unrelated rows).
**Fix Options:**
1. Escape `%`, `_`, and the escape character itself before interpolating, and pass `escape='\\'` to `.ilike()`.
2. Switch to Postgres full-text search (`ts_vector`) for name/location search — overkill for the current need.
**Recommended Fix:** Option 1 — a small, contained fix.

---

### Phone normalization fallback stores unvalidated garbage
**Category:** Validation
**Severity:** Medium
**Problem:** `normalizer_service.normalize_phone`: when `phonenumbers.parse`/`is_valid_number` fails (common for partial/garbled scraped text), it falls back to `_NON_PHONE_CHARS_RE.sub("", stripped)` — a bare digit-strip with **no minimum/maximum length or format check** — and stores whatever remains as the lead's `phone`.
**Impact:** Scraper noise (e.g. a business-hours string, an ID number, a truncated fragment) that superficially looks phone-like can be persisted as `phone` unchecked, polluting CRM data with values that were never actually valid phone numbers, silently defeating the `phonenumbers` validation this function otherwise does.
**Fix Options:**
1. Add a sane length bound (e.g. 7–15 digits per E.164) to the fallback before accepting it; reject/drop otherwise.
2. Drop the fallback entirely and return `None` when `phonenumbers` can't validate — lose a few partial-but-real numbers in exchange for zero garbage.
3. Keep the fallback but flag such leads (e.g. a `phone_unverified` bool) so downstream UI/outreach can treat them differently.
**Recommended Fix:** Option 1 — keeps the "best effort over nothing" intent from the code comment while filtering out obvious garbage.

---

### Discovery fan-out has no partial-failure recovery
**Category:** Edge Case Failure
**Severity:** Medium
**Problem:** `discovery_service.start_discovery` creates a `DiscoveryRun` with `total_jobs = len(cities) * len(sources)` up front, then loops city × source creating a `DiscoveryJob` row and enqueuing it. If `redis.enqueue_job` fails partway through (e.g. Redis drops mid-loop), the function marks that one job FAILED and immediately raises `DiscoveryQueueError` — every remaining city/source combination in the request is simply never created.
**Impact:** The run's `total_jobs` count permanently overstates the actual number of `DiscoveryJob` rows that exist for it, and there is no way to resume/retry just the missing city/source combinations — the caller must re-submit an entirely new discovery request (which may re-enqueue combinations that already succeeded).
**Fix Options:**
1. Continue the loop on a per-job enqueue failure (mark that job FAILED, keep going) instead of aborting the whole fan-out, so partial infrastructure blips only cost one job, not the rest of the run.
2. Add a "retry failed jobs in this run" endpoint that re-reads the run's job rows and re-enqueues only non-terminal/failed ones.
3. Both.
**Recommended Fix:** Option 1 first (small change, immediately reduces blast radius); option 2 as a follow-up for operator convenience.

---

### No cascade behavior defined for lead-scoped foreign keys
**Category:** Logical Bug (latent)
**Severity:** Minor
**Problem:** `activities.lead_id`, `outreach_drafts.lead_id`, and `lead_chat_messages.lead_id` all use bare `ForeignKey("leads.id")` with no `ondelete` — Postgres defaults to `NO ACTION`/`RESTRICT`. Currently unreachable in practice since **no lead-deletion endpoint exists anywhere in the API**.
**Impact:** None today. The moment a delete-lead feature is added, deleting any lead with activities/drafts/chat history will raise a raw `IntegrityError` unless cascade behavior is added at the same time.
**Fix Options:**
1. Add `ondelete="CASCADE"` to all three FKs now (with a migration) so the schema is ready whenever deletion ships.
2. Leave as-is and remember to address it in the same changeset that adds lead deletion.
**Recommended Fix:** Option 1 — zero cost now, avoids a foreseeable break later.

---

## Optimization Notes
- **Repeated pattern — per-call `session.commit()` inside repository functions.** Every repository (`lead_repository`, `activity_repository`, `outreach_draft_repository`, `lead_chat_repository`) commits internally rather than letting the service/route own the transaction boundary. This is the root cause of the non-atomicity issue above and also means repositories can never be composed into a larger atomic unit without refactoring. Consider moving all `commit()` calls up to the service layer (or a `Depends`-provided transactional session) as a general cleanup, not just for the three call sites flagged above.
- **Repeated pattern — inconsistent exception wrapping.** `lead_service`/`activity_service`/`outreach_draft_service` wrap DB errors; `chat_service`/`outreach_service`/`website_audit_service`/`discovery_service` don't. Worth standardizing via a shared helper/decorator once, rather than patching each service individually.
- **JobTracker (`job_tracking_service.py`) is a good reference pattern** — fail-open, swallow-and-log design for a non-critical side channel (progress reporting) that must never take down the actual scrape. Worth reusing this shape if similar "best-effort telemetry" needs arise elsewhere.
- **Config (`core/config.py`)** is clean, well-commented, and centralizes all tunables — no issues found there. `main.py` lifespan handling of Redis-unavailable-at-startup is a solid degraded-mode pattern worth keeping as the template for future optional dependencies.
