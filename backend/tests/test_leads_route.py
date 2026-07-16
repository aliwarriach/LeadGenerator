import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db_session
from app.main import app
from app.schemas.chat import ChatHistoryResponse, ChatMessageItem, ChatMessageResponse
from app.schemas.lead import LeadListResponse, LeadResponse
from app.schemas.website_audit import LeadAuditResponse
from app.services.chat_service import AiChatUnavailableError
from app.services.lead_service import LeadNotFoundError, LeadServiceUnavailableError
from app.services.website_audit_service import AiAuditUnavailableError, LeadHasNoWebsiteError


def _override_db_session(mock_session):
    async def _get_db_session():
        yield mock_session

    app.dependency_overrides[get_db_session] = _get_db_session


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_db_session, None)


async def test_list_leads_returns_paginated_response():
    _override_db_session(AsyncMock())
    fake_response = LeadListResponse(items=[], total=0, page=1, page_size=20, total_pages=0)

    with patch("app.routes.leads.lead_service.list_leads", new=AsyncMock(return_value=fake_response)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/leads")

    assert response.status_code == 200
    body = response.json()
    assert body == {"items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0}


async def test_list_leads_passes_query_params_through_to_service():
    _override_db_session(AsyncMock())
    fake_response = LeadListResponse(items=[], total=0, page=2, page_size=5, total_pages=0)

    with patch(
        "app.routes.leads.lead_service.list_leads", new=AsyncMock(return_value=fake_response)
    ) as mock_list:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/leads",
                params={
                    "source": "google_maps",
                    "has_website": "true",
                    "min_rating": 4.0,
                    "niche": "plumbers",
                    "page": 2,
                    "page_size": 5,
                },
            )

    assert response.status_code == 200
    _, kwargs = mock_list.call_args
    assert kwargs["source"] == "google_maps"
    assert kwargs["has_website"] is True
    assert kwargs["min_rating"] == 4.0
    assert kwargs["niche"] == "plumbers"
    assert kwargs["page"] == 2
    assert kwargs["page_size"] == 5


async def test_list_leads_rejects_invalid_page_size():
    _override_db_session(AsyncMock())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/leads", params={"page_size": 500})

    assert response.status_code == 422


async def test_list_leads_rejects_invalid_source():
    _override_db_session(AsyncMock())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/leads", params={"source": "not-a-real-source"})

    assert response.status_code == 422


async def test_get_lead_returns_404_when_not_found():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.leads.lead_service.get_lead",
        new=AsyncMock(side_effect=LeadNotFoundError("not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/leads/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_get_lead_rejects_invalid_uuid():
    _override_db_session(AsyncMock())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/leads/not-a-uuid")

    assert response.status_code == 422


async def test_list_leads_returns_503_when_db_unavailable():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.leads.lead_service.list_leads",
        new=AsyncMock(side_effect=LeadServiceUnavailableError("Database connection failed")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/leads")

    assert response.status_code == 503


async def test_get_lead_returns_503_when_db_unavailable():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.leads.lead_service.get_lead",
        new=AsyncMock(side_effect=LeadServiceUnavailableError("Database connection failed")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/leads/{uuid.uuid4()}")

    assert response.status_code == 503


async def test_update_lead_returns_200_with_updated_lead():
    _override_db_session(AsyncMock())
    lead_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    fake_response = LeadResponse(
        id=lead_id,
        name="Bahu Plumbers",
        location=None,
        website=None,
        website_domain=None,
        phone=None,
        source="google_maps",
        has_website=False,
        rating=None,
        category=None,
        query=None,
        search_location=None,
        estimated_revenue_level=None,
        pipeline_stage="contacted",
        website_score=None,
        website_score_details=None,
        pagespeed_score=None,
        seo_score=None,
        performance_issues=None,
        emails=None,
        tech_stack=None,
        is_registered=None,
        logo_valid=None,
        enriched_at=None,
        ai_ui_score=None,
        ai_conversion_score=None,
        ai_content_score=None,
        ai_trust_score=None,
        ai_issues=None,
        ai_summary=None,
        ai_audited_at=None,
        raw_data={},
        created_at=now,
        updated_at=now,
    )

    with patch(
        "app.routes.leads.lead_service.update_lead", new=AsyncMock(return_value=fake_response)
    ) as mock_update:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(f"/leads/{lead_id}", json={"pipeline_stage": "contacted"})

    assert response.status_code == 200
    assert response.json()["pipeline_stage"] == "contacted"
    args, _ = mock_update.call_args
    assert args[2].pipeline_stage == "contacted"


async def test_update_lead_rejects_invalid_pipeline_stage():
    _override_db_session(AsyncMock())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(f"/leads/{uuid.uuid4()}", json={"pipeline_stage": "not-a-stage"})

    assert response.status_code == 422


async def test_update_lead_returns_404_when_not_found():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.leads.lead_service.update_lead",
        new=AsyncMock(side_effect=LeadNotFoundError("not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(f"/leads/{uuid.uuid4()}", json={"pipeline_stage": "won"})

    assert response.status_code == 404


async def test_update_lead_stage_returns_200_with_updated_lead():
    _override_db_session(AsyncMock())
    lead_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    fake_response = LeadResponse(
        id=lead_id,
        name="Bahu Plumbers",
        location=None,
        website=None,
        website_domain=None,
        phone=None,
        source="google_maps",
        has_website=False,
        rating=None,
        category=None,
        query=None,
        search_location=None,
        estimated_revenue_level=None,
        pipeline_stage="contacted",
        website_score=None,
        website_score_details=None,
        pagespeed_score=None,
        seo_score=None,
        performance_issues=None,
        emails=None,
        tech_stack=None,
        is_registered=None,
        logo_valid=None,
        enriched_at=None,
        ai_ui_score=None,
        ai_conversion_score=None,
        ai_content_score=None,
        ai_trust_score=None,
        ai_issues=None,
        ai_summary=None,
        ai_audited_at=None,
        raw_data={},
        created_at=now,
        updated_at=now,
    )

    with patch(
        "app.routes.leads.activity_service.change_lead_stage", new=AsyncMock(return_value=fake_response)
    ) as mock_change_stage:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(f"/leads/{lead_id}/stage", json={"stage": "contacted"})

    assert response.status_code == 200
    assert response.json()["pipeline_stage"] == "contacted"
    args, _ = mock_change_stage.call_args
    assert args[2] == "contacted"


async def test_update_lead_stage_rejects_invalid_stage():
    _override_db_session(AsyncMock())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(f"/leads/{uuid.uuid4()}/stage", json={"stage": "not-a-stage"})

    assert response.status_code == 422


async def test_update_lead_stage_returns_404_when_not_found():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.leads.activity_service.change_lead_stage",
        new=AsyncMock(side_effect=LeadNotFoundError("not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(f"/leads/{uuid.uuid4()}/stage", json={"stage": "won"})

    assert response.status_code == 404


async def test_update_lead_stage_returns_503_when_db_unavailable():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.leads.activity_service.change_lead_stage",
        new=AsyncMock(side_effect=LeadServiceUnavailableError("db down")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(f"/leads/{uuid.uuid4()}/stage", json={"stage": "won"})

    assert response.status_code == 503


async def test_audit_lead_returns_200_with_audit_result():
    _override_db_session(AsyncMock())
    lead_id = uuid.uuid4()
    fake_response = LeadAuditResponse(
        lead_id=lead_id, ui_score=7, conversion_score=5, content_score=6, trust_score=8,
        issues=["No clear CTA"], summary="Decent site, weak conversion path.",
        audited_at=datetime.now(timezone.utc),
    )

    with patch(
        "app.routes.leads.website_audit_service.audit_lead_website", new=AsyncMock(return_value=fake_response)
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/leads/{lead_id}/audit")

    assert response.status_code == 200
    body = response.json()
    assert body["ui_score"] == 7
    assert body["issues"] == ["No clear CTA"]


async def test_audit_lead_returns_404_when_lead_not_found():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.leads.website_audit_service.audit_lead_website",
        new=AsyncMock(side_effect=LeadNotFoundError("not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/leads/{uuid.uuid4()}/audit")

    assert response.status_code == 404


async def test_audit_lead_returns_422_when_lead_has_no_website():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.leads.website_audit_service.audit_lead_website",
        new=AsyncMock(side_effect=LeadHasNoWebsiteError("no website")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/leads/{uuid.uuid4()}/audit")

    assert response.status_code == 422


async def test_audit_lead_returns_503_when_ai_audit_unavailable():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.leads.website_audit_service.audit_lead_website",
        new=AsyncMock(side_effect=AiAuditUnavailableError("groq not configured")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/leads/{uuid.uuid4()}/audit")

    assert response.status_code == 503


async def test_audit_lead_rejects_invalid_uuid():
    _override_db_session(AsyncMock())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/leads/not-a-uuid/audit")

    assert response.status_code == 422


async def test_chat_with_lead_returns_200_with_reply():
    _override_db_session(AsyncMock())
    lead_id = uuid.uuid4()
    fake_response = ChatMessageResponse(
        lead_id=lead_id, reply="Lead with the slow load time.", created_at=datetime.now(timezone.utc)
    )

    with patch(
        "app.routes.leads.chat_service.send_chat_message", new=AsyncMock(return_value=fake_response)
    ) as mock_chat:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/leads/{lead_id}/chat", json={"message": "How should I pitch this?"})

    assert response.status_code == 200
    assert response.json()["reply"] == "Lead with the slow load time."
    args, _ = mock_chat.call_args
    assert args[3] == "How should I pitch this?"


async def test_chat_with_lead_rejects_empty_message():
    _override_db_session(AsyncMock())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(f"/leads/{uuid.uuid4()}/chat", json={"message": ""})

    assert response.status_code == 422


async def test_chat_with_lead_returns_404_when_lead_not_found():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.leads.chat_service.send_chat_message",
        new=AsyncMock(side_effect=LeadNotFoundError("not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/leads/{uuid.uuid4()}/chat", json={"message": "hi"})

    assert response.status_code == 404


async def test_chat_with_lead_returns_503_when_ai_unavailable():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.leads.chat_service.send_chat_message",
        new=AsyncMock(side_effect=AiChatUnavailableError("groq not configured")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/leads/{uuid.uuid4()}/chat", json={"message": "hi"})

    assert response.status_code == 503


async def test_get_lead_chat_history_returns_200_with_messages():
    _override_db_session(AsyncMock())
    lead_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    fake_response = ChatHistoryResponse(
        lead_id=lead_id,
        messages=[
            ChatMessageItem(role="user", content="hi", created_at=now),
            ChatMessageItem(role="assistant", content="hello", created_at=now),
        ],
    )

    with patch(
        "app.routes.leads.chat_service.get_chat_history", new=AsyncMock(return_value=fake_response)
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/leads/{lead_id}/chat")

    assert response.status_code == 200
    body = response.json()
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "user"


async def test_get_lead_chat_history_returns_404_when_lead_not_found():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.leads.chat_service.get_chat_history",
        new=AsyncMock(side_effect=LeadNotFoundError("not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/leads/{uuid.uuid4()}/chat")

    assert response.status_code == 404
