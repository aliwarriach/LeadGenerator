import uuid

from sqlalchemy import Select, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.schemas.website_audit import WebsiteAuditResult

_SORT_COLUMNS = {
    "created_at": Lead.created_at,
    "rating": Lead.rating,
    "website_score": Lead.website_score,
    "name": Lead.name,
}


def _escape_ilike_wildcards(value: str) -> str:
    """Escapes literal `%`/`_`/`\\` in a substring-filter value before it's
    wrapped in `%...%` for `ILIKE`. Parameterized, so this was never SQL
    injection — but an unescaped `%`/`_` in `name`/`search_location` matches
    more (or differently) than the substring the caller actually typed, e.g.
    filtering by a business literally named "50% Off Plumbing"."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def upsert_lead(session: AsyncSession, lead_data: dict) -> Lead:
    """Insert a lead, or refresh it in place if `dedupe_key` already exists.

    Runs as a single statement so concurrent workers racing on the same
    dedupe_key don't raise IntegrityError — safe to retry a scrape job.
    """
    stmt = (
        insert(Lead)
        .values(**lead_data)
        .on_conflict_do_update(
            index_elements=[Lead.dedupe_key],
            set_={
                "name": lead_data["name"],
                "location": lead_data.get("location"),
                "website": lead_data.get("website"),
                "website_domain": lead_data.get("website_domain"),
                "phone": lead_data.get("phone"),
                "has_website": lead_data.get("has_website", False),
                "rating": lead_data.get("rating"),
                "category": lead_data.get("category"),
                "website_score": lead_data.get("website_score"),
                "website_score_details": lead_data.get("website_score_details"),
                "pagespeed_score": lead_data.get("pagespeed_score"),
                "seo_score": lead_data.get("seo_score"),
                "performance_issues": lead_data.get("performance_issues"),
                "emails": lead_data.get("emails"),
                "tech_stack": lead_data.get("tech_stack"),
                "is_registered": lead_data.get("is_registered"),
                "logo_valid": lead_data.get("logo_valid"),
                "enriched_at": lead_data.get("enriched_at"),
                "raw_data": lead_data.get("raw_data", {}),
                "updated_at": func.now(),
            },
        )
        .returning(Lead)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.scalar_one()


async def get_by_dedupe_key(session: AsyncSession, dedupe_key: str) -> Lead | None:
    result = await session.execute(select(Lead).where(Lead.dedupe_key == dedupe_key))
    return result.scalar_one_or_none()


async def list_by_search_location(session: AsyncSession, search_location: str) -> list[Lead]:
    """Candidate pool for fuzzy-name deduplication, scoped to one search
    location to keep the in-memory fuzzy match cheap."""
    result = await session.execute(select(Lead).where(Lead.search_location == search_location))
    return list(result.scalars().all())


async def count_by_query(session: AsyncSession, query: str, search_location: str) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(Lead)
        .where(Lead.query == query, Lead.search_location == search_location)
    )
    return result.scalar_one()


async def get_by_id(session: AsyncSession, lead_id: uuid.UUID) -> Lead | None:
    result = await session.execute(select(Lead).where(Lead.id == lead_id))
    return result.scalar_one_or_none()


async def update_ai_audit(session: AsyncSession, lead_id: uuid.UUID, audit: WebsiteAuditResult) -> Lead | None:
    result = await session.execute(
        update(Lead)
        .where(Lead.id == lead_id)
        .values(
            ai_ui_score=audit.ui_score,
            ai_conversion_score=audit.conversion_score,
            ai_content_score=audit.content_score,
            ai_trust_score=audit.trust_score,
            ai_issues=audit.issues,
            ai_summary=audit.summary,
            ai_audited_at=func.now(),
        )
        .returning(Lead)
    )
    await session.commit()
    return result.scalar_one_or_none()


async def update_lead_pipeline(
    session: AsyncSession,
    lead_id: uuid.UUID,
    *,
    pipeline_stage: str | None,
    estimated_revenue_level: str | None,
) -> Lead | None:
    """Patches only the CRM fields a user sets manually. Both params are
    optional independently — only the ones actually passed are updated, so
    a partial patch never clobbers the other field back to null."""
    values: dict = {}
    if pipeline_stage is not None:
        values["pipeline_stage"] = pipeline_stage
    if estimated_revenue_level is not None:
        values["estimated_revenue_level"] = estimated_revenue_level

    if not values:
        return await get_by_id(session, lead_id)

    values["updated_at"] = func.now()
    result = await session.execute(update(Lead).where(Lead.id == lead_id).values(**values).returning(Lead))
    await session.commit()
    return result.scalar_one_or_none()


async def count_by_source(session: AsyncSession, sources: list[str]) -> dict[str, int]:
    """Total lead count per source, across all runs — a single GROUP BY query
    rather than one COUNT(*) per source, so callers rendering several jobs at
    once (or a job list) don't trigger N separate queries."""
    if not sources:
        return {}
    result = await session.execute(
        select(Lead.source, func.count()).where(Lead.source.in_(sources)).group_by(Lead.source)
    )
    return dict(result.all())


def _apply_lead_filters(
    stmt: Select,
    *,
    source: str | None,
    has_website: bool | None,
    min_rating: float | None,
    min_website_score: float | None,
    name_contains: str | None,
    search_location_contains: str | None,
    niche_equals: str | None,
) -> Select:
    if source is not None:
        stmt = stmt.where(Lead.source == source)
    if has_website is not None:
        stmt = stmt.where(Lead.has_website == has_website)
    if min_rating is not None:
        stmt = stmt.where(Lead.rating >= min_rating)
    if min_website_score is not None:
        stmt = stmt.where(Lead.website_score >= min_website_score)
    if name_contains:
        stmt = stmt.where(Lead.name.ilike(f"%{_escape_ilike_wildcards(name_contains)}%", escape="\\"))
    if search_location_contains:
        stmt = stmt.where(
            Lead.search_location.ilike(f"%{_escape_ilike_wildcards(search_location_contains)}%", escape="\\")
        )
    if niche_equals:
        stmt = stmt.where(Lead.query == niche_equals)
    return stmt


async def list_leads(
    session: AsyncSession,
    *,
    source: str | None = None,
    has_website: bool | None = None,
    min_rating: float | None = None,
    min_website_score: float | None = None,
    name_contains: str | None = None,
    search_location_contains: str | None = None,
    niche_equals: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Lead], int]:
    """Paginated, filtered lead listing. Returns (items, total_matching_count)."""
    filter_kwargs = dict(
        source=source,
        has_website=has_website,
        min_rating=min_rating,
        min_website_score=min_website_score,
        name_contains=name_contains,
        search_location_contains=search_location_contains,
        niche_equals=niche_equals,
    )

    count_stmt = _apply_lead_filters(select(func.count()).select_from(Lead), **filter_kwargs)
    total = (await session.execute(count_stmt)).scalar_one()

    column = _SORT_COLUMNS.get(sort_by, Lead.created_at)
    order = column.desc() if sort_order == "desc" else column.asc()

    items_stmt = _apply_lead_filters(select(Lead), **filter_kwargs).order_by(order).limit(limit).offset(offset)
    result = await session.execute(items_stmt)
    return list(result.scalars().all()), total
