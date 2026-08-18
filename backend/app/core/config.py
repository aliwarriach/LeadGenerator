import os
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.permissions import Role
from app.core.principal import AuthAccount


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Lead Generator API"
    environment: str = "development"
    # "127.0.0.1" rather than "localhost": on machines where localhost resolves
    # to ::1 (IPv6) first, connecting hangs/times out entirely if the DB/Redis
    # server only binds the IPv4 loopback (Memurai on Windows does this) —
    # confirmed to cause exactly this failure during local setup.
    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/lead_generator"
    db_echo: bool = False
    # SQLAlchemy's defaults (5 + 10 overflow) allow 15 connections per process.
    # A small managed Postgres instance caps out around 25 total, and several
    # processes share it (API instances + the ARQ worker + the dispatcher), so
    # the per-process ceiling is lowered rather than left to chance.
    db_pool_size: int = 3
    db_max_overflow: int = 2

    # Queue (ARQ / Redis)
    redis_url: str = "redis://127.0.0.1:6379/0"
    # Spawns `python -m arq app.workers.queue.WorkerSettings` as a child
    # process of the API on startup, so a single `uvicorn app.main:app` run
    # is enough for local dev. Set False if the worker is run/scaled as its
    # own deployment (e.g. production, or multiple uvicorn workers sharing
    # one queue) — each API process would otherwise spawn its own worker.
    auto_start_arq_worker: bool = True

    # How a queued discovery job reaches the ARQ worker.
    #   "queue" — the API enqueues into Redis itself. Local development, and
    #             any deployment where the API and the worker share a Redis.
    #   "db"    — the API only writes the DiscoveryJob row (already created
    #             before enqueue anyway) and stops there; app/workers/
    #             dispatcher.py claims pending rows and enqueues them into the
    #             Redis its own worker consumes. This is what allows the API
    #             and the worker to live on hosts that cannot share a Redis —
    #             e.g. the API on Cloud Run, the scrapers on an operator
    #             machine behind NAT. In this mode the API needs no Redis.
    dispatch_mode: Literal["queue", "db"] = "queue"
    dispatcher_poll_seconds: float = 5.0
    dispatcher_batch_size: int = 20

    # Built SPA served by this API when the directory exists — same-origin in
    # production, which is why CORS is a non-issue there. Absent in local dev,
    # where Vite serves the frontend on its own port.
    frontend_dist_dir: str = "frontend_dist"

    # HTTP Basic credentials guarding the whole app (except /health, which the
    # platform health check calls unauthenticated). Both unset — the default —
    # disables the check entirely, keeping local dev and the test suite open.
    # That default is only tolerable because configure_basic_auth() refuses to
    # start a non-development environment without credentials.
    basic_auth_user: str | None = None
    basic_auth_password: str | None = None
    # Role carried by the primary credential above.
    basic_auth_role: Role = Role.OWNER

    # Additional Basic credentials, each with its own role — a JSON array in
    # the environment, e.g.
    #   AUTH_ACCOUNTS=[{"username":"analyst","password":"...","role":"viewer"}]
    # This is what makes the role system real without a users table: a
    # read-only account can be handed out without granting write access. See
    # app/core/principal.py::AuthAccount for why roles live on credentials.
    auth_accounts: list[AuthAccount] = []

    # Role granted when no credentials are configured at all (local dev, tests).
    # Owner by default so development behaves exactly as it did before roles
    # existed; set to "viewer" to exercise a lower-privilege path locally.
    unauthenticated_role: Role = Role.OWNER

    # Passwords shorter than this only produce a startup warning, not a
    # failure — a weak password still protects the app, and refusing to boot
    # over it would turn a security nudge into an outage.
    min_auth_password_length: int = 12

    # Security response headers (app/core/security_headers.py). The CSP is
    # overridable because it has to match whatever the built SPA loads — the
    # default matches the current build (self-hosted JS/CSS + Google Fonts).
    security_headers_enabled: bool = True
    content_security_policy: str = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "upgrade-insecure-requests"
    )

    # Cloud SQL instance connection name (project:region:instance). The app
    # itself never reads this — DATABASE_URL already points at the Auth
    # Proxy's local port — but it lives in the same .env.production the
    # operator scripts load, and pydantic-settings rejects unrecognized keys
    # by default, so it must be a real field rather than a stray env var.
    # worker-prod.ps1 reads it directly to start the proxy on the right instance.
    cloud_sql_connection_name: str | None = None

    # CORS — origins allowed to call this API from a browser (the frontend's
    # dev server). Vite's default port is 5173, but it falls forward to 5174+
    # if 5173 is already taken by another process; both localhost and
    # 127.0.0.1 are listed since browsers treat them as distinct origins.
    cors_allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ]

    # Scraper behavior
    scraper_headless: bool = False
    scraper_max_results: int = 50
    scraper_max_retries: int = 3
    scraper_action_delay_min: float = 0.5
    scraper_action_delay_max: float = 2.0
    scraper_rate_limit_min: float = 1.5
    scraper_rate_limit_max: float = 4.0
    scraper_search_delay_min: float = 4.0
    scraper_search_delay_max: float = 9.0
    scraper_navigation_timeout_ms: int = 30_000
    scraper_screenshot_dir: str = "screenshots"
    # On-disk Chromium profile dir (cookies/local storage persist across
    # runs, one subfolder per source) — a free, zero-IP-rotation mitigation
    # for "looks like a fresh bot every single run." Not a substitute for a
    # real proxy pool; see ScraperConfig.profile_dir / _launch_persistent_context.
    scraper_profile_dir: str = "browser_profiles"

    # Locale / geo fingerprint
    scraper_locale: str = "en-US"
    scraper_timezone: str = "Asia/Karachi"
    scraper_geolocation_lat: float = 24.8607
    scraper_geolocation_lon: float = 67.0011
    scraper_viewport_width: int = 1920
    scraper_viewport_height: int = 1080

    # Proxy: "http://user:pass@host:port" or None to disable
    scraper_proxy_server: str | None = None
    scraper_proxy_username: str | None = None
    scraper_proxy_password: str | None = None

    scraper_user_agents: list[str] = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    ]

    # Serper.dev search API (https://serper.dev) — organic web search used to
    # discover businesses outside Google Maps/Facebook coverage.
    serper_api_key: str | None = None
    serper_base_url: str = "https://google.serper.dev/search"
    serper_max_results: int = 20
    serper_timeout_seconds: float = 15.0
    serper_max_retries: int = 3
    serper_country: str = "pk"
    serper_language: str = "en"

    # Enrichment: Google PageSpeed Insights — drives the per-lead Website
    # Quality Score. Works without a key at low volume; a key raises quota.
    pagespeed_api_key: str | None = None
    pagespeed_base_url: str = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    # A real Lighthouse run against a live site commonly takes 40-60s+ — 25s
    # (this setting's original value) meant PSI would time out on almost
    # every call. Confirmed against a real site: ~55s to complete.
    pagespeed_timeout_seconds: float = 75.0
    pagespeed_strategy: str = "mobile"

    # Enrichment: Hunter.io domain email search (free tier is heavily rate-limited)
    hunter_api_key: str | None = None
    hunter_base_url: str = "https://api.hunter.io/v2/domain-search"
    hunter_timeout_seconds: float = 10.0
    hunter_max_emails: int = 3

    # Enrichment: Wappalyzer tech-stack detection — local pattern matching
    # against fetched HTML/headers, no external API or key required.
    wappalyzer_enabled: bool = True
    wappalyzer_fetch_timeout_seconds: float = 10.0

    # Enrichment: OpenCorporates company registration lookup (optional)
    opencorporates_api_key: str | None = None
    opencorporates_base_url: str = "https://api.opencorporates.com/v0.4/companies/search"
    opencorporates_timeout_seconds: float = 10.0

    # Enrichment: Clearbit Logo — keyless quick domain validation.
    # Disabled by default: logo.clearbit.com no longer resolves (confirmed via
    # direct DNS lookup — NXDOMAIN, not a per-domain failure), so every call
    # was failing identically and just adding a DNS-timeout round trip plus
    # log noise per lead. Re-enable if Clearbit restores the host, or point
    # clearbit_logo_base_url at a replacement service.
    clearbit_logo_enabled: bool = False
    clearbit_logo_base_url: str = "https://logo.clearbit.com"
    clearbit_timeout_seconds: float = 8.0

    # AI website audit (Groq) — on-demand only (POST /leads/{id}/audit), not
    # part of the automatic per-lead enrichment pipeline: an LLM call per
    # lead is real cost/latency that shouldn't be spent on every scraped
    # lead regardless of whether anyone ever looks at it. Groq's OpenAI-
    # compatible chat completions endpoint, called directly via httpx rather
    # than pulling in their SDK for one endpoint.
    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1/chat/completions"
    # Verify this against Groq's current model list before relying on it —
    # available models change over time; override via .env if it's retired.
    # llama-3.3-70b-versatile was retired by Groq (confirmed via a live
    # /openai/v1/models call — no longer in the catalog, every Groq-backed
    # endpoint returned a 404). qwen/qwen3.6-27b was tried next and rejected
    # by Groq's own server-side validation (400 json_validate_failed) — it's
    # a reasoning model that doesn't reliably put valid JSON in `content`
    # under response_format=json_object, only in Groq's separate `reasoning`
    # field. openai/gpt-oss-20b was confirmed live (direct API call, the
    # actual audit prompt) to return clean schema-matching JSON in `content`
    # every time, with its chain-of-thought correctly segregated into
    # `reasoning` instead of leaking into the field this app parses.
    groq_model: str = "openai/gpt-oss-20b"
    groq_timeout_seconds: float = 30.0
    # Sent as `max_tokens` on every Groq call. Uncapped generation is an open
    # cost/latency tap on top of having no other budget in front of these
    # endpoints — 2048 comfortably covers the longest structured response
    # (the 5-section proposal) with headroom, and bounds free-form chat
    # replies to the same ceiling.
    groq_max_tokens: int = 2048
    # Per-`Principal.subject` call budget shared across every Groq-backed
    # route (audit, chat, outreach x3) — see SecurityIssues.md M-5.
    llm_rate_limit_per_hour: int = 200
    # Retries here are for malformed/unparseable JSON output specifically
    # (an LLM occasionally returns non-conforming JSON despite json_object
    # mode), not general network flakiness — one retry is enough to smooth
    # over that without masking a genuinely broken prompt/response.
    groq_max_retries: int = 2
    # Body/heading text sent to the model is truncated to this many
    # characters to keep the prompt small and bounded regardless of how
    # large the target page is.
    website_content_max_chars: int = 3000
    website_content_fetch_timeout_seconds: float = 10.0

    # AI sales chatbot (Groq) — POST/GET /leads/{id}/chat. Full conversation
    # history is persisted forever, but only the most recent N messages are
    # replayed as context on each request — keeps prompt size bounded for
    # Groq's free-tier rate limits regardless of how long a conversation gets.
    chat_history_max_messages: int = 12

    # Normalization / deduplication
    default_phone_region: str = "PK"
    fuzzy_match_name_threshold: float = 85.0

    # Shared HTTP client used for enrichment calls within a single scrape job.
    # Sites commonly WAF-block requests with no/generic User-Agent (e.g. httpx's
    # default) even when the request is otherwise legitimate, so this uses a
    # realistic browser UA rather than none.
    enrichment_client_timeout_seconds: float = 90.0
    enrichment_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )


