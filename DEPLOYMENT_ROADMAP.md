# Lead Generator — GCP Deployment Roadmap

> **Status:** v3 — **Phases 0–8 are ALL COMPLETE.** The app is live on Cloud Run at
> `https://leadgen-app-366622816060.us-central1.run.app`, Cloud SQL is provisioned, and
> the full cloud↔local dispatch hand-off has been verified end-to-end with real data —
> real leads scraped, enriched, saved, and all four Groq AI features working. See §12 for
> day-to-day operating instructions (URL, credentials, how to start the local worker).
> **Written:** 2026-08-16 · **Revised:** v2 (hybrid) → **v3 (local dispatcher + local Redis)**
> **Architecture:** Cloud Run hosts the API + UI. **Redis and the entire scraping worker
> stay on the local machine.** The only shared resource is Cloud SQL.
> **Purpose:** Single source of truth for deploying this project to GCP. A future Claude
> session should be able to execute the whole deployment by reading *this file only*,
> without re-exploring the codebase.

---

## 0. How to use this file

| If you need to… | Read section |
|---|---|
| Understand the design and why it's shaped this way | §0.1, §2 |
| Understand what the app currently is | §1 |
| Know what breaks and why | §3 |
| Know what it costs | §4 |
| Actually deploy | §5 Phases 0→8, in order |
| Know exact env vars / secrets | §6 |
| Verify it worked | §7 |
| Run it day-to-day | §8 |
| Undo / tear down | §9 |
| Know what we deliberately did *not* do | §10 |
| Look up a fact without re-reading the codebase | §11 |

**Rules for the executing session:**
- Do not restructure the application. Every code change is listed explicitly in Phase 4
  with its rationale. If a change is not listed here, don't make it.
- `backend/CLAUDE.md` and `frontend/CLAUDE.md` still govern their directories. New/changed
  backend logic ships with tests, matching existing conventions.
- Never inline real secret values into any file, image, or command. Secrets live in
  Secret Manager (cloud) or a gitignored `.env.production` (local), read once from
  `backend/.env` by hand.

### 0.1 Decisions this plan implements

| Decision | Answer | Consequence |
|---|---|---|
| **Auth** | HTTP Basic in-app | §3.1 |
| **Scrapers** | **Stay local** | Scraping runs from your residential IP exactly as today — no CAPTCHA/datacenter-IP risk, no Chromium in the cloud image, no cloud file storage. §2.2 |
| **Redis** | **Stays local (Memurai)** | Cloud Run never touches Redis. The cloud→local hand-off moves to the database. §2.3 |
| **Database** | **Cloud SQL** db-f1-micro | The one shared resource, and the only line item that costs money. Managed backups + PITR chosen over a self-run VM. |
| **Project** | `lead-generation-project-502410` | Separate from HR Automation so billing reports answer "what did *this* cost?" |
| **Credit** | $300 trial confirmed mostly unused | ~$12–17/mo is fully credit-covered → **$0 out of pocket** |

### 0.2 The one idea that makes this work

You asked whether Redis could stay local and the pieces talk over APIs. Yes — with one
correction and one simplification.

**Correction:** the cloud can never initiate a connection to your machine (NAT, no public
IP). Only your machine can initiate. That's fine — it's exactly how GitHub Actions
self-hosted runners work.

**Simplification:** you don't need new API endpoints, because **the database is already a
job queue**. `discovery_service.start_discovery` creates the `discovery_jobs` row with
`status='pending'` *before* it enqueues to ARQ (`discovery_service.py:53-79`), and
`arq_job_id` is a nullable, unique, indexed column. So:

```
Cloud API   →  INSERT discovery_jobs (status='pending', arq_job_id=NULL)   [and stop]
                            │
                            │  local dispatcher polls, claims with FOR UPDATE SKIP LOCKED
                            ▼
Local       →  redis.enqueue_job(...) into YOUR Memurai  →  UPDATE arq_job_id
                            │
                            ▼
Local       →  ARQ worker → scrapers → enrich → write leads back to Cloud SQL
```

**ARQ, all three scrapers, cooldown, `JobTracker`, and cooperative stop are completely
untouched.** This is a new *dispatch mode*, not a worker redesign. Cooldown even becomes
semantically more correct: it tracks your IP's block state, so it belongs on the machine
that actually scrapes.

Cooperative stop keeps working across the split for free — `POST /discovery-jobs/{id}/stop`
sets `stop_requested` in the DB, and the worker already polls that column.

---

## 1. Current Architecture (source of truth)

### 1.1 Shape

```
Lead_Generator/
├── backend/          FastAPI + SQLAlchemy(async) + Alembic + ARQ + Playwright
│   ├── app/
│   │   ├── main.py            FastAPI app, lifespan, CORS, ApiError handler, 7 routers
│   │   ├── core/config.py     pydantic-settings Settings (ALL config, ~60 fields)
│   │   ├── db/session.py      async engine + async_sessionmaker (module-level)
│   │   ├── routes/            health, dashboard, discovery, leads, outreach,
│   │   │                      activities, outreach_drafts
│   │   ├── services/          business logic (incl. job_tracking_service.JobTracker)
│   │   ├── repositories/      DB access
│   │   ├── models/            Lead, DiscoveryRun/Job/JobEvent, Activity,
│   │   │                      LeadChatMessage, OutreachDraft
│   │   ├── scrapers/          base_scraper (Playwright lifecycle), google_maps,
│   │   │                      facebook, serper_worker
│   │   ├── enrichers/         pagespeed, hunter, wappalyzer, opencorporates,
│   │   │                      clearbit, groq, website_content
│   │   └── workers/           queue.py (ARQ WorkerSettings), discovery_worker.py
│   │                          (the 3 job functions), supervisor.py, cooldown.py
│   ├── alembic/               8 migrations, head = 16e8b92ef39c
│   ├── requirements.txt       pinned; playwright==1.49.0, arq==0.26.3, asyncpg==0.31.0
│   └── .env                   REAL API KEYS — gitignored, never commit/bake
└── frontend/         React 19 + Vite 8 + Tailwind 3 + Zustand + TanStack Query + apisauce
    └── src/          components/ features/ hooks/ services/ store/ utils/ constants/
```

### 1.2 Runtime processes

Two long-lived processes; today the API spawns the second itself:

1. **API** — `uvicorn app.main:app`
2. **ARQ worker** — `python -m arq app.workers.queue.WorkerSettings`

`app/workers/supervisor.py::WorkerSupervisor` starts the worker as a **`subprocess.Popen`
child of the API** during FastAPI's `lifespan`, gated on `Settings.auto_start_arq_worker`
(default `True`). A subprocess, not an asyncio task, deliberately: it drives
Playwright/Chromium, which can crash or OOM independently of the API.

`Settings.auto_start_arq_worker`'s own docstring anticipates this deployment:
> *"Set False if the worker is run/scaled as its own deployment (e.g. production, or
> multiple uvicorn workers sharing one queue) — each API process would otherwise spawn
> its own worker."*

Cloud Run sets it `false`. The local worker is started directly with `python -m arq`,
exactly as `backend/scripts/dev.ps1` already does today.

### 1.3 Job pipeline (today)

```
POST /start-discovery
  → discovery_service.start_discovery()
      → 1 discovery_runs row (immutable, no status column — status derived from children)
      → per city × per source (google_maps, facebook, serper):
          → discovery_jobs row created FIRST (canonical id, status='pending', arq_job_id=NULL)
          → redis.enqueue_job("scrape_*_job", job_row.id, niche, location, min_rating)
          → attach_arq_job_id(job_row.id, arq_job.job_id)
  → ARQ worker
      → scrape → normalize → dedupe (exact key + rapidfuzz fuzzy) → enrich → upsert lead
      → progress/events → discovery_job_events (append-only, bigint cursor)
```

- `JOB_TIMEOUT_SECONDS = 3600` (jobs legitimately run 30–45 min; PageSpeed alone is
  40–60 s **per lead**), `JOB_MAX_TRIES = 3`, `max_jobs = 4` concurrent per worker.
- `_browser_scrape_lock` — process-wide `asyncio.Lock` (`discovery_worker.py:41-48`),
  documented as relying on *"exactly one ARQ worker process."* Trivially satisfied here:
  one worker, one machine.
