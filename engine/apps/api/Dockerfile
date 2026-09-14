# engine-api — ONE deployment serving every city (ARCHITECTURE.md §3.5).
# The site comes from the request path (/v1/{site}/...) and is resolved to a
# pooled connection via the sites registry, so there is nothing city-specific
# to bake in here.
#
# BUILD CONTEXT IS THE REPO ROOT, not this directory:
#
#     docker build -f engine/apps/api/Dockerfile .
#
# pyproject.toml declares two local path dependencies —
#   now-config = { path = "../../packages/config" }
#   now-rails  = { path = "../../packages/rails"  }
# — which escape this directory. Building with `context: engine/apps/api`
# cannot see them and fails at dependency resolution. deploy/ and the
# publish-images workflow both pass `.` for this reason.

FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

FROM base AS builder
# uv resolves and installs an order of magnitude faster than pip here, and
# the repo already standardises on it (every package has a uv.lock).
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# Manifests first, so a source-only change does not re-resolve dependencies.
# The two local packages' manifests must be present before `uv sync`, since
# they are part of the resolution.
COPY engine/apps/api/pyproject.toml engine/apps/api/uv.lock ./engine/apps/api/
COPY engine/packages/config/pyproject.toml ./engine/packages/config/
COPY engine/packages/rails/pyproject.toml ./engine/packages/rails/

# The local deps are editable installs pointing at source that does not exist
# yet at this layer, so install non-editable from the full tree below instead
# of trying to split it further — correctness over one more cache layer.
COPY engine/packages/config ./engine/packages/config
COPY engine/packages/rails ./engine/packages/rails
COPY engine/apps/api ./engine/apps/api

WORKDIR /app/engine/apps/api
RUN uv sync --frozen --no-dev

FROM base AS runner
# Never run as root: a container escape should not land on uid 0, and the
# app writes nothing to disk that needs privilege.
RUN useradd --create-home --uid 10001 app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/engine/apps/api /app
ENV PATH="/opt/venv/bin:$PATH"

USER app
EXPOSE 8000

# No --reload, no --workers: one process per container, scaled by running
# more containers. uvicorn's own worker manager duplicates what the
# orchestrator already does and hides crashes behind a restart loop.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
