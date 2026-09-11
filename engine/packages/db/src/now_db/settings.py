"""Connection resolution for city databases.

Mirrors `now_platform_db.settings` (kept separate deliberately — see that
module's docstring). One extra piece here: `city_dsn(db_ref)` builds a sync
psycopg DSN from a bare database name using the exact same
host/port/user/password convention `engine-api`'s `Settings.build_city_dsn`
uses for its async DSN (`engine/apps/api/app/config.py`). If `db_ref` is
already a full DSN, it is used as-is (same "two shapes, zero code change"
rule the API documents for its side).

Settings are loaded from the project's `.env` file (if present) with explicit
`NOW_PG_*` environment variables taking precedence over file-based config.
This ensures tooling can run without needing manual environment setup, while
still allowing CI/deployment env vars to override.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_HOST = "localhost"
DEFAULT_PORT = "5432"
DEFAULT_USER = "now"
DEFAULT_PASSWORD = "now"


def _load_env_file() -> dict[str, str]:
    """Load the project's .env file if it exists, return as dict."""
    # Walk up from this module to find the project root (where .env lives).
    # From engine/packages/db/src/now_db/settings.py, we need to go up 5 levels
    # (now_db -> src -> db -> packages -> engine -> now!)
    module_dir = Path(__file__).resolve().parent
    project_root = module_dir.parents[4]  # now! project root

    env_file = project_root / ".env"
    if not env_file.exists():
        return {}

    env_vars = {}
    try:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue
                # Parse KEY=VALUE
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    except Exception:
        # If we can't read the file, just continue with defaults
        pass

    return env_vars


# Load .env file once at module import time
_ENV_FILE_VARS = _load_env_file()


def _get_setting(env_var_name: str, env_file_var_name: str, default: str) -> str:
    """Get a setting with precedence: explicit env var > .env file > default.

    Args:
        env_var_name: The NOW_PG_* environment variable name (e.g. "NOW_PG_PORT")
        env_file_var_name: The .env file variable name (e.g. "POSTGRES_PORT")
        default: Default value if neither env var nor .env file has a value
    """
    # Explicit env var takes highest precedence
    if env_var_name in os.environ:
        return os.environ[env_var_name]

    # .env file takes precedence over default
    if env_file_var_name in _ENV_FILE_VARS:
        return _ENV_FILE_VARS[env_file_var_name]

    # Finally, use the default
    return default


def pg_host() -> str:
    return _get_setting("NOW_PG_HOST", "POSTGRES_HOST", DEFAULT_HOST)


def pg_port() -> str:
    return _get_setting("NOW_PG_PORT", "POSTGRES_PORT", DEFAULT_PORT)


def pg_user() -> str:
    return _get_setting("NOW_PG_USER", "POSTGRES_USER", DEFAULT_USER)


def pg_password() -> str:
    return _get_setting("NOW_PG_PASSWORD", "POSTGRES_PASSWORD", DEFAULT_PASSWORD)


def admin_database_url() -> str:
    """DSN to the `postgres` maintenance database, for CREATE DATABASE etc."""
    return f"postgresql+psycopg://{pg_user()}:{pg_password()}@{pg_host()}:{pg_port()}/postgres"


def city_database_url(db_ref: str) -> str:
    """Build a sync DSN for a city DB from its `sites.db_ref` value.

    `db_ref` is a bare database name in the common case (e.g. "now_bandung")
    per ARCHITECTURE.md §2 — every city lives on the same Postgres instance,
    so only the dbname varies. A full DSN is passed through untouched.
    """
    if "://" in db_ref:
        return db_ref
    return f"postgresql+psycopg://{pg_user()}:{pg_password()}@{pg_host()}:{pg_port()}/{db_ref}"


def explicit_city_database_url() -> str | None:
    return os.environ.get("NOW_CITY_DATABASE_URL")
