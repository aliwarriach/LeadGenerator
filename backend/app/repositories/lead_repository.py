import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead

_SORT_COLUMNS = {
    "created_at": Lead.created_at,
    "rating": Lead.rating,
    "website_score": Lead.website_score,
    "name": Lead.name,
}


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
        stmt = stmt.where(Lead.name.ilike(f"%{name_contains}%"))
    if search_location_contains:
        stmt = stmt.where(Lead.search_location.ilike(f"%{search_location_contains}%"))
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
