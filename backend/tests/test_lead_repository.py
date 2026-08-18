import uuid
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models.lead import Lead
from app.repositories import lead_repository
from app.repositories.lead_repository import _apply_lead_filters
from app.schemas.website_audit import WebsiteAuditResult


def test_apply_lead_filters_with_no_filters_leaves_statement_unfiltered():
    stmt = _apply_lead_filters(
        select(Lead),
        source=None,
        has_website=None,
        min_rating=None,
        min_website_score=None,
        name_contains=None,
        search_location_contains=None,
        niche_equals=None,
    )
    assert "WHERE" not in str(stmt)


def test_apply_lead_filters_combines_all_filters():
    stmt = _apply_lead_filters(
        select(Lead),
        source="google_maps",
        has_website=True,
        min_rating=4.0,
        min_website_score=70.0,
        name_contains="plumb",
        search_location_contains="karachi",
        niche_equals="plumbers",
    )
    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "leads.source" in compiled
    assert "leads.has_website" in compiled
    assert "leads.rating" in compiled
    assert "leads.website_score" in compiled
    assert "leads.name ILIKE" in compiled
    assert "leads.search_location ILIKE" in compiled
    assert "leads.query" in compiled


def test_apply_lead_filters_escapes_ilike_wildcards_in_name_contains():
    """A literal '%' or '_' typed by the caller must filter on that literal
    character, not act as an ILIKE wildcard — e.g. a business named
    "50% Off Plumbing". See SecurityIssues.md hardening item 11."""
    stmt = _apply_lead_filters(
        select(Lead),
        source=None,
        has_website=None,
        min_rating=None,
        min_website_score=None,
        name_contains="50%_off",
        search_location_contains=None,
        niche_equals=None,
    )
    compiled = stmt.compile(dialect=postgresql.dialect())
    bind_value = next(iter(compiled.params.values()))
    assert bind_value == "%50\\%\\_off%"
    assert "ESCAPE" in str(compiled)


async def test_list_leads_returns_items_and_total_count():
    mock_session = AsyncMock()
    fake_leads = [Lead(name="A"), Lead(name="B")]

    count_result = MagicMock()
    count_result.scalar_one.return_value = 42
    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = fake_leads
    mock_session.execute = AsyncMock(side_effect=[count_result, items_result])

    items, total = await lead_repository.list_leads(mock_session, limit=2, offset=0)

    assert total == 42
    assert items == fake_leads
    assert mock_session.execute.call_count == 2


async def test_get_by_id_returns_none_when_not_found():
    mock_session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=result)

    lead = await lead_repository.get_by_id(mock_session, uuid.uuid4())
    assert lead is None


async def test_get_by_id_returns_lead_when_found():
    mock_session = AsyncMock()
    fake_lead = Lead(name="Bahu Plumbers")
    result = MagicMock()
    result.scalar_one_or_none.return_value = fake_lead
    mock_session.execute = AsyncMock(return_value=result)

    lead = await lead_repository.get_by_id(mock_session, uuid.uuid4())
    assert lead is fake_lead


async def test_update_ai_audit_commits_and_returns_updated_lead():
    mock_session = AsyncMock()
    fake_lead = Lead(name="Bahu Plumbers", ai_ui_score=7)
    result = MagicMock()
    result.scalar_one_or_none.return_value = fake_lead
    mock_session.execute = AsyncMock(return_value=result)

    audit = WebsiteAuditResult(
        ui_score=7, conversion_score=5, content_score=6, trust_score=8,
        issues=["No clear CTA"], summary="Decent site, weak conversion path.",
    )

    lead = await lead_repository.update_ai_audit(mock_session, uuid.uuid4(), audit)

    assert lead is fake_lead
    mock_session.commit.assert_awaited_once()
    stmt = mock_session.execute.call_args.args[0]
    compiled_params = stmt.compile().params
    assert compiled_params["ai_ui_score"] == 7
    assert compiled_params["ai_issues"] == ["No clear CTA"]


async def test_update_ai_audit_returns_none_when_lead_missing():
    mock_session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=result)

    audit = WebsiteAuditResult(
        ui_score=7, conversion_score=5, content_score=6, trust_score=8, issues=[], summary="ok",
    )

    lead = await lead_repository.update_ai_audit(mock_session, uuid.uuid4(), audit)
    assert lead is None


async def test_upsert_lead_does_not_overwrite_pipeline_stage_on_conflict():
    """pipeline_stage/estimated_revenue_level are CRM fields set manually via
    PATCH — a re-scrape upsert must never touch them in the ON CONFLICT SET
    clause, or sales progress would reset every discovery run."""
    mock_session = AsyncMock()
    fake_lead = Lead(name="Joe's Plumbing")
    result = MagicMock()
    result.scalar_one.return_value = fake_lead
    mock_session.execute = AsyncMock(return_value=result)

    await lead_repository.upsert_lead(
        mock_session, {"name": "Joe's Plumbing", "dedupe_key": "k", "source": "google_maps"}
    )

    stmt = mock_session.execute.call_args.args[0]
    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    # Isolate the SET clause only — RETURNING lists every column (including
    # pipeline_stage) regardless, so including it would defeat the assertion.
    set_clause = compiled.split("DO UPDATE SET")[1].split("RETURNING")[0]
    assert "pagespeed_score" in set_clause
    assert "seo_score" in set_clause
    assert "performance_issues" in set_clause
    assert "pipeline_stage" not in set_clause
    assert "estimated_revenue_level" not in set_clause


async def test_update_lead_pipeline_updates_only_provided_fields():
    mock_session = AsyncMock()
    fake_lead = Lead(name="Bahu Plumbers", pipeline_stage="contacted")
    result = MagicMock()
    result.scalar_one_or_none.return_value = fake_lead
    mock_session.execute = AsyncMock(return_value=result)

    lead = await lead_repository.update_lead_pipeline(
        mock_session, uuid.uuid4(), pipeline_stage="contacted", estimated_revenue_level=None
    )

    assert lead is fake_lead
    mock_session.commit.assert_awaited_once()
    stmt = mock_session.execute.call_args.args[0]
    compiled_params = stmt.compile().params
    assert compiled_params["pipeline_stage"] == "contacted"
    assert "estimated_revenue_level" not in compiled_params


async def test_update_lead_pipeline_returns_lead_unchanged_when_no_fields_given():
    mock_session = AsyncMock()
    fake_lead = Lead(name="Bahu Plumbers")
    result = MagicMock()
    result.scalar_one_or_none.return_value = fake_lead
    mock_session.execute = AsyncMock(return_value=result)

    lead = await lead_repository.update_lead_pipeline(
        mock_session, uuid.uuid4(), pipeline_stage=None, estimated_revenue_level=None
    )

    assert lead is fake_lead
    mock_session.commit.assert_not_awaited()


async def test_update_lead_pipeline_returns_none_when_lead_missing():
    mock_session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=result)

    lead = await lead_repository.update_lead_pipeline(
        mock_session, uuid.uuid4(), pipeline_stage="won", estimated_revenue_level=None
    )
    assert lead is None
