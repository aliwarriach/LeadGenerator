import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

OutreachDraftTypeLiteral = Literal["email", "whatsapp", "proposal"]


class OutreachDraftCreateRequest(BaseModel):
    subject: str | None = Field(default=None, max_length=512)
    content: str = Field(min_length=1)


class OutreachDraftUpdateRequest(BaseModel):
    subject: str | None = Field(default=None, max_length=512)
    content: str = Field(min_length=1)


class OutreachDraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lead_id: uuid.UUID
    type: OutreachDraftTypeLiteral
    subject: str | None
    content: str
    created_at: datetime
    updated_at: datetime