def effective_cors_origins(settings: Settings) -> list[str]:
    """The CORS origin list actually used for `CORSMiddleware`.

    `cors_allowed_origins`' default is the Vite dev server's localhost
    ports, which is correct for local development but must never reach a
    deployed environment as a silent fallback: a revision deployed without
    CORS_ALLOWED_ORIGINS set would otherwise allow credentialed
    cross-origin reads from any page served on those local ports
    (SecurityIssues.md L-1). Deployments are same-origin (the SPA is served
    by this API — see `main.mount_frontend`), so an empty list is the
    correct default outside development; set CORS_ALLOWED_ORIGINS explicitly
    if a deployment ever needs a separate frontend origin.
    """
    if settings.environment == "development":
        return settings.cors_allowed_origins
    if settings.cors_allowed_origins == Settings.model_fields["cors_allowed_origins"].default:
        return []
    return settings.cors_allowed_origins


@lru_cache
def get_settings() -> Settings:
    # ENV_FILE lets one checkout drive two environments without duplicating the
    # code: `.env` for local development, `.env.production` for the operator
    # machine that runs the dispatcher/worker against the deployed database.
    # Real environment variables still win over whichever file is loaded, which
    # is what makes container deployments (no file at all) work unchanged.
    return Settings(_env_file=os.environ.get("ENV_FILE", ".env"))
