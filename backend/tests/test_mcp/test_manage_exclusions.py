# backend/tests/test_mcp/test_manage_exclusions.py
"""Tests for add_exclusion and remove_exclusion MCP tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestAddExclusion:
    """Tests for add_exclusion tool."""

    @pytest.mark.asyncio
    async def test_adds_exclusion(self):
        """Should add exclusion and return success."""
        from app.mcp.tools import add_exclusion

        mock_exclusion = MagicMock()
        mock_exclusion.value = "internal.corp"
        mock_exclusion.type = "domain"

        with patch("app.mcp.tools.async_session_maker") as mock_sm, \
             patch("app.mcp.tools.add_exclusion_svc") as mock_add:
            mock_session = AsyncMock()
            mock_sm.return_value.__aenter__.return_value = mock_session
            mock_add.return_value = {"exclusion": mock_exclusion, "purged": []}

            result = await add_exclusion.fn("internal.corp", "Internal domain")

            assert result.success is True
            assert result.value == "internal.corp"
            assert result.exclusion_type == "domain"

    @pytest.mark.asyncio
    async def test_shows_purged_when_purge_conflicts(self):
        """Should show purged IOCs when purge_conflicts=True."""
        from app.mcp.tools import add_exclusion

        mock_exclusion = MagicMock()
        mock_exclusion.value = "10.0.0.0/8"
        mock_exclusion.type = "cidr"

        with patch("app.mcp.tools.async_session_maker") as mock_sm, \
             patch("app.mcp.tools.add_exclusion_svc") as mock_add:
            mock_session = AsyncMock()
            mock_sm.return_value.__aenter__.return_value = mock_session
            mock_add.return_value = {
                "exclusion": mock_exclusion,
                "purged": [
                    {"value": "10.1.2.3", "type": "ip", "lists": ["threat-ips"]},
                ],
            }

            result = await add_exclusion.fn("10.0.0.0/8", "Private", purge_conflicts=True)

            assert len(result.purged) == 1
            assert result.purged[0].value == "10.1.2.3"
            assert "purged" in result.message.lower()


class TestRemoveExclusion:
    """Tests for remove_exclusion tool."""

    @pytest.mark.asyncio
    async def test_removes_exclusion(self):
        """Should remove exclusion and return success."""
        from app.mcp.tools import remove_exclusion

        with patch("app.mcp.tools.async_session_maker") as mock_sm, \
             patch("app.mcp.tools.remove_exclusion_svc") as mock_remove:
            mock_session = AsyncMock()
            mock_sm.return_value.__aenter__.return_value = mock_session
            mock_remove.return_value = True

            result = await remove_exclusion.fn("internal.corp")

            assert result.success is True

    @pytest.mark.asyncio
    async def test_rejects_builtin_removal(self):
        """Should reject removal of builtin exclusions."""
        from app.mcp.tools import remove_exclusion
        from app.services.exclusion_service import BuiltinExclusionError

        with patch("app.mcp.tools.async_session_maker") as mock_sm, \
             patch("app.mcp.tools.remove_exclusion_svc") as mock_remove:
            mock_session = AsyncMock()
            mock_sm.return_value.__aenter__.return_value = mock_session
            mock_remove.side_effect = BuiltinExclusionError("Cannot remove builtin")

            result = await remove_exclusion.fn("10.0.0.0/8")

            assert result.success is False
            assert "cannot" in result.message.lower() or "built-in" in result.message.lower()

    @pytest.mark.asyncio
    async def test_returns_not_found(self):
        """Should return not found message for missing exclusion."""
        from app.mcp.tools import remove_exclusion

        with patch("app.mcp.tools.async_session_maker") as mock_sm, \
             patch("app.mcp.tools.remove_exclusion_svc") as mock_remove:
            mock_session = AsyncMock()
            mock_sm.return_value.__aenter__.return_value = mock_session
            mock_remove.return_value = False

            result = await remove_exclusion.fn("nonexistent.com")

            assert result.success is False
            assert "not found" in result.message.lower()
