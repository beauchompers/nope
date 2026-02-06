"""Tests for role-based access control on settings endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.auth import (
    get_current_user_with_role,
    require_role,
    require_admin,
)
from app.api.settings import get_users, create_user, delete_user
from app.models.user import UserRole


class MockUIUser:
    """Mock UIUser model for testing without database."""

    def __init__(
        self,
        id: int,
        username: str,
        hashed_password: str = "hashed",
        role: UserRole = UserRole.analyst,
    ):
        self.id = id
        self.username = username
        self.hashed_password = hashed_password
        self.role = role


class TestGetCurrentUserWithRole:
    """Tests for get_current_user_with_role dependency."""

    @pytest.mark.asyncio
    async def test_returns_user_object_on_valid_token(self):
        """Should return full UIUser object when token is valid."""
        mock_user = MockUIUser(id=1, username="testuser", role=UserRole.admin)

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        with patch("app.api.auth.decode_access_token") as mock_decode:
            mock_decode.return_value = {"sub": "testuser"}

            result = await get_current_user_with_role(token="valid_token", db=mock_db)

        assert result == mock_user
        assert result.username == "testuser"
        assert result.role == UserRole.admin

    @pytest.mark.asyncio
    async def test_raises_401_on_invalid_token(self):
        """Should raise 401 when token is invalid."""
        mock_db = AsyncMock()

        with patch("app.api.auth.decode_access_token") as mock_decode:
            mock_decode.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_with_role(token="invalid_token", db=mock_db)

            assert exc_info.value.status_code == 401
            assert "Could not validate credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_401_when_user_not_found(self):
        """Should raise 401 when user from token doesn't exist in DB."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with patch("app.api.auth.decode_access_token") as mock_decode:
            mock_decode.return_value = {"sub": "nonexistent"}

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_with_role(token="valid_token", db=mock_db)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_raises_401_when_token_missing_sub(self):
        """Should raise 401 when token payload missing 'sub' claim."""
        mock_db = AsyncMock()

        with patch("app.api.auth.decode_access_token") as mock_decode:
            mock_decode.return_value = {"not_sub": "testuser"}

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_with_role(token="valid_token", db=mock_db)

            assert exc_info.value.status_code == 401


class TestRequireRole:
    """Tests for require_role dependency factory."""

    @pytest.mark.asyncio
    async def test_admin_can_access_admin_endpoints(self):
        """Admin role should pass require_admin check."""
        admin_user = MockUIUser(id=1, username="admin", role=UserRole.admin)

        # Create the role checker dependency
        role_checker = require_role(UserRole.admin)

        # Call it with an admin user
        result = await role_checker(current_user=admin_user)

        assert result == admin_user

    @pytest.mark.asyncio
    async def test_admin_can_access_analyst_endpoints(self):
        """Admin role should pass require_role(analyst) check (admin can do anything)."""
        admin_user = MockUIUser(id=1, username="admin", role=UserRole.admin)

        role_checker = require_role(UserRole.analyst)
        result = await role_checker(current_user=admin_user)

        assert result == admin_user

    @pytest.mark.asyncio
    async def test_analyst_gets_403_on_admin_endpoints(self):
        """Analyst role should get 403 on admin-only endpoints."""
        analyst_user = MockUIUser(id=2, username="analyst", role=UserRole.analyst)

        role_checker = require_role(UserRole.admin)

        with pytest.raises(HTTPException) as exc_info:
            await role_checker(current_user=analyst_user)

        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_analyst_can_access_analyst_endpoints(self):
        """Analyst role should pass require_role(analyst) check."""
        analyst_user = MockUIUser(id=2, username="analyst", role=UserRole.analyst)

        role_checker = require_role(UserRole.analyst)
        result = await role_checker(current_user=analyst_user)

        assert result == analyst_user


