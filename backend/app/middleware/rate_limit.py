"""Rate limiting middleware using sliding window algorithm."""

import time
from collections import defaultdict
from threading import Lock
from typing import Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimiter:
    """Sliding window rate limiter."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)
        self.lock = Lock()

    def is_allowed(self, key: str) -> Tuple[bool, int]:
        """Check if request is allowed for given key.

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        now = time.time()
        window_start = now - self.window_seconds

        with self.lock:
            # Remove old requests outside window
            self.requests[key] = [t for t in self.requests[key] if t > window_start]

            if len(self.requests[key]) >= self.max_requests:
                # Calculate retry-after
                oldest = self.requests[key][0]
                retry_after = int(oldest - window_start) + 1
                return False, max(retry_after, 1)

            # Record this request
            self.requests[key].append(now)
            return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that applies rate limiting to specific paths."""

    def __init__(self, app, login_limiter: RateLimiter, api_limiter: RateLimiter):
        super().__init__(app)
        self.login_limiter = login_limiter
        self.api_limiter = api_limiter

    def _get_client_ip(self, request: Request) -> str:
        """Extract real client IP from proxy headers or fall back to direct IP."""
        # Check X-Forwarded-For first (may contain multiple IPs: client, proxy1, proxy2)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # First IP is the original client
            return forwarded.split(",")[0].strip()
        # Check X-Real-IP (set by nginx)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        # Fall back to direct connection IP
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        path = request.url.path

        # Apply stricter limits to login
        if path == "/api/auth/login" and request.method == "POST":
            allowed, retry_after = self.login_limiter.is_allowed(client_ip)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many login attempts. Please try again later."},
                    headers={"Retry-After": str(retry_after)},
                )

        # Apply general limits to API
        elif path.startswith("/api/"):
            allowed, retry_after = self.api_limiter.is_allowed(client_ip)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please try again later."},
                    headers={"Retry-After": str(retry_after)},
                )

        return await call_next(request)
