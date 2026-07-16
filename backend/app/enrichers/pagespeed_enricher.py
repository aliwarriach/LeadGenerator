from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# PSI's request query param uses SCREAMING_SNAKE_CASE category enums; its
# response JSON keys the same categories in lower-hyphen-case. Both are
# needed since we build the request from one and parse the response with
# the other.
_REQUEST_CATEGORIES = ("PERFORMANCE", "SEO", "BEST_PRACTICES")
_RESPONSE_CATEGORY_KEYS = ("performance", "seo", "best-practices")

# Lighthouse audits scored below this are surfaced as performance_issues.
# 0.9 is Lighthouse's own "passing" cutoff (score bands: 0.9-1 green,
# 0.5-0.89 orange, 0-0.49 red) — anything under it is a real opportunity.
_FAILING_AUDIT_THRESHOLD = 0.9


@dataclass
class PageSpeedResult:
    scores: dict[str, float]
    performance_issues: list[str] | None


def _extract_performance_issues(lighthouse_result: dict) -> list[str] | None:
    audits = lighthouse_result.get("audits", {})
    audit_refs = lighthouse_result.get("categories", {}).get("performance", {}).get("auditRefs", [])

    titles: list[str] = []
    for ref in audit_refs:
        audit = audits.get(ref.get("id"), {})
        score = audit.get("score")
        title = audit.get("title")
        if score is not None and score < _FAILING_AUDIT_THRESHOLD and title:
            titles.append(title)
    return titles or None


async def get_pagespeed_scores(
    client: httpx.AsyncClient,
    website: str,
    *,
    api_key: str | None,
    base_url: str,
    strategy: str,
    timeout_seconds: float,
) -> PageSpeedResult | None:
    """Fetch Lighthouse category scores (0-100) and failing performance
    audit titles for `website`.

    Returns None on any failure (invalid key, quota exceeded, unreachable
    site, malformed response) — PageSpeed is a nice-to-have enrichment, never
    worth failing the whole lead-save pipeline over.
    """
    params: dict[str, object] = {
        "url": website,
        "strategy": strategy,
        "category": list(_REQUEST_CATEGORIES),
    }
    if api_key:
        params["key"] = api_key

    try:
        response = await client.get(base_url, params=params, timeout=timeout_seconds)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # noqa: BLE001 - enrichment failures must never propagate
        logger.warning("PageSpeed request failed for %s: %s", website, exc)
        return None

    try:
        lighthouse_result = data["lighthouseResult"]
        categories = lighthouse_result["categories"]
        scores: dict[str, float] = {}
        for key in _RESPONSE_CATEGORY_KEYS:
            score = categories.get(key, {}).get("score")
            if score is not None:
                scores[key.replace("-", "_")] = round(score * 100, 1)
        if not scores:
            return None
        return PageSpeedResult(
            scores=scores, performance_issues=_extract_performance_issues(lighthouse_result)
        )
    except (KeyError, TypeError) as exc:
        logger.warning("PageSpeed response for %s missing expected fields: %s", website, exc)
        return None


def compute_website_quality_score(scores: dict[str, float]) -> float | None:
    """Equal-weighted average of performance/seo/best-practices (0-100).

    Equal weighting is a deliberate simplification — a fast-but-unpolished
    site and a well-built-but-slow one land at a similar score rather than
    letting one dimension dominate. Revisit if the business wants a speed-
    or SEO-first ranking instead. This is a per-lead *website* score, not the
    overall client rating (that mechanic is built separately, later).
    """
    if not scores:
        return None
    values = list(scores.values())
    return round(sum(values) / len(values), 1)
