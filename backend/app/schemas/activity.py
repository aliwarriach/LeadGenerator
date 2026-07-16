import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.lead import PipelineStageLiteral

ActivityTypeLiteral = Literal["email", "whatsapp", "proposal", "stage_change"]


class StageUpdateRequest(BaseModel):
    stage: PipelineStageLiteral


class ActivityCreateRequest(BaseModel):
    type: ActivityTypeLiteral
    description: str = Field(min_length=1, max_length=1024)


class ActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: uuid.UUID
    type: ActivityTypeLiteral
    description: str
    created_at: datetime


class ActivityListResponse(BaseModel):
    lead_id: uuid.UUID
    items: list[ActivityResponse]
