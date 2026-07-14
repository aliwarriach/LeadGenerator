from __future__ import annotations

import logging

from rapidfuzz import fuzz
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.repositories import lead_repository

logger = logging.getLogger(__name__)

DEFAULT_FUZZY_MATCH_THRESHOLD = 85.0


async def resolve_dedupe_key(
    session: AsyncSession,
    *,
    computed_dedupe_key: str,
    name: str,
    search_location: str | None,
    threshold: float = DEFAULT_FUZZY_MATCH_THRESHOLD,
) -> str:
    """Return the dedupe_key a lead should be upserted under.

    `computed_dedupe_key` is source-specific (it hashes in the source name),
    so it only catches re-runs of the *same* source/query — it can never
    match across sources for the same real-world business. This adds a
    second pass: if no exact match exists, fuzzy-match `name` against other
    leads already saved for the same `search_location` (rapidfuzz
    token_sort_ratio >= threshold). A hit means "this is the same business
    a different source already found" — reuse its dedupe_key so the upsert
    updates that row instead of creating a near-duplicate.
    """
    existing = await lead_repository.get_by_dedupe_key(session, computed_dedupe_key)
    if existing is not None:
        return computed_dedupe_key

    if not search_location:
        return computed_dedupe_key

    candidates = await lead_repository.list_by_search_location(session, search_location)
    match = _best_fuzzy_match(name, candidates, threshold)
    if match is not None:
        logger.info(
            "Fuzzy-matched %r to existing lead %r (dedupe_key=%s)", name, match.name, match.dedupe_key
        )
        return match.dedupe_key

    return computed_dedupe_key


def _best_fuzzy_match(name: str, candidates: list[Lead], threshold: float) -> Lead | None:
    name_lower = name.strip().lower()
    best_match: Lead | None = None
    best_score = 0.0
    for candidate in candidates:
        score = fuzz.token_sort_ratio(name_lower, candidate.name.strip().lower())
        if score > best_score:
            best_match, best_score = candidate, score
    return best_match if best_match is not None and best_score >= threshold else None
