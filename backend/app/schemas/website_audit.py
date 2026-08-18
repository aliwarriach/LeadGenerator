import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

# Matches Lead.ai_issues' column width (ARRAY(String(512))) — an over-long
# model response would otherwise reach the database and raise there instead
# of failing validation at this boundary. See SecurityIssues.md L-4.
_IssueStr = Annotated[str, StringConstraints(max_length=512)]
# The count cap is arbitrary (a real audit lists a handful of issues) but
# bounds how much of a runaway/adversarial response gets persisted and later
# replayed into every other prompt for the lead (see SecurityIssues.md M-2).
_MAX_ISSUES = 50


class WebsiteAuditResult(BaseModel):
    """Validated shape of the Groq model's JSON response — also what
    website_audit_service persists onto the Lead row."""

    ui_score: int = Field(ge=1, le=10)
    conversion_score: int = Field(ge=1, le=10)
    content_score: int = Field(ge=1, le=10)
    trust_score: int = Field(ge=1, le=10)
    issues: list[_IssueStr] = Field(max_length=_MAX_ISSUES)
    # Matches Lead.ai_summary's column width (String(4096)).
    summary: str = Field(max_length=4096)


class LeadAuditResponse(BaseModel):
    lead_id: uuid.UUID
    ui_score: int | None
    conversion_score: int | None
    content_score: int | None
    trust_score: int | None
    issues: list[str] | None
    summary: str | None
    audited_at: datetime | None
