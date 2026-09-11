"""Connection resolution for the target city DB.

Deliberately self-contained (does not import `now_db`, which this ticket's
scope explicitly excludes touching or depending on) but mirrors its env-var
convention (`NOW_PG_HOST/PORT/USER/PASSWORD`) so operators don't need a
second mental model for "how does a NOW! tool find Postgres".

Zero site-name literals: the caller always names the target database via
`--city` (a bare `db_ref` like `now_jakarta`/`now_bali`/`now_test`, or a
full DSN) — nothing here defaults to any one city.
"""

from __future__ import annotations

import os

DEFAULT_HOST = "localhost"
DEFAULT_PORT = "15432"  # docker-compose.yml maps Postgres to 15432 on the host
DEFAULT_USER = "now"
DEFAULT_PASSWORD = "now"


def pg_host() -> str:
    return os.environ.get("NOW_PG_HOST", DEFAULT_HOST)


def pg_port() -> str:
    return os.environ.get("NOW_PG_PORT", DEFAULT_PORT)


def pg_user() -> str:
    return os.environ.get("NOW_PG_USER", DEFAULT_USER)


def pg_password() -> str:
    return os.environ.get("NOW_PG_PASSWORD", DEFAULT_PASSWORD)


def city_database_url(db_ref: str) -> str:
    """Build a SQLAlchemy/psycopg3 DSN for a city DB.

    `db_ref` is a bare database name in the common case (e.g. "now_jakarta");
    a full DSN (contains "://") is passed through untouched.
    """
    if "://" in db_ref:
        return db_ref
    return f"postgresql+psycopg://{pg_user()}:{pg_password()}@{pg_host()}:{pg_port()}/{db_ref}"
