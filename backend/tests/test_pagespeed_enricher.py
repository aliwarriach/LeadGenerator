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
                        "performance": {"score": 0.87, "auditRefs": []},
                        "seo": {"score": 0.95},
                        "best-practices": {"score": 0.75},
                    },
                    "audits": {},
                }
            },
        )

    client = _client_with_handler(handler)
    result = await get_pagespeed_scores(
        client,
        "https://example.com",
        api_key=None,
        base_url="https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
        strategy="mobile",
        timeout_seconds=10,
    )

    assert result.scores == {"performance": 87.0, "seo": 95.0, "best_practices": 75.0}
    assert result.performance_issues is None


async def test_get_pagespeed_scores_extracts_failing_performance_audits():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "lighthouseResult": {
                    "categories": {
                        "performance": {
                            "score": 0.6,
                            "auditRefs": [
                                {"id": "render-blocking-resources"},
                                {"id": "uses-optimized-images"},
                                {"id": "first-contentful-paint"},
                            ],
                        },
                        "seo": {"score": 0.95},
                        "best-practices": {"score": 0.75},
                    },
                    "audits": {
                        "render-blocking-resources": {
                            "title": "Eliminate render-blocking resources",
                            "score": 0.2,
                        },
                        "uses-optimized-images": {"title": "Efficiently encode images", "score": 1.0},
                        "first-contentful-paint": {"title": "First Contentful Paint", "score": None},
                    },
                }
            },
        )

    client = _client_with_handler(handler)
    result = await get_pagespeed_scores(
        client,
        "https://example.com",
        api_key=None,
        base_url="https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
        strategy="mobile",
        timeout_seconds=10,
    )

    assert result.performance_issues == ["Eliminate render-blocking resources"]


async def test_get_pagespeed_scores_returns_none_on_http_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "internal error"})

    client = _client_with_handler(handler)
    result = await get_pagespeed_scores(
        client,
        "https://example.com",
        api_key=None,
        base_url="https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
        strategy="mobile",
        timeout_seconds=10,
    )
    assert result is None


async def test_get_pagespeed_scores_returns_none_on_malformed_response():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    client = _client_with_handler(handler)
    result = await get_pagespeed_scores(
        client,
        "https://example.com",
        api_key=None,
        base_url="https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
        strategy="mobile",
        timeout_seconds=10,
    )
    assert result is None


def test_compute_website_quality_score_averages_categories():
    score = compute_website_quality_score({"performance": 80.0, "seo": 100.0, "best_practices": 60.0})
    assert score == 80.0


def test_compute_website_quality_score_returns_none_for_empty_scores():
    assert compute_website_quality_score({}) is None
