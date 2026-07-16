# Scraper/Discovery System Reference

Token-efficient technical map of the scraping pipeline. Read this instead of re-exploring
`backend/app/scrapers/`, `backend/app/workers/`, `backend/app/services/discovery_service.py`,
and related files at session start. Verify with a targeted grep before relying on a specific
line number — this snapshot may drift from the code.

## File Map

```
backend/app/scrapers/
  base_scraper.py        BaseScraper(ABC) — shared Playwright lifecycle, retry, stealth, exceptions
  google_maps_scraper.py GoogleMapsScraper(BaseScraper)
  facebook_scraper.py    FacebookScraper(BaseScraper)
  serper_worker.py       SerperWorker — NOT a BaseScraper subclass, HTTP-only (httpx)
  domain_filters.py      is_business_domain(), NON_BUSINESS_DOMAINS
  __init__.py            re-exports all of the above

backend/app/workers/
  discovery_worker.py    ARQ job fns: scrape_google_maps_job / scrape_facebook_job / scrape_serper_job
  queue.py                WorkerSettings (ARQ entrypoint), get_arq_pool()
  cooldown.py             Redis escalating cooldown / circuit breaker per source
  supervisor.py           WorkerSupervisor — spawns ARQ worker as subprocess of API process

backend/app/services/
  discovery_service.py    start_discovery() — fans out DiscoveryRun -> N DiscoveryJobs -> ARQ enqueue
  job_tracking_service.py JobTracker — worker-facing run/job/event CRUD + status derivation
  enrichment_service.py   enrich_lead() — runs 5 enrichers concurrently via asyncio.gather
  normalizer_service.py   name/website/phone/domain normalization
  deduplicator_service.py resolve_dedupe_key() — exact key + rapidfuzz cross-source fuzzy match
  lead_service.py         read/update API for saved leads — NOT part of scrape path

backend/app/routes/discovery.py       POST /start-discovery, /discovery-runs*, /discovery-jobs*
backend/app/schemas/discovery.py      DiscoveryRequest/Response (kickoff)
backend/app/schemas/discovery_job.py  job/run/event response models
backend/app/schemas/errors.py         ErrorDetail, ApiError, ErrorCode
backend/app/repositories/lead_repository.py          upsert_lead() — atomic ON CONFLICT upsert
backend/app/repositories/discovery_job_repository.py
backend/app/models/lead.py            Lead, LeadSource, PipelineStage
backend/app/models/discovery_job.py   DiscoveryRun, DiscoveryJob, DiscoveryJobEvent, DiscoveryJobStatus, DiscoveryEventType
backend/app/enrichers/
  pagespeed_enricher.py    Google PageSpeed — perf/seo/best-practices scores
  hunter_enricher.py       Hunter.io — domain email search
  wappalyzer_enricher.py   local pattern-matching tech stack detection (no API key)
  opencorporates_enricher.py  company registration lookup
  clearbit_enricher.py     logo existence check — DISABLED by default (host dead)
  groq_enricher.py         on-demand AI audit — NOT in the auto pipeline
  website_content_enricher.py  feeds groq_enricher — NOT in the auto pipeline
backend/app/core/config.py  Settings(BaseSettings) — all env-driven config, get_settings() lru_cached
```

## Pipeline Flow (request -> DB row)

1. `POST /start-discovery` (routes/discovery.py) validates `DiscoveryRequest` (schemas/discovery.py:
   `country`, `city` comma-separated up to `MAX_CITIES_PER_REQUEST=10`, `custom_niche`, optional
   `min_rating` 0-5). 503 if `request.app.state.arq_redis` is None.
2. `discovery_service.start_discovery()`: creates one `DiscoveryRun` row, then for each
   `city x source` (google_maps, facebook, serper) creates a `DiscoveryJob` row FIRST, then
   `redis.enqueue_job(job_name, job_id, custom_niche, location, min_rating)`. If enqueue returns
   None -> job marked FAILED (`queue_unavailable`), raises `DiscoveryQueueError` -> route 503.
3. ARQ (Redis-backed queue, not Celery). `workers/queue.py`: `job_timeout=3600s`, `max_tries=3`,
   `max_jobs=4`. `workers/supervisor.py` spawns the ARQ worker as a subprocess (`subprocess.Popen`,
   deliberately not `asyncio.create_subprocess_exec` — works around Windows SelectorEventLoop +
   uvicorn `--reload` not supporting subprocess creation).
