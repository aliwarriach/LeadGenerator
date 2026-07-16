import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead_chat_message import LeadChatMessage


async def add_message(session: AsyncSession, lead_id: uuid.UUID, *, role: str, content: str) -> LeadChatMessage:
    message = LeadChatMessage(lead_id=lead_id, role=role, content=content)
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return message


async def list_recent_messages(
    session: AsyncSession, lead_id: uuid.UUID, *, limit: int
) -> list[LeadChatMessage]:
    """Most recent `limit` messages for `lead_id`, oldest-first — the order
    Groq expects a conversation's context to be replayed in."""
    result = await session.execute(
        select(LeadChatMessage)
        .where(LeadChatMessage.lead_id == lead_id)
        .order_by(LeadChatMessage.id.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))


async def list_all_messages(session: AsyncSession, lead_id: uuid.UUID) -> list[LeadChatMessage]:
    result = await session.execute(
        select(LeadChatMessage).where(LeadChatMessage.lead_id == lead_id).order_by(LeadChatMessage.id.asc())
    )
    return list(result.scalars().all())
