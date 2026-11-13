# ── Build / dependency stage ──────────────────────────────────────────────────
# Use a full image to compile any C extensions (numpy, pandas), then copy
# only the installed packages into the slim runtime image.
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools needed for some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies into an isolated prefix
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ ./app/

# Transfer ownership to non-root user
RUN chown -R appuser:appuser /app

USER appuser

# Expose the application port
EXPOSE 8000

# Health check — the /api/health endpoint returns 200 when cache is loaded
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" \
    || exit 1

# Production command — single worker, no --reload
# Render sets PORT env var; default to 8000 if not set
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --log-level info"]
