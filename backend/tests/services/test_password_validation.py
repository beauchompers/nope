import pytest
from app.services.auth import validate_password_complexity


def test_password_too_short():
    """Password under 6 characters should fail."""
    with pytest.raises(ValueError, match="at least 6 characters"):
        validate_password_complexity("short")


def test_password_exactly_5_chars():
    """Password with exactly 5 characters should fail."""
    with pytest.raises(ValueError, match="at least 6 characters"):
        validate_password_complexity("12345")


def test_password_exactly_6_chars():
    """Password with exactly 6 characters should pass."""
    validate_password_complexity("123456")  # Should not raise


def test_valid_password():
    """Valid password should pass."""
    validate_password_complexity("password123")  # Should not raise
