import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

OutreachDraftTypeLiteral = Literal["email", "whatsapp", "proposal"]


# Proposals are long-form, but not unbounded: `content` is rendered to PDF by
# xhtml2pdf, whose cost grows with input size. Without a ceiling a single large
# draft is a cheap way to tie up a worker. 100k characters is far above any
# real proposal (the generator produces ~5k) and far below a problem.
MAX_DRAFT_CONTENT_LENGTH = 100_000


class OutreachDraftCreateRequest(BaseModel):
    subject: str | None = Field(default=None, max_length=512)
    content: str = Field(min_length=1, max_length=MAX_DRAFT_CONTENT_LENGTH)


class OutreachDraftUpdateRequest(BaseModel):
    subject: str | None = Field(default=None, max_length=512)
    content: str = Field(min_length=1, max_length=MAX_DRAFT_CONTENT_LENGTH)


class OutreachDraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lead_id: uuid.UUID
    type: OutreachDraftTypeLiteral
    subject: str | None
    content: str
    created_at: datetime
    updated_at: datetime