- `app/workers/cooldown.py` — Redis-backed escalating per-source cooldown (5 min base,
  30 min for confirmed CAPTCHA, 4 h cap). State lives **only in Redis**.
- Stop is cooperative: `stop_requested` column, polled by the worker in two places.

### 1.4 External dependencies — and which side needs them

| Dependency | Used by | Cloud API | Local worker |
|---|---|---|---|
| PostgreSQL | everything | ✅ | ✅ |
| **Redis** | ARQ enqueue/dequeue + cooldown | **❌ (removed in `db` dispatch mode)** | ✅ |
| Chromium (Playwright) | google_maps + facebook scrapers | ❌ | ✅ |
| Serper.dev | serper scraper (`build_serper_config`, worker-only) | ❌ | ✅ |
| PageSpeed Insights | `enrichment_service.enrich_lead` (worker-only) | ❌ | ✅ |
| Groq | audit / chat / outreach **API endpoints** | ✅ | ❌ |
| Wappalyzer | enrichment (bundled ruleset, **no network call**) | ❌ | ✅ |
| Hunter / OpenCorporates | enrichment | ❌ | unconfigured by choice |
| Clearbit | enrichment | ❌ | disabled (`clearbit_logo_enabled=False`) |

> Groq is deliberately **not** in `enrich_lead` (`config.py:126-131`) — only called on
> demand from `/leads/{id}/audit`, `/leads/{id}/chat`, `/outreach/*`. That's why
> `GROQ_API_KEY` is cloud-side and `SERPER_API_KEY`/`PAGESPEED_API_KEY` are local-side.
> Keeping them separate minimizes cloud secret surface.

### 1.5 Filesystem writes (complete list — verified by grep)

| Path | Written by | In this design |
|---|---|---|
| `browser_profiles/<source>/` | `base_scraper._launch_persistent_context:188-189` | **Local disk, unchanged** |
| `screenshots/` | `base_scraper.screenshot_on_failure:346-351` | **Local disk, unchanged** |

PDF generation (`pdf_service.py:33-39`) is fully in-memory (`io.BytesIO`) and streamed in
the HTTP response — never touches disk. **→ No cloud file storage is required. §3.5.**

### 1.6 Authentication

**There is none.** Verified by grep across `backend/app/` — no auth dependency, no
middleware, no token check, no user model, no login route. Fine on localhost; not fine on
a public URL. → §3.1.

---

## 2. Target Architecture

### 2.1 Topology

```
   Browser ──HTTPS──▶ ┌──────────────────────────────────────────┐
   (SPA + API,        │ Cloud Run: leadgen-app                   │
    same origin,      │ us-central1 · 1 vCPU / 1 GiB             │
    HTTP Basic)       │ min=0  max=3   (scales to zero)          │
                      │  uvicorn app.main:app  (:$PORT)          │
                      │   ├─ /            → frontend dist        │
                      │   ├─ API routes                          │
                      │   ├─ AUTO_START_ARQ_WORKER=false         │
                      │   └─ DISPATCH_MODE=db  → no Redis at all │
                      └──────────┬──────────────────┬────────────┘
                                 │ Direct VPC       │ HTTPS
                                 │ egress           ▼
                                 ▼               Groq API
                    ┌─────────────────────────────┐
                    │ Cloud SQL PostgreSQL 17     │
                    │ db-f1-micro                 │
                    │ private IP ← Cloud Run      │
                    │ public  IP ← Auth Proxy     │
                    └─────────────┬───────────────┘
                                  │ TLS, gcloud-authenticated
                                  │ (Cloud SQL Auth Proxy)
   ┌──────────────────────────────┴───────────────────────────────┐
   │ YOUR WINDOWS MACHINE                                         │
   │  1. cloud-sql-proxy.exe          → 127.0.0.1:5433            │
   │  2. python -m app.workers.dispatcher   (NEW, ~60 lines)      │
   │       polls discovery_jobs WHERE status='pending'            │
   │              AND arq_job_id IS NULL                          │
   │       → enqueues into LOCAL Memurai                          │
   │  3. python -m arq app.workers.queue.WorkerSettings           │
   │       ├─ Chromium (headed, residential IP) ✅ unchanged      │
   │       ├─ cooldown state → local Memurai   ✅ unchanged       │
   │       ├─ browser_profiles/, screenshots/  ✅ local disk      │
   │       └─ Serper / PageSpeed / Wappalyzer  ✅ unchanged       │
   │  · Memurai 127.0.0.1:6379 — already installed, unchanged     │
   └──────────────────────────────────────────────────────────────┘
```

All three local processes are started by one script: `backend/scripts/worker-prod.ps1`
(three windows, same pattern as the existing `dev.ps1`).

### 2.2 What this design buys

- Scraping runs from your **residential IP**, exactly as today → no CAPTCHA/datacenter-IP
  risk, which was the dominant problem with an all-cloud deployment.
- Chromium profiles and screenshots keep working on real disk → **no GCS, no FUSE, no
  profile-corruption risk, no code change**.
- Redis never leaves your machine → **no Memorystore ($36/mo), no VM, no tunnel for it**.
- Cloud Run **scales to zero** and sits inside the free tier → effectively $0.
- Cloud image has no Chromium → ~350 MB, fast cold starts.
- **The AI features work 24/7 without your PC** — audit, chat, and outreach are cloud-side
  Groq calls against data already in Cloud SQL. Only *discovery* needs your machine on.

### 2.3 What it costs you

- **Discovery only runs while your PC is on**, with the three local processes up. Jobs
  created while you're offline sit at `pending` and start when the dispatcher reconnects.
  Nothing is lost. §3.2.
- ~150 lines of new backend code + tests (dispatch mode + dispatcher). Contained to the
  queue layer; scrapers, enrichment, and `JobTracker` are untouched. Phase 4.
