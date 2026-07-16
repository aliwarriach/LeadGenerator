from __future__ import annotations

import json
import logging
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.enrichers.website_content_enricher import WebsiteContent
from app.schemas.outreach import EmailGenerationResult, ProposalGenerationResult, WhatsAppGenerationResult
from app.schemas.website_audit import WebsiteAuditResult

logger = logging.getLogger(__name__)

_T = TypeVar("_T", bound=BaseModel)

_SYSTEM_PROMPT = (
    "You are a website auditor. Evaluate the given business website's UI/UX, conversion potential, "
    "content quality, and trust signals. Respond with ONLY a single JSON object — no prose, no "
    "markdown fences — matching exactly this schema: "
    '{"ui_score": <int 1-10>, "conversion_score": <int 1-10>, "content_score": <int 1-10>, '
    '"trust_score": <int 1-10>, "issues": [<string>, ...], "summary": <string>}. '
    "The four scores are each an integer from 1 to 10 — not a percentage, not 0-100. "
    "issues is a list of key problems. summary is an overall evaluation."
)


def _build_user_prompt(
    website: str, pagespeed_scores: dict[str, float] | None, content: WebsiteContent | None
) -> str:
    parts = [f"Website: {website}"]

    if pagespeed_scores:
        scores_str = ", ".join(f"{key}: {value}" for key, value in pagespeed_scores.items())
        parts.append(f"PageSpeed scores (0-100): {scores_str}")
    else:
        parts.append("PageSpeed scores: unavailable")

    if content:
        parts.append(f"Page title: {content.get('title') or '(none)'}")
        parts.append(f"Meta description: {content.get('meta_description') or '(none)'}")
        headings = content.get("headings") or []
        parts.append(f"Headings: {' | '.join(headings) if headings else '(none)'}")
        parts.append(f"Page text sample: {content.get('text_sample') or '(none)'}")
    else:
        parts.append("Page content: could not be fetched — evaluate based on PageSpeed data alone")

    return "\n".join(parts)


async def evaluate_website(
    client: httpx.AsyncClient,
    website: str,
    *,
    pagespeed_scores: dict[str, float] | None,
    content: WebsiteContent | None,
    api_key: str | None,
    base_url: str,
    model: str,
    timeout_seconds: float,
    max_retries: int,
) -> WebsiteAuditResult | None:
    """Ask Groq to evaluate `website` on UI/conversion/content/trust and
    return a validated WebsiteAuditResult, or None on any failure.

    Retries (up to `max_retries`) are specifically for the model returning
    JSON that doesn't parse/validate — a network-level failure still fails
    on the first attempt, matching every other enricher's behavior.
    """
    if not api_key:
        logger.warning("GROQ_API_KEY not configured — skipping AI website audit")
        return None

    messages: list[dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(website, pagespeed_scores, content)},
    ]
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    return await _request_json_completion(
        client,
        base_url,
        headers,
        model,
        messages,
        timeout_seconds,
        max_retries,
        response_model=WebsiteAuditResult,
        correction_instruction=(
            "Respond again with ONLY a corrected JSON object matching the exact schema given — "
            "scores must be integers 1-10."
        ),
    )


_EMAIL_SYSTEM_PROMPT = (
    "You are an expert cold-outreach copywriter for a web design/marketing agency. Write a "
    "personalized, non-spammy cold email pitching website improvement services to the business "
    "described below — grounded strictly in the real data given, never invent facts you weren't "
    "told. Avoid spam trigger words, excessive punctuation/caps, or generic templates. "
    "Respond with ONLY a single JSON object — no prose, no markdown fences — matching exactly this "
    'schema: {"subject": <string>, "email_body": <string>}.'
)

