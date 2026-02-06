"""Tests for MCP tools audit trail functionality."""

from unittest.mock import MagicMock, patch

import pytest

from app.mcp.tools import _get_added_by


class TestGetAddedBy:
    """Tests for _get_added_by helper function."""

    def test_returns_mcp_with_key_name_when_available(self):
        """Should return 'mcp:{key_name}' when API key name is in request state."""
        mock_request = MagicMock()
        mock_request.scope = {"state": {"api_key_name": "my-api-key"}}

        with patch("app.mcp.tools.get_http_request", return_value=mock_request):
            result = _get_added_by()

        assert result == "mcp:my-api-key"

    def test_returns_mcp_when_no_key_name_in_state(self):
        """Should return 'mcp' when state exists but has no api_key_name."""
        mock_request = MagicMock()
        mock_request.scope = {"state": {}}

        with patch("app.mcp.tools.get_http_request", return_value=mock_request):
            result = _get_added_by()

        assert result == "mcp"

    def test_returns_mcp_when_no_state_in_scope(self):
        """Should return 'mcp' when scope has no state dictionary."""
        mock_request = MagicMock()
        mock_request.scope = {}

        with patch("app.mcp.tools.get_http_request", return_value=mock_request):
            result = _get_added_by()

        assert result == "mcp"

    def test_returns_mcp_when_no_request_context(self):
        """Should return 'mcp' when no HTTP request context is available."""
        with patch("app.mcp.tools.get_http_request", side_effect=RuntimeError("No active HTTP request found.")):
            result = _get_added_by()

        assert result == "mcp"

    def test_returns_mcp_when_key_name_is_none(self):
        """Should return 'mcp' when api_key_name is explicitly None."""
        mock_request = MagicMock()
        mock_request.scope = {"state": {"api_key_name": None}}

        with patch("app.mcp.tools.get_http_request", return_value=mock_request):
            result = _get_added_by()

        assert result == "mcp"

    def test_returns_mcp_when_key_name_is_empty_string(self):
        """Should return 'mcp' when api_key_name is empty string."""
        mock_request = MagicMock()
        mock_request.scope = {"state": {"api_key_name": ""}}

        with patch("app.mcp.tools.get_http_request", return_value=mock_request):
            result = _get_added_by()

        assert result == "mcp"

    def test_handles_special_characters_in_key_name(self):
        """Should handle key names with special characters."""
        mock_request = MagicMock()
        mock_request.scope = {"state": {"api_key_name": "key-with_special.chars"}}

        with patch("app.mcp.tools.get_http_request", return_value=mock_request):
            result = _get_added_by()

        assert result == "mcp:key-with_special.chars"

    def test_handles_key_name_with_spaces(self):
        """Should handle key names containing spaces."""
        mock_request = MagicMock()
        mock_request.scope = {"state": {"api_key_name": "key with spaces"}}

        with patch("app.mcp.tools.get_http_request", return_value=mock_request):
            result = _get_added_by()

        assert result == "mcp:key with spaces"
