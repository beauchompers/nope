# backend/tests/test_mcp/test_list_lists.py
"""Tests for list_lists MCP tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestListListsTagFilter:
    """Tests for list_lists tag filtering."""

    @pytest.mark.asyncio
    async def test_list_lists_with_tag_filters_results(self):
        """Should only return lists with the specified tag."""
        from app.mcp.tools import list_lists

        mock_list = MagicMock()
        mock_list.name = "Threat IPs"
        mock_list.slug = "threat-ips"
        mock_list.description = "Bad IPs"
        mock_list.tags = ["threat-intel", "automated"]
        mock_list.list_iocs = []

        # Create a mock that supports chained query building
        mock_stmt = MagicMock()
        mock_stmt.options.return_value = mock_stmt
        mock_stmt.order_by.return_value = mock_stmt
        mock_stmt.where.return_value = mock_stmt

        with patch("app.mcp.tools.async_session_maker") as mock_session_maker, \
             patch("app.mcp.tools.select", return_value=mock_stmt), \
             patch("app.mcp.tools.get_edl_base_url", return_value="https://nope.local:8081"):
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_list]
            mock_session.execute.return_value = mock_result

            result = await list_lists.fn(tag="threat-intel")

            assert len(result.lists) == 1
            assert result.lists[0].name == "Threat IPs"
            assert result.lists[0].slug == "threat-ips"
            # Verify that where was called (indicating tag filter was applied)
            mock_stmt.where.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_lists_without_tag_returns_all(self):
        """Should return all lists when tag is None."""
        from app.mcp.tools import list_lists

        # Create a mock that supports chained query building
        mock_stmt = MagicMock()
        mock_stmt.options.return_value = mock_stmt
        mock_stmt.order_by.return_value = mock_stmt
        mock_stmt.where.return_value = mock_stmt

        with patch("app.mcp.tools.async_session_maker") as mock_session_maker, \
             patch("app.mcp.tools.select", return_value=mock_stmt), \
             patch("app.mcp.tools.get_edl_base_url", return_value="https://nope.local:8081"):
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_session.execute.return_value = mock_result

            result = await list_lists.fn()

            assert len(result.lists) == 0
            # Verify that where was NOT called (no tag filter)
            mock_stmt.where.assert_not_called()
