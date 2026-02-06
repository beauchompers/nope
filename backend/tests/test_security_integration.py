"""Integration tests for security hardening features.

These tests verify that the security features work together correctly:
- Rate limiting on login
- Account lockout after failed attempts
- Password complexity validation on user creation
- Role-based access control (RBAC)
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.auth import login, require_admin, get_current_user_with_role
from app.api.settings import UserCreate, create_user
from app.middleware.rate_limit import RateLimiter, RateLimitMiddleware
from app.models.user import UserRole
from app.services.auth import (
    AccountLockedError,
    authenticate_user_with_lockout,
    validate_password_complexity,
)


class MockOAuth2PasswordRequestForm:
    """Mock OAuth2PasswordRequestForm for testing."""

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password


class MockUIUser:
    """Mock UIUser model for testing without database."""

    def __init__(
        self,
        id: int,
        username: str,
        hashed_password: str = "hashed",
        role: UserRole = UserRole.analyst,
        failed_attempts: int = 0,
        locked_until: datetime | None = None,
    ):
        self.id = id
        self.username = username
        self.hashed_password = hashed_password
        self.role = role
        self.failed_attempts = failed_attempts
        self.locked_until = locked_until


class MockRequest:
    """Mock Starlette Request for testing middleware."""

    def __init__(self, path: str, method: str = "POST", client_host: str = "192.168.1.1"):
        self.url = MagicMock()
        self.url.path = path
        self.method = method
        self.client = MagicMock()
        self.client.host = client_host


class TestRateLimitingOnLogin:
    """Tests for rate limiting on the login endpoint."""

    def test_login_rate_limiter_blocks_after_5_attempts(self):
        """Login should be rate limited after 5 attempts from same IP."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        client_ip = "192.168.1.100"

        # First 5 requests should be allowed
        for i in range(5):
            allowed, retry_after = limiter.is_allowed(client_ip)
            assert allowed is True, f"Request {i+1} should be allowed"

        # 6th request should be blocked
        allowed, retry_after = limiter.is_allowed(client_ip)
        assert allowed is False
        assert retry_after > 0

    def test_rate_limiter_returns_retry_after_header(self):
        """Rate limiter should return Retry-After value when blocked."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        client_ip = "192.168.1.100"

        # Exhaust the limit
        for _ in range(3):
            limiter.is_allowed(client_ip)

        # Verify retry-after is returned
        allowed, retry_after = limiter.is_allowed(client_ip)
        assert allowed is False
        assert retry_after >= 1

    def test_different_ips_have_separate_limits(self):
        """Different IPs should have independent rate limits."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)

        # Exhaust limit for IP 1
        for _ in range(3):
            limiter.is_allowed("192.168.1.1")

        # IP 1 should be blocked
        allowed_ip1, _ = limiter.is_allowed("192.168.1.1")
        assert allowed_ip1 is False

        # IP 2 should still be allowed
        allowed_ip2, _ = limiter.is_allowed("192.168.1.2")
        assert allowed_ip2 is True


