import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db_session
from app.main import app
from app.schemas.outreach_draft import OutreachDraftResponse
from app.services.lead_service import LeadNotFoundError, LeadServiceUnavailableError
from app.services.outreach_draft_service import OutreachDraftNotFoundError, PdfNotSupportedError
from app.services.pdf_service import PdfGenerationError


def _override_db_session(mock_session):
    async def _get_db_session():
        yield mock_session

    app.dependency_overrides[get_db_session] = _get_db_session


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_db_session, None)


def _draft_response(**overrides) -> OutreachDraftResponse:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid.uuid4(), lead_id=uuid.uuid4(), type="email", subject="Quick question", content="Draft body",
        created_at=now, updated_at=now,
    )
    defaults.update(overrides)
    return OutreachDraftResponse(**defaults)


async def test_create_draft_returns_200_with_saved_draft():
    _override_db_session(AsyncMock())
    lead_id = uuid.uuid4()
    fake_response = _draft_response(lead_id=lead_id, type="email")

    with patch(
        "app.routes.outreach_drafts.outreach_draft_service.create_draft", new=AsyncMock(return_value=fake_response)
    ) as mock_create:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/outreach-drafts/{lead_id}",
                params={"type": "email"},
                json={"subject": "Quick question", "content": "Draft body"},
            )

    assert response.status_code == 200
    assert response.json()["content"] == "Draft body"
    _, kwargs = mock_create.call_args
    assert kwargs["type"] == "email"
    assert kwargs["subject"] == "Quick question"
    assert kwargs["content"] == "Draft body"


async def test_create_draft_rejects_invalid_type():
    _override_db_session(AsyncMock())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/outreach-drafts/{uuid.uuid4()}", params={"type": "not-a-type"}, json={"content": "x"}
        )

    assert response.status_code == 422


async def test_create_draft_requires_type_param():
    _override_db_session(AsyncMock())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(f"/outreach-drafts/{uuid.uuid4()}", json={"content": "x"})

    assert response.status_code == 422


async def test_create_draft_returns_404_when_lead_not_found():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.outreach_drafts.outreach_draft_service.create_draft",
        new=AsyncMock(side_effect=LeadNotFoundError("not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/outreach-drafts/{uuid.uuid4()}", params={"type": "whatsapp"}, json={"content": "hi"}
            )

    assert response.status_code == 404


async def test_get_latest_draft_returns_200():
    _override_db_session(AsyncMock())
    lead_id = uuid.uuid4()
    fake_response = _draft_response(lead_id=lead_id, type="proposal", subject=None)

    with patch(
        "app.routes.outreach_drafts.outreach_draft_service.get_latest_draft",
        new=AsyncMock(return_value=fake_response),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/outreach-drafts/{lead_id}", params={"type": "proposal"})

    assert response.status_code == 200
    assert response.json()["type"] == "proposal"


async def test_get_latest_draft_returns_404_when_none_exists():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.outreach_drafts.outreach_draft_service.get_latest_draft",
        new=AsyncMock(side_effect=OutreachDraftNotFoundError("no draft")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/outreach-drafts/{uuid.uuid4()}", params={"type": "email"})

    assert response.status_code == 404


async def test_update_draft_returns_200_with_edited_content():
    _override_db_session(AsyncMock())
    draft_id = uuid.uuid4()
    fake_response = _draft_response(id=draft_id, content="Edited content")

    with patch(
        "app.routes.outreach_drafts.outreach_draft_service.update_draft", new=AsyncMock(return_value=fake_response)
    ) as mock_update:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(f"/outreach-drafts/{draft_id}", json={"content": "Edited content"})

    assert response.status_code == 200
    assert response.json()["content"] == "Edited content"
    _, kwargs = mock_update.call_args
    assert kwargs["content"] == "Edited content"


async def test_update_draft_returns_404_when_missing():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.outreach_drafts.outreach_draft_service.update_draft",
        new=AsyncMock(side_effect=OutreachDraftNotFoundError("not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(f"/outreach-drafts/{uuid.uuid4()}", json={"content": "x"})

    assert response.status_code == 404


async def test_generate_draft_pdf_returns_pdf_bytes():
    _override_db_session(AsyncMock())
    draft_id = uuid.uuid4()

    with patch(
        "app.routes.outreach_drafts.outreach_draft_service.generate_draft_pdf",
        new=AsyncMock(return_value=b"%PDF-1.4 fake"),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/outreach-drafts/{draft_id}/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == b"%PDF-1.4 fake"


async def test_generate_draft_pdf_returns_404_when_draft_missing():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.outreach_drafts.outreach_draft_service.generate_draft_pdf",
        new=AsyncMock(side_effect=OutreachDraftNotFoundError("not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/outreach-drafts/{uuid.uuid4()}/pdf")

    assert response.status_code == 404


async def test_generate_draft_pdf_returns_422_for_non_proposal_type():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.outreach_drafts.outreach_draft_service.generate_draft_pdf",
        new=AsyncMock(side_effect=PdfNotSupportedError("not supported")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/outreach-drafts/{uuid.uuid4()}/pdf")

    assert response.status_code == 422


async def test_generate_draft_pdf_returns_500_on_render_failure():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.outreach_drafts.outreach_draft_service.generate_draft_pdf",
        new=AsyncMock(side_effect=PdfGenerationError("render failed")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/outreach-drafts/{uuid.uuid4()}/pdf")

    assert response.status_code == 500
