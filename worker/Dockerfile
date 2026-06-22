# ── Build stage ───────────────────────────────────────────────
FROM python:3.12-slim AS base

# Non-root user
RUN groupadd -r worker && useradd -r -g worker worker

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Ensure db directory exists and is writable by non-root user
RUN mkdir -p /app/db && chown -R worker:worker /app

USER worker

# docs/data is volume-mounted from the repo root (or baked in CI)
# Entry point: run once per invocation; scheduling is external.
ENTRYPOINT ["python", "main.py"]
