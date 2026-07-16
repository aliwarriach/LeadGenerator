from datetime import date, datetime, timedelta, timezone

from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Date

from app.models.activity import Activity
from app.models.lead import Lead, PipelineStage

_ACTIVE_DEAL_STAGES = (
    PipelineStage.CONTACTED,
    PipelineStage.QUALIFIED,
    PipelineStage.PROPOSAL,
)


async def get_stats(session: AsyncSession, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    discovered_total = (await session.execute(select(func.count()).select_from(Lead))).scalar_one()
    discovered_this_week = (
        await session.execute(select(func.count()).select_from(Lead).where(Lead.created_at >= week_ago))
    ).scalar_one()
    no_website_total = (
        await session.execute(select(func.count()).select_from(Lead).where(Lead.has_website.is_(False)))
    ).scalar_one()
    audits_completed_total = (
        await session.execute(select(func.count()).select_from(Lead).where(Lead.ai_audited_at.isnot(None)))
    ).scalar_one()
    audits_completed_this_week = (
        await session.execute(
            select(func.count()).select_from(Lead).where(Lead.ai_audited_at >= week_ago)
        )
    ).scalar_one()
    active_deals = (
        await session.execute(
            select(func.count()).select_from(Lead).where(Lead.pipeline_stage.in_(_ACTIVE_DEAL_STAGES))
        )
    ).scalar_one()

    no_website_pct = (no_website_total / discovered_total * 100) if discovered_total else 0.0

    return {
        "discovered_total": discovered_total,
        "discovered_this_week": discovered_this_week,
        "no_website_total": no_website_total,
        "no_website_pct": round(no_website_pct, 1),
        "audits_completed_total": audits_completed_total,
        "audits_completed_this_week": audits_completed_this_week,
        "active_deals": active_deals,
    }


async def get_discovery_volume(
    session: AsyncSession, *, days: int, now: datetime | None = None
) -> list[dict]:
    """Per-day has_website/no_website counts for the trailing `days` days
    (including today), oldest first. Days with zero leads are still present
    in the output (zero-filled) so the frontend chart has a continuous axis.
    """
    now = now or datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days - 1)).date()

    created_day = cast(Lead.created_at, Date)
    result = await session.execute(
        select(created_day.label("day"), Lead.has_website, func.count())
        .where(created_day >= start_date)
        .group_by("day", Lead.has_website)
        .order_by("day")
    )

    counts: dict[date, dict[str, int]] = {}
    for day, has_website, count in result.all():
        bucket = counts.setdefault(day, {"has_website": 0, "no_website": 0})
        bucket["has_website" if has_website else "no_website"] += count

    return [
        {
            "day": start_date + timedelta(days=offset),
            "has_website": counts.get(start_date + timedelta(days=offset), {}).get("has_website", 0),
            "no_website": counts.get(start_date + timedelta(days=offset), {}).get("no_website", 0),
        }
        for offset in range(days)
    ]


async def get_lead_stage_mix(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        select(Lead.pipeline_stage, func.count()).group_by(Lead.pipeline_stage)
    )
    counts = dict(result.all())
    # Zero-fill every stage (not just the ones with rows) so the frontend
    # donut/legend always renders all 5 stages in a fixed order.
    return [{"stage": stage.value, "count": counts.get(stage.value, 0)} for stage in PipelineStage]


async def list_recent_activity(session: AsyncSession, *, limit: int) -> list[dict]:
    result = await session.execute(
        select(Activity, Lead.name)
        .join(Lead, Lead.id == Activity.lead_id)
        .order_by(Activity.created_at.desc(), Activity.id.desc())
        .limit(limit)
    )
    return [
        {
            "id": activity.id,
            "lead_id": activity.lead_id,
            "lead_name": lead_name,
            "type": activity.type,
            "description": activity.description,
            "created_at": activity.created_at,
        }
        for activity, lead_name in result.all()
    ]
