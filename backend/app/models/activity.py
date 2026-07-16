import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ActivityType(StrEnum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    PROPOSAL = "proposal"
    STAGE_CHANGE = "stage_change"


class Activity(Base):
    """Append-only CRM activity log for a lead — outreach actions logged via
    POST /activities/{lead_id}, plus automatic stage_change entries from
    PATCH /leads/{lead_id}/stage."""

    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, index=True
    )

    type: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(String(1024), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
