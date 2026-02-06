#!/bin/bash
set -e

CERT_DIR="$(dirname "$0")/certs"
mkdir -p "$CERT_DIR"

if [ ! -f "$CERT_DIR/cert.pem" ]; then
    echo "Generating self-signed certificate..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$CERT_DIR/key.pem" \
        -out "$CERT_DIR/cert.pem" \
        -subj "/CN=localhost/O=NOPE/C=US"
    echo "Certificate generated."
fi

# Generate default htpasswd if not exists
if [ ! -f "$CERT_DIR/.htpasswd" ]; then
    echo "Generating default htpasswd (admin:admin)..."
    # Using openssl to generate htpasswd-compatible hash
    echo "admin:$(openssl passwd -apr1 admin)" > "$CERT_DIR/.htpasswd"
    echo "htpasswd generated. Change in production!"
fi
