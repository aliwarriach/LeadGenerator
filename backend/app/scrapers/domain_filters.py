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
    netloc = urlparse(url).netloc.lower()
    return bool(netloc) and not any(domain in netloc for domain in NON_BUSINESS_DOMAINS)
