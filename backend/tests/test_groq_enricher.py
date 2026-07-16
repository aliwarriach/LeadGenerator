import json

import httpx

from app.enrichers.groq_enricher import (
    draft_cold_email,
    draft_proposal,
    draft_whatsapp_message,
    evaluate_website,
    send_chat_completion,
)

_VALID_AUDIT = {
    "ui_score": 7,
    "conversion_score": 5,
    "content_score": 6,
    "trust_score": 8,
    "issues": ["No clear call-to-action above the fold", "Missing customer testimonials"],
    "summary": "Solid foundation but weak conversion path.",
}


def _client_with_handler(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _completion_response(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


async def test_evaluate_website_returns_none_without_api_key():
    client = _client_with_handler(lambda request: httpx.Response(200, json={}))
    result = await evaluate_website(
        client, "https://example.com", pagespeed_scores=None, content=None,
        api_key=None, base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10, max_retries=2,
    )
    assert result is None


async def test_evaluate_website_parses_valid_response():
    async def handler(request: httpx.Request) -> httpx.Response:
        return _completion_response(json.dumps(_VALID_AUDIT))

    client = _client_with_handler(handler)
    result = await evaluate_website(
        client, "https://example.com",
        pagespeed_scores={"performance": 80.0, "seo": 90.0},
        content={"title": "Example", "meta_description": None, "headings": [], "text_sample": "hi"},
        api_key="key", base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10, max_retries=2,
    )

    assert result is not None
    assert result.ui_score == 7
    assert result.conversion_score == 5
    assert result.issues == _VALID_AUDIT["issues"]
    assert result.summary == _VALID_AUDIT["summary"]


async def test_evaluate_website_sends_authorization_header_and_model():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return _completion_response(json.dumps(_VALID_AUDIT))

    client = _client_with_handler(handler)
    await evaluate_website(
        client, "https://example.com", pagespeed_scores=None, content=None,
        api_key="secret-key", base_url="https://api.groq.com/openai/v1/chat/completions",
        model="llama-3.3-70b-versatile", timeout_seconds=10, max_retries=2,
    )

    assert captured["auth"] == "Bearer secret-key"
    assert captured["body"]["model"] == "llama-3.3-70b-versatile"
    assert captured["body"]["response_format"] == {"type": "json_object"}


async def test_evaluate_website_returns_none_on_request_failure():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = _client_with_handler(handler)
    result = await evaluate_website(
        client, "https://example.com", pagespeed_scores=None, content=None,
        api_key="key", base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10, max_retries=2,
    )
    assert result is None


async def test_evaluate_website_returns_none_when_score_out_of_range():
    bad_audit = dict(_VALID_AUDIT, ui_score=15)  # exceeds the 1-10 bound

    async def handler(request: httpx.Request) -> httpx.Response:
        return _completion_response(json.dumps(bad_audit))

    client = _client_with_handler(handler)
    result = await evaluate_website(
        client, "https://example.com", pagespeed_scores=None, content=None,
        api_key="key", base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10, max_retries=1,
    )
    assert result is None


async def test_evaluate_website_retries_once_on_malformed_json_then_succeeds():
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _completion_response("not valid json")
        return _completion_response(json.dumps(_VALID_AUDIT))

    client = _client_with_handler(handler)
    result = await evaluate_website(
        client, "https://example.com", pagespeed_scores=None, content=None,
        api_key="key", base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10, max_retries=2,
    )

    assert call_count == 2
    assert result is not None
    assert result.ui_score == 7


async def test_evaluate_website_returns_none_after_exhausting_retries_on_malformed_json():
    async def handler(request: httpx.Request) -> httpx.Response:
        return _completion_response("still not valid json")

    client = _client_with_handler(handler)
    result = await evaluate_website(
        client, "https://example.com", pagespeed_scores=None, content=None,
        api_key="key", base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10, max_retries=2,
    )
    assert result is None


async def test_evaluate_website_retry_feeds_bad_response_and_error_back_to_model():
    """Regression test: a blind identical retry reproduces a scale/format
    mistake deterministically — the retry must append the model's own bad
    response plus a correction instruction, not just resend the same request."""
    out_of_range_audit = dict(_VALID_AUDIT, ui_score=80, conversion_score=70)
    captured_bodies: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured_bodies.append(body)
        if len(captured_bodies) == 1:
            return _completion_response(json.dumps(out_of_range_audit))
        return _completion_response(json.dumps(_VALID_AUDIT))

    client = _client_with_handler(handler)
    result = await evaluate_website(
        client, "https://example.com", pagespeed_scores=None, content=None,
        api_key="key", base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10, max_retries=2,
    )

    assert result is not None
    assert result.ui_score == 7  # from the corrected response, not the out-of-range one

    assert len(captured_bodies) == 2
    first_messages = captured_bodies[0]["messages"]
    second_messages = captured_bodies[1]["messages"]
    assert len(second_messages) == len(first_messages) + 2  # bad assistant reply + correction appended
    assert second_messages[-2]["role"] == "assistant"
    assert json.loads(second_messages[-2]["content"])["ui_score"] == 80
    assert second_messages[-1]["role"] == "user"
    assert "1-10" in second_messages[-1]["content"]


async def test_send_chat_completion_returns_none_without_api_key():
    client = _client_with_handler(lambda request: httpx.Response(200, json={}))
    result = await send_chat_completion(
        client, [{"role": "user", "content": "hi"}],
        api_key=None, base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10,
    )
    assert result is None


async def test_send_chat_completion_returns_reply_text():
    async def handler(request: httpx.Request) -> httpx.Response:
        return _completion_response("Lead with the slow homepage load time in your opener.")

    client = _client_with_handler(handler)
    result = await send_chat_completion(
        client, [{"role": "user", "content": "How should I pitch this client?"}],
        api_key="key", base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10,
    )
    assert result == "Lead with the slow homepage load time in your opener."


async def test_send_chat_completion_does_not_request_json_mode():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _completion_response("some reply")

    client = _client_with_handler(handler)
    await send_chat_completion(
        client, [{"role": "user", "content": "hi"}],
        api_key="key", base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10,
    )
    assert "response_format" not in captured["body"]


async def test_send_chat_completion_returns_none_on_request_failure():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = _client_with_handler(handler)
    result = await send_chat_completion(
        client, [{"role": "user", "content": "hi"}],
        api_key="key", base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10,
    )
    assert result is None


_VALID_EMAIL = {
    "subject": "Quick question about your website",
    "email_body": "Hi there, noticed your site loads slowly on mobile...",
}

_VALID_WHATSAPP = {"message": "Hey! Noticed your site takes 8s to load on mobile — costing you customers. Got 5 min to chat?"}

_VALID_PROPOSAL = {
    "title": "Website Optimization Proposal",
    "sections": [
        {"heading": "Problem Analysis", "content": "Your site currently..."},
        {"heading": "Proposed Solution", "content": "We recommend..."},
        {"heading": "Pricing Estimate", "content": "$2,000-$5,000..."},
        {"heading": "Timeline", "content": "4-6 weeks..."},
        {"heading": "ROI Justification", "content": "Improved conversion..."},
    ],
}


async def test_draft_cold_email_returns_none_without_api_key():
    client = _client_with_handler(lambda request: httpx.Response(200, json={}))
    result = await draft_cold_email(
        client, "Business name: Joe's Plumbing",
        api_key=None, base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10, max_retries=2,
    )
    assert result is None


async def test_draft_cold_email_parses_valid_response():
    async def handler(request: httpx.Request) -> httpx.Response:
        return _completion_response(json.dumps(_VALID_EMAIL))

    client = _client_with_handler(handler)
    result = await draft_cold_email(
        client, "Business name: Joe's Plumbing",
        api_key="key", base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10, max_retries=2,
    )

    assert result is not None
    assert result.subject == _VALID_EMAIL["subject"]
    assert result.email_body == _VALID_EMAIL["email_body"]


async def test_draft_cold_email_does_not_request_json_mode_disabled():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _completion_response(json.dumps(_VALID_EMAIL))

    client = _client_with_handler(handler)
    await draft_cold_email(
        client, "Business name: Joe's Plumbing",
        api_key="key", base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10, max_retries=2,
    )
    assert captured["body"]["response_format"] == {"type": "json_object"}


async def test_draft_cold_email_retries_once_on_malformed_json_then_succeeds():
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _completion_response("not valid json")
        return _completion_response(json.dumps(_VALID_EMAIL))

    client = _client_with_handler(handler)
    result = await draft_cold_email(
        client, "Business name: Joe's Plumbing",
        api_key="key", base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10, max_retries=2,
    )
    assert call_count == 2
    assert result is not None


async def test_draft_whatsapp_message_parses_valid_response():
    async def handler(request: httpx.Request) -> httpx.Response:
        return _completion_response(json.dumps(_VALID_WHATSAPP))

    client = _client_with_handler(handler)
    result = await draft_whatsapp_message(
        client, "Business name: Joe's Plumbing",
        api_key="key", base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10, max_retries=2,
    )

    assert result is not None
    assert result.message == _VALID_WHATSAPP["message"]


async def test_draft_whatsapp_message_returns_none_without_api_key():
    client = _client_with_handler(lambda request: httpx.Response(200, json={}))
    result = await draft_whatsapp_message(
        client, "Business name: Joe's Plumbing",
        api_key=None, base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10, max_retries=2,
    )
    assert result is None


async def test_draft_proposal_parses_valid_response():
    async def handler(request: httpx.Request) -> httpx.Response:
        return _completion_response(json.dumps(_VALID_PROPOSAL))

    client = _client_with_handler(handler)
    result = await draft_proposal(
        client, "Business name: Joe's Plumbing",
        api_key="key", base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10, max_retries=2,
    )

    assert result is not None
    assert result.title == _VALID_PROPOSAL["title"]
    assert len(result.sections) == 5
    assert result.sections[0].heading == "Problem Analysis"


async def test_draft_proposal_returns_none_when_fewer_than_five_sections():
    incomplete_proposal = dict(_VALID_PROPOSAL, sections=_VALID_PROPOSAL["sections"][:3])

    async def handler(request: httpx.Request) -> httpx.Response:
        return _completion_response(json.dumps(incomplete_proposal))

    client = _client_with_handler(handler)
    result = await draft_proposal(
        client, "Business name: Joe's Plumbing",
        api_key="key", base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10, max_retries=1,
    )
    assert result is None


async def test_draft_proposal_returns_none_without_api_key():
    client = _client_with_handler(lambda request: httpx.Response(200, json={}))
    result = await draft_proposal(
        client, "Business name: Joe's Plumbing",
        api_key=None, base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10, max_retries=2,
    )
    assert result is None


async def test_draft_cold_email_defaults_to_default_tone_instruction():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _completion_response(json.dumps(_VALID_EMAIL))

    client = _client_with_handler(handler)
    await draft_cold_email(
        client, "Business name: Joe's Plumbing",
        api_key="key", base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10, max_retries=2,
    )
    system_message = captured["body"]["messages"][0]["content"]
    assert "professional, warm, and balanced" in system_message


async def test_draft_cold_email_applies_direct_tone_instruction():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _completion_response(json.dumps(_VALID_EMAIL))

    client = _client_with_handler(handler)
    await draft_cold_email(
        client, "Business name: Joe's Plumbing",
        api_key="key", base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10, max_retries=2, tone="direct",
    )
    system_message = captured["body"]["messages"][0]["content"]
    assert "direct and to-the-point" in system_message


async def test_draft_whatsapp_message_applies_value_first_tone_instruction():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _completion_response(json.dumps(_VALID_WHATSAPP))

    client = _client_with_handler(handler)
    await draft_whatsapp_message(
        client, "Business name: Joe's Plumbing",
        api_key="key", base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10, max_retries=2, tone="value_first",
    )
    system_message = captured["body"]["messages"][0]["content"]
    assert "value-first" in system_message


async def test_draft_proposal_applies_direct_tone_instruction():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _completion_response(json.dumps(_VALID_PROPOSAL))

    client = _client_with_handler(handler)
    await draft_proposal(
        client, "Business name: Joe's Plumbing",
        api_key="key", base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model", timeout_seconds=10, max_retries=2, tone="direct",
    )
    system_message = captured["body"]["messages"][0]["content"]
    assert "direct and to-the-point" in system_message
