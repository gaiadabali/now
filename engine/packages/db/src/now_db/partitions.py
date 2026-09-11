"""Daily range-partition management for `engine.interactions` / `engine.impressions`.

These two tables are the highest-volume tables in the system (every beacon
event lands here) — see ARCHITECTURE.md §2 and the E0.2 task brief. Daily
partitioning keeps individual partitions small enough to vacuum/index/drop
cheaply, and lets old partitions be retired without a slow `DELETE`.

This module intentionally has no CLI dependency and no knowledge of *which*
city it's running against — it operates on whatever connection it is given,
so it is exercised the same way whether called from `site:create`, from
`now-db ensure-partitions` (a cron/systemd-timer entry point — the schedule
itself is an infra decision, out of scope for this package), or from a test.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import text
from sqlalchemy.engine import Connection

PARTITIONED_TABLES: tuple[str, ...] = ("interactions", "impressions")


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

    Idempotent — safe to call every day (or every deploy). Returns the
    partition names it actually created; empty on a no-op re-run.
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

    Not wired to a schedule by this package — that is an infra decision.
    Detach-then-drop avoids holding a long lock while scanning a full
    partition for row-by-row deletion.
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
