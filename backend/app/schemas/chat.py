import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ChatRoleLiteral = Literal["user", "assistant"]


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatMessageResponse(BaseModel):
    lead_id: uuid.UUID
    reply: str
    created_at: datetime


class ChatMessageItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: ChatRoleLiteral
    content: str
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    lead_id: uuid.UUID
    messages: list[ChatMessageItem]
