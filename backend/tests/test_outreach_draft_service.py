import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.lead import Lead
from app.models.outreach_draft import OutreachDraft
from app.services import outreach_draft_service
from app.services.lead_service import LeadNotFoundError, LeadServiceUnavailableError
from app.services.outreach_draft_service import OutreachDraftNotFoundError, PdfNotSupportedError
from app.services.pdf_service import PdfGenerationError


def _lead(**overrides) -> Lead:
    defaults = dict(id=uuid.uuid4(), name="Bahu Plumbers", source="google_maps")
    defaults.update(overrides)
    return Lead(**defaults)


def _draft(**overrides) -> OutreachDraft:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid.uuid4(), lead_id=uuid.uuid4(), type="email", subject="Quick question", content="Draft body",
        created_at=now, updated_at=now,
    )
    defaults.update(overrides)
    return OutreachDraft(**defaults)


async def test_create_draft_raises_not_found_when_lead_missing():
    mock_session = AsyncMock()

    with patch("app.services.outreach_draft_service.lead_repository.get_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(LeadNotFoundError):
            await outreach_draft_service.create_draft(
                mock_session, uuid.uuid4(), type="email", subject="s", content="c"
            )


async def test_create_draft_saves_and_logs_matching_activity():
    mock_session = AsyncMock()
    lead = _lead()
    draft = _draft(lead_id=lead.id, type="whatsapp", subject=None, content="Hey there!")

    with patch(
        "app.services.outreach_draft_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)
    ), patch(
        "app.services.outreach_draft_service.outreach_draft_repository.create_draft",
        new=AsyncMock(return_value=draft),
    ), patch(
        "app.services.outreach_draft_service.activity_repository.add_activity", new=AsyncMock()
    ) as mock_add_activity:
        response = await outreach_draft_service.create_draft(
            mock_session, lead.id, type="whatsapp", subject=None, content="Hey there!"
        )

    assert response.content == "Hey there!"
    _, kwargs = mock_add_activity.call_args
    assert kwargs["type"] == "whatsapp"
    assert kwargs["description"] == "WhatsApp draft saved"


async def test_create_draft_logs_proposal_created_for_proposal_type():
    mock_session = AsyncMock()
    lead = _lead()
    draft = _draft(lead_id=lead.id, type="proposal", subject=None, content="Proposal text")

    with patch(
        "app.services.outreach_draft_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)
    ), patch(
        "app.services.outreach_draft_service.outreach_draft_repository.create_draft",
        new=AsyncMock(return_value=draft),
    ), patch(
        "app.services.outreach_draft_service.activity_repository.add_activity", new=AsyncMock()
    ) as mock_add_activity:
        await outreach_draft_service.create_draft(
            mock_session, lead.id, type="proposal", subject=None, content="Proposal text"
        )

    _, kwargs = mock_add_activity.call_args
    assert kwargs["description"] == "Proposal created"


async def test_get_latest_draft_raises_not_found_when_none_exists():
    mock_session = AsyncMock()

    with patch(
        "app.services.outreach_draft_service.outreach_draft_repository.get_latest_by_lead_and_type",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(OutreachDraftNotFoundError):
            await outreach_draft_service.get_latest_draft(mock_session, uuid.uuid4(), type="email")


async def test_get_latest_draft_returns_response_when_found():
    mock_session = AsyncMock()
    draft = _draft()

    with patch(
        "app.services.outreach_draft_service.outreach_draft_repository.get_latest_by_lead_and_type",
        new=AsyncMock(return_value=draft),
    ):
        response = await outreach_draft_service.get_latest_draft(mock_session, draft.lead_id, type="email")

    assert response.id == draft.id


async def test_update_draft_raises_not_found_when_missing():
    mock_session = AsyncMock()

    with patch(
        "app.services.outreach_draft_service.outreach_draft_repository.update_draft", new=AsyncMock(return_value=None)
    ):
        with pytest.raises(OutreachDraftNotFoundError):
            await outreach_draft_service.update_draft(mock_session, uuid.uuid4(), subject=None, content="edited")


async def test_update_draft_returns_response_when_updated():
    mock_session = AsyncMock()
    draft = _draft(content="Edited content")

    with patch(
        "app.services.outreach_draft_service.outreach_draft_repository.update_draft",
        new=AsyncMock(return_value=draft),
    ):
        response = await outreach_draft_service.update_draft(mock_session, draft.id, subject=None, content="Edited content")

    assert response.content == "Edited content"


async def test_generate_draft_pdf_raises_not_found_when_missing():
    mock_session = AsyncMock()

    with patch(
        "app.services.outreach_draft_service.outreach_draft_repository.get_by_id", new=AsyncMock(return_value=None)
    ):
        with pytest.raises(OutreachDraftNotFoundError):
            await outreach_draft_service.generate_draft_pdf(mock_session, uuid.uuid4())


async def test_generate_draft_pdf_raises_not_supported_for_email():
    mock_session = AsyncMock()
    draft = _draft(type="email")

    with patch(
        "app.services.outreach_draft_service.outreach_draft_repository.get_by_id", new=AsyncMock(return_value=draft)
    ):
        with pytest.raises(PdfNotSupportedError):
            await outreach_draft_service.generate_draft_pdf(mock_session, draft.id)


async def test_generate_draft_pdf_raises_not_supported_for_whatsapp():
    mock_session = AsyncMock()
    draft = _draft(type="whatsapp")

    with patch(
        "app.services.outreach_draft_service.outreach_draft_repository.get_by_id", new=AsyncMock(return_value=draft)
    ):
        with pytest.raises(PdfNotSupportedError):
            await outreach_draft_service.generate_draft_pdf(mock_session, draft.id)


async def test_generate_draft_pdf_returns_bytes_for_proposal_type():
    mock_session = AsyncMock()
    draft = _draft(type="proposal", content="# Proposal\n\nSome text.")

    with patch(
        "app.services.outreach_draft_service.outreach_draft_repository.get_by_id", new=AsyncMock(return_value=draft)
    ), patch(
        "app.services.outreach_draft_service.render_proposal_pdf", return_value=b"%PDF-1.4 fake"
    ) as mock_render:
        pdf_bytes = await outreach_draft_service.generate_draft_pdf(mock_session, draft.id)

    assert pdf_bytes == b"%PDF-1.4 fake"
    mock_render.assert_called_once_with(draft.content)


async def test_generate_draft_pdf_propagates_pdf_generation_error():
    mock_session = AsyncMock()
    draft = _draft(type="proposal")

    with patch(
        "app.services.outreach_draft_service.outreach_draft_repository.get_by_id", new=AsyncMock(return_value=draft)
    ), patch(
        "app.services.outreach_draft_service.render_proposal_pdf", side_effect=PdfGenerationError("render failed")
    ):
        with pytest.raises(PdfGenerationError):
            await outreach_draft_service.generate_draft_pdf(mock_session, draft.id)
