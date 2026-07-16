from unittest.mock import AsyncMock

from app.workers import cooldown


def _mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.ttl = AsyncMock(return_value=-2)  # default: key doesn't exist
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    return redis


async def test_seconds_remaining_returns_none_when_key_missing():
    redis = _mock_redis()
    redis.ttl.return_value = -2
    assert await cooldown.seconds_remaining(redis, "google_maps") is None


async def test_seconds_remaining_returns_none_when_no_expiry():
    redis = _mock_redis()
    redis.ttl.return_value = -1
    assert await cooldown.seconds_remaining(redis, "google_maps") is None


async def test_seconds_remaining_returns_ttl_when_cooling_down():
    redis = _mock_redis()
    redis.ttl.return_value = 120
    assert await cooldown.seconds_remaining(redis, "google_maps") == 120


async def test_record_failure_sets_base_cooldown_on_first_strike():
    redis = _mock_redis()
    redis.incr.return_value = 1
    seconds = await cooldown.record_failure(redis, "google_maps")
    assert seconds == cooldown.BASE_COOLDOWN_SECONDS
    redis.set.assert_awaited_once_with("scraper:cooldown:google_maps", 1, ex=cooldown.BASE_COOLDOWN_SECONDS)


async def test_record_failure_doubles_cooldown_on_consecutive_strikes():
    redis = _mock_redis()
    redis.incr.return_value = 3
    seconds = await cooldown.record_failure(redis, "facebook")
    assert seconds == cooldown.BASE_COOLDOWN_SECONDS * 4


async def test_record_failure_caps_at_max_cooldown():
    redis = _mock_redis()
    redis.incr.return_value = 20
    seconds = await cooldown.record_failure(redis, "facebook")
    assert seconds == cooldown.MAX_COOLDOWN_SECONDS


async def test_record_success_clears_strikes():
    redis = _mock_redis()
    await cooldown.record_success(redis, "google_maps")
    redis.delete.assert_awaited_once_with("scraper:strikes:google_maps")
