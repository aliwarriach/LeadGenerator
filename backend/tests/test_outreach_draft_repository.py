import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.models.outreach_draft import OutreachDraft
from app.repositories import outreach_draft_repository


async def test_create_draft_commits_and_returns_draft():
    mock_session = AsyncMock()
    # AsyncSession.add() is synchronous in real SQLAlchemy — a bare AsyncMock
    # would make it awaitable and leave an unawaited-coroutine warning.
    mock_session.add = MagicMock()
    lead_id = uuid.uuid4()

    draft = await outreach_draft_repository.create_draft(
        mock_session, lead_id, type="email", subject="Quick question", content="Draft body"
    )

    assert draft.lead_id == lead_id
    assert draft.type == "email"
    assert draft.subject == "Quick question"
    assert draft.content == "Draft body"
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once()


async def test_get_latest_by_lead_and_type_returns_none_when_no_draft():
    mock_session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=result)

    draft = await outreach_draft_repository.get_latest_by_lead_and_type(mock_session, uuid.uuid4(), type="proposal")
    assert draft is None


async def test_get_latest_by_lead_and_type_returns_draft_when_found():
    mock_session = AsyncMock()
    lead_id = uuid.uuid4()
    fake_draft = OutreachDraft(lead_id=lead_id, type="whatsapp", content="Hey!")
    result = MagicMock()
    result.scalar_one_or_none.return_value = fake_draft
    mock_session.execute = AsyncMock(return_value=result)

    draft = await outreach_draft_repository.get_latest_by_lead_and_type(mock_session, lead_id, type="whatsapp")
    assert draft is fake_draft


async def test_get_by_id_returns_none_when_not_found():
    mock_session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=result)

    draft = await outreach_draft_repository.get_by_id(mock_session, uuid.uuid4())
    assert draft is None


async def test_update_draft_commits_and_returns_updated_draft():
    mock_session = AsyncMock()
    now = datetime.now(timezone.utc)
    fake_draft = OutreachDraft(id=uuid.uuid4(), type="proposal", content="Edited content", updated_at=now)
    result = MagicMock()
    result.scalar_one_or_none.return_value = fake_draft
    mock_session.execute = AsyncMock(return_value=result)

    draft = await outreach_draft_repository.update_draft(
        mock_session, fake_draft.id, subject=None, content="Edited content"
    )

    assert draft is fake_draft
    mock_session.commit.assert_awaited_once()
    stmt = mock_session.execute.call_args.args[0]
    compiled_params = stmt.compile().params
    assert compiled_params["content"] == "Edited content"


async def test_update_draft_returns_none_when_missing():
    mock_session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=result)

    draft = await outreach_draft_repository.update_draft(mock_session, uuid.uuid4(), subject=None, content="x")
    assert draft is None
