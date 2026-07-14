from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import phonenumbers

_WHITESPACE_RE = re.compile(r"\s+")
_SCHEME_RE = re.compile(r"^https?://", re.IGNORECASE)
_NON_PHONE_CHARS_RE = re.compile(r"[^\d+]")


def normalize_name(name: str) -> str:
    return _WHITESPACE_RE.sub(" ", name.strip())


def normalize_website(website: str | None) -> str | None:
    """Ensure a scheme is present and lowercase the scheme/host; leave the
    path/query as-is since those can be case-sensitive."""
    if not website:
        return None
    candidate = website.strip()
    if not candidate:
        return None
    if not _SCHEME_RE.match(candidate):
        candidate = f"https://{candidate}"

    parts = urlsplit(candidate)
    if not parts.netloc:
        return None
    return urlunsplit(parts._replace(scheme=parts.scheme.lower(), netloc=parts.netloc.lower()))


def normalize_domain(website: str | None) -> str | None:
    """Strip scheme/www/path down to a bare, lowercase registrable-ish domain."""
    normalized = normalize_website(website)
    if not normalized:
        return None
    netloc = urlsplit(normalized).netloc
    return netloc[4:] if netloc.startswith("www.") else netloc


def normalize_phone(phone: str | None, default_region: str = "PK") -> str | None:
    """Parse and format to E.164 via `phonenumbers` when possible.

    Falls back to a plain digit-strip when the number can't be parsed against
    `default_region` (e.g. a partial/garbled number scraped from free text) —
    better to keep a best-effort cleaned value than drop the phone entirely.
    """
    if not phone:
        return None
    stripped = phone.strip()
    if not stripped:
        return None

    try:
        parsed = phonenumbers.parse(stripped, default_region)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass

    cleaned = _NON_PHONE_CHARS_RE.sub("", stripped)
    return cleaned or None


def normalize_lead(lead: dict[str, Any], default_phone_region: str = "PK") -> dict[str, Any]:
    """Return a copy of `lead` with name/website/phone cleaned and standardized.

    Adds `website_domain` (bare, lowercase domain) alongside the cleaned
    `website` URL — the domain form is what enrichment and deduplication key
    off of, the full URL is what gets shown/visited.
    """
    normalized = dict(lead)
    normalized["name"] = normalize_name(lead["name"])
    website = normalize_website(lead.get("website"))
    normalized["website"] = website
    normalized["website_domain"] = normalize_domain(website)
    normalized["phone"] = normalize_phone(lead.get("phone"), default_phone_region)
    normalized["has_website"] = bool(website)
    return normalized
