import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class LeadChatMessage(Base):
    """One row per turn in a lead's AI sales chatbot conversation.

    Append-only, full history kept forever — but chat_service only replays
    the most recent N rows as context to Groq (see Settings.chat_history_max_messages),
    to stay within the free tier's per-request token/rate limits regardless
    of how long a conversation runs.
    """

    __tablename__ = "lead_chat_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, index=True
    )

    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(String(4096), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
