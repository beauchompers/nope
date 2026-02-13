"""Tests for bulk_unblock_ioc MCP tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestBulkUnblockIoc:
    """Tests for bulk_unblock_ioc operations."""

    @pytest.mark.asyncio
    async def test_bulk_unblock_returns_summary(self):
        """Should return summary with removed/not_found counts."""
        from app.mcp.tools import bulk_unblock_ioc

        with patch("app.mcp.tools.async_session_maker") as mock_session_maker, \
             patch("app.mcp.tools.bulk_remove_iocs") as mock_bulk_remove:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            mock_bulk_remove.return_value = {
                "removed": ["evil.com", "bad.com"],
                "not_found": ["nonexistent.com"],
            }

            result = await bulk_unblock_ioc.fn(
                values=["evil.com", "bad.com", "nonexistent.com"],
                list_slug="threat-domains",
            )

            assert result.removed == 2
            assert result.not_found == 1

    @pytest.mark.asyncio
    async def test_bulk_unblock_requires_list_slug_or_all_lists(self):
        """Should require either list_slug or all_lists=True."""
        from app.mcp.tools import bulk_unblock_ioc

        result = await bulk_unblock_ioc.fn(values=["evil.com"])

        assert "must specify" in result.message.lower()

    @pytest.mark.asyncio
    async def test_bulk_unblock_rejects_over_500(self):
        """Should reject more than 500 IOCs."""
        from app.mcp.tools import bulk_unblock_ioc

        values = [f"evil{i}.com" for i in range(501)]
        result = await bulk_unblock_ioc.fn(values=values, list_slug="test-list")

        assert "Maximum 500" in result.message
        assert "501" in result.message

    @pytest.mark.asyncio
    async def test_bulk_unblock_rejects_empty_list(self):
        """Should reject empty IOC list."""
        from app.mcp.tools import bulk_unblock_ioc

        result = await bulk_unblock_ioc.fn(values=[], list_slug="test-list")

        assert "No IOCs provided" in result.message

    @pytest.mark.asyncio
    async def test_bulk_unblock_all_lists(self):
        """Should support removing from all lists."""
        from app.mcp.tools import bulk_unblock_ioc

        with patch("app.mcp.tools.async_session_maker") as mock_session_maker, \
             patch("app.mcp.tools.bulk_remove_iocs") as mock_bulk_remove:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            mock_bulk_remove.return_value = {
                "removed": ["evil.com"],
                "not_found": [],
            }

            result = await bulk_unblock_ioc.fn(
                values=["evil.com"],
                all_lists=True,
            )

            assert "all lists" in result.message
            assert result.removed == 1
            mock_bulk_remove.assert_called_once()
            call_kwargs = mock_bulk_remove.call_args[1]
            assert call_kwargs["all_lists"] is True

    @pytest.mark.asyncio
    async def test_bulk_unblock_shows_not_found_items(self):
        """Should list not found items when count is 10 or fewer."""
        from app.mcp.tools import bulk_unblock_ioc

        with patch("app.mcp.tools.async_session_maker") as mock_session_maker, \
             patch("app.mcp.tools.bulk_remove_iocs") as mock_bulk_remove:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            mock_bulk_remove.return_value = {
                "removed": [],
                "not_found": ["missing1.com", "missing2.com"],
            }

            result = await bulk_unblock_ioc.fn(
                values=["missing1.com", "missing2.com"],
                list_slug="test-list",
            )

            assert "missing1.com" in result.not_found_items
            assert "missing2.com" in result.not_found_items
