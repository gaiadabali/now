"""Engine creation + small introspection helpers shared by every load_*
module. All actual DML lives in the load_* modules themselves (each table's
upsert is different enough — different conflict target, different derived
columns — that a one-size-fits-all `upsert()` would hide more than it'd
save); this module is deliberately small.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import Connection

from now_loader.config import city_database_url


def get_engine(city: str) -> Engine:
    return create_engine(city_database_url(city), future=True)


def enum_values(conn: Connection, enum_type: str) -> set[str]:
    """The live set of labels for a Postgres enum type in `public` — used
    only for safe, exact-match normalization (e.g. `places.area_term` from
    a venue's `province`/`state` string), never for guessing a
    classification value. F20/the loader's hard constraint: facet columns
    are real enums generated from the seeded taxonomy, so any value this
    loader writes must already be a label Postgres knows about, or the
    INSERT fails at the DB level — that failure mode is intentional and
    must not be worked around by loosening the column.
    """
    rows = conn.execute(
        text(
            """
            SELECT e.enumlabel
              FROM pg_type t
              JOIN pg_enum e ON e.enumtypid = t.oid
              JOIN pg_namespace n ON n.oid = t.typnamespace
             WHERE n.nspname = 'public' AND t.typname = :enum_type
            """
        ),
        {"enum_type": enum_type},
    ).fetchall()
    return {r[0] for r in rows}


def table_count(conn: Connection, table: str) -> int:
    return conn.execute(text(f'SELECT count(*) FROM "public"."{table}"')).scalar_one()  # noqa: S608 (fixed allowlist call sites only)
