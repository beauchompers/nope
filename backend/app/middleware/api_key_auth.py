"""API key authentication middleware for MCP endpoints."""

from datetime import datetime, timezone

from sqlalchemy import select
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.db import async_session_maker
from app.models.api_key import APIKey


class APIKeyAuthMiddleware:
    """ASGI middleware that validates API key authentication.

    Extracts api-key header, validates against database,
    and updates last_used_at on success. Returns 401 for missing or invalid keys.
    Stores authenticated key name in request state for audit trail.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract api-key header
        headers = dict(scope.get("headers", []))
        api_key_header = headers.get(b"api-key")

        if not api_key_header:
            response = JSONResponse(
                {"detail": "API key required"},
                status_code=401,
            )
            await response(scope, receive, send)
            return

        provided_key = api_key_header.decode("utf-8")

        # Validate against database
        validated_key_name = await self._validate_api_key(provided_key)

        if validated_key_name is None:
            response = JSONResponse(
                {"detail": "Invalid API key"},
                status_code=401,
            )
            await response(scope, receive, send)
            return

        # Store authenticated key name in scope state for audit trail
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["api_key_name"] = validated_key_name

        await self.app(scope, receive, send)

    async def _validate_api_key(self, provided_key: str) -> str | None:
        """Validate the provided API key against database.

        Args:
            provided_key: The API key provided in the request header.

        Returns:
            The name of the validated API key, or None if invalid.
        """
        async with async_session_maker() as db:
            # Query for matching API key directly
            result = await db.execute(
                select(APIKey).where(APIKey.key == provided_key)
            )
            api_key = result.scalar_one_or_none()

            if api_key is None:
                return None

            # Update last_used_at
            api_key.last_used_at = datetime.now(timezone.utc)
            await db.commit()
            return api_key.name


def create_authenticated_mcp_app(mcp) -> ASGIApp:
    """Wrap FastMCP's http_app with API key authentication middleware.

    Args:
        mcp: The FastMCP instance to wrap.

    Returns:
        An ASGI app that requires API key authentication for all requests.
    """
    # Get the underlying ASGI app from FastMCP
    # FastMCP's http_app() already includes routes at /mcp
    mcp_app = mcp.http_app()

    # Wrap with authentication middleware
    return APIKeyAuthMiddleware(mcp_app)
