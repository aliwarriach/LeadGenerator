import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity


async def add_activity(
    session: AsyncSession, lead_id: uuid.UUID, *, type: str, description: str
) -> Activity:
    activity = Activity(lead_id=lead_id, type=type, description=description)
    session.add(activity)
    await session.commit()
    await session.refresh(activity)
    return activity


async def list_by_lead(session: AsyncSession, lead_id: uuid.UUID) -> list[Activity]:
    """All activities for a lead, latest first."""
    result = await session.execute(
        select(Activity).where(Activity.lead_id == lead_id).order_by(Activity.created_at.desc(), Activity.id.desc())
    )
    return list(result.scalars().all())
