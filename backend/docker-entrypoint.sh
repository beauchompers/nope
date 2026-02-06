#!/bin/sh
set -e

# Fix ownership of mounted volumes (runs as root)
chown -R appuser:appuser /app/edl

echo "Running database migrations..."
# Run migrations as root (needs DB access)
alembic upgrade head

echo "Starting NOPE API..."
# Drop privileges and run as appuser
exec gosu appuser "$@"
