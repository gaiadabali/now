"""Daily range-partition management for `engine.ad_events`.

Mirrors `now_db.partitions` (city DB `interactions`/`impressions`) exactly —
same function shapes, same naming convention (`<table>_pYYYY_MM_DD`) — so an
operator only has to learn one mental model for both packages. See that
module's docstring for the full rationale; this file only lists the one
partitioned table platform-side.

Deliberately duplicated rather than shared: this package and `now-db` target
different databases and have no other reason to depend on each other. ~40
lines of duplication is cheaper than a third shared package for one function.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import text
from sqlalchemy.engine import Connection

PARTITIONED_TABLES: tuple[str, ...] = ("ad_events",)


def _partition_name(table: str, day: dt.date) -> str:
    return f"{table}_p{day:%Y_%m_%d}"


def ensure_daily_partitions(
    connection: Connection,
    *,
    tables: tuple[str, ...] = PARTITIONED_TABLES,
    schema: str = "engine",
    days_back: int = 1,
    days_ahead: int = 7,
    today: dt.date | None = None,
) -> list[str]:
    """Create any missing daily partitions in [today - days_back, today + days_ahead].

    Idempotent: uses CREATE TABLE IF NOT EXISTS. Returns the partition names
    it created (empty list on a re-run with nothing new to do).
    """
    today = today or dt.date.today()
    created: list[str] = []
    for table in tables:
        for offset in range(-days_back, days_ahead + 1):
            day = today + dt.timedelta(days=offset)
            next_day = day + dt.timedelta(days=1)
            part_name = _partition_name(table, day)
            exists = connection.execute(
                text(
                    "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = :schema AND c.relname = :part_name"
                ),
                {"schema": schema, "part_name": part_name},
            ).first()
            if exists:
                continue
            # Postgres cannot plan a bound parameter inside a partition-bound
            # literal for DDL ("could not determine data type of parameter
            # $1") — CAST(:x AS date) doesn't help either, it's the DDL
            # context itself that rejects a parameter here. `day`/`next_day`
            # are `datetime.date` objects computed by this function, never
            # user input, so a literal-safe ISO string is interpolated
            # directly rather than routed through a bind parameter.
            connection.execute(
                text(
                    f'CREATE TABLE "{schema}"."{part_name}" '
                    f'PARTITION OF "{schema}"."{table}" '
                    f"FOR VALUES FROM ('{day.isoformat()}') TO ('{next_day.isoformat()}')"
                )
            )
            created.append(part_name)
    return created


def drop_partitions_older_than(
    connection: Connection,
    *,
    retention_days: int,
    tables: tuple[str, ...] = PARTITIONED_TABLES,
    schema: str = "engine",
    today: dt.date | None = None,
) -> list[str]:
    """Detach + drop daily partitions older than `retention_days`.

    `ad_events` is the billing ledger (ARCHITECTURE.md §11) — call this with
    a retention window long enough to survive any reconciliation/dispute
    period. Not wired to a schedule by this package; that is an infra
    decision. Detach-then-drop avoids holding a long lock on the parent while
    scanning a full partition for deletion.
    """
    today = today or dt.date.today()
    cutoff = today - dt.timedelta(days=retention_days)
    dropped: list[str] = []
    for table in tables:
        rows = connection.execute(
            text(
                "SELECT c.relname FROM pg_inherits i "
                "JOIN pg_class c ON c.oid = i.inhrelid "
                "JOIN pg_class p ON p.oid = i.inhparent "
                "JOIN pg_namespace n ON n.oid = p.relnamespace "
                "WHERE n.nspname = :schema AND p.relname = :table"
            ),
            {"schema": schema, "table": table},
        ).fetchall()
        for (part_name,) in rows:
            prefix = f"{table}_p"
            if not part_name.startswith(prefix):
                continue
            date_str = part_name[len(prefix) :]
            try:
                part_date = dt.datetime.strptime(date_str, "%Y_%m_%d").date()
            except ValueError:
                continue
            if part_date < cutoff:
                connection.execute(
                    text(f'ALTER TABLE "{schema}"."{table}" DETACH PARTITION "{schema}"."{part_name}"')
                )
                connection.execute(text(f'DROP TABLE "{schema}"."{part_name}"'))
                dropped.append(part_name)
    return dropped
