import httpx

from app.enrichers.pagespeed_enricher import compute_website_quality_score, get_pagespeed_scores


def _client_with_handler(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_get_pagespeed_scores_parses_lighthouse_categories():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "lighthouseResult": {
                    "categories": {
                        "performance": {"score": 0.87},
                        "seo": {"score": 0.95},
                        "best-practices": {"score": 0.75},
                    }
                }
            },
        )

    client = _client_with_handler(handler)
    scores = await get_pagespeed_scores(
        client,
        "https://example.com",
        api_key=None,
        base_url="https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
        strategy="mobile",
        timeout_seconds=10,
    )

    assert scores == {"performance": 87.0, "seo": 95.0, "best_practices": 75.0}


async def test_get_pagespeed_scores_returns_none_on_http_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "internal error"})

    client = _client_with_handler(handler)
    scores = await get_pagespeed_scores(
        client,
        "https://example.com",
        api_key=None,
        base_url="https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
        strategy="mobile",
        timeout_seconds=10,
    )
    assert scores is None


async def test_get_pagespeed_scores_returns_none_on_malformed_response():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    client = _client_with_handler(handler)
    scores = await get_pagespeed_scores(
        client,
        "https://example.com",
        api_key=None,
        base_url="https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
        strategy="mobile",
        timeout_seconds=10,
    )
    assert scores is None


def test_compute_website_quality_score_averages_categories():
    score = compute_website_quality_score({"performance": 80.0, "seo": 100.0, "best_practices": 60.0})
    assert score == 80.0


def test_compute_website_quality_score_returns_none_for_empty_scores():
    assert compute_website_quality_score({}) is None