_WHATSAPP_SYSTEM_PROMPT = (
    "You are an expert cold-outreach copywriter. Write a short, direct WhatsApp message pitching "
    "website improvement services to the business described below — grounded strictly in the real "
    "data given, never invent facts you weren't told. Style: 2-4 sentences, casual but "
    "professional, no corporate jargon, written to maximize response rate — lead with a specific, "
    "concrete observation about their business, not a generic greeting. "
    'Respond with ONLY a single JSON object — no prose, no markdown fences — matching exactly this '
    'schema: {"message": <string>}.'
)

_PROPOSAL_SYSTEM_PROMPT = (
    "You are a senior consultant at a web design/marketing agency writing a client-facing project "
    "proposal for the business described below — grounded strictly in the real data given, never "
    "invent facts you weren't told. "
    "Respond with ONLY a single JSON object — no prose, no markdown fences — matching exactly this "
    'schema: {"title": <string>, "sections": [{"heading": <string>, "content": <string>}, ...]}. '
    "sections must include exactly these five, in this order, using these exact headings: "
    '"Problem Analysis", "Proposed Solution", "Pricing Estimate", "Timeline", "ROI Justification". '
    "Each section's content should be several sentences, specific and grounded in the data given — "
    "not generic boilerplate."
)

# Appended to the relevant system prompt to steer voice/angle without touching
# the schema — one instruction set shared by all three generators so adding a
# tone later means one edit here, not three.
_TONE_INSTRUCTIONS: dict[str, str] = {
    "default": "Tone: professional, warm, and balanced — a credible, friendly pitch.",
    "direct": (
        "Tone: direct and to-the-point. Skip pleasantries and throat-clearing — lead with the "
        "specific problem and the ask within the first sentence. Minimal fluff."
    ),
    "value_first": (
        "Tone: value-first. Open with the concrete benefit or ROI the business would gain — "
        "quantify it where the data supports it — before mentioning any ask."
    ),
}


def _with_tone(system_prompt: str, tone: str) -> str:
    instruction = _TONE_INSTRUCTIONS.get(tone, _TONE_INSTRUCTIONS["default"])
    return f"{system_prompt}\n\n{instruction}"


async def draft_cold_email(
    client: httpx.AsyncClient,
    lead_context: str,
    *,
    api_key: str | None,
    base_url: str,
    model: str,
    timeout_seconds: float,
    max_retries: int,
    tone: str = "default",
) -> EmailGenerationResult | None:
    """Ask Groq for a personalized cold email grounded in `lead_context`,
    written in the given `tone`. Returns None on any failure — missing key,
    network/HTTP error, or JSON that still fails validation after retries."""
    if not api_key:
        logger.warning("GROQ_API_KEY not configured — skipping AI email generation")
        return None

    messages = [
        {"role": "system", "content": _with_tone(_EMAIL_SYSTEM_PROMPT, tone)},
        {"role": "user", "content": lead_context},
    ]
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    return await _request_json_completion(
        client,
        base_url,
        headers,
        model,
        messages,
        timeout_seconds,
        max_retries,
        response_model=EmailGenerationResult,
        correction_instruction="Respond again with ONLY a corrected JSON object matching the exact schema given.",
    )


async def draft_whatsapp_message(
    client: httpx.AsyncClient,
    lead_context: str,
    *,
    api_key: str | None,
    base_url: str,
    model: str,
    timeout_seconds: float,
    max_retries: int,
    tone: str = "default",
) -> WhatsAppGenerationResult | None:
    """Ask Groq for a short, direct WhatsApp outreach message grounded in
    `lead_context`, written in the given `tone`. Returns None on any failure."""
    if not api_key:
        logger.warning("GROQ_API_KEY not configured — skipping AI WhatsApp message generation")
        return None

    messages = [
        {"role": "system", "content": _with_tone(_WHATSAPP_SYSTEM_PROMPT, tone)},
        {"role": "user", "content": lead_context},
    ]
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    return await _request_json_completion(
        client,
        base_url,
        headers,
        model,
        messages,
        timeout_seconds,
        max_retries,
        response_model=WhatsAppGenerationResult,
        correction_instruction="Respond again with ONLY a corrected JSON object matching the exact schema given.",
    )


