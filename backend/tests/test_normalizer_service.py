from app.services.normalizer_service import (
    normalize_domain,
    normalize_lead,
    normalize_name,
    normalize_phone,
    normalize_website,
)


def test_normalize_name_collapses_whitespace():
    assert normalize_name("  Joe's   Plumbing  ") == "Joe's Plumbing"


def test_normalize_website_adds_scheme_when_missing():
    assert normalize_website("bahuplumbers.org") == "https://bahuplumbers.org"


def test_normalize_website_lowercases_scheme_and_host_only():
    assert normalize_website("HTTPS://BahuPlumbers.ORG/Contact-Us") == "https://bahuplumbers.org/Contact-Us"


def test_normalize_website_returns_none_for_empty_input():
    assert normalize_website(None) is None
    assert normalize_website("   ") is None


def test_normalize_domain_strips_scheme_and_www():
    assert normalize_domain("https://www.Bahuplumbers.org/contact") == "bahuplumbers.org"
    assert normalize_domain("bahuplumbers.org") == "bahuplumbers.org"


def test_normalize_domain_returns_none_for_no_website():
    assert normalize_domain(None) is None


def test_normalize_phone_formats_valid_pakistani_number_to_e164():
    assert normalize_phone("0300 1234567", default_region="PK") == "+923001234567"
    assert normalize_phone("+92 300 1234567", default_region="PK") == "+923001234567"


def test_normalize_phone_falls_back_to_digit_strip_when_unparseable():
    # Too short to be a valid number in any region — parsing fails, so we
    # fall back to a best-effort cleanup rather than dropping it entirely.
    assert normalize_phone("call 123", default_region="PK") == "123"


def test_normalize_phone_returns_none_for_empty_input():
    assert normalize_phone(None) is None
    assert normalize_phone("   ") is None


def test_normalize_lead_produces_cleaned_copy_with_website_domain():
    lead = {
        "name": "  Bahu  Plumbers ",
        "location": "Karachi",
        "website": "www.bahuplumbers.org",
        "phone": "0300 1234567",
        "source": "google_maps",
        "has_website": False,
        "raw_data": {"rating": 4.9},
    }
    normalized = normalize_lead(lead, default_phone_region="PK")

    assert normalized["name"] == "Bahu Plumbers"
    assert normalized["website"] == "https://www.bahuplumbers.org"
    assert normalized["website_domain"] == "bahuplumbers.org"
    assert normalized["phone"] == "+923001234567"
    assert normalized["has_website"] is True
    # untouched fields pass through
    assert normalized["source"] == "google_maps"
    assert normalized["raw_data"] == {"rating": 4.9}


def test_normalize_lead_handles_missing_website_and_phone():
    lead = {"name": "No Site Co", "website": None, "phone": None}
    normalized = normalize_lead(lead)

    assert normalized["website"] is None
    assert normalized["website_domain"] is None
    assert normalized["phone"] is None
    assert normalized["has_website"] is False
