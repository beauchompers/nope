# backend/tests/middleware/test_rate_limit.py
import pytest
from app.middleware.rate_limit import RateLimiter


def test_allows_requests_under_limit():
    """Should allow requests under the rate limit."""
    limiter = RateLimiter(max_requests=5, window_seconds=60)
    for _ in range(5):
        allowed, _ = limiter.is_allowed("192.168.1.1")
        assert allowed is True


def test_blocks_requests_over_limit():
    """Should block requests over the rate limit."""
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    for _ in range(3):
        limiter.is_allowed("192.168.1.1")
    allowed, retry_after = limiter.is_allowed("192.168.1.1")
    assert allowed is False
    assert retry_after > 0


def test_different_keys_tracked_separately():
    """Different IPs should have separate limits."""
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    limiter.is_allowed("192.168.1.1")
    limiter.is_allowed("192.168.1.1")
    allowed1, _ = limiter.is_allowed("192.168.1.1")
    assert allowed1 is False
    allowed2, _ = limiter.is_allowed("192.168.1.2")
    assert allowed2 is True
