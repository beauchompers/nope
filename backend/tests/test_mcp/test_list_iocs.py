# backend/tests/test_mcp/test_list_iocs.py
"""Tests for list_iocs MCP tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestListIocs:
    """Tests for list_iocs pagination."""

    @pytest.mark.asyncio
    async def test_list_iocs_returns_paginated_results(self):
        """Should return IOCs with pagination info."""
        from app.mcp.tools import list_iocs

        mock_ioc = MagicMock()
        mock_ioc.value = "evil.com"
        mock_ioc.type = "domain"

        with patch("app.mcp.tools.async_session_maker") as mock_session_maker, \
             patch("app.mcp.tools.get_iocs_for_list") as mock_get:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            mock_get.return_value = ([mock_ioc], 1)

            result = await list_iocs.fn("threat-domains", limit=100, offset=0)

            assert result.found is True
            assert len(result.iocs) == 1
            assert result.iocs[0].value == "evil.com"
            assert result.iocs[0].ioc_type == "domain"

    @pytest.mark.asyncio
    async def test_list_iocs_shows_pagination_hint(self):
        """Should indicate more results when they exist."""
        from app.mcp.tools import list_iocs

        mock_iocs = [MagicMock(value=f"ip{i}.com", type="domain") for i in range(100)]

        with patch("app.mcp.tools.async_session_maker") as mock_session_maker, \
             patch("app.mcp.tools.get_iocs_for_list") as mock_get:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            mock_get.return_value = (mock_iocs, 250)

            result = await list_iocs.fn("threat-domains", limit=100, offset=0)

            assert result.has_more is True
            assert result.total == 250

    @pytest.mark.asyncio
    async def test_list_iocs_returns_error_for_nonexistent_list(self):
        """Should return error message for non-existent list."""
        from app.mcp.tools import list_iocs

        with patch("app.mcp.tools.async_session_maker") as mock_session_maker, \
             patch("app.mcp.tools.get_iocs_for_list") as mock_get:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            mock_get.return_value = (None, 0)

            result = await list_iocs.fn("nonexistent")

            assert result.found is False
            assert "not found" in result.message.lower()
