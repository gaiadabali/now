"""Connection resolution for the platform database.

Kept deliberately dependency-free (no pydantic-settings) so this package can
be imported by both the Alembic env and a plain `python -m` CLI without
pulling in the API's settings stack.

Resolution order for the platform DSN:
    1. `NOW_PLATFORM_DATABASE_URL` — a full DSN, e.g.
       postgresql+psycopg://now:now@localhost:5432/now_platform
    2. Discrete `NOW_PG_*` vars, `.env`-file fallback, then a fixed default
       + a fixed `now_platform` database name.

Note this is a *sync* psycopg DSN (`postgresql+psycopg://`) because Alembic
migrations run synchronously. engine-api's runtime pool is async
(`postgresql+asyncpg://`) and is configured independently in
`engine/apps/api` — the two never need to agree on driver, only on host/
port/user/password/dbname, which is why the discrete NOW_PG_* vars exist.

F52 (PROGRESS.md): mirrors `now_db.settings`'s `.env`-loading fix (F31)
exactly — the tsv/embeddings workers and this module's own callers must not
need `NOW_PG_*` exported manually outside compose. Precedence, matching
`now_db.settings._get_setting()`: explicit `NOW_PG_*` env var > project
`.env` file (`POSTGRES_*` keys) > hardcoded default. Kept as a second,
independent implementation (not imported from now_db) rather than a shared
dependency, for the same reason this module already gives for staying
pydantic-free: now_db and now_platform_db must each be importable — by the
Alembic env, in particular — without requiring the other package installed.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_HOST = "localhost"
DEFAULT_PORT = "5432"
DEFAULT_USER = "now"
DEFAULT_PASSWORD = "now"
PLATFORM_DB_NAME = "now_platform"


_ENV_SEARCH_MAX_LEVELS = 12


def _find_env_file(start: Path) -> Path | None:
    """Walk upward from `start` looking for a `.env`, rather than assuming
    a fixed depth.

    E4.1 (PROGRESS.md) surfaced a real bug in the old fixed-`parents[4]`
    version of this function: it assumed `__file__` always lives at
    `engine/packages/platform-db/src/now_platform_db/settings.py` *inside
    the checked-out repo*. That holds when this package is installed
    editable into its own venv, but not when another package in the same
    repo (e.g. `now-loader`, which E4.1 needs to import
    `platform_database_url()` from for its `load-orgs` command) declares
    it as an ordinary path dependency — `uv sync` there builds and copies
    this module into `<consumer>/.venv/Lib/site-packages/now_platform_db/
    settings.py`, five fixed levels up from which is deep inside that
    *consumer's* `.venv`, nowhere near the actual project `.env`. Verified
    live: running `now-loader load-orgs` with the fixed-depth version
    silently fell back to the wrong host/port/password (an amazing failure
    mode: it looks like a normal `.env` miss, not a bug in this function).

    A consumer's `.venv` is still nested *inside* the real project tree
    though (`engine/packages/loader/.venv/...`), so searching upward for
    `.env` — rather than trusting a fixed offset — finds the real one from
    either location. Capped at `_ENV_SEARCH_MAX_LEVELS` so a genuinely
    missing `.env` (e.g. under pytest's `tmp_path`, or a real deployment
    that only sets `NOW_PG_*`/`NOW_PLATFORM_DATABASE_URL` directly with no
    `.env` at all) fails fast back to `{}` instead of walking to the
    filesystem root.
    """
    current = start
    for _ in range(_ENV_SEARCH_MAX_LEVELS):
        candidate = current / ".env"
        if candidate.exists():
            return candidate
        if current.parent == current:  # filesystem root
            break
        current = current.parent
    return None


def _load_env_file() -> dict[str, str]:
    """Load the project's .env file if it exists, return as dict.

    See `_find_env_file` for why this searches upward instead of assuming
    a fixed depth from this module's own location.
    """
    module_dir = Path(__file__).resolve().parent
    env_file = _find_env_file(module_dir)

    if env_file is None:
        return {}

    env_vars: dict[str, str] = {}
    try:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    except Exception:
        # If we can't read the file, just continue with defaults.
        pass

    return env_vars


# Load .env file once at module import time.
_ENV_FILE_VARS = _load_env_file()


def _get_setting(env_var_name: str, env_file_var_name: str, default: str) -> str:
    """Get a setting with precedence: explicit env var > .env file > default.

    Args:
        env_var_name: The NOW_PG_* environment variable name (e.g. "NOW_PG_PORT")
        env_file_var_name: The .env file variable name (e.g. "POSTGRES_PORT")
        default: Default value if neither env var nor .env file has a value
    """
    if env_var_name in os.environ:
        return os.environ[env_var_name]

    if env_file_var_name in _ENV_FILE_VARS:
        return _ENV_FILE_VARS[env_file_var_name]

    return default


def pg_host() -> str:
    return _get_setting("NOW_PG_HOST", "POSTGRES_HOST", DEFAULT_HOST)


def pg_port() -> str:
    return _get_setting("NOW_PG_PORT", "POSTGRES_PORT", DEFAULT_PORT)


def pg_user() -> str:
    return _get_setting("NOW_PG_USER", "POSTGRES_USER", DEFAULT_USER)


def pg_password() -> str:
    return _get_setting("NOW_PG_PASSWORD", "POSTGRES_PASSWORD", DEFAULT_PASSWORD)


def platform_database_url() -> str:
    explicit = os.environ.get("NOW_PLATFORM_DATABASE_URL")
    if explicit:
        return explicit

    return f"postgresql+psycopg://{pg_user()}:{pg_password()}@{pg_host()}:{pg_port()}/{PLATFORM_DB_NAME}"


def admin_database_url() -> str:
    """DSN to the `postgres` maintenance database, for CREATE DATABASE etc."""
    return f"postgresql+psycopg://{pg_user()}:{pg_password()}@{pg_host()}:{pg_port()}/postgres"
