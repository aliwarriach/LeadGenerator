import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

LeadSortBy = Literal["created_at", "rating", "website_score", "name"]
SortOrder = Literal["asc", "desc"]


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

    # Website Quality Score (0-100) — only ever set when has_website is true.
    # NOT the overall client rating; that mechanic doesn't exist yet.
    website_score: float | None
    website_score_details: dict[str, float] | None
    emails: list[str] | None
    tech_stack: list[str] | None
    is_registered: bool | None
    logo_valid: bool | None
    enriched_at: datetime | None

    raw_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class LeadListResponse(BaseModel):
    items: list[LeadResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
