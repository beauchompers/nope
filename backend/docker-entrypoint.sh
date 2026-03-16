#!/bin/sh
set -e

# Fix ownership of mounted volumes (runs as root)
# Pre-create htpasswd file so it exists before dropping privileges
touch /app/edl/.htpasswd
chown -R appuser:appuser /app/edl
chmod 755 /app/edl

echo "Running database migrations..."
# Run migrations as root (needs DB access)
alembic upgrade head

echo "Starting NOPE API..."
# Drop privileges and run as appuser
exec gosu appuser "$@"
