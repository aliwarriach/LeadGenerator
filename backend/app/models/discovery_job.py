import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DiscoveryJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED_COOLDOWN = "skipped_cooldown"
    STOPPED = "stopped"


# Terminal states a job can't leave without a new run — used to decide which
# jobs a run-level stop should still bother flipping stop_requested on.
TERMINAL_JOB_STATUSES = frozenset(
    {
        DiscoveryJobStatus.COMPLETED,
        DiscoveryJobStatus.FAILED,
        DiscoveryJobStatus.BLOCKED,
        DiscoveryJobStatus.SKIPPED_COOLDOWN,
        DiscoveryJobStatus.STOPPED,
    }
)


class DiscoveryEventType(StrEnum):
    JOB_STATUS_CHANGED = "job_status_changed"
    SCRAPER_STARTED = "scraper_started"
    BUSINESS_PROCESSING = "business_processing"
    LEAD_SAVED = "lead_saved"
    RATE_LIMIT_DELAY = "rate_limit_delay"
    ERROR = "error"
    WARNING = "warning"
    STOPPED = "stopped"


class DiscoveryRun(Base):
    """One row per POST /start-discovery call.

    Deliberately immutable after insert — up to len(cities) x 3 sibling jobs
    can write concurrently, and there's no single safe owner for run-level
    mutable state. Status/timestamps/warnings are derived at read time from
    the child DiscoveryJob rows instead (see job_tracking_service).
    """

    __tablename__ = "discovery_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    country: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(512), nullable=False)
    custom_niche: Mapped[str] = mapped_column(String(256), nullable=False)
    min_rating: Mapped[float | None] = mapped_column(Float)
    total_jobs: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DiscoveryJob(Base):
    """One row per (source x city) fan-out job — the canonical, frontend-facing
    id, created before the ARQ job is enqueued so the row always exists before
    the worker could possibly start it.

    Owned by exactly one worker coroutine for its lifecycle (safe to mutate
    directly), except `stop_requested`, which the stop endpoint also writes —
    a single boolean UPDATE, safe as a second writer.
    """

    __tablename__ = "discovery_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discovery_runs.id"), nullable=False, index=True
    )
    arq_job_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    query: Mapped[str] = mapped_column(String(512), nullable=False)
    location: Mapped[str] = mapped_column(String(512), nullable=False)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DiscoveryJobStatus.PENDING, index=True
    )
    current_business_name: Mapped[str | None] = mapped_column(String(512))

    leads_found_session: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    leads_saved_session: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extraction_failures_session: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Mirrors the ErrorDetail envelope (app/schemas/errors.py) so a terminal
    # non-success job carries the same code/message/retryable vocabulary the
    # API surfaces everywhere else.
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(2048))
    error_retryable: Mapped[bool | None] = mapped_column(Boolean)
    error_retry_after_seconds: Mapped[int | None] = mapped_column(Integer)

    stop_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DiscoveryJobEvent(Base):
    """Append-only live event log for one DiscoveryJob.

    `id` is a plain autoincrementing bigint (not a UUID) specifically because
    it doubles as the monotonic cursor for `GET .../events?after=<id>` —
    offset pagination would skip/duplicate rows against a table that's
    actively growing while the frontend polls it.
    """

    __tablename__ = "discovery_job_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discovery_jobs.id"), nullable=False, index=True
    )

    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    code: Mapped[str | None] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(String(1024), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
