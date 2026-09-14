# engine-worker — ONE instance for every city (ARCHITECTURE.md §3.5). It
# iterates the site registry; nothing here is city-specific, so a new region
# needs a registry row, not a redeploy.
#
# BUILD CONTEXT IS THE REPO ROOT, same as engine-api and for the same reason:
#
#     docker build -f engine/apps/worker/Dockerfile .
#
# pyproject.toml declares local path dependencies (now-db, now-embeddings)
# that escape this directory, so a scoped context cannot resolve them.

FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# Whole packages tree — see engine/apps/api/Dockerfile for why enumerating
# the transitive closure by hand is a trap.
COPY engine/packages ./engine/packages
COPY engine/apps/worker ./engine/apps/worker

WORKDIR /app/engine/apps/worker
# No --frozen: this app has no uv.lock committed yet, unlike the API. Resolve
# at build time and let the image be the artifact that gets promoted.
RUN uv sync --no-dev

FROM base AS runner
RUN useradd --create-home --uid 10001 app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/engine/apps/worker /app
ENV PATH="/opt/venv/bin:$PATH"

# The local embedding provider (BAAI/bge-small-en-v1.5, ONNX) downloads its
# weights on first use. Give it a writable, predictable home inside the
# image rather than letting it land in root's cache or fail as uid 10001.
ENV HF_HOME=/home/app/.cache/huggingface \
    XDG_CACHE_HOME=/home/app/.cache
RUN mkdir -p /home/app/.cache && chown -R app:app /home/app/.cache

USER app

# No port: this process has no HTTP surface. Liveness is a Redis heartbeat
# the worker renews every minute — `docker ps` showing "running" would
# otherwise only prove PID 1 had not exited while arq was wedged.
HEALTHCHECK --interval=60s --timeout=10s --start-period=90s --retries=3 \
    CMD ["now-worker", "health"]

CMD ["arq", "app.main.WorkerSettings"]
