# =====================================================================
# Build multi-stage: dependencias isoladas do runtime
# =====================================================================
FROM python:3.11-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------------------------------------------------------------------
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="Moinho Analytics" \
      org.opencontainers.image.description="Plataforma Analitica do Diagnostico Comercial"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 moinho

COPY --from=builder /install /usr/local

COPY --chown=moinho:moinho src/ ./src/
COPY --chown=moinho:moinho app/ ./app/
COPY --chown=moinho:moinho scripts/ ./scripts/
COPY --chown=moinho:moinho migrations/ ./migrations/
COPY --chown=moinho:moinho config/ ./config/
COPY --chown=moinho:moinho data/ ./data/
COPY --chown=moinho:moinho .streamlit/ ./.streamlit/
COPY --chown=moinho:moinho pyproject.toml ./

RUN mkdir -p /app/data/input /app/data/parquet /app/data/exports /app/logs \
    && chown -R moinho:moinho /app/data /app/logs \
    && chmod +x /app/scripts/entrypoint.sh

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PORT=8501

USER moinho
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:${PORT:-8501}/healthz || exit 1

ENTRYPOINT ["/bin/sh", "/app/scripts/entrypoint.sh"]
