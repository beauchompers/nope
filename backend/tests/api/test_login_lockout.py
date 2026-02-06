"""Tests for login lockout functionality in the login endpoint."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.auth import login
from app.services.auth import AccountLockedError


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
        hashed_password: str,
        failed_attempts: int = 0,
        locked_until: datetime | None = None,
    ):
        self.id = id
        self.username = username
        self.hashed_password = hashed_password
        self.failed_attempts = failed_attempts
        self.locked_until = locked_until


class TestLoginLockout:
    """Tests for account lockout behavior on login endpoint."""

    @pytest.mark.asyncio
    async def test_locked_account_returns_423(self):
        """Should return 423 status code when account is locked."""
        mock_db = AsyncMock()
        locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)

        form_data = MockOAuth2PasswordRequestForm(
            username="testuser", password="wrongpassword"
        )

        with patch(
            "app.api.auth.authenticate_user_with_lockout"
        ) as mock_auth:
            mock_auth.side_effect = AccountLockedError(locked_until)

            with pytest.raises(HTTPException) as exc_info:
                await login(form_data=form_data, db=mock_db)

            assert exc_info.value.status_code == 423
            assert "locked" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_locked_account_detail_includes_locked_until(self):
        """Should include locked_until timestamp in response detail."""
        mock_db = AsyncMock()
        locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)

        form_data = MockOAuth2PasswordRequestForm(
            username="testuser", password="wrongpassword"
        )

        with patch(
            "app.api.auth.authenticate_user_with_lockout"
        ) as mock_auth:
            mock_auth.side_effect = AccountLockedError(locked_until)

            with pytest.raises(HTTPException) as exc_info:
                await login(form_data=form_data, db=mock_db)

            assert locked_until.isoformat() in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_credentials_returns_401(self):
        """Should return 401 for invalid credentials when not locked."""
        mock_db = AsyncMock()

        form_data = MockOAuth2PasswordRequestForm(
            username="testuser", password="wrongpassword"
        )

        with patch(
            "app.api.auth.authenticate_user_with_lockout"
        ) as mock_auth:
            mock_auth.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await login(form_data=form_data, db=mock_db)

            assert exc_info.value.status_code == 401
            assert "Incorrect username or password" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_credentials_returns_token(self):
        """Should return token for valid credentials."""
        mock_db = AsyncMock()
        mock_user = MockUIUser(
            id=1,
            username="testuser",
            hashed_password="hashed",
        )

        form_data = MockOAuth2PasswordRequestForm(
            username="testuser", password="correctpassword"
        )

        with patch(
            "app.api.auth.authenticate_user_with_lockout"
        ) as mock_auth, patch("app.api.auth.create_access_token") as mock_token:
            mock_auth.return_value = mock_user
            mock_token.return_value = "test_access_token"

            result = await login(form_data=form_data, db=mock_db)

            assert result.access_token == "test_access_token"
            assert result.token_type == "bearer"

    @pytest.mark.asyncio
    async def test_sixth_attempt_after_five_failures_returns_423(self):
        """After 5 failed attempts, the 6th attempt should return 423."""
        mock_db = AsyncMock()
        locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)

        form_data = MockOAuth2PasswordRequestForm(
            username="testuser", password="wrongpassword"
        )

        # Simulate 5 failed attempts followed by lockout on 6th
        with patch(
            "app.api.auth.authenticate_user_with_lockout"
        ) as mock_auth:
            # First 5 calls return None (failed auth), 6th raises AccountLockedError
            mock_auth.side_effect = [
                None,  # Attempt 1
                None,  # Attempt 2
                None,  # Attempt 3
                None,  # Attempt 4
                None,  # Attempt 5
                AccountLockedError(locked_until),  # Attempt 6 - locked
            ]

            # First 5 attempts should return 401
            for i in range(5):
                with pytest.raises(HTTPException) as exc_info:
                    await login(form_data=form_data, db=mock_db)
                assert exc_info.value.status_code == 401, f"Attempt {i+1} should return 401"

            # 6th attempt should return 423
            with pytest.raises(HTTPException) as exc_info:
                await login(form_data=form_data, db=mock_db)

            assert exc_info.value.status_code == 423
            assert "locked" in exc_info.value.detail.lower()
