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

# COPY the WHOLE packages tree, not an enumerated subset.
#
# An earlier version copied only config and rails — the two packages named in
# this app's pyproject.toml — and the build failed on
# `Distribution not found at: file:///app/engine/packages/blender`, because
# now-rails itself depends on now-db, now-platform-db, now-search,
# now-filters, now-blender and now-quality. Enumerating a transitive closure
# by hand in a Dockerfile is a trap that re-arms every time a package gains a
# dependency; .dockerignore already strips .venv and node_modules, so the
# whole tree is ~95 MB and copying it is the cheaper correctness.
COPY engine/packages ./engine/packages
COPY engine/apps/api ./engine/apps/api

WORKDIR /app/engine/apps/api
# `--no-editable` is load-bearing, not tidiness.
#
# pyproject.toml declares its local path dependencies with
# `editable = true`, which is right for development: an editable install
# writes a .pth file pointing at `/app/engine/packages/<pkg>/src` instead
# of copying anything into site-packages. The runner stage below copies
# `/opt/venv` and this app's own directory -- NOT `engine/packages` -- so
# those .pth targets do not exist at runtime and the container dies on
# `ModuleNotFoundError: No module named 'now_config'` while the *build*
# reports success.
#
# `--no-editable` materialises the packages into the venv, which makes
# /opt/venv self-contained and is what a runtime image should carry
# anyway. The alternative -- copying the whole packages tree into the
# runner too -- ships ~95 MB of source that nothing imports by path.
RUN uv sync --frozen --no-dev --no-editable

FROM base AS runner
# Never run as root: a container escape should not land on uid 0, and the
# app writes nothing to disk that needs privilege.
RUN useradd --create-home --uid 10001 app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/engine/apps/api /app
ENV PATH="/opt/venv/bin:$PATH"

# The taxonomy seed is DATA the competitor guard reads at run time: the
# hidden-rival lexicon (terms/type.json + hidden_rival_lexicon_overrides.json).
# `now_db.provisioning.TAXONOMY_SEED_DIR` defaults to a path under the repo
# root, which does not exist in this image — the venv holds the packages, not
# the repo — so without these two lines every per-publish and nightly flag
# rebuild would fail on a missing file, and the flags would silently go stale.
COPY --from=builder /app/engine/packages/taxonomy/seed /app/taxonomy-seed
ENV NOW_TAXONOMY_SEED_DIR=/app/taxonomy-seed

USER app
EXPOSE 8000

# No --reload, no --workers: one process per container, scaled by running
# more containers. uvicorn's own worker manager duplicates what the
# orchestrator already does and hides crashes behind a restart loop.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
