from __future__ import annotations

from urllib.parse import urlparse

# Directory/social/aggregator domains that show up constantly as "website"
# candidates (in organic search results, and in a business's own Facebook
# "Contact info" links) but aren't the business's own site — never worth
# treating as its website or spending enrichment quota on.
NON_BUSINESS_DOMAINS = (
    "facebook.com",
    "fb.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "pinterest.com",
    "yelp.com",
    "yellowpages.com",
    "tripadvisor.com",
    "indeed.com",
    "glassdoor.com",
    "wikipedia.org",
    "whatsapp.com",
    "messenger.com",
)


def is_business_domain(url: str | None) -> bool:
    if not url:
        return False
    hostname = (urlparse(url).hostname or "").lower()
    if not hostname:
        return False
    # Host suffix match rather than a substring test on the whole netloc —
    # the old check would also (harmlessly, since it only ever over-rejects)
    # match a business actually named e.g. "myfacebook.com". See L-5.
    return not any(
        hostname == domain or hostname.endswith(f".{domain}") for domain in NON_BUSINESS_DOMAINS
    )
