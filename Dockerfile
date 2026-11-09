# ==============================================================
# ExamVault - Production-Ready Dockerfile
# Multi-stage security and minimal attack surface
# ==============================================================

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5003 \
    PYTHONPATH=/app

WORKDIR /app

# Install minimal OS dependencies for healthcheck and compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root user and group
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

# Install Python requirements
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy application directories
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY database/ /app/database/

# Set proper permissions for non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose backend application port
EXPOSE 5003

# Container healthcheck
HEALTHCHECK --interval=20s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5003/health || exit 1

# Run with Gunicorn WSGI server in production
CMD ["gunicorn", "--bind", "0.0.0.0:5003", "--workers", "2", "--threads", "4", "backend.app:app"]
