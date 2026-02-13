# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

### Backend (Python 3.12+ / FastAPI)
```bash
cd backend
pip install -e ".[dev]"                    # Install with dev dependencies
uvicorn app.main:app --reload --port 8000  # Run dev server
```

### Frontend (React + TypeScript + Vite)
```bash
cd frontend
npm install
npm run dev      # Dev server at localhost:5173 (proxies /api to :8000)
npm run build    # Production build
npm run lint     # ESLint
```

### Docker (full stack)
```bash
docker compose up -d              # Start postgres + api + nginx
NOPE_PORT=9443 docker compose up  # Custom port
```

### Database Migrations
```bash
cd backend
alembic upgrade head                              # Apply all
alembic downgrade -1                              # Rollback one
alembic revision --autogenerate -m "Description"  # Generate from models
```

## Testing

```bash
cd backend
pytest                                          # All 176 tests
pytest -k "test_config"                         # By pattern
pytest tests/test_config.py                     # Single file
pytest tests/api/test_api_keys.py::TestGetApiKeys::test_returns_api_keys  # Single test
pytest -v -s                                    # Verbose with print output
pytest -x --lf                                  # Stop on first failure, rerun last failed
```

## Architecture

### Backend (`backend/app/`)

**Layered architecture**: Router → Service → SQLAlchemy Model

- `api/` - FastAPI routers (auth, lists, iocs, settings, stats)
- `services/` - Business logic (ioc_service, validation, exclusion_service, auth)
- `models/` - SQLAlchemy ORM models (List, IOC, ListIOC, UIUser, Exclusion, APIKey)
- `schemas/` - Pydantic request/response models
- `mcp/tools.py` - 16 MCP tools for LLM integration (response models defined inline)
- `middleware/` - API key auth, rate limiting

**Key patterns:**
- All DB calls are async (`AsyncSession`)
- FastAPI `Depends()` for DB sessions, auth, current user
- RBAC via `require_admin()`, `require_role()` dependencies
- IOC validation pipeline: type detection → exclusion check → uniqueness check

### MCP Tools (`backend/app/mcp/tools.py`)

Tools follow the [MCP spec (2025-06-18)](https://modelcontextprotocol.io/specification/2025-06-18/server/tools). Every tool must have:

- **`inputSchema`**: Use `Annotated[type, Field(description="...")]` for all parameters — FastMCP does NOT parse docstring `Args:` sections into `inputSchema`
- **`outputSchema`**: Return a Pydantic `BaseModel` subclass (not a string). FastMCP auto-generates `outputSchema` from the return type and returns `structuredContent` in responses
- **`annotations`**: Use `@mcp.tool(annotations=ToolAnnotations(...))` with appropriate hints:
  - `readOnlyHint=True` for queries (search, list, get, preview)
  - `destructiveHint=True` for deletions and removals
  - `idempotentHint=True` for operations safe to retry
- **Response models**: Defined as `BaseModel` classes at the top of `tools.py` with `Field(description="...")` on every attribute
- **`description`**: Tool docstrings become the MCP tool description — keep them concise and useful

### Frontend (`frontend/src/`)

- `pages/` - Page components (Dashboard, Lists, IOCs, Settings, Login)
- `components/` - Reusable UI (Layout, ConfirmModal)
- `api/client.ts` - Axios client with auth interceptors
- `context/AuthContext.tsx` - Authentication state

**Key patterns:**
- TanStack Query for server state
- Axios interceptors auto-attach JWT, redirect on 401
- React Router v7 with protected routes

### Database Models

**Core entities:**
- `List` - Blocklists with slug, name, list_type (ip/domain/hash/mixed)
- `IOC` - Indicators with value, type (ip/cidr/domain/wildcard/md5/sha1/sha256)
- `ListIOC` - Many-to-many junction (list_id, ioc_id, added_by)
- `Exclusion` - Built-in (RFC1918, TLDs) and custom exclusion rules
- `UIUser` - Web users with role (admin/analyst) and lockout tracking
- `APIKey` - MCP authentication keys

### API Authentication

- **UI endpoints** (`/api/*`): JWT Bearer token (1-hour expiry)
- **MCP endpoint** (`/mcp`): API key in `api-key` header
- **EDL access** (`/edl/{slug}`): HTTP Basic Auth

## Entry Points

- Backend: `backend/app/main.py` - FastAPI app, lifespan, middleware setup
- Frontend: `frontend/src/main.tsx` - React entry
- MCP tools: `backend/app/mcp/tools.py` - LLM integration

## Environment Variables

Required (app won't start without):
- `SECRET_KEY` - JWT signing key (`openssl rand -hex 32`)
- `DEFAULT_ADMIN_PASSWORD` - Initial admin password
- `DEFAULT_EDL_PASSWORD` - EDL basic auth password
- `DB_PASSWORD` - PostgreSQL password

Optional:
- `NOPE_PORT` - HTTPS port (default: 8081)
- `EDL_BASE_URL` - Override EDL URL base for MCP tools
