# backend/tests/test_mcp/test_list_exclusions.py
"""Tests for list_exclusions MCP tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestListExclusions:
    """Tests for list_exclusions tool."""

    @pytest.mark.asyncio
    async def test_formats_exclusions_by_type(self):
        """Should format exclusions grouped by builtin vs user-defined."""
        from app.mcp.tools import list_exclusions

        mock_builtin = MagicMock()
        mock_builtin.value = "10.0.0.0/8"
        mock_builtin.type = "cidr"
        mock_builtin.reason = "RFC1918"

        mock_user = MagicMock()
        mock_user.value = "internal.corp"
        mock_user.type = "domain"
        mock_user.reason = "Internal"

        with patch("app.mcp.tools.async_session_maker") as mock_sm, \
             patch("app.mcp.tools.get_all_exclusions") as mock_get:
            mock_session = AsyncMock()
            mock_sm.return_value.__aenter__.return_value = mock_session
            mock_get.return_value = {
                "builtin": [mock_builtin],
                "user_defined": [mock_user],
            }

            result = await list_exclusions.fn()

            assert "Built-in" in result
            assert "10.0.0.0/8" in result
            assert "RFC1918" in result
            assert "User-defined" in result
            assert "internal.corp" in result

    @pytest.mark.asyncio
    async def test_handles_empty_exclusions(self):
        """Should handle case with no exclusions."""
        from app.mcp.tools import list_exclusions

        with patch("app.mcp.tools.async_session_maker") as mock_sm, \
             patch("app.mcp.tools.get_all_exclusions") as mock_get:
            mock_session = AsyncMock()
            mock_sm.return_value.__aenter__.return_value = mock_session
            mock_get.return_value = {
                "builtin": [],
                "user_defined": [],
            }

            result = await list_exclusions.fn()

            assert "No exclusion rules" in result or "0 total" in result
