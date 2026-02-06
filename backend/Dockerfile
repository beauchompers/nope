FROM python:3.12-slim

WORKDIR /app

# Install gosu for privilege dropping
RUN apt-get update && apt-get install -y --no-install-recommends gosu && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

# Create EDL output directory
RUN mkdir -p /app/edl

# Create non-root user for security
RUN adduser --disabled-password --gecos '' --uid 1000 appuser

EXPOSE 8000

# Copy entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Entrypoint runs as root to fix permissions, then drops to appuser
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
