import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outreach_draft import OutreachDraft


async def create_draft(
    session: AsyncSession, lead_id: uuid.UUID, *, type: str, subject: str | None, content: str
) -> OutreachDraft:
    draft = OutreachDraft(lead_id=lead_id, type=type, subject=subject, content=content)
    session.add(draft)
    await session.commit()
    await session.refresh(draft)
    return draft


async def get_latest_by_lead_and_type(
    session: AsyncSession, lead_id: uuid.UUID, *, type: str
) -> OutreachDraft | None:
    result = await session.execute(
        select(OutreachDraft)
        .where(OutreachDraft.lead_id == lead_id, OutreachDraft.type == type)
        .order_by(OutreachDraft.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, draft_id: uuid.UUID) -> OutreachDraft | None:
    result = await session.execute(select(OutreachDraft).where(OutreachDraft.id == draft_id))
    return result.scalar_one_or_none()


async def update_draft(
    session: AsyncSession, draft_id: uuid.UUID, *, subject: str | None, content: str
) -> OutreachDraft | None:
    result = await session.execute(
        update(OutreachDraft)
        .where(OutreachDraft.id == draft_id)
        .values(subject=subject, content=content, updated_at=func.now())
        .returning(OutreachDraft)
    )
    await session.commit()
    return result.scalar_one_or_none()
