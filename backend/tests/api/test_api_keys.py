"""Tests for API key CRUD endpoints in app/api/settings.py."""

import re
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from app.api.settings import (
    APIKeyCreate,
    APIKeyResponse,
    get_api_keys,
    create_api_key,
    delete_api_key,
)


class MockAPIKey:
    """Mock APIKey model for testing without database."""

    def __init__(self, id: int, name: str, key: str, created_at=None, last_used_at=None):
        self.id = id
        self.name = name
        self.key = key
        self.created_at = created_at or datetime.now()
        self.last_used_at = last_used_at


class TestAPIKeyCreate:
    """Tests for the APIKeyCreate schema."""

    def test_valid_name(self):
        """Should accept a valid name."""
        data = APIKeyCreate(name="my-api-key")
        assert data.name == "my-api-key"

    def test_name_with_spaces(self):
        """Should accept name with spaces."""
        data = APIKeyCreate(name="My API Key")
        assert data.name == "My API Key"


class TestAPIKeyResponse:
    """Tests for the APIKeyResponse schema."""

    def test_from_attributes(self):
        """Should create from model attributes."""
        now = datetime.now()
        response = APIKeyResponse(
            id=1,
            name="test-key",
            key="nope_1234567890abcdef1234567890abcdef",
            created_at=now,
            last_used_at=None,
        )
        assert response.id == 1
        assert response.name == "test-key"
        assert response.key == "nope_1234567890abcdef1234567890abcdef"
        assert response.created_at == now
        assert response.last_used_at is None


class TestGetApiKeys:
    """Tests for GET /api/settings/api-keys endpoint."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_keys(self):
        """Should return empty list when no API keys exist."""
        mock_db = AsyncMock()

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_db.execute.return_value = mock_result

        result = await get_api_keys(db=mock_db, _="test_user")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_api_keys(self):
        """Should return API keys directly from database."""
        now = datetime.now()
        mock_key = MockAPIKey(
            id=1,
            name="test-key",
            key="nope_abcdef1234567890abcdef1234567890",
            created_at=now,
        )

        mock_db = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_key]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        result = await get_api_keys(db=mock_db, _="test_user")

        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].name == "test-key"
        assert result[0].key == "nope_abcdef1234567890abcdef1234567890"
        assert result[0].created_at == now


class TestCreateApiKey:
    """Tests for POST /api/settings/api-keys endpoint."""

    @pytest.mark.asyncio
    async def test_creates_api_key_successfully(self):
        """Should create API key and return it."""
        mock_db = AsyncMock()

        # First query checks for duplicate - returns None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Track what gets added to db
        added_objects = []

        def track_add(obj):
            added_objects.append(obj)
            obj.id = 1
            obj.created_at = datetime.now()

        mock_db.add = track_add

        data = APIKeyCreate(name="test-key")

        with patch("app.api.settings.generate_api_key") as mock_gen:
            mock_gen.return_value = "nope_1234567890abcdef1234567890abcdef"
            result = await create_api_key(data=data, db=mock_db, _="test_user")

        assert result.name == "test-key"
        assert result.key == "nope_1234567890abcdef1234567890abcdef"
        assert len(added_objects) == 1
        assert added_objects[0].name == "test-key"
        assert added_objects[0].key == "nope_1234567890abcdef1234567890abcdef"

    @pytest.mark.asyncio
    async def test_rejects_duplicate_name_with_409(self):
        """Should return 409 when API key name already exists."""
        from fastapi import HTTPException

        mock_db = AsyncMock()

        # First query checks for duplicate - returns existing key
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MockAPIKey(
            id=1, name="existing-key", key="nope_existing"
        )
        mock_db.execute.return_value = mock_result

        data = APIKeyCreate(name="existing-key")

        with pytest.raises(HTTPException) as exc_info:
            await create_api_key(data=data, db=mock_db, _="test_user")

        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_rejects_empty_name_with_400(self):
        """Should return 400 when name is empty or whitespace."""
        from fastapi import HTTPException

        mock_db = AsyncMock()

        data = APIKeyCreate(name="   ")

        with pytest.raises(HTTPException) as exc_info:
            await create_api_key(data=data, db=mock_db, _="test_user")

        assert exc_info.value.status_code == 400
        assert "cannot be empty" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_strips_whitespace_from_name(self):
        """Should strip whitespace from name before saving."""
        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        added_objects = []

        def track_add(obj):
            added_objects.append(obj)
            obj.id = 1
            obj.created_at = datetime.now()

        mock_db.add = track_add

        data = APIKeyCreate(name="  test-key  ")

        with patch("app.api.settings.generate_api_key") as mock_gen:
            mock_gen.return_value = "nope_1234567890abcdef1234567890abcdef"
            result = await create_api_key(data=data, db=mock_db, _="test_user")

        assert result.name == "test-key"
        assert added_objects[0].name == "test-key"


class TestDeleteApiKey:
    """Tests for DELETE /api/settings/api-keys/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_deletes_api_key_successfully(self):
        """Should delete API key by ID."""
        mock_key = MockAPIKey(id=1, name="test-key", key="nope_key")

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key
        mock_db.execute.return_value = mock_result

        await delete_api_key(api_key_id=1, db=mock_db, _="test_user")

        mock_db.delete.assert_called_once_with(mock_key)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_404_when_not_found(self):
        """Should return 404 when API key ID doesn't exist."""
        from fastapi import HTTPException

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_api_key(api_key_id=999, db=mock_db, _="test_user")

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail


class TestAPIKeyFormat:
    """Tests to verify generated API keys match expected format."""

    @pytest.mark.asyncio
    async def test_generated_key_format(self):
        """Verify generated key matches nope_ + 32 hex chars format."""
        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        def track_add(obj):
            obj.id = 1
            obj.created_at = datetime.now()

        mock_db.add = track_add

        data = APIKeyCreate(name="test-key")

        result = await create_api_key(data=data, db=mock_db, _="test_user")

        # Verify the returned key matches expected format
        pattern = r"^nope_[a-f0-9]{32}$"
        assert re.match(pattern, result.key) is not None
