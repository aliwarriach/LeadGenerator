import uuid
from unittest.mock import AsyncMock, MagicMock

from app.models.lead_chat_message import ChatRole, LeadChatMessage
from app.repositories import lead_chat_repository


async def test_add_message_commits_and_returns_saved_message():
    mock_session = AsyncMock()
    # AsyncSession.add() is synchronous in real SQLAlchemy — a bare AsyncMock
    # would make it awaitable and leave an unawaited-coroutine warning.
    mock_session.add = MagicMock()
    lead_id = uuid.uuid4()

    message = await lead_chat_repository.add_message(mock_session, lead_id, role=ChatRole.USER, content="hi")

    assert message.lead_id == lead_id
    assert message.role == ChatRole.USER
    assert message.content == "hi"
    mock_session.add.assert_called_once_with(message)
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(message)


async def test_list_recent_messages_returns_oldest_first():
    lead_id = uuid.uuid4()
    # DB query is DESC-ordered (newest first) — the repository must reverse
    # it so callers get chronological order for replaying to Groq.
    newest_first = [
        LeadChatMessage(id=3, lead_id=lead_id, role="assistant", content="third"),
        LeadChatMessage(id=2, lead_id=lead_id, role="user", content="second"),
        LeadChatMessage(id=1, lead_id=lead_id, role="user", content="first"),
    ]
    mock_session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = newest_first
    mock_session.execute = AsyncMock(return_value=result)

    messages = await lead_chat_repository.list_recent_messages(mock_session, lead_id, limit=12)

    assert [m.content for m in messages] == ["first", "second", "third"]


async def test_list_all_messages_returns_chronological_order():
    lead_id = uuid.uuid4()
    oldest_first = [
        LeadChatMessage(id=1, lead_id=lead_id, role="user", content="first"),
        LeadChatMessage(id=2, lead_id=lead_id, role="assistant", content="second"),
    ]
    mock_session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = oldest_first
    mock_session.execute = AsyncMock(return_value=result)

    messages = await lead_chat_repository.list_all_messages(mock_session, lead_id)

    assert messages == oldest_first
