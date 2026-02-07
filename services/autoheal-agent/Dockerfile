# AutoHeal AI - AutoHeal Agent Service
# Multi-stage build

FROM python:3.11-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

FROM python:3.11-slim as runtime

WORKDIR /app

RUN groupadd --gid 1000 autoheal && \
    useradd --uid 1000 --gid autoheal --shell /bin/bash --create-home autoheal

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache /wheels/*

COPY ../../shared /app/shared
COPY src /app/src

ENV PYTHONPATH=/app

USER autoheal

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8003/health || exit 1

EXPOSE 8003

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8003"]
