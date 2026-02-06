"""Tests for search_ioc MCP tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSearchIocListFilter:
    """Tests for search_ioc list_slug filtering."""

    @pytest.mark.asyncio
    async def test_search_with_list_slug_filters_results(self):
        """Should only return IOCs from the specified list."""
        from app.mcp.tools import search_ioc

        mock_ioc = MagicMock()
        mock_ioc.value = "evil.com"
        mock_ioc.type.value = "domain"
        mock_list_ioc = MagicMock()
        mock_list_ioc.list.slug = "threat-domains"
        mock_ioc.list_iocs = [mock_list_ioc]
        mock_ioc.comments = []

        with patch("app.mcp.tools.async_session_maker") as mock_session_maker, \
             patch("app.mcp.tools.search_iocs") as mock_search:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            mock_search.return_value = [mock_ioc]

            result = await search_ioc.fn("evil", list_slug="threat-domains")

            mock_search.assert_called_once()
            call_args = mock_search.call_args
            assert call_args.kwargs.get("list_slug") == "threat-domains"

    @pytest.mark.asyncio
    async def test_search_without_list_slug_searches_all(self):
        """Should search all lists when list_slug is None."""
        from app.mcp.tools import search_ioc

        with patch("app.mcp.tools.async_session_maker") as mock_session_maker, \
             patch("app.mcp.tools.search_iocs") as mock_search:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            mock_search.return_value = []

            await search_ioc.fn("test")

            call_args = mock_search.call_args
            assert call_args.kwargs.get("list_slug") is None
