# backend/tests/test_mcp/test_update_list.py
"""Tests for update_list MCP tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestUpdateList:
    """Tests for update_list metadata updates."""

    @pytest.mark.asyncio
    async def test_update_list_updates_name(self):
        """Should update list name."""
        from app.mcp.tools import update_list

        mock_list = MagicMock()
        mock_list.name = "Old Name"
        mock_list.slug = "old-name"
        mock_list.description = "Desc"
        mock_list.tags = []

        with patch("app.mcp.tools.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_list
            mock_session.execute.return_value = mock_result

            result = await update_list.fn("old-name", name="New Name")

            assert mock_list.name == "New Name"
            assert result.success is True
            assert "name" in result.updated_fields

    @pytest.mark.asyncio
    async def test_update_list_returns_error_for_nonexistent(self):
        """Should return error for non-existent list."""
        from app.mcp.tools import update_list

        with patch("app.mcp.tools.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result

            result = await update_list.fn("nonexistent", name="New Name")

            assert result.success is False
            assert "not found" in result.message.lower()

    @pytest.mark.asyncio
    async def test_update_list_with_no_changes(self):
        """Should handle call with no update parameters."""
        from app.mcp.tools import update_list

        result = await update_list.fn("some-list")

        assert result.success is False
        assert "no updates" in result.message.lower()