class TestAccountLockoutAfterFailedAttempts:
    """Tests for account lockout functionality."""

    @pytest.mark.asyncio
    async def test_account_locks_after_5_failed_attempts(self):
        """Account should lock after 5 failed password attempts."""
        user = MockUIUser(
            id=1,
            username="testuser",
            hashed_password="hashed",
            failed_attempts=4,  # Already 4 failures
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        # 5th failed attempt should trigger lockout
        with patch("app.services.auth.verify_password", return_value=False):
            result = await authenticate_user_with_lockout(
                mock_db, "testuser", "wrongpassword"
            )

        assert result is None
        assert user.failed_attempts == 5
        assert user.locked_until is not None

    @pytest.mark.asyncio
    async def test_locked_account_returns_423_on_login(self):
        """Locked account should return 423 status code on login attempt."""
        locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
        mock_db = AsyncMock()

        form_data = MockOAuth2PasswordRequestForm(
            username="lockeduser", password="anypassword"
        )

        with patch("app.api.auth.authenticate_user_with_lockout") as mock_auth:
            mock_auth.side_effect = AccountLockedError(locked_until)

            with pytest.raises(HTTPException) as exc_info:
                await login(form_data=form_data, db=mock_db)

            assert exc_info.value.status_code == 423
            assert "locked" in exc_info.value.detail.lower()
            assert locked_until.isoformat() in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_successful_login_resets_failed_attempts(self):
        """Successful login should reset the failed attempts counter."""
        user = MockUIUser(
            id=1,
            username="testuser",
            hashed_password="hashed",
            failed_attempts=4,
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        with patch("app.services.auth.verify_password", return_value=True):
            result = await authenticate_user_with_lockout(
                mock_db, "testuser", "correctpassword"
            )

        assert result == user
        assert user.failed_attempts == 0
        assert user.locked_until is None


class TestWeakPasswordRejectedOnUserCreate:
    """Tests for password validation on user creation."""

    @pytest.mark.asyncio
    async def test_short_password_rejected(self):
        """User creation with password less than 6 characters should fail."""
        mock_db = AsyncMock()
        data = UserCreate(username="newuser", password="short")

        with pytest.raises(HTTPException) as exc_info:
            await create_user(data=data, db=mock_db, _="admin_user")

        assert exc_info.value.status_code == 400
        assert "6 characters" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_password_accepted(self):
        """User creation with valid password should succeed."""
        mock_db = AsyncMock()

        # Mock the duplicate check query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Track what gets added
        added_objects = []

        def track_add(obj):
            added_objects.append(obj)
            obj.id = 1

        mock_db.add = track_add

        data = UserCreate(username="newuser", password="password123")

        result = await create_user(data=data, db=mock_db, _="admin_user")

        assert result.id == 1
        assert result.username == "newuser"
        mock_db.commit.assert_called_once()


class TestAnalystBlockedFromAdminEndpoints:
    """Tests for role-based access control (RBAC)."""

    @pytest.mark.asyncio
    async def test_analyst_gets_403_on_admin_endpoints(self):
        """Analyst role should get 403 on admin-only endpoints."""
        analyst_user = MockUIUser(
            id=2,
            username="analyst",
            role=UserRole.analyst,
        )

        with pytest.raises(HTTPException) as exc_info:
            await require_admin(current_user=analyst_user)

        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_admin_can_access_admin_endpoints(self):
        """Admin role should be able to access admin-only endpoints."""
        admin_user = MockUIUser(
            id=1,
            username="admin",
            role=UserRole.admin,
        )

        result = await require_admin(current_user=admin_user)
        assert result == admin_user

    @pytest.mark.asyncio
    async def test_full_rbac_flow_analyst_blocked(self):
        """Full RBAC flow: analyst token -> user lookup -> role check -> 403."""
        analyst_user = MockUIUser(
            id=2,
            username="analyst",
            role=UserRole.analyst,
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = analyst_user
        mock_db.execute.return_value = mock_result

        with patch("app.api.auth.decode_access_token") as mock_decode:
            mock_decode.return_value = {"sub": "analyst"}

            # Step 1: get_current_user_with_role succeeds and returns user
            user = await get_current_user_with_role(token="valid_token", db=mock_db)
            assert user.role == UserRole.analyst

            # Step 2: require_admin raises 403
            with pytest.raises(HTTPException) as exc_info:
                await require_admin(current_user=user)

            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_full_rbac_flow_admin_allowed(self):
        """Full RBAC flow: admin token -> user lookup -> role check -> success."""
        admin_user = MockUIUser(
            id=1,
            username="admin",
            role=UserRole.admin,
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = admin_user
        mock_db.execute.return_value = mock_result

        with patch("app.api.auth.decode_access_token") as mock_decode:
            mock_decode.return_value = {"sub": "admin"}

            # Step 1: get_current_user_with_role succeeds
            user = await get_current_user_with_role(token="valid_token", db=mock_db)
            assert user.role == UserRole.admin

            # Step 2: require_admin passes
            result = await require_admin(current_user=user)
            assert result == admin_user


class TestSecurityFeaturesIntegration:
    """Integration tests verifying multiple security features work together."""

    @pytest.mark.asyncio
    async def test_rate_limit_and_lockout_work_together(self):
        """Rate limiting should work independently of account lockout.

        Scenario: An attacker tries to brute-force a login.
        - Rate limiting blocks after 5 requests per minute per IP.
        - Account lockout blocks after 5 failed password attempts per account.
        Both mechanisms should function independently.
        """
        # Rate limiter for login
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        client_ip = "192.168.1.100"

        # User starts with 0 failed attempts
        user = MockUIUser(
            id=1,
            username="target",
            hashed_password="hashed",
            failed_attempts=0,
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        # Simulate 5 requests - all should be rate-limit allowed
        for i in range(5):
            allowed, _ = limiter.is_allowed(client_ip)
            assert allowed is True, f"Request {i+1} should pass rate limit"

            # Each request with wrong password
            with patch("app.services.auth.verify_password", return_value=False):
                await authenticate_user_with_lockout(mock_db, "target", "wrong")

        # After 5 failed attempts, account is locked
        assert user.failed_attempts == 5
        assert user.locked_until is not None

        # Rate limit also kicks in for 6th request
        allowed, _ = limiter.is_allowed(client_ip)
        assert allowed is False

    def test_password_minimum_length_requirement(self):
        """Verify password minimum length is enforced."""
        # Too short (< 6 characters)
        with pytest.raises(ValueError) as exc_info:
            validate_password_complexity("short")
        assert "6 characters" in str(exc_info.value)

        # Valid password should not raise
        validate_password_complexity("password")  # No exception

    @pytest.mark.asyncio
    async def test_admin_can_create_user_with_role(self):
        """Admin should be able to create a user with specified role."""
        mock_db = AsyncMock()

        # Mock the duplicate check
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        added_objects = []

        def track_add(obj):
            added_objects.append(obj)
            obj.id = 1

        mock_db.add = track_add

        # Create user with analyst role
        data = UserCreate(
            username="newanalyst",
            password="password123",
            role=UserRole.analyst,
        )

        result = await create_user(data=data, db=mock_db, _="admin_user")

        assert result.username == "newanalyst"
        assert len(added_objects) == 1
        assert added_objects[0].role == UserRole.analyst
