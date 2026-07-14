from app.scrapers.google_maps_scraper import GoogleMapsScraper


def _lead(rating: float | None) -> dict:
    return {"name": "Bahu Plumbers", "raw_data": {"rating": rating}}


def test_meets_rating_threshold_passes_when_no_min_rating_given():
    assert GoogleMapsScraper._meets_rating_threshold(_lead(3.0), None) is True
    assert GoogleMapsScraper._meets_rating_threshold(_lead(None), None) is True


def test_meets_rating_threshold_passes_when_rating_at_or_above_minimum():
    assert GoogleMapsScraper._meets_rating_threshold(_lead(4.5), 4.5) is True
    assert GoogleMapsScraper._meets_rating_threshold(_lead(4.9), 4.5) is True


def test_meets_rating_threshold_fails_when_rating_below_minimum():
    assert GoogleMapsScraper._meets_rating_threshold(_lead(4.2), 4.5) is False


def test_meets_rating_threshold_fails_when_no_rating_available():
    # A listing with no rating at all can't be confirmed to meet the
    # threshold, so it's excluded rather than assumed to pass.
    assert GoogleMapsScraper._meets_rating_threshold(_lead(None), 4.0) is False
