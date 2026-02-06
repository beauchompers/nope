"""Tests for password validation in the create_user endpoint."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.settings import UserCreate, create_user


class TestCreateUserPasswordValidation:
    """Tests for password validation in POST /api/settings/users endpoint."""

    @pytest.mark.asyncio
    async def test_weak_password_too_short_returns_400(self):
        """Should return 400 when password is too short."""
        mock_db = AsyncMock()
        data = UserCreate(username="newuser", password="short")

        with pytest.raises(HTTPException) as exc_info:
            await create_user(data=data, db=mock_db, _="test_user")

        assert exc_info.value.status_code == 400
        assert "at least 6 characters" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_password_accepted_returns_201(self):
        """Should create user successfully with a valid password."""
        mock_db = AsyncMock()

        # Mock the duplicate check query - no existing user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Track what gets added to db
        added_objects = []

        def track_add(obj):
            added_objects.append(obj)
            obj.id = 1

        mock_db.add = track_add

        data = UserCreate(username="newuser", password="password123")

        result = await create_user(data=data, db=mock_db, _="test_user")

        assert result.id == 1
        assert result.username == "newuser"
        assert len(added_objects) == 1
        assert added_objects[0].username == "newuser"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_password_exactly_6_chars_accepted(self):
        """Should accept password with exactly 6 characters."""
        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        added_objects = []

        def track_add(obj):
            added_objects.append(obj)
            obj.id = 1

        mock_db.add = track_add

        data = UserCreate(username="newuser", password="123456")

        result = await create_user(data=data, db=mock_db, _="test_user")

        assert result.id == 1
        assert result.username == "newuser"

    @pytest.mark.asyncio
    async def test_password_exactly_5_chars_rejected(self):
        """Should reject password with exactly 5 characters."""
        mock_db = AsyncMock()
        data = UserCreate(username="newuser", password="12345")

        with pytest.raises(HTTPException) as exc_info:
            await create_user(data=data, db=mock_db, _="test_user")

        assert exc_info.value.status_code == 400
        assert "at least 6 characters" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_password_validation_happens_before_duplicate_check(self):
        """Password validation should run before checking for duplicate username."""
        mock_db = AsyncMock()

        # Even if user exists, password validation should fail first
        # (db.execute should never be called for weak password)
        data = UserCreate(username="existinguser", password="weak")

        with pytest.raises(HTTPException) as exc_info:
            await create_user(data=data, db=mock_db, _="test_user")

        assert exc_info.value.status_code == 400
        # Database should not have been queried
        mock_db.execute.assert_not_called()
