from app.scrapers.domain_filters import is_business_domain


def test_is_business_domain_true_for_ordinary_site():
    assert is_business_domain("https://urbanestimation.com/") is True


def test_is_business_domain_false_for_none_or_empty():
    assert is_business_domain(None) is False
    assert is_business_domain("") is False


def test_is_business_domain_false_for_social_and_directory_domains():
    for url in (
        "https://www.facebook.com/urbanestimation",
        "https://www.linkedin.com/company/urbanestimation/",
        "https://twitter.com/urbanestimation",
        "https://x.com/urbanestimation",
        "https://www.instagram.com/urbanestimation",
        "https://www.yelp.com/biz/urbanestimation",
        "https://en.wikipedia.org/wiki/Urban_estimation",
    ):
        assert is_business_domain(url) is False, url


def test_is_business_domain_false_for_url_with_no_netloc():
    assert is_business_domain("not-a-url") is False