- Worker↔Cloud SQL latency adds ~2–4 min per 50-lead job (<10% of a job's runtime). §3.4.
- Three local processes to start instead of two — automated by one script. §8.

### 2.4 Why these services

| Requirement | Choice | Why not the alternative |
|---|---|---|
| Relational DB | **Cloud SQL PG 17, db-f1-micro, private + public IP** | Managed backups and PITR, matching the HR project's proven version/tier. A self-run Postgres on a free `e2-micro` would be $0 but puts DB durability on you — you chose managed. |
| Cloud→DB path | **Private IP + Direct VPC egress** | Plain `host:port` URL → **zero code change**. The Cloud SQL Unix-socket integration is *broken* for this stack — §3.6. |
| Local→DB path | **Cloud SQL Auth Proxy on the public IP** | Authenticates with your gcloud credentials over TLS. No VM, no SSH tunnel, no authorized-network allowlist to update when your home IP changes. |
| Queue | **Local Memurai, unchanged** | Already installed and working. Cloud Run doesn't need Redis at all in `db` dispatch mode. |
| File storage | **none (local disk)** | The only two disk paths are written exclusively by the scraper, which runs locally. Creating a GCS bucket would be an unused service. §3.5. |
| Image registry | **Artifact Registry** (0.5 GB free) | Container Registry is deprecated. |
| Build | **Cloud Build** (2,500 free min/mo) | **Docker is not installed on this machine** (verified) — `gcloud builds submit` is the only build path. |
| Secrets | **Secret Manager** (cloud) + gitignored `.env.production` (local) | Keeps keys out of the image and out of git. |
| Frontend hosting | **served by FastAPI from the same container** | Free, and same-origin deletes the CORS problem instead of managing it. A LB + CDN would add ~$18/mo for no benefit. |

### 2.5 GCP project

| | Value |
|---|---|
| Project | `lead-generation-project-502410` (**exists**, billing **not yet linked**) |
| Billing account | `01C0B3-E652F2-0968E9` (same as HR Automation; $300 credit confirmed available) |
| Region / zone | `us-central1` / `us-central1-a` (same as HR) |
| Project number | `366622816060` |

---

## 3. Blockers & Behavioral Changes

### 3.1 BLOCKER — No authentication

Cloud Run with `--allow-unauthenticated` exposes every endpoint publicly, including the
Groq-backed ones that spend real money.

**Fix:** `backend/app/core/security.py` (new) — HTTP Basic middleware over the whole app,
credentials from Secret Manager, `secrets.compare_digest` for constant-time comparison.
`/health` exempt (Cloud Run's probe must not require credentials). **No-op when
`basic_auth_password` is unset**, so local dev and the existing 280+ tests are unaffected.
The browser handles the prompt natively → **zero frontend change**. Ships with tests.

### 3.2 BEHAVIORAL — Discovery is bounded by your machine's uptime

- Discovery progresses only while the Auth Proxy, dispatcher, and worker are running.
- Jobs created from the cloud UI while you're offline stay `pending` (`arq_job_id IS NULL`)
  and dispatch when you come back. **Nothing is lost.**
- The UI shows a run sitting at `pending` with no explanation — the app has no concept of
  "worker offline." Flagged, not built (§10.1).
- `JOB_TIMEOUT_SECONDS=3600` bounds *execution* time, not queue time, so a long wait
  doesn't fail the job.
- Everything else — browsing leads, AI audit, chat, outreach drafts, PDF export, pipeline
  edits — works 24/7 without your PC.

### 3.3 BLOCKER — `AUTO_START_ARQ_WORKER` must be `false` on Cloud Run

Otherwise every Cloud Run instance spawns its own ARQ worker. With `false`, no worker is
ever spawned in the cloud, so the API may scale freely (`--max-instances=3`).

**Hard requirement:** if this is ever flipped to `true` on Cloud Run, `--max-instances`
**must** simultaneously be set to 1 — otherwise N instances spawn N workers, N Chromium
sessions from one datacenter IP, and `_browser_scrape_lock` (a *process-wide* lock) stops
protecting anything.

### 3.4 BEHAVIORAL — Worker↔Cloud SQL latency

The worker now writes across the internet. Per lead the pipeline issues roughly: 1 dedupe
query, 1 upsert, and 2+ `JobTracker` calls (each opening its own short-lived session — by
design, so a DB hiccup can't break a scrape). At ~280 ms RTT × ~3 round trips per
operation that's **~3–4 s added per lead**, i.e. **~2–4 min per 50-lead job**.

Jobs already run 30–45 min (PageSpeed-dominated at 40–60 s/lead), so this is <10% overhead.
**No action.** `pool_pre_ping=True` is already set (`session.py:10`), which also makes the
pool resilient to a proxy blip.

> `asia-south1` (Mumbai) would cut RTT to ~50 ms for ~15% higher Cloud SQL cost. Not worth
> it at <10% overhead — but it's the lever if the worker ever feels slow.

### 3.5 RESOLVED — No cloud file storage is required

`browser_profiles/` and `screenshots/` are written **only** by the scraper → local disk,
unchanged. PDF generation is in-memory. **Deliberately creating no GCS bucket** — it would
be an unused service.

### 3.6 BLOCKER — Cloud SQL Unix socket does NOT work with this stack

The obvious pattern (`--add-cloudsql-instances`, which the HR backend uses) **breaks here**.
Recorded so nobody retries it:

SQLAlchemy 2.0's asyncpg dialect parses `?host=` query args as *multi-host* `host:port`
pairs (`asyncpg.py::create_connect_args` → `_split_multihost_from_url`). A Cloud SQL
instance connection name contains colons (`project:region:instance`), so
`postgresql+asyncpg://u:p@/db?host=/cloudsql/proj:us-central1:inst` is shredded into
host=`/cloudsql/proj`, port=`us-central1:inst`. It cannot work as a URL.

**Fix:** Cloud SQL **private IP** + Direct VPC egress → `DATABASE_URL` is a plain
`postgresql+asyncpg://leadgen:<pw>@10.x.x.x:5432/lead_generator`. **Zero code change** in
both `app/db/session.py` and `alembic/env.py`.

*(Fallback, not needed: pass the socket dir via SQLAlchemy `connect_args={"host": ...}`
instead of the URL query string, in both files.)*

### 3.7 BLOCKER — DB connection pool sizing

SQLAlchemy defaults to `pool_size=5, max_overflow=10` → up to **15 connections per
process**. `db-f1-micro` (0.6 GB RAM) allows roughly **25**. Worst case here: 3 Cloud Run
instances + local worker + local dispatcher = 5 processes × 15 = **75**.
`app/db/session.py:10` passes no pool arguments at all.

**Fix:** add `db_pool_size: int = 3` / `db_max_overflow: int = 2` to `Settings` and pass
them to `create_async_engine` → max 5 per process, 25 worst case. The dispatcher should
run at `pool_size=1` (it issues one small query per poll) — set via its own env.

### 3.8 `scraper_headless` stays `False` locally

`config.py:41` is `scraper_headless: bool = False` (headed). **Correct — keep it.** Headed
Chromium is better anti-bot behavior and is what you run today. Irrelevant on Cloud Run
since no browser launches there, but still set `SCRAPER_HEADLESS=true` in the cloud as
defense in depth in case `AUTO_START_ARQ_WORKER` is ever flipped by mistake.

### 3.9 Frontend must be repointed and rebuilt

`frontend/src/services/api.js:4` — `import.meta.env.VITE_API_BASE_URL || 'http://localhost:7000'`.

**Fix without touching code:** build with `VITE_API_BASE_URL=/`. apisauce/axios joins
baseURL `/` + path `/leads` → `/leads`, i.e. same-origin relative calls. `"/"` is truthy so
the localhost fallback isn't hit. **No frontend source change required.**

### 3.10 Local port conflict on the Auth Proxy

Per this project's own infra notes, this machine already runs **Postgres 17 on 5432**
(shared across ~5 projects). The Cloud SQL Auth Proxy must therefore listen on **5433**.

Memurai stays on **6379** — no conflict, since cloud Redis no longer exists.

Also: this machine resolves `localhost` to IPv6 `::1` first, which has previously caused
silent hangs. `.env.production` must use **`127.0.0.1`**, never `localhost` — consistent
with every existing connection string in this project.

### 3.11 Dispatcher edge case — Redis data loss

If the dispatcher enqueues a job (`arq_job_id` set) and Memurai then loses that job
(flush, or a crash before its RDB snapshot), the row stays `pending` forever — the
dispatcher won't re-claim it because `arq_job_id IS NOT NULL`.

Memurai persists to disk by default, so this only occurs on actual Redis data loss.
**Accepted, with a documented one-line remedy** (§8): clear `arq_job_id` on the stuck rows
and the dispatcher re-claims them. Auto-recovery was deliberately not built — a naive
"re-dispatch anything pending for >N minutes" rule would double-dispatch jobs that are
legitimately waiting behind `max_jobs=4`.

### 3.13 GOTCHA — never pass `VITE_API_BASE_URL=/` as a shell environment variable

Found while verifying Phase 4. MSYS-based shells on Windows (Git Bash, and therefore
anything shelling out through it) rewrite a bare `/` argument into a Windows path:
`VITE_API_BASE_URL=/ npm run build` produced a bundle with
`baseURL:"C:/Program Files/Git/"` baked in. Every API call would 404, with nothing in the
build output hinting at why.

**The value therefore comes from the committed `frontend/.env.production` file**, which
`vite build` loads automatically for production mode and which no shell can rewrite. The
Dockerfile deliberately does **not** set `ENV VITE_API_BASE_URL`. Both `.dockerignore` and
`.gcloudignore` carry an explicit `!frontend/.env.production` negation so the file survives
their blanket `**/.env.*` exclusion — without it the build context has no `.env` files at
all and the base URL silently falls back to `http://localhost:7000`.

Verified: with only `.env.production` present and no shell variable — exactly the Docker
build's situation — the bundle contains ``baseURL:`/` `` and zero occurrences of
`localhost:7000`.

### 3.12 Smaller items (no action, recorded so they aren't re-investigated)

- **Playwright the Python package is imported by the API** — `main.py` → `workers.queue`
  → `discovery_worker` → `scrapers.base_scraper` → `playwright.async_api`. The pip package
  must be installed in the cloud image, but **`playwright install` (the ~150 MB Chromium
  binary) must be skipped**. No browser is ever launched there.
- **Python version:** the code uses `enum.StrEnum` (Python **3.11+**) in 6 modules.
  `mcr.microsoft.com/playwright/python:v1.49.0-jammy` ships Python 3.10 → would break.
  Base image is `python:3.12-slim-bookworm`.
- **`.env` absence in the image:** pydantic-settings silently skips a missing `env_file`;
  real env vars take precedence. No change needed.
- **`--no-sandbox` / `--disable-dev-shm-usage`** already present in Chromium launch args
  (`base_scraper.py:201-205`). Local-only now; harmless.
- **UUID generation** is Python-side (`default=uuid.uuid4`) → no `pgcrypto`/`uuid-ossp`
  extension needed on Cloud SQL.
- **`pytest` ships in `requirements.txt`** and lands in the image (~5 MB). Leaving it —
  splitting requirements is restructuring for no real gain.
- **`/health` checks the DB only.** A green `/health` does **not** imply the worker is running.
- **Cloud Run request timeout 300 s** — the longest HTTP path is a Groq audit/chat (30 s
  ceiling per `groq_timeout_seconds`). Jobs are not HTTP-bound.
- **`max_jobs = 4`** (`queue.py:38`) is unchanged. A multi-city run fanning out to 6–12
  jobs will run 4 at a time with the rest waiting — identical to today's behavior.

---

## 4. Cost Model

us-central1, ~730 h/month.

| Item | Spec | Monthly |
|---|---|---|
| Cloud Run `leadgen-app` | 1 vCPU / 1 GiB, min=0, max=3 | **$0.00** — inside the free tier (2M req, 180k vCPU-s, 360k GiB-s/mo) at single-user volume |
| **Cloud SQL `leadgen-db`** | db-f1-micro + 10 GB SSD, zonal, PG 17 | **$11.10** |
| Cloud SQL external IPv4 | for the local Auth Proxy | **$0–5** — verify at the 24 h checkpoint |
| Artifact Registry | ~350 MB image (0.5 GB free) | $0.00 |
| Cloud Build | ~4 min/build (2,500 free min/mo) | $0.00 |
| Secret Manager | 4 secrets (6 versions free) | $0.00 |
| Cloud Logging | under 50 GiB free tier | $0.00 |
| Network egress | worker↔cloud chatter | ~$0.50 |
| Memorystore / GCE / GCS | **not used** | $0.00 |
| **Total** | | **≈ $12–17/mo ≈ $0.40–0.55/day** |

**24-hour trial cost ≈ $0.50.** With the $300 credit confirmed available, this is **$0 out
of pocket** — and at this burn the credit outlasts its own 90-day expiry many times over.

**Cloud SQL is the only service here without a free tier** — it is ~100% of the cost.

**Guardrail (Phase 0):** billing budget alert at $25 / $50 / $100 scoped to this project.
At this burn rate, any alert firing means something is misconfigured.

**If you later want $0.00 exactly:** move Postgres to an Always-Free `e2-micro` GCE VM
(us-central1, no external IP, reached by an IAP tunnel), with a nightly `pg_dump` to a
free-tier GCS bucket. Saves $11–16/mo at the cost of owning DB uptime, patching, and
backups on 1 GB RAM. Not recommended while the credit covers the managed option.

---

## 5. Deployment Phases

> Run in **PowerShell** (primary shell here) or Bash — all `gcloud` commands, no
> shell-specific syntax except where noted.

### Shared variables

```
PROJECT_ID      = lead-generation-project-502410
PROJECT_NUMBER  = 366622816060
REGION          = us-central1
BILLING_ACCOUNT = 01C0B3-E652F2-0968E9
SQL_INSTANCE    = leadgen-db     SQL_DB = lead_generator     SQL_USER = leadgen
AR_REPO         = leadgen
SERVICE         = leadgen-app
SA              = leadgen-run@lead-generation-project-502410.iam.gserviceaccount.com
LOCAL           = Auth Proxy 127.0.0.1:5433 → Cloud SQL · Memurai 127.0.0.1:6379 (unchanged)
```

---

### Phase 0 — Project & billing prerequisites  *(~10 min)*

1. Link billing (project currently has `billingEnabled: false`):
   ```
   gcloud billing projects link lead-generation-project-502410 --billing-account=01C0B3-E652F2-0968E9
   ```
2. `gcloud config set project lead-generation-project-502410`
3. Enable APIs:
   ```
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com sqladmin.googleapis.com secretmanager.googleapis.com compute.googleapis.com servicenetworking.googleapis.com logging.googleapis.com
   ```
   *(No `redis.googleapis.com` — Memorystore is not used. No `iap`/`oslogin` — no VM.)*
4. **Create a budget alert** in the billing console scoped to this project ($25/$50/$100).

**Exit:** `gcloud billing projects describe lead-generation-project-502410` → `billingEnabled: true`.

---

### Phase 1 — Network foundation  *(~10 min, one wait)*

Needed only so Cloud SQL can hold a private IP that Cloud Run reaches directly (§3.6).

1. Confirm the `default` VPC subnet (created by enabling `compute.googleapis.com`):
   ```
   gcloud compute networks subnets describe default --region=us-central1 --format="value(ipCidrRange)"
   ```
2. Reserve the peering range for Google-managed services:
   ```
   gcloud compute addresses create google-managed-services-default --global --purpose=VPC_PEERING --addresses=10.100.0.0 --prefix-length=16 --network=default
   ```
3. Establish the peering (can take several minutes):
   ```
   gcloud services vpc-peerings connect --service=servicenetworking.googleapis.com --ranges=google-managed-services-default --network=default --project=lead-generation-project-502410
   ```

**Exit:** `gcloud services vpc-peerings list --network=default` shows an active peering.
**Cost:** $0 — Direct VPC egress has no hourly charge (unlike a Serverless VPC Access
*connector*, which we deliberately do not use). **No firewall rules needed** — there is no VM.

---

### Phase 2 — Cloud SQL  *(~15 min, mostly waiting)*

Both private IP (for Cloud Run) and public IP (for the local Auth Proxy):
```
gcloud sql instances create leadgen-db --database-version=POSTGRES_17 --tier=db-f1-micro --region=us-central1 --network=projects/lead-generation-project-502410/global/networks/default --assign-ip --storage-size=10GB --storage-type=SSD --availability-type=zonal --backup-start-time=03:00
gcloud sql databases create lead_generator --instance=leadgen-db
gcloud sql users create leadgen --instance=leadgen-db --password=<GENERATED_STRONG_PASSWORD>
gcloud sql instances describe leadgen-db --format="value(ipAddresses[].ipAddress)"   # record BOTH
gcloud sql instances describe leadgen-db --format="value(connectionName)"            # for the Auth Proxy
```
*(~8–12 min to create. Generate the password locally, use it here and in Phase 3, then
discard the local copy — Secret Manager and the gitignored `.env.production` are the only
places it should persist.)*

**No `--authorized-networks` is set**, deliberately: the Auth Proxy authenticates with
your gcloud credentials over TLS, so nothing needs to be allowlisted and a changing home
IP never breaks it.

**Exit:** `RUNNABLE`, with both a `10.x` private address and a public address.

---

### Phase 3 — Secrets  *(~5 min)*

Read real values from `backend/.env` (gitignored — never print them into chat or any
committed file). **Cloud Run needs only three secrets** (§1.4):

| Secret | Value shape |
|---|---|
| `leadgen-database-url` | `postgresql+asyncpg://leadgen:<pw>@<SQL_PRIVATE_IP>:5432/lead_generator` |
| `leadgen-groq-api-key` | from `.env` → `GROQ_API_KEY` |
| `leadgen-basic-auth` | `user:password` for §3.1 (generated) |

**No `leadgen-redis-url`** — Cloud Run runs in `db` dispatch mode and never touches Redis.

Create each from a temp file (keeps values out of process listings), writing temp files to
the scratchpad directory — never the repo — and deleting them after:
```
gcloud secrets create leadgen-groq-api-key --replication-policy=automatic --data-file=<tmpfile>
```

**Exit:** `gcloud secrets list` shows all three.

---

### Phase 4 — Application changes  ✅ **COMPLETE**

The minimum set that makes this architecture work. **Nothing restructures the app** —
scrapers, enrichment, `JobTracker`, cooldown, and the ARQ worker itself are untouched.

**Result:** 386 backend tests pass (was 352 before; +34 new), 146 frontend tests pass.
Verified live against the local Postgres and Memurai — see the evidence list after the
tables below.

**One addition beyond the original plan:** `get_settings()` now honours an `ENV_FILE`
environment variable (defaulting to `.env`). Without it there is no way to point the same
checkout at `.env.production` for the operator processes, and the alternative — having
`worker-prod.ps1` parse the file and re-export every key into each child window — is
fragile string handling for something pydantic-settings already does properly. Real
environment variables still take precedence, so container deployments (no file at all)
are unaffected.

#### 4a. Dispatch mode (the core change)

| # | File | Change |
|---|---|---|
| 4.1 | `app/core/config.py` | Add `dispatch_mode: Literal["queue", "db"] = "queue"`. **`"queue"` is the default → local dev and all 280+ existing tests keep today's behavior exactly.** `"db"` is set only on Cloud Run. Also add `dispatcher_poll_seconds: float = 5.0`, `dispatcher_batch_size: int = 20`. |
| 4.2 | `app/services/discovery_service.py` | In `start_discovery`, accept `redis: ArqRedis \| None`. When `dispatch_mode == "db"`, create the run + job rows and **skip** `enqueue_job` / `attach_arq_job_id`. Everything else identical. |
| 4.3 | `app/routes/discovery.py` | `get_redis_pool` currently raises 503 when `app.state.arq_redis is None`. Make it return `None` in `db` mode instead, and keep the 503 in `queue` mode. |
| 4.4 | `app/main.py` | In `db` mode, skip the Redis pool creation and the `WorkerSupervisor` entirely — avoids a pointless startup error log in the cloud. |
| 4.5 | `app/repositories/discovery_job_repository.py` | **New** `claim_pending_jobs(session, *, limit)`: joins `discovery_runs` for `min_rating`, filters `status='pending' AND arq_job_id IS NULL`, orders by `created_at`, `LIMIT n`, `FOR UPDATE OF discovery_jobs SKIP LOCKED`. The `SKIP LOCKED` makes it safe even if two dispatchers ever run. |
| 4.6 | `app/workers/dispatcher.py` | **New**, ~60 lines. Async loop: claim a batch → `redis.enqueue_job(_JOB_NAMES[source], str(job.id), job.query, job.location, run.min_rating)` against **local** Memurai → `set_arq_job_id`, or `mark_job_enqueue_failed` on failure (reusing the exact error path `start_discovery` already has). Runnable as `python -m app.workers.dispatcher`. |

**Why a separate process, not an ARQ cron job:** ARQ cron jobs count against `max_jobs=4`.
With 4 long scrapes running, the dispatcher would be starved for 30–45 min. A separate
process has no such contention and is independently restartable.

**Why `arq_job_id IS NULL` is the right marker:** it's nullable, `unique`, and indexed
(`discovery_job.py:86`), and it's set *only* after a successful enqueue — so it means
exactly "not yet dispatched." No new column, no migration.

#### 4b. Deployment plumbing

| # | File | Change | Traces to |
|---|---|---|---|
| 4.7 | `app/core/config.py` | Add `db_pool_size: int = 3`, `db_max_overflow: int = 2`, `frontend_dist_dir: str = "frontend_dist"`, `basic_auth_user`/`basic_auth_password` (both `str \| None = None`); and make `get_settings()` honour `ENV_FILE` (default `.env`) | §3.7, §3.9, §3.1, §8 |
| 4.8 | `app/db/session.py` | Pass `pool_size=` / `max_overflow=` to `create_async_engine` | §3.7 |
| 4.9 | `app/main.py` | After all `include_router` calls, mount the SPA **only if the dist dir exists**: `StaticFiles(directory=..., html=True)`. Mounted last so API routes win. | §3.9 |
| 4.10 | `app/core/security.py` **(new)** + wired in `main.py` | HTTP Basic middleware, `secrets.compare_digest`, `/health` exempt, no-op when unconfigured | §3.1 |
| 4.11 | `Dockerfile` **(new, repo root)** | Multi-stage: `node:20-alpine` builds the frontend (base URL from `frontend/.env.production`, **not** a build ENV — §3.13) → `python:3.12-slim-bookworm` installs `requirements.txt` **but skips `playwright install`** (§3.12), copies `backend/` → `/app` and `dist/` → `/app/frontend_dist` | §2.2, §3.12, §3.13 |
| 4.11b | `.gitattributes` **(new, root)** | `*.sh text eol=lf` — `entrypoint.sh` is run by bash in a Linux image; checked out with CRLF on Windows it dies with a "bad interpreter" error | Windows checkout |
| 4.12 | `docker/entrypoint.sh` **(new)** | `set -e; alembic upgrade head; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}` | migrations |
| 4.13 | `.dockerignore` **(new, root)** | Exclude `**/.venv`, `**/node_modules`, `**/__pycache__`, `.git`, `**/.env*`, `backend/browser_profiles`, `backend/screenshots`, `frontend/dist`, `**/.pytest_cache` | image size |
| 4.14 | `.gcloudignore` **(new, root)** | Same exclusions. **Required** — without it `gcloud builds submit` falls back to the root `.gitignore`, which does *not* exclude `backend/.venv` or `frontend/node_modules`, and would upload hundreds of MB. | upload size |
| 4.15 | `frontend/.env.production` **(new)** | `VITE_API_BASE_URL=/` | §3.9 |
| 4.16 | `backend/.env.production.example` **(new)** | Template for the local side: `DATABASE_URL` on `127.0.0.1:5433`, `REDIS_URL` on `127.0.0.1:6379`, `SERPER_API_KEY`, `PAGESPEED_API_KEY`, `SCRAPER_HEADLESS=false`, `DISPATCH_MODE=queue`. Real file is **gitignored**. | §6.3, §3.10 |
| 4.17 | `backend/scripts/worker-prod.ps1` **(new)** | Sibling of `dev.ps1`: three windows — Cloud SQL Auth Proxy, dispatcher, ARQ worker | §8 |
| 4.18 | `backend/.gitignore` | Add `.env.production` | secrets |

**Tests required** (per `backend/CLAUDE.md`): `claim_pending_jobs` (claims only
undispatched pending rows; `SKIP LOCKED` behavior), the dispatcher loop (success, enqueue
failure → `mark_job_enqueue_failed`, empty batch), `start_discovery` in both dispatch
modes, and the Basic auth middleware (no creds → 401, wrong creds → 401, right creds →
pass, `/health` exempt, unconfigured → no-op).

**Docker layout invariants (the app depends on these):**
- `WORKDIR /app`, with `backend/`'s *contents* at `/app` → `/app/app/main.py`,
  `/app/alembic.ini`, `/app/alembic/`.
- `alembic.ini` uses `script_location = %(here)s/alembic` + `prepend_sys_path = .`, so
  `alembic upgrade head` must run with cwd `/app`.
- Frontend build output at `/app/frontend_dist`.

#### 4c. Phase 4 verification evidence (all confirmed)

Run against the real local Postgres and Memurai, not mocks:

- `DISPATCH_MODE=db` app boots with **no Redis**: lifespan completes, `app.state.arq_redis`
  is `None`, no error logged.
- `POST /start-discovery` in `db` mode created 3 rows — `status='pending'`,
  `arq_job_id=NULL` — with no queue involved.
- The dispatcher then claimed all 3, enqueued them into ARQ (`zcard arq:queue` = 3), and
  set each `arq_job_id` to the row's own id.
- **A second dispatch cycle claimed 0** — the idempotency guarantee holds, no double-run.
- Basic auth: unauthenticated `POST /start-discovery` → `401` with `code=unauthorized` and
  a `WWW-Authenticate` challenge header; `/health` still `200` unauthenticated.
- SPA mount does not shadow the API: `/` and `/index.html` serve HTML while `/health`,
  `/docs`, `/openapi.json`, and `/discovery-runs/stats` all still return their own
  responses.
- `ENV_FILE` override loads an alternate file; unset, `.env` still wins
  (`dispatch_mode=queue`, `environment=development`) — local dev is untouched.
- Production bundle contains ``baseURL:`/` `` and zero `localhost:7000` (see §3.13).
- All test rows and queued jobs created during verification were cleaned up (Redis db 15
  was used so a running worker could never pick up test jobs).

**Every change above is additive and default-off in `queue` mode**, which is why the
pre-existing suite needed no modification.

---

### Phase 5 — Build & push image  *(~6 min)*

```
gcloud artifacts repositories create leadgen --repository-format=docker --location=us-central1
gcloud builds submit --tag us-central1-docker.pkg.dev/lead-generation-project-502410/leadgen/app:v1 .
```
Run from the **repo root** — the Dockerfile needs both `backend/` and `frontend/`.

**Expected:** ~4–6 min, image ~350 MB (no Chromium).

---

### Phase 6 — Service account & deploy  *(~10 min)*

```
gcloud iam service-accounts create leadgen-run --display-name="Lead Generator Cloud Run"
```
Grant `roles/secretmanager.secretAccessor` on the project. *(No storage role — no bucket.
No `cloudsql.client` — private IP is reached over the VPC, not the connector.)*

```
gcloud run deploy leadgen-app \
  --image=us-central1-docker.pkg.dev/lead-generation-project-502410/leadgen/app:v1 \
  --region=us-central1 \
  --service-account=leadgen-run@lead-generation-project-502410.iam.gserviceaccount.com \
  --cpu=1 --memory=1Gi \
  --min-instances=0 --max-instances=3 \
  --concurrency=80 --timeout=300 \
  --network=default --subnet=default --vpc-egress=private-ranges-only \
  --allow-unauthenticated \
  --set-env-vars=... (see §6.1) \
  --set-secrets=...  (see §6.2)
```

**Why each non-obvious flag:**
- `--vpc-egress=private-ranges-only` — RFC-1918 traffic (Cloud SQL private IP) goes
  through the VPC; public traffic (Groq) takes the normal internet path. **No Cloud NAT
  needed, no NAT cost.**
- `--min-instances=0` — the worker is local, so nothing needs to stay warm. This is what
  keeps Cloud Run inside the free tier.
- `--max-instances=3` — safe only because `AUTO_START_ARQ_WORKER=false` (§3.3).
- `--allow-unauthenticated` — acceptable **only** because §3.1 Basic auth is in the app.
  If Phase 4.10 was skipped, do not deploy with this flag.

**Exit:** revision `Ready`; logs show Alembic applied migrations and uvicorn started; logs
show **no** `Started ARQ worker subprocess` and **no** Redis connection attempt.

---

### Phase 7 — Local bring-up  *(~20 min)*

1. Download the **Cloud SQL Auth Proxy** (`cloud-sql-proxy.x64.exe`) into `backend/scripts/`
   (gitignored) and authenticate: `gcloud auth application-default login`.
2. Fill `backend/.env.production` from `.env.production.example` (Phase 4.16) with the
   Cloud SQL password and the existing Serper/PageSpeed keys from `backend/.env`.
3. Run `backend/scripts/worker-prod.ps1` — three windows:
   - **Auth Proxy:** `cloud-sql-proxy.exe --port 5433 <CONNECTION_NAME>`
   - **Dispatcher:** `.venv\Scripts\python.exe -m app.workers.dispatcher`
   - **Worker:** `.venv\Scripts\python.exe -m arq app.workers.queue.WorkerSettings`

   All three load `.env.production`. `SCRAPER_HEADLESS` stays `false` — headed Chromium,
   residential IP, exactly as today.

**Exit:** proxy reports "ready for new connections"; dispatcher logs a poll cycle; worker
logs a Redis connection to local Memurai.

---

### Phase 8 — Verification & cost checkpoint

Run §7 in full. Then at T+24 h: billing console → Reports → filter to
`lead-generation-project-502410`, group by SKU, compare against §4 (expect ~$0.50), and
confirm whether the external-IPv4 line item appears.

---

## 6. Configuration Matrix

### 6.1 Cloud Run env vars

| Variable | Value | Why |
|---|---|---|
| `ENVIRONMENT` | `production` | |
| **`DISPATCH_MODE`** | **`db`** | **The core switch.** API creates `pending` rows and stops; no Redis. §0.2 |
| `AUTO_START_ARQ_WORKER` | `false` | No worker subprocess in the cloud. §3.3 |
| `SCRAPER_HEADLESS` | `true` | Defense in depth only — no browser runs here. §3.8 |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `3` / `2` | §3.7 |
| `FRONTEND_DIST_DIR` | `/app/frontend_dist` | SPA served same-origin |
| `CORS_ALLOWED_ORIGINS` | `["https://<service-url>"]` | Same-origin makes this mostly moot; set it so a future split frontend isn't a mystery |

**Deliberately left at code defaults:** all `scraper_*` delays/timeouts, `pagespeed_*`,
`groq_*`, `chat_history_max_messages=12`, `fuzzy_match_name_threshold=85`. These are tuned
behavior, not deployment concerns — do not change them.

### 6.2 Cloud Run secrets

| Env var | Secret |
|---|---|
| `DATABASE_URL` | `leadgen-database-url:latest` |
| `GROQ_API_KEY` | `leadgen-groq-api-key:latest` |
| `BASIC_AUTH_USER` / `BASIC_AUTH_PASSWORD` | `leadgen-basic-auth:latest` |

> **Changed 2026-08-18 (authorization work):** `BASIC_AUTH_USER` / `BASIC_AUTH_PASSWORD`
> are now **mandatory** whenever `ENVIRONMENT != development` — the app raises
> `InsecureConfigurationError` at startup instead of logging a warning and serving
> publicly. The Cloud Run service already injects them from `leadgen-basic-auth`, so this
> deployment is unaffected; a revision deployed *without* that secret will now fail its
> health check rather than come up open. Two optional vars were added: `BASIC_AUTH_ROLE`
> (default `owner`) and `AUTH_ACCOUNTS` (JSON array of extra `{username, password, role}`
> credentials). The local worker/dispatcher are unaffected — neither imports `app.main`.
> See `AI_ASSISTANT_ROADMAP.md` §3 Phase 1.

`REDIS_URL` is **not set** — unused in `db` mode. `SERPER_API_KEY` / `PAGESPEED_API_KEY`
are worker-only (§1.4). `HUNTER_API_KEY` / `OPENCORPORATES_API_KEY` stay unset by your
existing choice; the enrichers degrade gracefully.

### 6.3 Local `backend/.env.production` (gitignored)

| Variable | Value | Why |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://leadgen:<pw>@127.0.0.1:5433/lead_generator` | Through the Auth Proxy. **`127.0.0.1`, not `localhost`**; port 5433 avoids local Postgres on 5432. §3.10 |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | **Local Memurai — unchanged from today** |
| `DISPATCH_MODE` | `queue` | Local dispatcher/worker use the normal ARQ path |
| `SERPER_API_KEY` / `PAGESPEED_API_KEY` | from `backend/.env` | |
| `SCRAPER_HEADLESS` | `false` | **Keep headed** — better anti-bot, matches current behavior |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `3` / `2` (worker), `1` / `0` (dispatcher) | §3.7 |

`GROQ_API_KEY` is **not** needed locally — Groq is never called from `enrich_lead`.
`browser_profiles/` and `screenshots/` stay at their default relative paths on local disk.

---

## 7. Verification Checklist

**Infrastructure**
- [ ] `gcloud sql instances describe leadgen-db` → `RUNNABLE`, both private and public IP
- [ ] `gcloud run services describe leadgen-app --region=us-central1` → latest revision `Ready`

**Cloud application**
- [ ] `GET /health` → `{"status":"ok","database":"connected"}` (proves private IP + VPC egress + pool config)
- [ ] Logs show Alembic ran (applied, or already at head)
- [ ] Logs show **no** `Started ARQ worker subprocess` and **no** Redis connection attempt
- [ ] Root URL serves the SPA; Overview loads real data (proves `VITE_API_BASE_URL=/`)
- [ ] Browser console: no CORS errors

**Auth**
- [ ] Unauthenticated request → `401` with a `WWW-Authenticate` challenge
- [ ] Correct credentials → app loads
- [ ] `GET /health` reachable **without** credentials (Cloud Run probe must not break)

**The dispatch hand-off — the core of this design**
- [ ] Auth Proxy up: `psql -h 127.0.0.1 -p 5433 -U leadgen -d lead_generator -c "select 1"`
- [ ] `POST /start-discovery` **from the cloud UI** → `202` with `run_id` + 3 job ids
- [ ] Immediately after: rows exist with `status='pending'` **and `arq_job_id IS NULL`**
- [ ] Within ~5 s the dispatcher logs a claim, and `arq_job_id` becomes non-NULL
- [ ] Jobs move `pending` → `running` in the **cloud UI**, driven by the local worker
- [ ] `GET /discovery-jobs/{id}/events` in the cloud UI streams events written locally
- [ ] All three sources (`google_maps`, `facebook`, `serper`) reach `completed` — **the
      payoff of keeping scrapers local**: Maps and Facebook should behave as they do today,
      not CAPTCHA out
- [ ] Leads scraped locally appear in the cloud UI's Businesses view
- [ ] Chromium ran **headed** locally (visual confirmation)
- [ ] `browser_profiles/` and `screenshots/` written to local disk as before
- [ ] Cooldown still works: force a failure, confirm the next job logs `in cooldown for Ns
      — skipping` (proves local Redis cooldown state is intact)
- [ ] **Stop from the cloud UI mid-run** → the local worker honors it and the job reaches
      `stopped` (proves cooperative stop works across the split)
- [ ] **Start a discovery with the dispatcher stopped** → rows sit `pending` with
      `arq_job_id IS NULL`; start the dispatcher → they dispatch and run (proves §3.2)

**Feature surface (each hits a different integration)**
- [ ] `POST /leads/{id}/audit` → Groq audit returns and persists (`ai_*` columns) — **cloud-side Groq**
- [ ] `POST /leads/{id}/chat` → reply returns, history persists
- [ ] `POST /outreach/email/{id}` → email + 2 variations
- [ ] `POST /outreach-drafts/{id}/pdf` → PDF downloads (proves in-memory xhtml2pdf in the container)
- [ ] `PATCH /leads/{id}` pipeline stage change persists (Kanban drag)
- [ ] **With all local processes stopped**, audit/chat/outreach still work (proves the
      24/7 AI surface is independent of your PC)
- [ ] Cold start: leave idle 20 min, then load the UI — acceptable latency at `min-instances=0`

---

## 8. Day-to-day Runbook

**Start:** run `backend/scripts/worker-prod.ps1` → three windows (Auth Proxy, dispatcher,
worker). Same one-command pattern as the existing `dev.ps1`.

**Stop:** close all three. Prefer stopping any active run from the UI first — stop is
cooperative and checked in the per-lead loop. In-flight jobs killed by closing the window
stay at `running` (§10.1).

**Local dev is unaffected.** `dev.ps1` and `backend/.env` still point at local Postgres +
Memurai with `DISPATCH_MODE=queue` (the default). Nothing about your current workflow
changes.

**If jobs stay `pending`:**
1. Is the dispatcher window alive? It's the only thing that moves jobs out of `pending`.
2. Is the Auth Proxy window alive? The dispatcher can't poll without it.
3. `SELECT id, status, arq_job_id FROM discovery_jobs WHERE status='pending'` — if
   `arq_job_id IS NULL`, the dispatcher isn't running or can't reach the DB. If it's
   **non-NULL**, the ARQ job was lost from Memurai (§3.11): clear it and it'll re-dispatch —
   `UPDATE discovery_jobs SET arq_job_id = NULL WHERE id = '<id>'`.
4. Confirm `.env.production` uses `127.0.0.1`, **not** `localhost` (§3.10 — this machine
   resolves `localhost` to `::1` first and hangs silently).
5. Per this project's history: a stale PowerShell window from an earlier run can hold
   ports and silently answer with old config. Close old windows before re-diagnosing.

**If the Auth Proxy drops mid-job:** `pool_pre_ping=True` (`session.py:10`) lets the pool
recover once it's back, and `JobTracker` swallows and logs its own failures by design, so
tracking gaps won't kill a scrape. A long outage may still orphan a job at `running`.

---

## 9. Rollback & Teardown

**Roll back a bad revision** (instant, no rebuild):
```
gcloud run services update-traffic leadgen-app --region=us-central1 --to-revisions=<PREVIOUS>=100
```

**Stop nearly all spend, keep data:**
```
gcloud sql instances patch leadgen-db --activation-policy=NEVER
```
*(Cloud Run at `min-instances=0` already costs ~nothing when idle.)*

**Full teardown**, in order:
```
gcloud run services delete leadgen-app --region=us-central1
gcloud sql instances delete leadgen-db                    # export first if data matters
gcloud artifacts repositories delete leadgen --location=us-central1
# then: secrets, service account, VPC peering, reserved range
```
Export leads first if wanted: `gcloud sql export sql leadgen-db gs://…/dump.sql --database=lead_generator`.

**Reverting the code to pure-local** is a one-line change: `DISPATCH_MODE=queue`
everywhere. That's already the default, so simply not setting it restores today's exact
behavior — the dispatcher becomes dead code, harmless.

---

## 10. Known Gaps & Deliberate Non-Goals

Recorded so a future session doesn't treat them as bugs or "fix" them unprompted.

### 10.1 Optional follow-ups (not in this plan)

| Gap | Why it's out of scope |
|---|---|
| **Stale `running` jobs** when the worker is killed mid-job | `_run_job_with_safety_net` catches Python exceptions, not process kills. A startup reaper (mark `running` jobs older than `JOB_TIMEOUT_SECONDS` as failed) is ~20 lines + tests, but it's new application behavior, not deployment plumbing. |
| **No "worker offline" indicator** in the UI | Runs sit at `pending` with no explanation while your PC is off (§3.2). Would need a heartbeat key + endpoint + UI. Genuinely useful here, but it's a feature. |
| **Auto-recovery from Redis job loss** (§3.11) | Deliberately not built — a naive "re-dispatch anything pending >N min" rule would double-dispatch jobs legitimately waiting behind `max_jobs=4`. Manual remedy documented in §8. |
| **Structured JSON logging** | `logging.basicConfig` plain text reads fine in Cloud Logging. |
| **CI/CD** (Cloud Build trigger on push) | Manual `builds submit` + `run deploy` is right for a project under cost evaluation. |

### 10.2 If you later want the worker in the cloud

Because `auto_start_arq_worker` and `dispatch_mode` both exist, this is config + a rebuild
**with** `playwright install --with-deps chromium`, plus a real Redis (Memorystore, ~$36/mo):
`DISPATCH_MODE=queue`, `AUTO_START_ARQ_WORKER=true`, `SCRAPER_HEADLESS=true`,
`--min-instances=1 --max-instances=1 --no-cpu-throttling --cpu=2 --memory=4Gi`
(`max-instances=1` is **mandatory** — §3.3). Cost rises to ~$160/mo **and the
datacenter-IP CAPTCHA risk returns** — which is the reason this design exists. Earlier
all-cloud analyses are preserved in this file's git history.

### 10.3 Pre-existing project gaps, unchanged by this deployment

No overall lead-rating mechanic; Hunter/OpenCorporates unconfigured by choice; no "needs
manual review" flag; ARQ hard-timeout doesn't feed the cooldown system; real-time delivery
is polling-only (no SSE/WebSocket); outreach drafts regenerate fresh each time (no history).

---

## 11. Quick Reference — file/line index

Facts a future session would otherwise have to re-derive:

| Fact | Location |
|---|---|
| **Job row is created BEFORE the enqueue** (why DB-dispatch works) | `app/services/discovery_service.py:53-79` |
| **`arq_job_id` — nullable, unique, indexed** = "not yet dispatched" marker | `app/models/discovery_job.py:86` |
| `min_rating` lives on the **run**, not the job (dispatcher must join) | `app/models/discovery_job.py:62` |
| Existing enqueue-failure path to reuse | `job_tracking_service.mark_job_enqueue_failed:138-141` |
| Setting `arq_job_id` after enqueue | `discovery_job_repository.set_arq_job_id:38` |
| Worker is spawned by the API | `app/workers/supervisor.py:37-43` |
| Flag that disables that in the cloud | `app/core/config.py:25` (`auto_start_arq_worker`) |
| Headless default is `False` (keep for local) | `app/core/config.py:41` |
| One-worker-process invariant | `app/workers/discovery_worker.py:41-48` (`_browser_scrape_lock`) |
| Cooperative stop column (works across the split) | `app/models/discovery_job.py:109` (`stop_requested`) |
| Chromium container flags already present | `app/scrapers/base_scraper.py:201-205` |
| Only disk writes in the app | `base_scraper.py:188-189` (profiles), `:346-351` (screenshots) |
| PDF is in-memory, never on disk | `app/services/pdf_service.py:33-39` |
| Engine created at import, no pool args | `app/db/session.py:10` |
| Alembic reads the app settings | `alembic/env.py:16` |
| Frontend API base URL | `frontend/src/services/api.js:4` |
| Job timeout / retries / concurrency | `app/workers/queue.py:16-17,38` |
| Cooldown tiers (Redis-only state, now local) | `app/workers/cooldown.py:14-20` |
| Groq is NOT in the auto-enrich pipeline | `app/core/config.py:126-131` |
| Existing local dev script (2 windows) | `backend/scripts/dev.ps1` |
| Migration head | `16e8b92ef39c` (outreach drafts) |
| Test suites | `backend/` 386 pytest · `frontend/` 146 vitest (both green as of Phase 4) |
| **Added in Phase 4 — dispatch mode switch** | `app/core/config.py` (`dispatch_mode`) |
| **Added in Phase 4 — the dispatcher** | `app/workers/dispatcher.py` |
| **Added in Phase 4 — the claim query** | `discovery_job_repository.claim_pending_jobs` |
| **Added in Phase 4 — Basic auth** | `app/core/security.py` (`configure_basic_auth`) |
| **Added in Phase 4 — SPA mount** | `app/main.py::mount_frontend` |
| **Added in Phase 4 — alternate env file** | `get_settings()` reads `ENV_FILE` (default `.env`) |
| `unauthorized` added to the `ErrorCode` literal | `app/schemas/errors.py` |
| Operator-side script (3 windows) | `backend/scripts/worker-prod.ps1` |
| Operator-side config template | `backend/.env.production.example` |

---

## 12. Live deployment — operating guide

**This section reflects the actual deployed state as of 2026-08-17, not a plan.**

### 12.1 URLs and credentials

| | Value |
|---|---|
| App URL | `https://leadgen-app-366622816060.us-central1.run.app` |
| Basic auth | username `leadgen-admin`, password stored in Secret Manager (`leadgen-basic-auth-user`/`leadgen-basic-auth-password`) — not repeated here; retrieve with `gcloud secrets versions access latest --secret=leadgen-basic-auth-password` if lost |
| Cloud SQL instance | `lead-generation-project-502410:us-central1:leadgen-db` |
| Current image | `us-central1-docker.pkg.dev/lead-generation-project-502410/leadgen/app:v3` |
| Cloud Run revision | `leadgen-app-00005-rx8` |

The browser will show a native login prompt on first visit (HTTP Basic) — enter the credentials above once per browser session.

### 12.2 Do you need to run the local worker every time?

**Only if you want discovery (scraping) to run.** This is the direct consequence of the architecture decision in §0.1/§2: scraping stays on your machine so it runs from a residential IP instead of a GCP datacenter IP (which gets CAPTCHA'd). Everything else does **not** need your PC:

| Feature | Needs local worker running? |
|---|---|
| Viewing the app / browsing existing leads | ❌ No — Cloud Run + Cloud SQL, always available |
| Pipeline (Kanban), lead detail, filters | ❌ No |
| AI audit / chat / outreach (email, WhatsApp, proposal) / PDF export | ❌ No — all cloud-side Groq calls |
| **Starting a new discovery run and having it actually scrape** | ✅ **Yes** |

If you click "Start Discovery" with the local worker off, the request still succeeds (`202`, run created) — the job rows just sit at `pending` until you start the worker. **Nothing is lost**, it just waits. There's no in-app indicator that the worker is offline yet (a known, documented gap — §10.1).

### 12.3 How to start the local worker

```
backend\scripts\worker-prod.ps1
```

Run this from a PowerShell window at the repo's `backend/` directory (or anywhere — the script resolves its own paths). It opens **three** windows:

1. **Cloud SQL Auth Proxy** — connects to `leadgen-db` on `127.0.0.1:5433`
2. **Dispatcher** — polls Cloud SQL every 5s for jobs the cloud API created, hands them to your local ARQ queue
3. **ARQ worker** — the actual scraper: headed Chromium, PageSpeed/Wappalyzer enrichment, writes results back to Cloud SQL

Prerequisites already in place: `backend/.env.production` (gitignored, has your real DB password and Serper/PageSpeed keys), `backend/scripts/cloud-sql-proxy.x64.exe` (gitignored, ~31 MB), and Memurai must be running locally (it's installed as a Windows service, so it should already be up).

**To stop:** close all three windows. Prefer stopping any in-progress run from the UI first (Stop button) — it's cooperative and honors a clean shutdown; killing the window mid-scrape just orphans that job at `running` in the DB (harmless, just cosmetic — see §10.1).

**You do not need to redeploy or touch Cloud Run to use the worker** — it talks to the already-running Cloud SQL instance directly. Starting/stopping the worker has zero effect on the Cloud Run service's availability.

### 12.4 What actually happened in Phase 8 verification — issues found and fixed

Three real issues were found and fixed during verification, all now resolved in the live deployment:

1. **`CLOUD_SQL_CONNECTION_NAME` crashed the dispatcher/worker on startup** — added to `.env.production` for the PowerShell script's own use, but `pydantic-settings` rejected it as an unrecognized key. Fixed by declaring it as a proper (if functionally unused-by-the-app) `Settings` field. `app/core/config.py`.

2. **Groq's `llama-3.3-70b-versatile` model no longer exists** — confirmed via a live call to Groq's own `/models` endpoint. This broke all four AI features identically (audit, chat, email, WhatsApp, proposal) and would have failed the same way in local dev, unrelated to deployment. Tried `qwen/qwen3.6-27b` next — rejected by Groq's own server-side validation (`400 json_validate_failed`): it's a reasoning model that doesn't reliably put valid JSON in the `content` field under `response_format: json_object`. Settled on **`openai/gpt-oss-20b`**, confirmed live (direct API calls with the actual audit/email/proposal prompts) to return clean, schema-matching JSON every time. This is now the default in `app/core/config.py` — fixed for local dev too, not just the deployed app.

3. **Cloud Run's GFE (Google Front End) returns a raw `411` for any POST with no body/no `Content-Length`** — hit on `/leads/{id}/audit` and `/outreach-drafts/{id}/pdf`, both of which take no request body. This isn't a bug in the app — Cloud Run's edge layer rejects the request before it ever reaches the container. **If you or the frontend ever call a bodyless POST endpoint directly (e.g. via `curl`), send an explicit empty JSON body (`-d '{}'`)** rather than omitting `-d` entirely. The actual frontend (apisauce/axios) already sets `Content-Length` correctly on every request, so this only matters for manual testing.

One item flagged but **not fixed** (pre-existing in the original code, not deployment-related, functionally harmless):

- **Chromium profiles land outside the repo.** `base_scraper.py` passes a relative path (`browser_profiles/google_maps`) to `playwright.chromium.launch_persistent_context`, and Playwright resolves it against its own browser install directory rather than the worker process's working directory. Confirmed live: profiles are actually accumulating at `%LOCALAPPDATA%\ms-playwright\chromium-1148\chrome-win\browser_profiles\` on this machine, not `backend/browser_profiles/`. The anti-bot benefit (cookies/history persisting across runs) still works — it's the same fixed location every run — this only matters if you go looking for the profiles at the path the code/docs imply. One-line fix if you want it: resolve to an absolute path before passing it to `launch_persistent_context`.

### 12.5 What was proven live, with real data

- A real discovery run (`dental clinics`, Karachi) was started from the deployed cloud UI/API and picked up by the local worker within seconds
- **Neither `google_maps` nor `facebook` got CAPTCHA'd** — validates the entire premise of keeping scrapers on a residential IP
- 14 leads scraped and enriched (real PageSpeed scores, Wappalyzer tech stacks), 12 survived cross-source fuzzy dedup, all visible through the cloud API within seconds of being written locally
- Cooperative stop verified via both of its code paths (`_run_scrape_job`'s per-lead check, and `_run_browser_scrape_job`'s `JobStoppedError` catch)
- All four Groq AI features confirmed end-to-end on the real lead above: audit, chat (correctly grounded in the audit + PageSpeed data), email, WhatsApp, and proposal (all 5 required sections, correct order)
- PDF export confirmed (real 2-page PDF, correct content-type)
- Pipeline stage update (Kanban drag equivalent) confirmed

Not tested (optional, low-risk): 20-minute idle cold-start latency; forcing a real cooldown/CAPTCHA escalation (would require deliberately triggering a block — not worth doing to a working demo).
