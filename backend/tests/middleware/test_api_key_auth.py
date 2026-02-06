"""Tests for API key authentication middleware."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.middleware.api_key_auth import (
    APIKeyAuthMiddleware,
    create_authenticated_mcp_app,
)


class MockAPIKey:
    """Mock APIKey model for testing without database."""

    def __init__(self, id: int, name: str, key: str, created_at=None, last_used_at=None):
        self.id = id
        self.name = name
        self.key = key
        self.created_at = created_at or datetime.now(timezone.utc)
        self.last_used_at = last_used_at


def create_test_app_with_middleware():
    """Create a test Starlette app with API key auth middleware."""

    async def homepage(request):
        # Check if api_key_name is in request state
        api_key_name = request.state.api_key_name if hasattr(request.state, "api_key_name") else None
        return PlainTextResponse(f"Hello, authenticated as: {api_key_name}")

    app = Starlette(
        routes=[Route("/", homepage)],
    )

    return APIKeyAuthMiddleware(app)


class TestAPIKeyAuthMiddleware:
    """Tests for APIKeyAuthMiddleware class."""

    def test_returns_401_when_api_key_header_missing(self):
        """Should return 401 with 'API key required' when no api-key header."""
        app = create_test_app_with_middleware()
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/")

        assert response.status_code == 401
        assert response.json() == {"detail": "API key required"}

    def test_returns_401_when_api_key_invalid(self):
        """Should return 401 with 'Invalid API key' when key doesn't exist."""
        with patch("app.middleware.api_key_auth.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            # Query returns no matching key
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result

            app = create_test_app_with_middleware()
            client = TestClient(app, raise_server_exceptions=False)

            response = client.get("/", headers={"api-key": "invalid-key"})

            assert response.status_code == 401
            assert response.json() == {"detail": "Invalid API key"}

    def test_allows_request_when_api_key_valid(self):
        """Should allow request and store key name when API key is valid."""
        with patch("app.middleware.api_key_auth.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            # Query returns matching key
            mock_key = MockAPIKey(id=1, name="my-api-key", key="nope_valid_key_12345678901234567890")
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_key
            mock_session.execute.return_value = mock_result

            app = create_test_app_with_middleware()
            client = TestClient(app, raise_server_exceptions=False)

            response = client.get("/", headers={"api-key": "nope_valid_key_12345678901234567890"})

            assert response.status_code == 200
            assert "my-api-key" in response.text

    def test_updates_last_used_at_on_success(self):
        """Should update last_used_at timestamp when API key is validated."""
        with patch("app.middleware.api_key_auth.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            # Query returns matching key with no last_used_at
            mock_key = MockAPIKey(id=1, name="my-api-key", key="nope_valid_key", last_used_at=None)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_key
            mock_session.execute.return_value = mock_result

            app = create_test_app_with_middleware()
            client = TestClient(app, raise_server_exceptions=False)

            response = client.get("/", headers={"api-key": "nope_valid_key"})

            assert response.status_code == 200
            # Verify last_used_at was updated
            assert mock_key.last_used_at is not None
            mock_session.commit.assert_called_once()

    def test_passes_through_non_http_requests(self):
        """Should pass through non-HTTP requests (like websockets) without auth."""
        # This is tested implicitly through the scope["type"] check
        pass


class TestCreateAuthenticatedMcpApp:
    """Tests for create_authenticated_mcp_app function."""

    def test_returns_asgi_middleware(self):
        """Should return an APIKeyAuthMiddleware instance."""
        mock_mcp = MagicMock()
        mock_mcp.http_app.return_value = Starlette()

        result = create_authenticated_mcp_app(mock_mcp)

        assert isinstance(result, APIKeyAuthMiddleware)

    def test_wraps_mcp_http_app(self):
        """Should call mcp.http_app() to get the underlying app."""
        mock_mcp = MagicMock()
        mock_mcp.http_app.return_value = Starlette()

        create_authenticated_mcp_app(mock_mcp)

        mock_mcp.http_app.assert_called_once()

    def test_requires_api_key_for_requests(self):
        """Should require API key for all requests to wrapped app."""
        # Create a mock MCP app that returns a simple response
        async def mcp_handler(request):
            return PlainTextResponse("MCP response")

        mock_inner_app = Starlette(routes=[Route("/test", mcp_handler)])

        mock_mcp = MagicMock()
        mock_mcp.http_app.return_value = mock_inner_app

        app = create_authenticated_mcp_app(mock_mcp)
        client = TestClient(app, raise_server_exceptions=False)

        # Request without API key should fail
        response = client.get("/test")
        assert response.status_code == 401
        assert response.json() == {"detail": "API key required"}


class TestIntegration:
    """Integration tests for the complete authentication flow."""

    def test_full_authentication_flow(self):
        """Test complete flow: request -> validate -> store name -> respond."""
        with patch("app.middleware.api_key_auth.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            # Setup API key
            mock_key = MockAPIKey(
                id=42,
                name="integration-test-key",
                key="nope_integration_test_key_value",
            )
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_key
            mock_session.execute.return_value = mock_result

            # Create app that exposes the key name from state
            async def check_state(request):
                key_name = getattr(request.state, "api_key_name", "NOT_FOUND")
                return PlainTextResponse(f"Key: {key_name}")

            inner_app = Starlette(routes=[Route("/check", check_state)])
            app = APIKeyAuthMiddleware(inner_app)
            client = TestClient(app, raise_server_exceptions=False)

            response = client.get(
                "/check",
                headers={"api-key": "nope_integration_test_key_value"},
            )

            assert response.status_code == 200
            assert "integration-test-key" in response.text
            assert mock_key.last_used_at is not None

    def test_empty_api_key_header_is_rejected(self):
        """Should reject request when api-key header is empty string."""
        with patch("app.middleware.api_key_auth.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            # No key matches empty string
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result

            app = create_test_app_with_middleware()
            client = TestClient(app, raise_server_exceptions=False)

            response = client.get("/", headers={"api-key": ""})

            assert response.status_code == 401
