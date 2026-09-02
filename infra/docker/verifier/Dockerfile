# ── Verifier Service Dockerfile ───────────────────────────────────────────────
FROM python:3.12-slim AS base

WORKDIR /app

COPY services/verifier/requirements.txt /tmp/verifier-requirements.txt
COPY shared/requirements.txt /tmp/shared-requirements.txt
RUN pip install --no-cache-dir \
    -r /tmp/shared-requirements.txt \
    -r /tmp/verifier-requirements.txt

COPY shared/ ./shared/
COPY services/ ./services/
COPY ml/ ./ml/

ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "services.verifier.main"]
