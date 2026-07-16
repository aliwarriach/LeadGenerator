import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.models.lead import Lead
from app.schemas.website_audit import WebsiteAuditResult
from app.services import website_audit_service
from app.services.lead_service import LeadNotFoundError
from app.services.website_audit_service import AiAuditUnavailableError, LeadHasNoWebsiteError


def _lead(**overrides) -> Lead:
    defaults = dict(
        id=uuid.uuid4(),
        name="Bahu Plumbers",
        website="https://bahuplumbers.example",
        website_score_details={"performance": 80.0},
        ai_ui_score=None,
        ai_conversion_score=None,
        ai_content_score=None,
        ai_trust_score=None,
        ai_issues=None,
        ai_summary=None,
        ai_audited_at=None,
    )
    defaults.update(overrides)
    return Lead(**defaults)


def _settings(**overrides) -> Settings:
    defaults = dict(groq_api_key="key")
    defaults.update(overrides)
    return Settings(**defaults)


async def test_audit_lead_website_raises_not_found_when_lead_missing():
    with patch(
        "app.services.website_audit_service.lead_repository.get_by_id", new=AsyncMock(return_value=None)
    ):
        with pytest.raises(LeadNotFoundError):
            await website_audit_service.audit_lead_website(AsyncMock(), AsyncMock(), uuid.uuid4(), _settings())


async def test_audit_lead_website_raises_when_lead_has_no_website():
    lead = _lead(website=None)
    with patch(
        "app.services.website_audit_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)
    ):
        with pytest.raises(LeadHasNoWebsiteError):
            await website_audit_service.audit_lead_website(AsyncMock(), AsyncMock(), lead.id, _settings())


async def test_audit_lead_website_raises_when_groq_not_configured():
    lead = _lead()
    with patch(
        "app.services.website_audit_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)
    ):
        with pytest.raises(AiAuditUnavailableError):
            await website_audit_service.audit_lead_website(
                AsyncMock(), AsyncMock(), lead.id, _settings(groq_api_key=None)
            )


async def test_audit_lead_website_raises_when_groq_evaluation_fails():
    lead = _lead()
    with (
        patch("app.services.website_audit_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)),
        patch(
            "app.services.website_audit_service.website_content_enricher.extract_content",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.website_audit_service.groq_enricher.evaluate_website", new=AsyncMock(return_value=None)
        ),
    ):
        with pytest.raises(AiAuditUnavailableError):
            await website_audit_service.audit_lead_website(AsyncMock(), AsyncMock(), lead.id, _settings())


async def test_audit_lead_website_persists_and_returns_result_on_success():
    lead = _lead()
    audit = WebsiteAuditResult(
        ui_score=7, conversion_score=5, content_score=6, trust_score=8,
        issues=["No clear CTA"], summary="Decent site, weak conversion path.",
    )
    now = datetime.now(timezone.utc)
    updated_lead = _lead(
        id=lead.id,
        ai_ui_score=7, ai_conversion_score=5, ai_content_score=6, ai_trust_score=8,
        ai_issues=["No clear CTA"], ai_summary="Decent site, weak conversion path.", ai_audited_at=now,
    )

    with (
        patch("app.services.website_audit_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)),
        patch(
            "app.services.website_audit_service.website_content_enricher.extract_content",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.website_audit_service.groq_enricher.evaluate_website", new=AsyncMock(return_value=audit)
        ),
        patch(
            "app.services.website_audit_service.lead_repository.update_ai_audit",
            new=AsyncMock(return_value=updated_lead),
        ) as mock_update,
    ):
        result = await website_audit_service.audit_lead_website(AsyncMock(), AsyncMock(), lead.id, _settings())

    mock_update.assert_awaited_once()
    assert mock_update.call_args.args[2] is audit
    assert result.lead_id == lead.id
    assert result.ui_score == 7
    assert result.summary == "Decent site, weak conversion path."
    assert result.audited_at == now
