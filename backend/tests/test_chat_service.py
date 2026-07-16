import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.models.lead import Lead
from app.models.lead_chat_message import LeadChatMessage
from app.services import chat_service
from app.services.chat_service import AiChatUnavailableError
from app.services.lead_service import LeadNotFoundError


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
        performance_issues=["Eliminate render-blocking resources"],
        ai_ui_score=7,
        ai_conversion_score=5,
        ai_content_score=6,
        ai_trust_score=8,
        ai_issues=["No clear CTA"],
        ai_summary="Decent site, weak conversion path.",
    )
    defaults.update(overrides)
    return Lead(**defaults)


def _settings(**overrides) -> Settings:
    defaults = dict(groq_api_key="key", chat_history_max_messages=12)
    defaults.update(overrides)
    return Settings(**defaults)


async def test_send_chat_message_raises_not_found_when_lead_missing():
    with patch("app.services.chat_service.lead_repository.get_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(LeadNotFoundError):
            await chat_service.send_chat_message(
                AsyncMock(), AsyncMock(), uuid.uuid4(), "hi", _settings()
            )


async def test_send_chat_message_raises_when_groq_not_configured():
    lead = _lead()
    with patch("app.services.chat_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)):
        with pytest.raises(AiChatUnavailableError):
            await chat_service.send_chat_message(
                AsyncMock(), AsyncMock(), lead.id, "hi", _settings(groq_api_key=None)
            )


async def test_send_chat_message_raises_when_groq_call_fails():
    lead = _lead()
    with (
        patch("app.services.chat_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)),
        patch(
            "app.services.chat_service.lead_chat_repository.list_recent_messages",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.chat_service.groq_enricher.send_chat_completion", new=AsyncMock(return_value=None)
        ),
        patch("app.services.chat_service.lead_chat_repository.add_message") as mock_add,
    ):
        with pytest.raises(AiChatUnavailableError):
            await chat_service.send_chat_message(AsyncMock(), AsyncMock(), lead.id, "hi", _settings())

    mock_add.assert_not_called()


async def test_send_chat_message_persists_both_turns_and_returns_reply():
    lead = _lead()
    now = datetime.now(timezone.utc)
    saved_assistant_message = LeadChatMessage(
        id=2, lead_id=lead.id, role="assistant", content="Lead with the slow load time.", created_at=now
    )

    with (
        patch("app.services.chat_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)),
        patch(
            "app.services.chat_service.lead_chat_repository.list_recent_messages",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.chat_service.groq_enricher.send_chat_completion",
            new=AsyncMock(return_value="Lead with the slow load time."),
        ),
        patch(
            "app.services.chat_service.lead_chat_repository.add_message",
            new=AsyncMock(side_effect=[AsyncMock(), saved_assistant_message]),
        ) as mock_add,
    ):
        result = await chat_service.send_chat_message(
            AsyncMock(), AsyncMock(), lead.id, "How should I pitch this client?", _settings()
        )

    assert result.lead_id == lead.id
    assert result.reply == "Lead with the slow load time."
    assert result.created_at == now
    assert mock_add.await_count == 2
    first_call_kwargs = mock_add.call_args_list[0].kwargs
    assert first_call_kwargs["role"] == "user"
    assert first_call_kwargs["content"] == "How should I pitch this client?"
    second_call_kwargs = mock_add.call_args_list[1].kwargs
    assert second_call_kwargs["role"] == "assistant"


async def test_send_chat_message_includes_bounded_history_and_lead_context_in_prompt():
    lead = _lead()
    session = AsyncMock()
    history = [
        LeadChatMessage(id=1, lead_id=lead.id, role="user", content="What's their weakest point?"),
        LeadChatMessage(id=2, lead_id=lead.id, role="assistant", content="Slow homepage load."),
    ]
    captured = {}

    async def fake_send_chat_completion(client, messages, **kwargs):
        captured["messages"] = messages
        return "some reply"

    with (
        patch("app.services.chat_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)),
        patch(
            "app.services.chat_service.lead_chat_repository.list_recent_messages",
            new=AsyncMock(return_value=history),
        ) as mock_list,
        patch(
            "app.services.chat_service.groq_enricher.send_chat_completion",
            new=fake_send_chat_completion,
        ),
        patch("app.services.chat_service.lead_chat_repository.add_message", new=AsyncMock()),
    ):
        await chat_service.send_chat_message(
            session, AsyncMock(), lead.id, "And pricing?", _settings(chat_history_max_messages=12)
        )

    mock_list.assert_awaited_once_with(session, lead.id, limit=12)
    messages = captured["messages"]
    assert messages[0]["role"] == "system"
    assert "Bahu Plumbers" in messages[0]["content"]
    assert "Decent site, weak conversion path." in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "What's their weakest point?"}
    assert messages[2] == {"role": "assistant", "content": "Slow homepage load."}
    assert messages[-1] == {"role": "user", "content": "And pricing?"}


async def test_get_chat_history_raises_not_found_when_lead_missing():
    with patch("app.services.chat_service.lead_repository.get_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(LeadNotFoundError):
            await chat_service.get_chat_history(AsyncMock(), uuid.uuid4())


async def test_get_chat_history_returns_all_messages():
    lead = _lead()
    now = datetime.now(timezone.utc)
    messages = [
        LeadChatMessage(id=1, lead_id=lead.id, role="user", content="hi", created_at=now),
        LeadChatMessage(id=2, lead_id=lead.id, role="assistant", content="hello", created_at=now),
    ]
    with (
        patch("app.services.chat_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)),
        patch(
            "app.services.chat_service.lead_chat_repository.list_all_messages",
            new=AsyncMock(return_value=messages),
        ),
    ):
        result = await chat_service.get_chat_history(AsyncMock(), lead.id)

    assert result.lead_id == lead.id
    assert len(result.messages) == 2
    assert result.messages[0].role == "user"
    assert result.messages[1].content == "hello"
