from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.config import settings, validate_settings
from app.db import async_session_maker
from app.services.seeder import seed_database
from app.api.lists import router as lists_router
from app.api.iocs import router as iocs_router
from app.api.auth import router as auth_router
from app.api.stats import router as stats_router
from app.api.settings import router as settings_router
from app.mcp.tools import mcp
from app.middleware.api_key_auth import create_authenticated_mcp_app
from app.middleware.rate_limit import RateLimitMiddleware, RateLimiter

# Get the MCP ASGI app (needed for lifespan integration)
# path="/" ensures the endpoint is at the mount point, not /mcp/mcp
mcp_app = mcp.http_app(path="/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate settings at startup
    validate_settings(settings)
    # Startup: seed database
    async with async_session_maker() as db:
        await seed_database(db)
    # Run FastMCP's lifespan for proper initialization
    async with mcp_app.lifespan(app):
        yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="NOPE - Network Object Protection Engine",
    description="EDL Manager for Palo Alto Firewalls",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Rate limiters
login_limiter = RateLimiter(max_requests=5, window_seconds=60)  # 5 per minute
api_limiter = RateLimiter(max_requests=100, window_seconds=60)  # 100 per minute

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware, login_limiter=login_limiter, api_limiter=api_limiter)

app.include_router(lists_router)
app.include_router(iocs_router)
app.include_router(auth_router)
app.include_router(stats_router)
app.include_router(settings_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Mount MCP server with API key authentication at /mcp
# Must be after other routes since mount() catches all sub-paths
from app.middleware.api_key_auth import APIKeyAuthMiddleware
app.mount("/mcp", APIKeyAuthMiddleware(mcp_app))
