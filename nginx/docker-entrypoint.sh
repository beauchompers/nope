#!/bin/sh
set -e

CERT_DIR="/etc/nginx/certs"
CERT_FILE="$CERT_DIR/cert.pem"
KEY_FILE="$CERT_DIR/key.pem"
HTPASSWD_FILE="$CERT_DIR/.htpasswd"

# Default port
LISTEN_PORT="${LISTEN_PORT:-8081}"
export LISTEN_PORT

# Generate nginx config from template
echo "Configuring nginx to listen on port $LISTEN_PORT..."
envsubst '${LISTEN_PORT}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

# Ensure certs directory exists
mkdir -p "$CERT_DIR"

# Generate self-signed certificate if not provided
if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    echo "No SSL certificate found. Generating self-signed certificate..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$KEY_FILE" \
        -out "$CERT_FILE" \
        -subj "/CN=localhost/O=NOPE/C=US"
    echo "Self-signed certificate generated."
else
    echo "Using existing SSL certificate."
fi

# Generate default htpasswd if not exists
# This is a fallback - the API will sync the real htpasswd from the database
if [ ! -f "$HTPASSWD_FILE" ]; then
    echo "Generating default htpasswd (admin:admin)..."
    htpasswd -bc "$HTPASSWD_FILE" "${EDL_USER:-admin}" "${EDL_PASSWORD:-admin}"
    echo "Default htpasswd generated."
fi

# Execute the main command
exec "$@"
