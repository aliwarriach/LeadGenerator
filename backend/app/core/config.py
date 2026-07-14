from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Queue (ARQ / Redis)
    redis_url: str = "redis://127.0.0.1:6379/0"

    # CORS — origins allowed to call this API from a browser (the frontend's
    # dev server). Vite's default port is 5173; both localhost and 127.0.0.1
    # are listed since browsers treat them as distinct origins.
    cors_allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
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

    # Enrichment: Clearbit Logo — keyless quick domain validation
    clearbit_logo_base_url: str = "https://logo.clearbit.com"
    clearbit_timeout_seconds: float = 8.0

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
