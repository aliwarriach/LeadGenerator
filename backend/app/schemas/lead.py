import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

LeadSortBy = Literal["created_at", "rating", "website_score", "name"]
SortOrder = Literal["asc", "desc"]
PipelineStageLiteral = Literal["new_lead", "contacted", "qualified", "proposal", "won"]


class LeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    location: str | None
    website: str | None
    website_domain: str | None
    phone: str | None
    source: Literal["google_maps", "facebook", "serper"]
    has_website: bool
    rating: float | None
    category: str | None
    query: str | None = Field(description="The custom_niche search term used to discover this lead")
    search_location: str | None

    # CRM fields — set via PATCH /leads/{id}, never by the discovery pipeline.
    estimated_revenue_level: str | None
    pipeline_stage: PipelineStageLiteral

    # Website Quality Score (0-100) — only ever set when has_website is true.
    # NOT the overall client rating; that mechanic doesn't exist yet.
    website_score: float | None
    website_score_details: dict[str, float] | None
    pagespeed_score: float | None
    seo_score: float | None
    performance_issues: list[str] | None
    emails: list[str] | None
    tech_stack: list[str] | None
    is_registered: bool | None
    logo_valid: bool | None
    enriched_at: datetime | None

    # AI website audit (Groq) — on-demand only via POST /leads/{id}/audit;
    # all null until an audit has actually been requested for this lead.
    ai_ui_score: int | None
    ai_conversion_score: int | None
    ai_content_score: int | None
    ai_trust_score: int | None
    ai_issues: list[str] | None
    ai_summary: str | None
    ai_audited_at: datetime | None

    raw_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class LeadUpdateRequest(BaseModel):
    """PATCH /leads/{id} body. Both fields optional and independent — only
    what's provided gets updated; omitted fields are left untouched."""

    pipeline_stage: PipelineStageLiteral | None = None
    estimated_revenue_level: str | None = Field(default=None, max_length=64)


class LeadListResponse(BaseModel):
    items: list[LeadResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
