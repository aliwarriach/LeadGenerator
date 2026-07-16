from __future__ import annotations

import logging
import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.enrichers import groq_enricher
from app.models.lead_chat_message import ChatRole
from app.repositories import lead_chat_repository, lead_repository
from app.schemas.chat import ChatHistoryResponse, ChatMessageItem, ChatMessageResponse
from app.services.lead_context import build_lead_context
from app.services.lead_service import LeadNotFoundError

logger = logging.getLogger(__name__)


class AiChatUnavailableError(Exception):
    pass


_SYSTEM_PROMPT_TEMPLATE = (
    "You are a senior sales and growth consultant helping an agency convert the "
    "business described below into a paying client. Base every recommendation "
    "strictly on the facts given below — never invent details about the business "
    "you were not told.\n\n"
    "When relevant to the user's question, you should:\n"
    "- Suggest concrete outreach strategies (channel, angle, timing)\n"
    "- Suggest a realistic pricing range for the proposed work\n"
    "- Identify the lead's key weaknesses to lead a pitch with\n"
    "- Provide closing strategies to move the deal forward\n\n"
    "Be clear, specific, and actionable — never generic boilerplate advice.\n\n"
    "--- LEAD DATA ---\n"
    "{lead_context}\n"
    "--- END LEAD DATA ---"
)


async def send_chat_message(
    session: AsyncSession,
    http_client: httpx.AsyncClient,
    lead_id: uuid.UUID,
    message: str,
    settings: Settings,
) -> ChatMessageResponse:
    """Sends one chat turn: injects full lead + AI-audit context plus a
    bounded window of prior turns, asks Groq, and persists both the user's
    message and the reply only on success (a failed call leaves no partial
    history entry).
    """
    lead = await lead_repository.get_by_id(session, lead_id)
    if lead is None:
        raise LeadNotFoundError(f"Lead {lead_id} not found")
    if not settings.groq_api_key:
        raise AiChatUnavailableError("Groq API key not configured")

    history = await lead_chat_repository.list_recent_messages(
        session, lead_id, limit=settings.chat_history_max_messages
    )

    messages = [{"role": "system", "content": _SYSTEM_PROMPT_TEMPLATE.format(lead_context=build_lead_context(lead))}]
    messages.extend({"role": m.role, "content": m.content} for m in history)
    messages.append({"role": "user", "content": message})

    reply = await groq_enricher.send_chat_completion(
        http_client,
        messages,
        api_key=settings.groq_api_key,
        base_url=settings.groq_base_url,
        model=settings.groq_model,
        timeout_seconds=settings.groq_timeout_seconds,
    )
    if reply is None:
        raise AiChatUnavailableError(f"AI chat failed for lead {lead_id} — Groq request was unusable")

    await lead_chat_repository.add_message(session, lead_id, role=ChatRole.USER, content=message)
    assistant_message = await lead_chat_repository.add_message(
        session, lead_id, role=ChatRole.ASSISTANT, content=reply
    )

    return ChatMessageResponse(lead_id=lead_id, reply=reply, created_at=assistant_message.created_at)


async def get_chat_history(session: AsyncSession, lead_id: uuid.UUID) -> ChatHistoryResponse:
    lead = await lead_repository.get_by_id(session, lead_id)
    if lead is None:
        raise LeadNotFoundError(f"Lead {lead_id} not found")

    messages = await lead_chat_repository.list_all_messages(session, lead_id)
    return ChatHistoryResponse(
        lead_id=lead_id,
        messages=[ChatMessageItem.model_validate(m) for m in messages],
    )
