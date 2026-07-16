import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LeadSource(StrEnum):
    GOOGLE_MAPS = "google_maps"
    FACEBOOK = "facebook"
    SERPER = "serper"


class PipelineStage(StrEnum):
    NEW_LEAD = "new_lead"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    WON = "won"


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(String(512), nullable=False)
    location: Mapped[str | None] = mapped_column(String(1024))
    website: Mapped[str | None] = mapped_column(String(2048))
    website_domain: Mapped[str | None] = mapped_column(String(512), index=True)
    phone: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    has_website: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rating: Mapped[float | None] = mapped_column(Float)
    category: Mapped[str | None] = mapped_column(String(256))

    # CRM fields — manually set via PATCH /leads/{id}, never touched by the
    # discovery/enrichment pipeline (re-scraping an existing lead must not
    # reset sales progress). estimated_revenue_level has no automatic source
    # (nothing in the pipeline can derive it reliably) so it stays null until
    # a user sets it.
    estimated_revenue_level: Mapped[str | None] = mapped_column(String(64))
    pipeline_stage: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PipelineStage.NEW_LEAD, server_default=PipelineStage.NEW_LEAD
    )

    query: Mapped[str | None] = mapped_column(String(512))
    search_location: Mapped[str | None] = mapped_column(String(512))

    # Deterministic hash of normalized (source, name, phone/website/location) used
    # for idempotent upserts — lets retried/duplicate scrape jobs overwrite in place
    # instead of creating duplicate rows.
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    # Website Quality Score (0-100, PageSpeed performance/seo/best-practices
    # average). Only ever set when `has_website` is true — None means either
    # "no website" or "not enriched yet", never a rating of the business
    # itself. NOT the overall client rating (separate mechanic, built later).
    website_score: Mapped[float | None] = mapped_column(Float)
    website_score_details: Mapped[dict | None] = mapped_column(JSONB)

    # PageSpeed performance/SEO broken out as their own fields (also present,
    # bundled with best_practices, inside website_score_details) since these
    # two are commonly filtered/sorted on independently of the combined score.
    pagespeed_score: Mapped[float | None] = mapped_column(Float)
    seo_score: Mapped[float | None] = mapped_column(Float)
    performance_issues: Mapped[list[str] | None] = mapped_column(ARRAY(String(512)))

    emails: Mapped[list[str] | None] = mapped_column(ARRAY(String(320)))
    tech_stack: Mapped[list[str] | None] = mapped_column(ARRAY(String(128)))
    is_registered: Mapped[bool | None] = mapped_column(Boolean)
    logo_valid: Mapped[bool | None] = mapped_column(Boolean)
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # AI website audit (Groq) — on-demand only, via POST /leads/{id}/audit, not
    # part of the automatic enrich_lead() pipeline. All null until requested.
    ai_ui_score: Mapped[int | None] = mapped_column(Integer)
    ai_conversion_score: Mapped[int | None] = mapped_column(Integer)
    ai_content_score: Mapped[int | None] = mapped_column(Integer)
    ai_trust_score: Mapped[int | None] = mapped_column(Integer)
    ai_issues: Mapped[list[str] | None] = mapped_column(ARRAY(String(512)))
    ai_summary: Mapped[str | None] = mapped_column(String(4096))
    ai_audited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
