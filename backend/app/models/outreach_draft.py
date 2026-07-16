import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class OutreachType(StrEnum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    PROPOSAL = "proposal"


class OutreachDraft(Base):
    """A saved, user-editable outreach draft (email, WhatsApp message, or
    proposal) for a lead. A lead can have several drafts of the same type
    over time (POST creates a new row each time); GET always returns the
    most recent one for the given lead+type.

    PDF export only makes sense for `proposal` — email/WhatsApp are sent
    through their respective channels, not exported as documents.
    """

    __tablename__ = "outreach_drafts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # Only meaningful for type == "email" — null for whatsapp/proposal.
    subject: Mapped[str | None] = mapped_column(String(512))
    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