4. Worker job fn (e.g. `scrape_google_maps_job(ctx, job_id, query, location, min_rating=None)`):
   builds `JobTracker`, marks RUNNING, instantiates scraper via `build_scraper_config(settings)`
   with event callbacks mapping `ScrapeEventType` -> `DiscoveryEventType`. Wrapped in
   `_run_job_with_safety_net` (catches any Exception -> FAILED `blocked_other`, re-raises for ARQ retry).
5. Browser sources (google_maps, facebook) go through `_run_browser_scrape_job`:
   - checks `cooldown.seconds_remaining(redis, source)` first; if cooling down -> job SKIPPED_COOLDOWN, no scrape
   - runs under a **single process-wide `asyncio.Lock()`** shared ONLY by Google Maps + Facebook
     (not Serper) — only one real Chromium session hits Google properties at a time
   - `JobStoppedError` -> STOPPED, no cooldown effect
   - `CaptchaDetectedError` -> BLOCKED `blocked_captcha`, harsh cooldown tier
   - `ScraperError` -> BLOCKED `blocked_other`, normal cooldown tier
   - success -> `cooldown.record_success()` clears strikes
   Serper skips the lock and cooldown entirely, goes straight to `_run_scrape_job`.
6. `_run_scrape_job`: calls `scrape_fn(query, location)` -> `list[dict]` raw leads. Opens ONE
   shared `httpx.AsyncClient` + ONE `AsyncSession` for the whole batch, processes leads
   **sequentially** (not concurrently — informal rate limiting + AsyncSession isn't concurrency-safe).
   Checks `tracker.should_stop()` before each lead; stops early with partial progress if true.
7. `_process_and_save_lead`: `normalize_lead()` -> `compute_dedupe_key(source, name, phone, website, location)`
   (SHA-256 of `source|name_norm|secondary_norm`) -> `deduplicator_service.resolve_dedupe_key()`
   (exact key match first, then rapidfuzz `token_sort_ratio >= fuzzy_match_name_threshold` (85.0)
   against same-`search_location` leads for cross-source dedup) -> `enrich_lead()` (only if website
   present) -> `lead_repository.upsert_lead()` (single `INSERT ... ON CONFLICT (dedupe_key) DO UPDATE`).
8. Enrichers run concurrently via `asyncio.gather` (each swallows its own errors, returns None):
   pagespeed, hunter (emails), wappalyzer (tech stack, no key needed), opencorporates (registration),
   clearbit (logo, disabled by default). `website_score` = equal-weighted avg of
   performance/seo/best_practices.
9. Progress surfaced via `JobTracker` writing to `DiscoveryJob` (status/counters/current_business_name)
   and append-only `DiscoveryJobEvent` (bigint id = polling cursor). Frontend polls
   `GET /discovery-jobs/{id}` and `GET /discovery-jobs/{id}/events?after=<cursor>`. **No websockets/SSE.**
   `JobTracker` methods swallow all their own exceptions — tracking must never abort the scrape.

## base_scraper.py Contract

```python
class BaseScraper(ABC):
    source: str  # subclass must set

    @abstractmethod
    async def scrape(self, query: str, location: str) -> list[dict[str, Any]]: ...
```
(`GoogleMapsScraper.scrape` adds optional `min_rating` kwarg — Liskov-compatible.)

Key inherited helpers subclasses use:
- `browser_session(playwright)` — persistent context lifecycle, closes on exit
- `_launch_persistent_context(playwright)` — on-disk profile at `config.profile_dir/{source}`,
  random UA, anti-detection Chromium flags
- `new_stealth_page(context)` — combines all `playwright-stealth` init scripts into ONE
  `add_init_script` call (workaround for playwright-stealth 1.0.6 scope bug)
- `human_delay/rate_limit_delay/search_delay` — randomized `asyncio.sleep`
- `human_mouse_move/human_click/human_scroll`
- `detect_captcha(page)` — raises `CaptchaDetectedError` on URL markers
  (`google.com/sorry`, `/sorry/index`) or content markers (`unusual traffic from your computer
  network`, `id="captcha-form"`, `g-recaptcha`, `recaptcha/api.js`)
- `with_retry(func, *, op_name, page=None)` — exponential backoff `2**(n-1) + jitter`,
  `config.max_retries` attempts; **CaptchaDetectedError skips retry entirely** (fails fast);
  other exceptions retried, wraps as `ScraperError` after exhaustion
- `screenshot_on_failure(page, name)` — saves to `config.screenshot_dir/{name}_{utc_ts}.png`,
  swallows its own failures
- `normalize(*, name, location, website, phone, raw_data)` -> canonical dict:
  `{name, location, website, phone, source, has_website, raw_data}`
- `_emit(event_type, message, **payload)` — calls `on_event`, swallows callback exceptions
- `_check_stop()` — raises `JobStoppedError` if `on_check_stop()` returns True

Exceptions: `ScraperError` (base) -> `CaptchaDetectedError` (not retried); `JobStoppedError`
(deliberately NOT a ScraperError subclass — must not trigger cooldown escalation).

`ScrapeEventType`: `SCRAPER_STARTED, BUSINESS_PROCESSING, RATE_LIMIT_DELAY, ERROR, WARNING`

`ScraperConfig` fields worth knowing: `headless, max_results=50, max_retries=3,
action_delay_min/max=0.5/2.0, rate_limit_min/max=1.5/4.0, search_delay_min/max=4.0/9.0,
navigation_timeout_ms=30000, locale="en-US", timezone_id="Asia/Karachi",
geolocation={24.8607,67.0011}, viewport=1920x1080, proxy_server/username/password,
user_agents, screenshot_dir="screenshots", profile_dir="browser_profiles"`.

## Per-Scraper Notes

**GoogleMapsScraper** — navigates `google.com/maps/search/{query}+in+{location}`. Selectors:
`div[role="feed"]` (feed), `div[role="feed"] div[role="article"]` (listings),
`a[data-item-id="authority"]` (website), `button[data-item-id="address"]`,
`button[data-item-id^="phone:tel:"]`, `div.F7nice span[aria-hidden='true']` (rating). Name via
`page.locator("h1").last` (deliberate — feed's own H1 stays in DOM). Handles both multi-result
feed and single-exact-match redirect. Infinite scroll: `MAX_STALE_SCROLLS=4`,
`MAX_SCROLL_ATTEMPTS=25`. Per-listing failures swallowed (`_safe_extract_listing`); the initial
search call is NOT swallowed (re-raised so worker distinguishes "zero results" from "search
failed"). `min_rating` filter excludes listings with `rating=None` if a threshold is set.

**FacebookScraper** — does NOT search Facebook directly; discovers page URLs via Google:
`site:facebook.com "{query}" "{location}"`. Paginates up to `MAX_SEARCH_PAGES=3`
(`#search`, `#pnnext`). Link filter (`_clean_facebook_link`) rejects
`/groups/, /events/, /watch, /marketplace/, /photo, /videos/, /posts/, sharer, /login, /policies,
/help, /plugins/, l.facebook.com` path substrings; strips query string. **Known gap**: `/media/set/`
(photo-album URLs) is NOT in this blocklist — confirmed via a captured failure screenshot hitting
Facebook's "Not Found" page; worth adding if seen again. Website extraction scans up to 30
outbound anchors, **unwraps `l.facebook.com/l.php?u=...` redirector links** before checking
`is_business_domain()` — regression-tested (LinkedIn/Instagram proxied through `l.facebook.com`
must still be rejected).

Phone extraction (`_extract_page` -> `_extract_phone_from_about`, then falls back to
`_extract_phone` on the homepage body): visits `{page_url}/about` (one extra page load per lead)
and searches for a number immediately followed by a `Mobile`/`Phone` field label
(`_ABOUT_PHONE_RE`) — this is how Facebook actually renders contact info on the About tab; there
are no `tel:` links to rely on. The original homepage-body regex (keyword window around
"call"/"phone") is kept only as a fallback since it rarely matches Facebook's real layout — it
got ~7% hit rate in testing vs ~80% after adding the About-page lookup. Confirmed via live runs
against real Facebook pages, 2026-07. Any failure in the About-page visit is swallowed (logged at
debug) and just falls through to the homepage fallback — never fails the whole lead.

Google search call re-raised on failure; per-page visits swallowed (`_safe_visit_page`).

**Diagnosed and ruled out** (2026-07): a user-reported "only 2-3 leads found, many pages fail to
extract" symptom did NOT reproduce in two standalone live runs (15/15 and 15/15 leads, zero
extraction failures, both against real Google + Facebook). If this recurs, the cause is more
likely pipeline-specific (the shared `asyncio.Lock` with Google Maps causing contention, stale
Redis cooldown state from a prior CAPTCHA/block, or the production `max_results`/`min_rating`
values) rather than a bug in `FacebookScraper` itself — check `DiscoveryJob`/`DiscoveryJobEvent`
rows for the actual run before assuming scraper code is at fault.

**SerperWorker** — NOT a BaseScraper subclass; duck-types the same `scrape()` signature. POST to
`serper.dev/search` with `X-API-KEY` header. If no `api_key`: emits `SCRAPER_STARTED` then
returns `[]` immediately (no exception). Retry (`_request_with_retry`): up to `max_retries`,
same backoff formula as base scraper; **429 treated as retryable**; returns `None` (not raised)
after exhaustion, caller returns `[]`. Result dict shape independently duplicates
`BaseScraper.normalize()` (not shared code — if you change one, check the other).

## Error/Retry Matrix

| Failure | Handled where | Result |
|---|---|---|
| Transient op failure | `with_retry` | backoff retry -> `ScraperError` after exhaustion |
| CAPTCHA | `detect_captcha` + `with_retry` | fails fast, no retry, screenshot taken |
| User stop | `_check_stop` | `JobStoppedError`, no cooldown effect |
| Per-listing/page extraction fail | `_safe_extract_listing`/`_safe_visit_page` | swallowed to None, WARNING event |
| Source blocked (job-level) | `_run_browser_scrape_job` | BLOCKED + Redis cooldown (5min base, doubles per strike, 4hr cap; CAPTCHA base 30min) |
| Source in cooldown | `_run_browser_scrape_job` pre-check | SKIPPED_COOLDOWN, scrape never runs |
| Unexpected bug | `_run_job_with_safety_net` | FAILED `blocked_other`, re-raised for ARQ retry |
| Enricher failure | each enricher's own try/except | always returns None, never fails lead save |
| Serper 429/5xx | `_request_with_retry` | retried, then `[]` (not raised) |
| Tracking layer failure | `JobTracker`, `_emit` | swallowed+logged, never aborts scrape |

## Config Keys (backend/app/core/config.py)

- Queue: `redis_url`, `auto_start_arq_worker`
- Scraper behavior: `scraper_headless, scraper_max_results=50, scraper_max_retries=3,
  scraper_action_delay_min/max, scraper_rate_limit_min/max, scraper_search_delay_min/max,
  scraper_navigation_timeout_ms=30000, scraper_screenshot_dir, scraper_profile_dir`
- Fingerprint: `scraper_locale, scraper_timezone, scraper_geolocation_lat/lon,
  scraper_viewport_width/height, scraper_user_agents`
- Proxy (optional): `scraper_proxy_server/username/password`
- Serper: `serper_api_key` (required or source returns `[]`), `serper_base_url,
  serper_max_results=20, serper_timeout_seconds=15.0, serper_max_retries=3,
  serper_country="pk", serper_language="en"`
- PageSpeed: `pagespeed_api_key` (optional), `pagespeed_timeout_seconds=75.0` (raised from 25s —
  Lighthouse runs take ~55s), `pagespeed_strategy="mobile"`
- Hunter: `hunter_api_key, hunter_timeout_seconds=10.0, hunter_max_emails=3`
- Wappalyzer: `wappalyzer_enabled=True` (no key, local pattern match)
- OpenCorporates: `opencorporates_api_key` (optional)
- Clearbit: `clearbit_logo_enabled=False` (disabled — `logo.clearbit.com` host dead)
- Groq (on-demand audit only): `groq_api_key, groq_model="llama-3.3-70b-versatile"`
- Normalization: `default_phone_region="PK"`, `fuzzy_match_name_threshold=85.0`
- Shared enrichment HTTP client: `enrichment_client_timeout_seconds=90.0`, `enrichment_user_agent`
  (realistic Chrome UA — httpx's default gets WAF-blocked)

## Data Model (backend/app/models/lead.py)

`Lead` table `leads`:
- Identity/scrape: `id, name, location, website, website_domain (indexed), phone,
  source (google_maps/facebook/serper), has_website, rating, category, query,
  search_location, dedupe_key (unique+indexed, drives upsert idempotency)`
- CRM (only touched via `PATCH /leads/{id}`, never by pipeline): `estimated_revenue_level,
  pipeline_stage (new_lead/contacted/qualified/proposal/won)`
- Enrichment (None until `has_website` and enriched): `website_score, website_score_details
  (JSONB), pagespeed_score, seo_score, performance_issues (ARRAY), emails (ARRAY),
  tech_stack (ARRAY), is_registered, logo_valid, enriched_at`
- AI audit (on-demand, `POST /leads/{id}/audit`, not auto pipeline): `ai_ui_score,
  ai_conversion_score, ai_content_score, ai_trust_score (1-10), ai_issues, ai_summary, ai_audited_at`
- `raw_data` (JSONB, default `{}`): scraper-specific extras — `maps_url, facebook_url,
  serper_link, snippet, og_description, address`

Raw scraper output (pre-normalize) shape — every scraper returns `list[dict]` matching
`BaseScraper.normalize()`:
```python
{"name": str, "location": str|None, "website": str|None, "phone": str|None,
 "source": str, "has_website": bool, "raw_data": dict}
```

`DiscoveryRun`/`DiscoveryJob`/`DiscoveryJobEvent` (models/discovery_job.py):
- `DiscoveryRun` — one row per kickoff call, immutable, **no status column** — status always
  derived at read time from child jobs (`job_tracking_service.derive_run_status`)
- `DiscoveryJob` — one row per (source x city). `status`: pending/running/completed/failed/
  blocked/skipped_cooldown/stopped. `stop_requested` has two writers: the worker coroutine and
  the stop endpoint.
- `DiscoveryJobEvent` — append-only, bigint `id` doubles as polling cursor.
  `DiscoveryEventType`: job_status_changed, scraper_started, business_processing, lead_saved,
  rate_limit_delay, error, warning, stopped

## Where To Make Common Changes

- **New scraper source**: add `backend/app/scrapers/<source>_scraper.py` subclassing
  `BaseScraper`, register in `scrapers/__init__.py`, add an ARQ job fn in
  `workers/discovery_worker.py`, register in `WorkerSettings.functions` (workers/queue.py),
  add to `_JOB_NAMES` in `discovery_service.py`. Decide if it needs the shared browser lock
  (Playwright-based) or not (HTTP-only like Serper).
- **Change retry/backoff behavior**: `BaseScraper.with_retry` (shared) or
  `SerperWorker._request_with_retry` (independent — Serper doesn't use the base class).
- **Change cooldown tiers**: `workers/cooldown.py` (`BASE_COOLDOWN_SECONDS`,
  `MAX_COOLDOWN_SECONDS`, `CAPTCHA_BASE_COOLDOWN_SECONDS`).
- **Change dedup logic**: `services/deduplicator_service.py` (fuzzy threshold is
  `settings.fuzzy_match_name_threshold`) and `compute_dedupe_key` in `discovery_worker.py`
  (key composition — currently source-scoped, so identical business across sources gets
  different keys; cross-source dedup only happens via the fuzzy match).
- **Add a new enricher**: create `backend/app/enrichers/<name>_enricher.py` returning `None` on
  any failure, wire into `enrichment_service.enrich_lead()`'s `asyncio.gather` call, add a
  settings flag if it needs one, add fields to `Lead` model + migration.
- **Change scrape selectors** (Google Maps/Facebook DOM changes): selectors are hardcoded as
  class-level constants at the top of each scraper file — check there first when a scraper
  starts returning empty/wrong data, since Google/Facebook DOM changes without notice.

## Test Coverage Signals (what's contractually guaranteed)

- `CaptchaDetectedError` never burns a retry attempt (`with_retry` fails fast, `call_count == 1`)
- `_meets_rating_threshold`: a listing with `rating=None` FAILS a set threshold (not assumed to pass)
- Facebook `_extract_website` rejects `l.facebook.com` redirects even when the unwrapped target
  is a non-business domain (LinkedIn/Instagram) — don't regress this
- `compute_dedupe_key` is source-scoped by design — same business via 2 sources gets 2 different
  keys; only fuzzy matching catches that overlap
- Shared `asyncio.Lock` genuinely serializes Google Maps + Facebook (test proves no interleaving);
  Serper runs unlocked/concurrent (test proves interleaving when no lock passed)
- Mid-loop stop saves partial progress (e.g. 1 of 2 leads) and calls `mark_stopped`, never
  `mark_completed`
- `JobStoppedError` path never touches Redis cooldown keys (`redis.set`/`redis.delete` not called)
- WARNING events bump `extraction_failures_session` but do NOT call `record_event`;
  BUSINESS_PROCESSING both updates `current_business_name` AND records an event