async def draft_proposal(
    client: httpx.AsyncClient,
    lead_context: str,
    *,
    api_key: str | None,
    base_url: str,
    model: str,
    timeout_seconds: float,
    max_retries: int,
    tone: str = "default",
) -> ProposalGenerationResult | None:
    """Ask Groq for a client-facing project proposal (problem analysis,
    proposed solution, pricing estimate, timeline, ROI justification)
    grounded in `lead_context`, written in the given `tone`. Returns None on
    any failure."""
    if not api_key:
        logger.warning("GROQ_API_KEY not configured — skipping AI proposal generation")
        return None

    messages = [
        {"role": "system", "content": _with_tone(_PROPOSAL_SYSTEM_PROMPT, tone)},
        {"role": "user", "content": lead_context},
    ]
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    return await _request_json_completion(
        client,
        base_url,
        headers,
        model,
        messages,
        timeout_seconds,
        max_retries,
        response_model=ProposalGenerationResult,
        correction_instruction="Respond again with ONLY a corrected JSON object matching the exact schema given.",
    )


async def send_chat_completion(
    client: httpx.AsyncClient,
    messages: list[dict[str, str]],
    *,
    api_key: str | None,
    base_url: str,
    model: str,
    timeout_seconds: float,
) -> str | None:
    """Free-form (non-JSON) chat completion — used by chat_service for the
    per-lead sales chatbot. No retry-on-malformed-output like
    evaluate_website: there's no schema to validate, just plain text.

    Returns None on any failure (missing key, network/HTTP error) — same
    fail-quiet convention as every other Groq/enrichment call here.
    """
    if not api_key:
        logger.warning("GROQ_API_KEY not configured — skipping AI chat")
        return None

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    return await _request_completion(client, base_url, headers, model, messages, timeout_seconds, json_mode=False)


async def _request_json_completion(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    model: str,
    messages: list[dict[str, str]],
    timeout_seconds: float,
    max_retries: int,
    *,
    response_model: type[_T],
    correction_instruction: str,
) -> _T | None:
    """Shared JSON-mode request/validate/retry loop used by every
    structured Groq call (audit, email, WhatsApp, proposal generation).

    Retries (up to `max_retries`) are specifically for the model returning
    JSON that doesn't parse/validate against `response_model` — a
    network-level failure still fails on the first attempt, matching every
    other enricher's behavior.
    """
    for attempt in range(1, max_retries + 1):
        message_content = await _request_completion(client, base_url, headers, model, messages, timeout_seconds)
        if message_content is None:
            # Network/HTTP-level failure — fails on first attempt like every
            # other enricher, no point retrying a dead connection/bad key.
            return None

        try:
            return response_model.model_validate(json.loads(message_content))
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(
                "Groq response failed %s validation (attempt %s/%s): %s | raw content: %r",
                response_model.__name__,
                attempt,
                max_retries,
                exc,
                message_content,
                exc_info=True,
            )
            if attempt >= max_retries:
                return None
            # A blind identical retry reliably reproduces the same mistake
            # (confirmed: a scale/format error repeats deterministically
            # enough to matter) — feed the bad response and the validation
            # error back to the model so it corrects itself instead.
            messages.append({"role": "assistant", "content": message_content})
            messages.append({"role": "user", "content": f"Your response was invalid: {exc}. {correction_instruction}"})

    return None


async def _request_completion(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    model: str,
    messages: list[dict[str, str]],
    timeout_seconds: float,
    *,
    json_mode: bool = True,
) -> str | None:
    payload: dict[str, object] = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        response = await client.post(base_url, json=payload, headers=headers, timeout=timeout_seconds)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as exc:  # noqa: BLE001 - enrichment failures must never propagate
        logger.warning("Groq request failed for %s: %s", base_url, exc, exc_info=True)
        return None
