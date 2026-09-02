# ── Gateway Service Dockerfile ────────────────────────────────────────────────
FROM python:3.12-slim AS base

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY services/gateway/requirements.txt /tmp/gateway-requirements.txt
COPY shared/requirements.txt /tmp/shared-requirements.txt
RUN pip install --no-cache-dir \
    -r /tmp/shared-requirements.txt \
    -r /tmp/gateway-requirements.txt

# Copy source code
COPY shared/ ./shared/
COPY services/ ./services/

# Make shared importable
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "services.gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
