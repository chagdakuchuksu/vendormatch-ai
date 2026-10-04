# VendorMatch AI — single container serving the FastAPI API and the static frontend.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/hf-cache \
    HF_HUB_DISABLE_TELEMETRY=1

WORKDIR /app

# CPU-only PyTorch keeps the image far smaller than the default CUDA build.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.1
COPY requirements.txt .
RUN pip install -r requirements.txt

# Bake the semantic model into the image: no download at start-up or per request.
ARG MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${MODEL_NAME}')" \
    && chmod -R a+rX /opt/hf-cache
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

COPY app ./app
COPY static ./static
COPY examples ./examples

# Non-root user; SQLite lives in /tmp (ephemeral on Cloud Run — demo data may reset).
RUN useradd --create-home --uid 10001 appuser && mkdir -p /tmp/vendormatch && chown appuser /tmp/vendormatch
USER appuser

ENV PORT=8080 \
    VENDORMATCH_DB_PATH=/tmp/vendormatch/vendormatch.db \
    VENDORMATCH_PRELOAD_MODEL=1

EXPOSE 8080
# One worker: one model in memory. Cloud Run sets $PORT.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
