# NOPE - Network Object Protection Engine

> "When your AI says NOPE, your firewall listens."

NOPE is an MCP-enabled External Dynamic List (EDL) manager for Palo Alto firewalls. It provides a web UI, REST API, and MCP tools for managing IP and domain blocklists that firewalls consume via HTTPS.

## Features

- **Web UI** - Modern React interface for managing lists and IOCs
- **REST API** - Full CRUD operations for lists and IOCs
- **MCP Integration** - LLM-friendly tools for blocking threats via natural language
- **EDL Serving** - NGINX serves text-based lists compatible with Palo Alto firewalls
- **Validation** - Automatic validation of IPs, CIDRs, and domains
- **Exclusions** - Built-in protection against blocking TLDs, RFC1918, and localhost
- **Deduplication** - IOCs are deduplicated with comments from multiple sources

## Quick Start

### Prerequisites

- Docker and Docker Compose

### 1. Clone and Start

```bash
git clone <repository-url>
cd nope-edl
./setup.sh
```

`setup.sh` will:
- Create `.env` from `.env.example` (if it doesn't exist)
- Auto-generate all required secrets
- Start the Docker Compose stack
- Print a startup banner with your credentials

Self-signed SSL certificates are automatically generated on first startup.

To use a different port, set `NOPE_PORT` in `.env` before running `setup.sh`, or:

```bash
NOPE_PORT=9443 docker compose up -d
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Docker Compose                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │   NGINX     │    │  NOPE API   │    │    PostgreSQL       │ │
│  │  (HTTPS)    │───▶│  (FastAPI)  │───▶│    (Database)       │ │
│  │  Port 8081  │    │  Port 8000  │    │    Port 5432        │ │
│  └─────────────┘    └─────────────┘    └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## API Endpoints

### Lists

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/lists` | Get all lists with IOC counts |
| POST | `/api/lists` | Create a new list |
| GET | `/api/lists/{slug}` | Get list details |
| PATCH | `/api/lists/{slug}` | Update a list |
| DELETE | `/api/lists/{slug}` | Delete a list |

### IOCs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/iocs?q={query}` | Search IOCs |
| POST | `/api/iocs` | Add IOC to list(s) |
| GET | `/api/iocs/{id}` | Get IOC details |
| DELETE | `/api/iocs/{id}` | Delete IOC from all lists |
| DELETE | `/api/iocs/{id}/lists/{slug}` | Remove IOC from specific list |

### EDL Access

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/edl/{slug}` | Get list as text (Basic Auth required) |

## MCP Tools

NOPE exposes MCP tools at `/mcp` for LLM integration. These tools enable AI assistants to manage blocklists through natural language.

### List Management

| Tool | Description |
|------|-------------|
| `list_lists` | Get all blocklists with IOC counts and descriptions |
| `get_list` | Get detailed information about a specific list |
| `create_list` | Create a new blocklist with name, description, and tags |
| `update_list` | Update list metadata (name, description, tags) |
| `delete_list` | Delete a list and remove all IOC associations |
| `list_iocs` | List all IOCs on a specific list with pagination |

### IOC Management

| Tool | Description |
|------|-------------|
| `block_ioc` | Add an IOC (IP, CIDR, domain, wildcard, or hash) to a blocklist |
| `unblock_ioc` | Remove an IOC from a specific list or all lists |
| `search_ioc` | Search for IOCs across all lists (supports partial matching) |
| `update_ioc` | Add a comment to an existing IOC for audit history |
| `bulk_block_ioc` | Add multiple IOCs (up to 500) in a single operation |
| `bulk_unblock_ioc` | Remove multiple IOCs (up to 500) in a single operation |

### Exclusion Management

Exclusions prevent certain IOCs from being added to blocklists (e.g., RFC1918 private ranges, TLDs).

| Tool | Description |
|------|-------------|
| `list_exclusions` | List all active exclusion rules (built-in and user-defined) |
| `preview_exclusion` | Preview impact of adding an exclusion (shows conflicting IOCs) |
| `add_exclusion` | Add a custom exclusion rule with optional conflict purging |
| `remove_exclusion` | Remove a user-defined exclusion rule |

### Supported IOC Types

NOPE automatically detects IOC types:

| Type | Examples |
|------|----------|
| IP Address | `203.0.113.50` |
| CIDR Range | `203.0.113.0/24` |
| Domain | `evil.com`, `malware.example.net` |
| Wildcard Domain | `*.badsite.com` |
| SHA256 Hash | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| SHA1 Hash | `da39a3ee5e6b4b0d3255bfef95601890afd80709` |
| MD5 Hash | `d41d8cd98f00b204e9800998ecf8427e` |

### MCP Authentication

MCP endpoints require API key authentication. Create an API key in **Settings > API Keys** and include it in the `api-key` header.

### Connecting Claude Desktop via mcp-proxy

Claude Desktop only supports stdio transport, so you need [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) to connect to NOPE's HTTP-based MCP server.

#### 1. Install mcp-proxy

```bash
# Using pip
pip install mcp-proxy

# Or using pipx (recommended)
pipx install mcp-proxy
```

#### 2. Create an API Key

1. Log in to NOPE at https://your-server
2. Go to **Settings > API Keys**
3. Click **+ ADD API KEY**
4. Enter a name (e.g., "claude-desktop")
5. Copy the generated key (starts with `nope_`)

#### 3. Configure Claude Desktop

Edit your Claude Desktop config file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Add the NOPE server configuration:

```json
{
  "mcpServers": {
    "nope": {
      "command": "mcp-proxy",
      "args": [
        "--transport=streamablehttp",
        "--no-verify-ssl",
        "--headers", "api-key", "nope_YOUR_API_KEY_HERE",
        "https://your-nope-server/mcp"
      ]
    }
  }
}
```

**Arguments explained:**
- `--transport=streamablehttp` - Use HTTP transport (required for NOPE's MCP endpoint)
- `--no-verify-ssl` - Skip SSL verification for self-signed certificates
- `--headers api-key ...` - Pass the API key for authentication

> **Note**: If Claude Desktop can't find mcp-proxy, use the full path. Run `which mcp-proxy` (macOS/Linux) or `where.exe mcp-proxy` (Windows) to get the path.

#### 4. Restart Claude Desktop

Completely quit and restart Claude Desktop to load the new configuration.

#### 5. Verify Connection

In Claude Desktop, you should see NOPE's tools available. Try asking:

> "What blocklists are available in NOPE?"

### Connecting Claude Code

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) supports both stdio and HTTP transports.

#### Option 1: Using mcp-proxy (HTTP transport)

Add the MCP server via the CLI:

```bash
claude mcp add nope -- mcp-proxy \
  --transport=streamablehttp \
  --no-verify-ssl \
  --headers api-key "nope_YOUR_API_KEY" \
  https://your-nope-server/mcp
```

Remove `--no-verify-ssl` if using a trusted certificate.

#### Option 2: Edit settings.json directly

Edit your Claude Code settings file:

- **macOS**: `~/.claude/settings.json`
- **Linux**: `~/.claude/settings.json`

Add the MCP server configuration:

```json
{
  "mcpServers": {
    "nope": {
      "command": "mcp-proxy",
      "args": [
        "--transport=streamablehttp",
        "--no-verify-ssl",
        "--headers", "api-key", "nope_YOUR_API_KEY_HERE",
        "https://your-nope-server/mcp"
      ]
    }
  }
}
```

#### Verify Connection

After adding the server, restart Claude Code and verify with:

```
/mcp
```

You should see `nope` listed with 17 available tools.

### Example MCP Conversations

**Blocking threats:**
```
User: "Block evil.com on the domain blocklist"
Agent: Uses block_ioc(value="evil.com", list_slug="domainblocklist")
→ "Successfully added evil.com (domain) to list 'domainblocklist'"
```

**Investigating IOCs:**
```
User: "Why is that IP blocked?"
Agent: Uses search_ioc(value="1.2.3.4")
→ "Found 1 IOC(s):
   - 1.2.3.4 (ip)
     Lists: ipblocklist
     Comments: Malicious C2 server"
```

**Bulk operations:**
```
User: "Block these IPs from the threat feed: 198.51.100.1, 198.51.100.2, 198.51.100.3"
Agent: Uses bulk_block_ioc(values=["198.51.100.1", "198.51.100.2", "198.51.100.3"],
                           list_slug="ipblocklist", comment="Threat feed import")
→ "Bulk add complete: Added: 3, Skipped: 0, Failed: 0"
```

**Exclusion handling:**
```
User: "Block 192.168.1.1"
Agent: Uses block_ioc(value="192.168.1.1", list_slug="ipblocklist")
→ "Cannot block: RFC1918 private range (matches exclusion '192.168.0.0/16')"
```

**Managing exclusions:**
```
User: "Add an exclusion for our partner's domain"
Agent: Uses add_exclusion(value="*.partner.com", reason="Trusted partner domain")
→ "Added exclusion '*.partner.com' (wildcard). Reason: Trusted partner domain"
```

### Audit Trail

All actions performed via MCP are logged with the API key name used (e.g., `mcp:claude-desktop`), visible in the IOC audit history.

## Configuration

### Required Environment Variables

NOPE requires these environment variables to start. Running `./setup.sh` auto-generates all of them. To configure manually, copy `.env.example` to `.env` and fill in values:

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | JWT signing key. Generate with `openssl rand -hex 32` |
| `DEFAULT_ADMIN_PASSWORD` | Initial admin password (minimum 6 characters) |
| `DEFAULT_EDL_PASSWORD` | EDL basic auth password (minimum 6 characters) |
| `DB_PASSWORD` | PostgreSQL password |

All passwords are validated at startup. The app will refuse to start if any required variable is missing or a password does not meet the minimum 6-character length requirement.

### All Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NOPE_PORT` | 8081 | HTTPS port for the web UI and API |
| `DB_USER` | nope | PostgreSQL username |
| `DB_PASSWORD` | (required) | PostgreSQL password |
| `SECRET_KEY` | (required) | JWT signing key |
| `DEFAULT_ADMIN_USER` | admin | Default UI admin username |
| `DEFAULT_ADMIN_PASSWORD` | (required) | Default UI admin password |
| `DEFAULT_EDL_USER` | edl | Default EDL basic auth username |
| `DEFAULT_EDL_PASSWORD` | (required) | Default EDL basic auth password |

### Custom SSL Certificates

By default, self-signed certificates are generated automatically. For production, provide your own certificates:

1. Create a directory with your certificates:
   ```bash
   mkdir my-certs
   cp your-cert.pem my-certs/cert.pem
   cp your-key.pem my-certs/key.pem
   ```

2. Update `docker-compose.yml` to mount your certs:
   ```yaml
   nginx:
     volumes:
       - ./my-certs:/etc/nginx/certs:ro  # Uncomment and update path
   ```

### Palo Alto Firewall Configuration

1. In PAN-OS, go to **Objects > External Dynamic Lists**
2. Create a new EDL:
   - **Type**: IP List or Domain List
   - **Source**: `https://your-nope-server/edl/{list-slug}`
   - **Certificate Profile**: (configure to trust your cert)
   - **Username/Password**: Your EDL credentials

## Development

### Local Development (without Docker)

```bash
# Backend
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
cd backend
pytest
```

## Built With

- **Backend**: Python, FastAPI, SQLAlchemy, Alembic, FastMCP
- **Frontend**: React, TypeScript, Vite, TanStack Query
- **Database**: PostgreSQL
- **Proxy**: NGINX

## License

MIT
