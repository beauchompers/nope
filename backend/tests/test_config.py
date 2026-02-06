# backend/tests/test_config.py
import pytest
from unittest.mock import patch
import os


def test_default_secret_key_raises():
    """Startup should fail if SECRET_KEY is the default value."""
    with patch.dict(os.environ, {
        "SECRET_KEY": "change-me-in-production",
        "DEFAULT_ADMIN_PASSWORD": "ValidPass123!",
        "DEFAULT_EDL_PASSWORD": "ValidEdlPass123",
    }, clear=False):
        from app.config import validate_settings, Settings
        settings = Settings()
        with pytest.raises(ValueError, match="SECRET_KEY"):
            validate_settings(settings)


def test_missing_secret_key_raises():
    """Startup should fail if SECRET_KEY is empty."""
    with patch.dict(os.environ, {
        "SECRET_KEY": "",
        "DEFAULT_ADMIN_PASSWORD": "ValidPass123!",
        "DEFAULT_EDL_PASSWORD": "ValidEdlPass123",
    }, clear=False):
        from app.config import validate_settings, Settings
        settings = Settings()
        with pytest.raises(ValueError, match="SECRET_KEY"):
            validate_settings(settings)


def test_missing_admin_password_raises():
    """Startup should fail if DEFAULT_ADMIN_PASSWORD is empty."""
    with patch.dict(os.environ, {
        "SECRET_KEY": "a-valid-secret-key-here",
        "DEFAULT_ADMIN_PASSWORD": "",
        "DEFAULT_EDL_PASSWORD": "ValidEdlPass123",
    }, clear=False):
        from app.config import validate_settings, Settings
        settings = Settings()
        with pytest.raises(ValueError, match="DEFAULT_ADMIN_PASSWORD"):
            validate_settings(settings)


def test_missing_edl_password_raises():
    """Startup should fail if DEFAULT_EDL_PASSWORD is empty."""
    with patch.dict(os.environ, {
        "SECRET_KEY": "a-valid-secret-key-here",
        "DEFAULT_ADMIN_PASSWORD": "ValidPass123!",
        "DEFAULT_EDL_PASSWORD": "",
    }, clear=False):
        from app.config import validate_settings, Settings
        settings = Settings()
        with pytest.raises(ValueError, match="DEFAULT_EDL_PASSWORD"):
            validate_settings(settings)


def test_valid_settings_passes():
    """Valid settings should pass validation."""
    with patch.dict(os.environ, {
        "SECRET_KEY": "a-valid-secret-key-here",
        "DEFAULT_ADMIN_PASSWORD": "ValidPass123!",
        "DEFAULT_EDL_PASSWORD": "ValidEdlPass123",
    }, clear=False):
        from app.config import validate_settings, Settings
        settings = Settings()
        validate_settings(settings)  # Should not raise
