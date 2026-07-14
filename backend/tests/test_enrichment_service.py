from unittest.mock import AsyncMock, patch

import httpx

from app.core.config import Settings
from app.services.enrichment_service import enrich_lead


def _settings(**overrides) -> Settings:
    return Settings(**overrides)


async def test_enrich_lead_skips_everything_when_no_website():
    lead = {"name": "Joe's Plumbing", "website": None}
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)))

    result = await enrich_lead(client, lead, _settings())

    assert result == {
        "website_score": None,
        "website_score_details": None,
        "emails": None,
        "tech_stack": None,
        "is_registered": None,
        "logo_valid": None,
        "enriched_at": None,
    }


async def test_enrich_lead_merges_all_enricher_results_and_computes_website_score():
    lead = {"name": "Joe's Plumbing", "website": "https://joesplumbing.example"}
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)))

    with (
        patch(
            "app.services.enrichment_service.pagespeed_enricher.get_pagespeed_scores",
            new=AsyncMock(return_value={"performance": 80.0, "seo": 100.0, "best_practices": 60.0}),
        ),
        patch(
            "app.services.enrichment_service.hunter_enricher.find_emails",
            new=AsyncMock(return_value=["info@joesplumbing.example"]),
        ),
        patch(
            "app.services.enrichment_service.wappalyzer_enricher.detect_tech_stack",
            new=AsyncMock(return_value=["WordPress"]),
        ),
        patch(
            "app.services.enrichment_service.opencorporates_enricher.validate_company",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.services.enrichment_service.clearbit_enricher.validate_logo",
            new=AsyncMock(return_value=True),
        ),
    ):
        result = await enrich_lead(client, lead, _settings())

    assert result["website_score"] == 80.0
    assert result["website_score_details"] == {"performance": 80.0, "seo": 100.0, "best_practices": 60.0}
    assert result["emails"] == ["info@joesplumbing.example"]
    assert result["tech_stack"] == ["WordPress"]
    assert result["is_registered"] is True
    assert result["logo_valid"] is True
    assert result["enriched_at"] is not None


async def test_enrich_lead_skips_wappalyzer_when_disabled():
    lead = {"name": "Joe's Plumbing", "website": "https://joesplumbing.example"}
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)))

    with (
        patch(
            "app.services.enrichment_service.pagespeed_enricher.get_pagespeed_scores",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.enrichment_service.hunter_enricher.find_emails", new=AsyncMock(return_value=None)
        ),
        patch(
            "app.services.enrichment_service.wappalyzer_enricher.detect_tech_stack"
        ) as mock_wappalyzer,
        patch(
            "app.services.enrichment_service.opencorporates_enricher.validate_company",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.enrichment_service.clearbit_enricher.validate_logo", new=AsyncMock(return_value=None)
        ),
    ):
        result = await enrich_lead(client, lead, _settings(wappalyzer_enabled=False))

    mock_wappalyzer.assert_not_called()
    assert result["tech_stack"] is None
    assert result["website_score"] is None
