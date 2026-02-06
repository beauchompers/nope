#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"

# --- Copy .env.example → .env if missing ---
if [ ! -f "$ENV_FILE" ]; then
  if [ ! -f "$ENV_EXAMPLE" ]; then
    echo "Error: .env.example not found. Are you in the project root?" >&2
    exit 1
  fi
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  echo "Created .env from .env.example"
fi

# --- Generate missing secrets ---
generate_secret() {
  local key="$1"
  local current
  current=$(grep "^${key}=" "$ENV_FILE" | cut -d= -f2-)

  # Skip if already set to a real value (not a placeholder)
  if [ -n "$current" ] && [[ "$current" != *"<"*">"* ]]; then
    return
  fi

  local value
  case "$key" in
    SECRET_KEY)
      value=$(openssl rand -hex 32)
      ;;
    DB_PASSWORD)
      value=$(openssl rand -hex 16)
      ;;
    DEFAULT_ADMIN_PASSWORD|DEFAULT_EDL_PASSWORD)
      value=$(openssl rand -base64 16)
      ;;
    *)
      return
      ;;
  esac

  # Use a different sed delimiter to avoid conflicts with base64 characters
  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i.bak "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
  else
    echo "${key}=${value}" >> "$ENV_FILE"
  fi

  echo "Generated $key"
}

generate_secret SECRET_KEY
generate_secret DB_PASSWORD
generate_secret DEFAULT_ADMIN_PASSWORD
generate_secret DEFAULT_EDL_PASSWORD

# Clean up sed backup file
rm -f "$ENV_FILE.bak"

# --- Read values for banner ---
get_env() {
  grep "^${1}=" "$ENV_FILE" | cut -d= -f2-
}

NOPE_PORT=$(get_env NOPE_PORT 2>/dev/null || echo "8081")
ADMIN_USER=$(get_env DEFAULT_ADMIN_USER 2>/dev/null || echo "admin")
ADMIN_PASS=$(get_env DEFAULT_ADMIN_PASSWORD)
EDL_USER=$(get_env DEFAULT_EDL_USER 2>/dev/null || echo "edl")
EDL_PASS=$(get_env DEFAULT_EDL_PASSWORD)

# Handle empty NOPE_PORT (key exists but no value)
NOPE_PORT="${NOPE_PORT:-8081}"
ADMIN_USER="${ADMIN_USER:-admin}"
EDL_USER="${EDL_USER:-edl}"

# --- Start Docker Compose ---
echo ""
echo "Starting NOPE..."
docker compose -f "$SCRIPT_DIR/docker-compose.yml" up -d

# --- Wait for health check ---
echo ""
echo "Waiting for NOPE to become healthy..."
MAX_WAIT=60
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
  if curl -sk "https://localhost:${NOPE_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
  ELAPSED=$((ELAPSED + 2))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
  echo "Warning: NOPE did not respond within ${MAX_WAIT}s. Check 'docker compose logs' for details."
fi

# --- Print startup banner ---
echo ""
echo "============================================"
echo " NOPE is running!"
echo ""
echo " Web UI:   https://localhost:${NOPE_PORT}"
echo " Login:    ${ADMIN_USER} / ${ADMIN_PASS}"
echo ""
echo " EDL User: ${EDL_USER} / ${EDL_PASS}"
echo " EDL URL:  https://localhost:${NOPE_PORT}/edl/{list-slug}"
echo "============================================"
echo ""
