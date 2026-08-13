# ── Cleaner Service Dockerfile ────────────────────────────────────────────────
FROM python:3.12-slim AS base

WORKDIR /app

COPY services/cleaner/requirements.txt /tmp/cleaner-requirements.txt
COPY shared/requirements.txt /tmp/shared-requirements.txt
RUN pip install --no-cache-dir \
    -r /tmp/shared-requirements.txt \
    -r /tmp/cleaner-requirements.txt

COPY shared/ ./shared/
COPY services/cleaner/ ./services/cleaner/

ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "services.cleaner.main"]
