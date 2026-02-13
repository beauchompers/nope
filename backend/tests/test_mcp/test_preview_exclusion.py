# backend/tests/test_mcp/test_preview_exclusion.py
"""Tests for preview_exclusion MCP tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestPreviewExclusion:
    """Tests for preview_exclusion tool."""

    @pytest.mark.asyncio
    async def test_shows_conflicts(self):
        """Should show conflicting IOCs."""
        from app.mcp.tools import preview_exclusion

        with patch("app.mcp.tools.async_session_maker") as mock_sm, \
             patch("app.mcp.tools.preview_exclusion_conflicts") as mock_preview, \
             patch("app.mcp.tools.detect_exclusion_type") as mock_detect:
            mock_session = AsyncMock()
            mock_sm.return_value.__aenter__.return_value = mock_session
            mock_detect.return_value = "cidr"
            mock_preview.return_value = [
                {"value": "10.1.2.3", "type": "ip", "lists": ["threat-ips"]},
            ]

            result = await preview_exclusion.fn("10.0.0.0/8")

            assert result.safe_to_add is False
            assert len(result.conflicts) == 1
            assert result.conflicts[0].value == "10.1.2.3"
            assert "threat-ips" in result.conflicts[0].lists

    @pytest.mark.asyncio
    async def test_shows_safe_when_no_conflicts(self):
        """Should indicate safe when no conflicts."""
        from app.mcp.tools import preview_exclusion

        with patch("app.mcp.tools.async_session_maker") as mock_sm, \
             patch("app.mcp.tools.preview_exclusion_conflicts") as mock_preview, \
             patch("app.mcp.tools.detect_exclusion_type") as mock_detect:
            mock_session = AsyncMock()
            mock_sm.return_value.__aenter__.return_value = mock_session
            mock_detect.return_value = "cidr"
            mock_preview.return_value = []

            result = await preview_exclusion.fn("192.168.0.0/16")

            assert result.safe_to_add is True
            assert result.conflicts == []

    @pytest.mark.asyncio
    async def test_rejects_invalid_pattern(self):
        """Should reject invalid exclusion patterns."""
        from app.mcp.tools import preview_exclusion

        with patch("app.mcp.tools.detect_exclusion_type") as mock_detect:
            mock_detect.return_value = None

            result = await preview_exclusion.fn("invalid-pattern")

            assert "invalid" in result.message.lower()
            assert result.safe_to_add is False
