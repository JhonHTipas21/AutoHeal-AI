# AutoHeal AI - Log Intelligence Service
# Multi-stage build for optimized production image

# Stage 1: Build dependencies
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim as runtime

WORKDIR /app

# Create non-root user for security
RUN groupadd --gid 1000 autoheal && \
    useradd --uid 1000 --gid autoheal --shell /bin/bash --create-home autoheal

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels and install
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache /wheels/*

# Copy shared library
COPY ../../shared /app/shared

# Copy service code
COPY src /app/src

# Set Python path
ENV PYTHONPATH=/app

# Switch to non-root user
USER autoheal

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Expose port
EXPOSE 8001

# Run the service
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
