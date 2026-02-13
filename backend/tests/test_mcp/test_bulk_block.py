# backend/tests/test_mcp/test_bulk_block.py
"""Tests for bulk_block_ioc MCP tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestBulkBlockIoc:
    """Tests for bulk_block_ioc operations."""

    @pytest.mark.asyncio
    async def test_bulk_block_returns_summary(self):
        """Should return summary with added/skipped/failed counts."""
        from app.mcp.tools import bulk_block_ioc

        with patch("app.mcp.tools.async_session_maker") as mock_session_maker, \
             patch("app.mcp.tools.bulk_add_iocs") as mock_bulk_add:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            mock_bulk_add.return_value = {
                "added": ["evil.com", "bad.com"],
                "skipped": ["existing.com"],
                "failed": [("192.168.1.1", "RFC1918 private range")],
            }

            result = await bulk_block_ioc.fn(
                values=["evil.com", "bad.com", "existing.com", "192.168.1.1"],
                list_slug="threat-domains",
            )

            assert result.added == 2
            assert result.skipped == 1
            assert result.failed == 1
            assert result.failed_items[0].reason == "RFC1918 private range"

    @pytest.mark.asyncio
    async def test_bulk_block_enforces_limit(self):
        """Should reject requests exceeding 500 items."""
        from app.mcp.tools import bulk_block_ioc

        result = await bulk_block_ioc.fn(
            values=["x"] * 501,
            list_slug="test",
        )

        assert "500" in result.message
        assert result.failed == 501

    @pytest.mark.asyncio
    async def test_bulk_block_handles_list_not_found(self):
        """Should return error for non-existent list."""
        from app.mcp.tools import bulk_block_ioc
        from app.services.ioc_service import ListNotFoundError

        with patch("app.mcp.tools.async_session_maker") as mock_session_maker, \
             patch("app.mcp.tools.bulk_add_iocs") as mock_bulk_add:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            mock_bulk_add.side_effect = ListNotFoundError("List not found")

            result = await bulk_block_ioc.fn(values=["evil.com"], list_slug="nonexistent")

            assert "not found" in result.message.lower()
