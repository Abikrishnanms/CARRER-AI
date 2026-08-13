# ── Embedder Service Dockerfile ───────────────────────────────────────────────
FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/embedder/requirements.txt /tmp/embedder-requirements.txt
COPY shared/requirements.txt /tmp/shared-requirements.txt
RUN pip install --no-cache-dir \
    -r /tmp/shared-requirements.txt \
    -r /tmp/embedder-requirements.txt

COPY shared/ ./shared/
COPY services/embedder/ ./services/embedder/

ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1
# Cache the embedding model inside the image
ENV SENTENCE_TRANSFORMERS_HOME="/app/.cache/sentence-transformers"

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" || true

CMD ["python", "-m", "services.embedder.main"]
