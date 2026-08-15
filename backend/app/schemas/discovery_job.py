import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.errors import ErrorCode

DiscoveryJobStatusLiteral = Literal[
    "pending", "running", "completed", "failed", "blocked", "skipped_cooldown", "stopped"
]
DiscoverySourceLiteral = Literal["google_maps", "facebook", "serper"]


class DiscoveryJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    source: DiscoverySourceLiteral
    query: str
    location: str
    status: DiscoveryJobStatusLiteral
    current_business_name: str | None
    leads_found_session: int
    leads_saved_session: int
    extraction_failures_session: int
    total_leads_scraped_by_source: int | None = None

    error_code: ErrorCode | None
    error_message: str | None
    error_retryable: bool | None
    error_retry_after_seconds: int | None

    stop_requested: bool
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class DiscoveryJobListResponse(BaseModel):
    items: list[DiscoveryJobResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class DiscoveryRunWarning(BaseModel):
    code: Literal["high_failure_rate"]
    source: DiscoverySourceLiteral
    message: str


class DiscoveryRunResponse(BaseModel):
    id: uuid.UUID
    country: str
    city: str
    custom_niche: str
    min_rating: float | None
    created_at: datetime

    # Derived at read time from child jobs — DiscoveryRun itself has no
    # status/timestamp columns (see app/models/discovery_job.py).
    status: DiscoveryJobStatusLiteral
    started_at: datetime | None
    finished_at: datetime | None
    warnings: list[DiscoveryRunWarning]
    jobs: list[DiscoveryJobResponse]


class DiscoveryRunSummary(BaseModel):
    id: uuid.UUID
    country: str
    city: str
    custom_niche: str
    min_rating: float | None
    created_at: datetime
    status: DiscoveryJobStatusLiteral


class DiscoveryRunListResponse(BaseModel):
    items: list[DiscoveryRunSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class SourcePerformance(BaseModel):
    source: DiscoverySourceLiteral
    avg_leads_saved: float


class DiscoveryRunStatsResponse(BaseModel):
    """Duration/leads figures are aggregated over fully-completed runs only
    (see derive_run_status) — stopped/failed/blocked runs would skew a
    "typical run" figure, so they're excluded rather than averaged in.
    success_rate is the one exception: it's defined precisely to measure
    those excluded outcomes, so it counts every terminal run instead."""

    completed_run_count: int
    avg_duration_seconds: float | None
    avg_leads_saved: float | None
    total_leads_saved: int
    # completed / (completed + failed + blocked + stopped + skipped_cooldown)
    # among terminal runs; None if no run has reached a terminal state yet.
    success_rate: float | None
    # Per-source average leads saved per job, across completed runs, ranked
    # best-first. Empty until at least one completed run exists.
    leads_by_source: list[SourcePerformance]


class DiscoveryJobEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: uuid.UUID
    event_type: str
    code: ErrorCode | None
    message: str
    payload: dict | None
    created_at: datetime


class DiscoveryJobEventListResponse(BaseModel):
    items: list[DiscoveryJobEventResponse]
    next_cursor: int | None
