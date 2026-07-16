import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WebsiteAuditResult(BaseModel):
    """Validated shape of the Groq model's JSON response — also what
    website_audit_service persists onto the Lead row."""

    ui_score: int = Field(ge=1, le=10)
    conversion_score: int = Field(ge=1, le=10)
    content_score: int = Field(ge=1, le=10)
    trust_score: int = Field(ge=1, le=10)
    issues: list[str]
    summary: str


class LeadAuditResponse(BaseModel):
    lead_id: uuid.UUID
    ui_score: int | None
    conversion_score: int | None
    content_score: int | None
    trust_score: int | None
    issues: list[str] | None
    summary: str | None
    audited_at: datetime | None
