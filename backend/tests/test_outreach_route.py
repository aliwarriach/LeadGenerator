import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db_session
from app.main import app
from app.schemas.outreach import EmailGenerationResult, ProposalGenerationResult, ProposalSection, WhatsAppGenerationResult
from app.services.lead_service import LeadNotFoundError
from app.services.outreach_service import AiOutreachUnavailableError


def _override_db_session(mock_session):
    async def _get_db_session():
        yield mock_session

    app.dependency_overrides[get_db_session] = _get_db_session


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_db_session, None)


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


async def test_generate_email_returns_200_with_result():
    _override_db_session(AsyncMock())
    with patch("app.routes.outreach.outreach_service.generate_email", new=AsyncMock(return_value=_EMAIL_RESULT)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/outreach/email/{uuid.uuid4()}")

    assert response.status_code == 200
    body = response.json()
    assert body["subject"] == "Quick question"
    assert body["email_body"] == "body"


async def test_generate_email_returns_404_when_lead_not_found():
    _override_db_session(AsyncMock())
    with patch(
        "app.routes.outreach.outreach_service.generate_email",
        new=AsyncMock(side_effect=LeadNotFoundError("not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/outreach/email/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_generate_email_returns_503_when_ai_unavailable():
    _override_db_session(AsyncMock())
    with patch(
        "app.routes.outreach.outreach_service.generate_email",
        new=AsyncMock(side_effect=AiOutreachUnavailableError("groq not configured")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/outreach/email/{uuid.uuid4()}")

    assert response.status_code == 503


async def test_generate_email_passes_tone_query_param_to_service():
    _override_db_session(AsyncMock())
    with patch(
        "app.routes.outreach.outreach_service.generate_email", new=AsyncMock(return_value=_EMAIL_RESULT)
    ) as mock_generate:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/outreach/email/{uuid.uuid4()}", params={"tone": "value_first"})

    assert response.status_code == 200
    _, kwargs = mock_generate.call_args
    assert kwargs["tone"] == "value_first"


async def test_generate_email_rejects_invalid_tone():
    _override_db_session(AsyncMock())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(f"/outreach/email/{uuid.uuid4()}", params={"tone": "not-a-tone"})

    assert response.status_code == 422


async def test_generate_email_rejects_invalid_uuid():
    _override_db_session(AsyncMock())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/outreach/email/not-a-uuid")

    assert response.status_code == 422


async def test_generate_whatsapp_returns_200_with_result():
    _override_db_session(AsyncMock())
    with patch(
        "app.routes.outreach.outreach_service.generate_whatsapp_message",
        new=AsyncMock(return_value=_WHATSAPP_RESULT),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/outreach/whatsapp/{uuid.uuid4()}")

    assert response.status_code == 200
    assert response.json()["message"] == "Hey! Quick question about your site."


async def test_generate_whatsapp_returns_404_when_lead_not_found():
    _override_db_session(AsyncMock())
    with patch(
        "app.routes.outreach.outreach_service.generate_whatsapp_message",
        new=AsyncMock(side_effect=LeadNotFoundError("not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/outreach/whatsapp/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_generate_whatsapp_returns_503_when_ai_unavailable():
    _override_db_session(AsyncMock())
    with patch(
        "app.routes.outreach.outreach_service.generate_whatsapp_message",
        new=AsyncMock(side_effect=AiOutreachUnavailableError("groq not configured")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/outreach/whatsapp/{uuid.uuid4()}")

    assert response.status_code == 503


async def test_generate_proposal_returns_200_with_result():
    _override_db_session(AsyncMock())
    with patch(
        "app.routes.outreach.outreach_service.generate_proposal", new=AsyncMock(return_value=_PROPOSAL_RESULT)
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/outreach/proposal/{uuid.uuid4()}")

    assert response.status_code == 200
    body = response.json()
    assert len(body["sections"]) == 5
    assert body["sections"][0]["heading"] == "Problem Analysis"


async def test_generate_proposal_returns_404_when_lead_not_found():
    _override_db_session(AsyncMock())
    with patch(
        "app.routes.outreach.outreach_service.generate_proposal",
        new=AsyncMock(side_effect=LeadNotFoundError("not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/outreach/proposal/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_generate_proposal_returns_503_when_ai_unavailable():
    _override_db_session(AsyncMock())
    with patch(
        "app.routes.outreach.outreach_service.generate_proposal",
        new=AsyncMock(side_effect=AiOutreachUnavailableError("groq not configured")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/outreach/proposal/{uuid.uuid4()}")

    assert response.status_code == 503
