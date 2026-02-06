# backend/tests/test_mcp/test_update_ioc.py
"""Tests for update_ioc MCP tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestUpdateIoc:
    """Tests for update_ioc comment append."""

    @pytest.mark.asyncio
    async def test_update_ioc_adds_comment(self):
        """Should add comment to existing IOC."""
        from app.mcp.tools import update_ioc

        with patch("app.mcp.tools.async_session_maker") as mock_session_maker, \
             patch("app.mcp.tools.add_ioc_comment") as mock_add_comment:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            mock_add_comment.return_value = True

            result = await update_ioc.fn("evil.com", "New intel from threat feed")

            assert "comment added" in result.lower() or "added" in result.lower()
            mock_add_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_ioc_returns_error_for_nonexistent(self):
        """Should return error for non-existent IOC."""
        from app.mcp.tools import update_ioc

        with patch("app.mcp.tools.async_session_maker") as mock_session_maker, \
             patch("app.mcp.tools.add_ioc_comment") as mock_add_comment:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            mock_add_comment.return_value = False

            result = await update_ioc.fn("nonexistent.com", "comment")

            assert "not found" in result.lower()
