"""Tests for exclusion service functions."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestGetAllExclusions:
    """Tests for get_all_exclusions."""

    @pytest.mark.asyncio
    async def test_returns_grouped_exclusions(self):
        """Should return exclusions grouped by builtin vs user-defined."""
        from app.services.exclusion_service import get_all_exclusions
        from app.models.exclusion import Exclusion, ExclusionType

        mock_builtin = MagicMock(spec=Exclusion)
        mock_builtin.is_builtin = True

        mock_user = MagicMock(spec=Exclusion)
        mock_user.is_builtin = False

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_builtin, mock_user]
        mock_session.execute.return_value = mock_result

        result = await get_all_exclusions(mock_session)

        assert len(result["builtin"]) == 1
        assert len(result["user_defined"]) == 1


class TestDetectExclusionType:
    """Tests for detect_exclusion_type."""

    def test_detects_ip(self):
        from app.services.exclusion_service import detect_exclusion_type
        assert detect_exclusion_type("192.168.1.1") == "ip"

    def test_detects_ipv6(self):
        from app.services.exclusion_service import detect_exclusion_type
        assert detect_exclusion_type("::1") == "ip"

    def test_detects_cidr(self):
        from app.services.exclusion_service import detect_exclusion_type
        assert detect_exclusion_type("10.0.0.0/8") == "cidr"

    def test_detects_cidr_v6(self):
        from app.services.exclusion_service import detect_exclusion_type
        assert detect_exclusion_type("2001:db8::/32") == "cidr"

    def test_detects_wildcard(self):
        from app.services.exclusion_service import detect_exclusion_type
        assert detect_exclusion_type("*.internal.corp") == "wildcard"

    def test_detects_domain(self):
        from app.services.exclusion_service import detect_exclusion_type
        assert detect_exclusion_type("example.com") == "domain"

    def test_returns_none_for_invalid(self):
        from app.services.exclusion_service import detect_exclusion_type
        assert detect_exclusion_type("invalid") is None

    def test_returns_none_for_empty(self):
        from app.services.exclusion_service import detect_exclusion_type
        assert detect_exclusion_type("") is None


class TestIocMatchesExclusion:
    """Tests for _ioc_matches_exclusion."""

    def test_cidr_matches_ip(self):
        from app.services.exclusion_service import _ioc_matches_exclusion
        assert _ioc_matches_exclusion("192.168.1.100", "ip", "192.168.0.0/16", "cidr") is True

    def test_cidr_does_not_match_outside_ip(self):
        from app.services.exclusion_service import _ioc_matches_exclusion
        assert _ioc_matches_exclusion("10.0.0.1", "ip", "192.168.0.0/16", "cidr") is False

    def test_wildcard_matches_subdomain(self):
        from app.services.exclusion_service import _ioc_matches_exclusion
        assert _ioc_matches_exclusion("mail.internal.corp", "domain", "*.internal.corp", "wildcard") is True

    def test_wildcard_matches_deep_subdomain(self):
        from app.services.exclusion_service import _ioc_matches_exclusion
        assert _ioc_matches_exclusion("a.b.c.internal.corp", "domain", "*.internal.corp", "wildcard") is True

    def test_wildcard_does_not_match_different_domain(self):
        from app.services.exclusion_service import _ioc_matches_exclusion
        assert _ioc_matches_exclusion("mail.external.corp", "domain", "*.internal.corp", "wildcard") is False

    def test_exact_domain_match(self):
        from app.services.exclusion_service import _ioc_matches_exclusion
        assert _ioc_matches_exclusion("example.com", "domain", "example.com", "domain") is True

    def test_exact_domain_no_partial_match(self):
        from app.services.exclusion_service import _ioc_matches_exclusion
        assert _ioc_matches_exclusion("sub.example.com", "domain", "example.com", "domain") is False

    def test_exact_ip_match(self):
        from app.services.exclusion_service import _ioc_matches_exclusion
        assert _ioc_matches_exclusion("192.168.1.1", "ip", "192.168.1.1", "ip") is True

    def test_exact_ip_no_match(self):
        from app.services.exclusion_service import _ioc_matches_exclusion
        assert _ioc_matches_exclusion("192.168.1.2", "ip", "192.168.1.1", "ip") is False


class TestAddExclusion:
    """Tests for add_exclusion."""

    @pytest.mark.asyncio
    async def test_add_exclusion_validation_error(self):
        """Should raise ValidationError for invalid pattern."""
        from app.services.exclusion_service import add_exclusion
        from app.services.validation import ValidationError

        mock_session = AsyncMock()

        with pytest.raises(ValidationError):
            await add_exclusion(mock_session, "invalid", "test reason")

    @pytest.mark.asyncio
    async def test_add_exclusion_duplicate_error(self):
        """Should raise DuplicateExclusionError for existing exclusion."""
        from app.services.exclusion_service import add_exclusion, DuplicateExclusionError
        from app.models.exclusion import Exclusion

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(spec=Exclusion)
        mock_session.execute.return_value = mock_result

        with pytest.raises(DuplicateExclusionError):
            await add_exclusion(mock_session, "192.168.1.1", "test reason")


class TestRemoveExclusion:
    """Tests for remove_exclusion."""

    @pytest.mark.asyncio
    async def test_remove_exclusion_not_found(self):
        """Should return False if exclusion not found."""
        from app.services.exclusion_service import remove_exclusion

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await remove_exclusion(mock_session, "192.168.1.1")
        assert result is False

    @pytest.mark.asyncio
    async def test_remove_builtin_exclusion_error(self):
        """Should raise BuiltinExclusionError for builtin exclusion."""
        from app.services.exclusion_service import remove_exclusion, BuiltinExclusionError
        from app.models.exclusion import Exclusion

        mock_session = AsyncMock()
        mock_exclusion = MagicMock(spec=Exclusion)
        mock_exclusion.is_builtin = True
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_exclusion
        mock_session.execute.return_value = mock_result

        with pytest.raises(BuiltinExclusionError):
            await remove_exclusion(mock_session, "10.0.0.0/8")

    @pytest.mark.asyncio
    async def test_remove_user_exclusion_success(self):
        """Should return True and delete user-defined exclusion."""
        from app.services.exclusion_service import remove_exclusion
        from app.models.exclusion import Exclusion

        mock_session = AsyncMock()
        mock_exclusion = MagicMock(spec=Exclusion)
        mock_exclusion.is_builtin = False
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_exclusion
        mock_session.execute.return_value = mock_result

        result = await remove_exclusion(mock_session, "192.168.1.1")

        assert result is True
        mock_session.delete.assert_called_once_with(mock_exclusion)
        mock_session.commit.assert_called_once()