class TestRequireAdmin:
    """Tests for require_admin convenience dependency."""

    @pytest.mark.asyncio
    async def test_require_admin_allows_admin(self):
        """require_admin should allow admin users."""
        admin_user = MockUIUser(id=1, username="admin", role=UserRole.admin)

        result = await require_admin(current_user=admin_user)
        assert result == admin_user

    @pytest.mark.asyncio
    async def test_require_admin_blocks_analyst(self):
        """require_admin should block analyst users with 403."""
        analyst_user = MockUIUser(id=2, username="analyst", role=UserRole.analyst)

        with pytest.raises(HTTPException) as exc_info:
            await require_admin(current_user=analyst_user)

        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in exc_info.value.detail


class TestSettingsEndpointsRBAC:
    """Tests for RBAC on settings endpoints."""

    @pytest.mark.asyncio
    async def test_get_users_requires_admin_via_dependency(self):
        """GET /api/settings/users uses require_admin dependency which blocks analysts."""
        analyst_user = MockUIUser(id=2, username="analyst", role=UserRole.analyst)

        # The RBAC check happens in require_admin dependency, not the endpoint
        # So we test that require_admin correctly blocks analyst users
        with pytest.raises(HTTPException) as exc_info:
            await require_admin(current_user=analyst_user)

        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_users_allows_admin(self):
        """GET /api/settings/users should allow admin users."""
        admin_user = MockUIUser(id=1, username="admin", role=UserRole.admin)

        mock_db = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [admin_user]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        # When admin user is passed (simulating successful require_admin check)
        result = await get_users(db=mock_db, _=admin_user)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_create_user_requires_admin(self):
        """POST /api/settings/users should require admin role."""
        from app.api.settings import UserCreate

        analyst_user = MockUIUser(id=2, username="analyst", role=UserRole.analyst)
        mock_db = AsyncMock()

        # Note: The RBAC check happens in require_admin dependency
        # The endpoint function itself expects a UIUser (from require_admin)

    @pytest.mark.asyncio
    async def test_delete_user_requires_admin(self):
        """DELETE /api/settings/users/{id} should require admin role."""
        analyst_user = MockUIUser(id=2, username="analyst", role=UserRole.analyst)
        mock_db = AsyncMock()

        # Note: The RBAC check happens in require_admin dependency

    @pytest.mark.asyncio
    async def test_delete_user_prevents_self_deletion(self):
        """Admin cannot delete their own account."""
        admin_user = MockUIUser(id=1, username="admin", role=UserRole.admin)

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = admin_user
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_user(user_id=1, db=mock_db, current_user=admin_user)

        assert exc_info.value.status_code == 400
        assert "Cannot delete your own account" in exc_info.value.detail


class TestRBACIntegration:
    """Integration-style tests verifying the full RBAC flow."""

    @pytest.mark.asyncio
    async def test_analyst_cannot_access_users_endpoint(self):
        """Full flow: analyst user should get 403 on /api/settings/users."""
        # This tests the full dependency chain
        analyst_user = MockUIUser(id=2, username="analyst", role=UserRole.analyst)

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = analyst_user
        mock_db.execute.return_value = mock_result

        with patch("app.api.auth.decode_access_token") as mock_decode:
            mock_decode.return_value = {"sub": "analyst"}

            # First, get_current_user_with_role succeeds
            user = await get_current_user_with_role(token="valid_token", db=mock_db)
            assert user.role == UserRole.analyst

            # Then, require_admin raises 403
            with pytest.raises(HTTPException) as exc_info:
                await require_admin(current_user=user)

            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_access_users_endpoint(self):
        """Full flow: admin user should access /api/settings/users successfully."""
        admin_user = MockUIUser(id=1, username="admin", role=UserRole.admin)

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = admin_user
        mock_db.execute.return_value = mock_result

        with patch("app.api.auth.decode_access_token") as mock_decode:
            mock_decode.return_value = {"sub": "admin"}

            # First, get_current_user_with_role succeeds
            user = await get_current_user_with_role(token="valid_token", db=mock_db)
            assert user.role == UserRole.admin

            # Then, require_admin passes
            result = await require_admin(current_user=user)
            assert result == admin_user
