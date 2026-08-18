import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.models.lead import Lead
from app.schemas.outreach import EmailGenerationResult, ProposalGenerationResult, ProposalSection, WhatsAppGenerationResult
from app.services import outreach_service
from app.services.lead_service import LeadNotFoundError, LeadServiceUnavailableError
from app.services.outreach_service import AiOutreachUnavailableError


def _lead(**overrides) -> Lead:
    defaults = dict(
        id=uuid.uuid4(),
        name="Bahu Plumbers",
        category="Plumber",
        location="Karachi",
        website="https://bahuplumbers.example",
        pipeline_stage="new_lead",
        estimated_revenue_level=None,
        website_score=62.0,
        performance_issues=None,
        ai_ui_score=None,
        ai_conversion_score=None,
        ai_content_score=None,
        ai_trust_score=None,
        ai_issues=None,
        ai_summary=None,
    )
    defaults.update(overrides)
    return Lead(**defaults)


def _settings(**overrides) -> Settings:
    defaults = dict(groq_api_key="key")
    defaults.update(overrides)
    return Settings(**defaults)


_EMAIL_RESULT = EmailGenerationResult(subject="Quick question", email_body="body")
_WHATSAPP_RESULT = WhatsAppGenerationResult(message="Hey! Quick question about your site.")
_PROPOSAL_RESULT = ProposalGenerationResult(
    title="Proposal",
    sections=[
        ProposalSection(heading="Problem Analysis", content="..."),
        ProposalSection(heading="Proposed Solution", content="..."),
        ProposalSection(heading="Pricing Estimate", content="..."),
        ProposalSection(heading="Timeline", content="..."),
        ProposalSection(heading="ROI Justification", content="..."),
    ],
)


async def test_generate_email_raises_not_found_when_lead_missing():
    with patch("app.services.outreach_service.lead_repository.get_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(LeadNotFoundError):
            await outreach_service.generate_email(AsyncMock(), AsyncMock(), uuid.uuid4(), _settings())


async def test_generate_email_raises_when_groq_not_configured():
    lead = _lead()
    with patch("app.services.outreach_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)):
        with pytest.raises(AiOutreachUnavailableError):
            await outreach_service.generate_email(AsyncMock(), AsyncMock(), lead.id, _settings(groq_api_key=None))


async def test_generate_email_raises_when_groq_call_fails():
    lead = _lead()
    with (
        patch("app.services.outreach_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)),
        patch("app.services.outreach_service.groq_enricher.draft_cold_email", new=AsyncMock(return_value=None)),
    ):
        with pytest.raises(AiOutreachUnavailableError):
            await outreach_service.generate_email(AsyncMock(), AsyncMock(), lead.id, _settings())


async def test_generate_email_returns_result_on_success():
    lead = _lead()
    with (
        patch("app.services.outreach_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)),
        patch(
            "app.services.outreach_service.groq_enricher.draft_cold_email",
            new=AsyncMock(return_value=_EMAIL_RESULT),
        ),
    ):
        result = await outreach_service.generate_email(AsyncMock(), AsyncMock(), lead.id, _settings())

    assert result is _EMAIL_RESULT


async def test_generate_email_passes_tone_through_to_groq_enricher():
    lead = _lead()
    with (
        patch("app.services.outreach_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)),
        patch(
            "app.services.outreach_service.groq_enricher.draft_cold_email",
            new=AsyncMock(return_value=_EMAIL_RESULT),
        ) as mock_draft,
    ):
        await outreach_service.generate_email(AsyncMock(), AsyncMock(), lead.id, _settings(), tone="direct")

    _, kwargs = mock_draft.call_args
    assert kwargs["tone"] == "direct"


async def test_generate_email_defaults_tone_to_default():
    lead = _lead()
    with (
        patch("app.services.outreach_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)),
        patch(
            "app.services.outreach_service.groq_enricher.draft_cold_email",
            new=AsyncMock(return_value=_EMAIL_RESULT),
        ) as mock_draft,
    ):
        await outreach_service.generate_email(AsyncMock(), AsyncMock(), lead.id, _settings())

    _, kwargs = mock_draft.call_args
    assert kwargs["tone"] == "default"


async def test_generate_email_raises_service_unavailable_on_db_error():
    with patch(
        "app.services.outreach_service.lead_repository.get_by_id", new=AsyncMock(side_effect=Exception("db down"))
    ):
        with pytest.raises(LeadServiceUnavailableError):
            await outreach_service.generate_email(AsyncMock(), AsyncMock(), uuid.uuid4(), _settings())


async def test_generate_whatsapp_message_raises_not_found_when_lead_missing():
    with patch("app.services.outreach_service.lead_repository.get_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(LeadNotFoundError):
            await outreach_service.generate_whatsapp_message(AsyncMock(), AsyncMock(), uuid.uuid4(), _settings())


async def test_generate_whatsapp_message_raises_when_groq_call_fails():
    lead = _lead()
    with (
        patch("app.services.outreach_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)),
        patch(
            "app.services.outreach_service.groq_enricher.draft_whatsapp_message", new=AsyncMock(return_value=None)
        ),
    ):
        with pytest.raises(AiOutreachUnavailableError):
            await outreach_service.generate_whatsapp_message(AsyncMock(), AsyncMock(), lead.id, _settings())


async def test_generate_whatsapp_message_returns_result_on_success():
    lead = _lead()
    with (
        patch("app.services.outreach_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)),
        patch(
            "app.services.outreach_service.groq_enricher.draft_whatsapp_message",
            new=AsyncMock(return_value=_WHATSAPP_RESULT),
        ),
    ):
        result = await outreach_service.generate_whatsapp_message(AsyncMock(), AsyncMock(), lead.id, _settings())

    assert result is _WHATSAPP_RESULT


async def test_generate_proposal_raises_not_found_when_lead_missing():
    with patch("app.services.outreach_service.lead_repository.get_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(LeadNotFoundError):
            await outreach_service.generate_proposal(AsyncMock(), AsyncMock(), uuid.uuid4(), _settings())


async def test_generate_proposal_raises_when_groq_not_configured():
    lead = _lead()
    with patch("app.services.outreach_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)):
        with pytest.raises(AiOutreachUnavailableError):
            await outreach_service.generate_proposal(AsyncMock(), AsyncMock(), lead.id, _settings(groq_api_key=None))


async def test_generate_proposal_raises_when_groq_call_fails():
    lead = _lead()
    with (
        patch("app.services.outreach_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)),
        patch("app.services.outreach_service.groq_enricher.draft_proposal", new=AsyncMock(return_value=None)),
    ):
        with pytest.raises(AiOutreachUnavailableError):
            await outreach_service.generate_proposal(AsyncMock(), AsyncMock(), lead.id, _settings())


async def test_generate_proposal_returns_result_on_success():
    lead = _lead()
    with (
        patch("app.services.outreach_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)),
        patch(
            "app.services.outreach_service.groq_enricher.draft_proposal",
            new=AsyncMock(return_value=_PROPOSAL_RESULT),
        ),
    ):
        result = await outreach_service.generate_proposal(AsyncMock(), AsyncMock(), lead.id, _settings())

    assert result is _PROPOSAL_RESULT
