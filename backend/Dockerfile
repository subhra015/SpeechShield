# Backend Dockerfile (Layer 1) - CPU only, non-root
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for soundfile/librosa (libsndfile)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Non-root user
RUN useradd -m -u 1000 speechshield
COPY backend/app /app/app
COPY backend/pyproject.toml /app/pyproject.toml
RUN chown -R speechshield:speechshield /app
USER speechshield

# Artifacts are provided via volume mount (never baked into image)
ENV ARTIFACT_DIR=/app/artifacts/v4

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
