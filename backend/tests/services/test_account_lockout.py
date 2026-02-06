import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.auth import (
    AccountLockedError,
    authenticate_user_with_lockout,
    MAX_FAILED_ATTEMPTS,
    LOCKOUT_DURATION_MINUTES,
)


def create_mock_user(
    username: str = "testuser",
    hashed_password: str = "hashed_password",
    failed_attempts: int = 0,
    locked_until: datetime | None = None,
):
    """Create a mock UIUser object."""
    user = MagicMock()
    user.username = username
    user.hashed_password = hashed_password
    user.failed_attempts = failed_attempts
    user.locked_until = locked_until
    return user


def create_mock_db_session(user=None):
    """Create a mock AsyncSession that returns the given user."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()

    return mock_db


@pytest.mark.asyncio
async def test_locked_account_raises_error():
    """Locked account raises AccountLockedError."""
    locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
    user = create_mock_user(locked_until=locked_until)
    mock_db = create_mock_db_session(user)

    with pytest.raises(AccountLockedError) as exc_info:
        await authenticate_user_with_lockout(mock_db, "testuser", "password")

    assert exc_info.value.locked_until == locked_until


@pytest.mark.asyncio
async def test_failed_login_increments_counter():
    """Failed login increments failed_attempts."""
    user = create_mock_user(failed_attempts=0)
    mock_db = create_mock_db_session(user)

    with patch("app.services.auth.verify_password", return_value=False):
        result = await authenticate_user_with_lockout(mock_db, "testuser", "wrongpassword")

    assert result is None
    assert user.failed_attempts == 1
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_fifth_failed_attempt_locks_account():
    """5th failed attempt locks account."""
    user = create_mock_user(failed_attempts=4)  # 4 previous failures
    mock_db = create_mock_db_session(user)

    with patch("app.services.auth.verify_password", return_value=False):
        result = await authenticate_user_with_lockout(mock_db, "testuser", "wrongpassword")

    assert result is None
    assert user.failed_attempts == 5
    assert user.locked_until is not None
    # Verify lockout is set to approximately LOCKOUT_DURATION_MINUTES in the future
    expected_lockout = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
    assert abs((user.locked_until - expected_lockout).total_seconds()) < 2


@pytest.mark.asyncio
async def test_successful_login_resets_counter():
    """Successful login resets failed_attempts counter."""
    user = create_mock_user(failed_attempts=3)
    mock_db = create_mock_db_session(user)

    with patch("app.services.auth.verify_password", return_value=True):
        result = await authenticate_user_with_lockout(mock_db, "testuser", "correctpassword")

    assert result == user
    assert user.failed_attempts == 0
    assert user.locked_until is None
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_expired_lockout_clears_on_next_attempt():
    """Expired lockout clears on next login attempt."""
    # Lockout expired 5 minutes ago
    expired_lockout = datetime.now(timezone.utc) - timedelta(minutes=5)
    user = create_mock_user(failed_attempts=5, locked_until=expired_lockout)
    mock_db = create_mock_db_session(user)

    with patch("app.services.auth.verify_password", return_value=True):
        result = await authenticate_user_with_lockout(mock_db, "testuser", "correctpassword")

    assert result == user
    assert user.failed_attempts == 0
    assert user.locked_until is None


@pytest.mark.asyncio
async def test_user_not_found_returns_none():
    """Non-existent user returns None."""
    mock_db = create_mock_db_session(user=None)

    result = await authenticate_user_with_lockout(mock_db, "nonexistent", "password")

    assert result is None
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_max_failed_attempts_constant():
    """Verify MAX_FAILED_ATTEMPTS is set to 5."""
    assert MAX_FAILED_ATTEMPTS == 5


@pytest.mark.asyncio
async def test_lockout_duration_constant():
    """Verify LOCKOUT_DURATION_MINUTES is set to 15."""
    assert LOCKOUT_DURATION_MINUTES == 15


@pytest.mark.asyncio
async def test_account_locked_error_message():
    """AccountLockedError contains locked_until in message."""
    locked_until = datetime(2024, 1, 15, 12, 30, 0, tzinfo=timezone.utc)
    error = AccountLockedError(locked_until)

    assert error.locked_until == locked_until
    assert "2024-01-15" in str(error)
