"""Deterministic structural hash of the `engine` schema — the CI drift gate.

Introspects tables/columns/types/nullability/defaults, primary keys, unique
constraints, check constraints and indexes (including partial-index
predicates and access methods, so a GiST/HNSW index silently dropped or
narrowed is caught) via `information_schema` + `pg_catalog`. Daily partitions
of `ad_events` are excluded by name pattern (`ad_events_pYYYY_MM_DD`) — they
are expected to differ by wall-clock time between two otherwise-identical
databases and are not part of the structural contract; the *parent* table
and its partitioning strategy are still hashed.

Deliberately independent of `now_db.schema_hash` (see `partitions.py` for
why these two packages don't share code) but structurally identical — a
diff between the two files should only ever be the partition-exclusion
pattern.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

_PARTITION_RE = re.compile(r"^ad_events_p\d{4}_\d{2}_\d{2}$")


def _is_partition_child(name: str) -> bool:
    return bool(_PARTITION_RE.match(name))


def introspect_schema(connection: Connection, schema: str = "engine") -> dict[str, Any]:
    tables_rows = connection.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_type = 'BASE TABLE' "
            "ORDER BY table_name"
        ),
        {"schema": schema},
    ).fetchall()
    table_names = [r[0] for r in tables_rows if not _is_partition_child(r[0])]

    result: dict[str, Any] = {"schema": schema, "tables": {}}

    for table in table_names:
        columns = connection.execute(
            text(
                "SELECT column_name, data_type, udt_name, is_nullable, column_default "
                "FROM information_schema.columns "
                "WHERE table_schema = :schema AND table_name = :table "
                # BY NAME, not ordinal_position. Postgres assigns a column its
                # position from how it arrived: inline in CREATE TABLE, or
                # appended by ALTER TABLE ADD COLUMN. A table built by running
                # every migration from empty and the same table built by
                # migrating a database that already existed therefore differ
                # in column ORDER while being identical in every way that has
                # a consequence -- same columns, types, nullability, defaults.
                #
                # Hashing the ordinal made that cosmetic difference a drift
                # failure. `embeddings.vec` sat fifth in every real city
                # database and seventh in a fresh migrate, and the gate was
                # red on main from 2026-09-14 for that alone, with no way to
                # fix it that did not involve rewriting a populated table.
                #
                # Sorting by name compares what the schema IS rather than how
                # it got there. A column added, removed, renamed or retyped
                # still changes the set -- which is what the gate is for, and
                # what its self-test asserts by adding a rogue column.
                #
                # Key column order is NOT sorted this way: see the array_agg
                # below, where ordinal_position is load-bearing because the
                # order of columns in an index changes what it can serve.
                "ORDER BY column_name"
            ),
            {"schema": schema, "table": table},
        ).fetchall()

        # `delete_rule`/`update_rule` are joined in because the gate was blind
        # to them (F139). Migration 0008 changed two foreign keys from NO
        # ACTION to CASCADE and SET NULL — a change in what happens to a
        # person's data when their account is deleted — and the schema hash
        # did not move. A gate that cannot see the difference between CASCADE
        # and NO ACTION cannot catch the class of bug F138 actually was.
        #
        # `::text` on the aggregated column names is not cosmetic either. The
        # `array_agg` returns `information_schema.sql_identifier[]`, which the
        # driver hands back as the literal string '{user_id,site_id}' — and
        # `list()` on a string splits it into CHARACTERS. Every recorded
        # constraint in the old baseline was a list like
        # ["{","u","s","e","r",...]. It hashed deterministically, so the gate
        # still worked, but the baseline was unreadable and a column-set
        # change was being compared as a character sequence.
        constraints = connection.execute(
            text(
                "SELECT tc.constraint_type, tc.constraint_name, "
                "       array_agg(kcu.column_name::text ORDER BY kcu.ordinal_position), "
                "       max(rc.delete_rule), max(rc.update_rule) "
                "FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema "
                "LEFT JOIN information_schema.referential_constraints rc "
                "  ON rc.constraint_name = tc.constraint_name AND rc.constraint_schema = tc.table_schema "
                "WHERE tc.table_schema = :schema AND tc.table_name = :table "
                "  AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE', 'FOREIGN KEY') "
                "GROUP BY tc.constraint_type, tc.constraint_name "
                "ORDER BY tc.constraint_type, tc.constraint_name"
            ),
            {"schema": schema, "table": table},
        ).fetchall()

        # Not information_schema.check_constraints: on modern Postgres it
        # also lists the implicit CHECK backing every NOT NULL column, and
        # those are auto-named from internal OIDs ("27551_28999_1_not_null")
        # that differ between two databases created from identical DDL —
        # comparing them would make the hash never match across cities.
        # Column nullability is already captured in `columns` above, so
        # querying pg_constraint directly and excluding the OID-named
        # not-null backing constraints gives only genuine, user-authored
        # CHECK constraints (e.g. `kind IN (...)`).
        checks = connection.execute(
            text(
                "SELECT co.conname, pg_get_constraintdef(co.oid) "
                "FROM pg_constraint co "
                "JOIN pg_class t ON t.oid = co.conrelid "
                "JOIN pg_namespace n ON n.oid = t.relnamespace "
                "WHERE n.nspname = :schema AND t.relname = :table AND co.contype = 'c' "
                "  AND co.conname !~ '^[0-9]+_[0-9]+_[0-9]+_not_null$' "
                "ORDER BY co.conname"
            ),
            {"schema": schema, "table": table},
        ).fetchall()

        indexes = connection.execute(
            text(
                "SELECT i.relname AS index_name, am.amname AS method, "
                "       pg_get_indexdef(ix.indexrelid) AS indexdef "
                "FROM pg_index ix "
                "JOIN pg_class i ON i.oid = ix.indexrelid "
                "JOIN pg_class t ON t.oid = ix.indrelid "
                "JOIN pg_namespace n ON n.oid = t.relnamespace "
                "JOIN pg_am am ON am.oid = i.relam "
                "WHERE n.nspname = :schema AND t.relname = :table "
                "ORDER BY i.relname"
            ),
            {"schema": schema, "table": table},
        ).fetchall()

        is_partitioned = connection.execute(
            text(
                "SELECT c.relkind FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = :schema AND c.relname = :table"
            ),
            {"schema": schema, "table": table},
        ).scalar()

        result["tables"][table] = {
            "partitioned": is_partitioned == "p",
            "columns": [
                {
                    "name": c[0],
                    "type": c[1],
                    "udt": c[2],
                    "nullable": c[3],
                    "default": c[4],
                }
                for c in columns
            ],
            "constraints": [
                {
                    "type": c[0],
                    "name": c[1],
                    "columns": list(c[2]),
                    # Present only on foreign keys; omitted elsewhere so the
                    # record stays the shape of the thing it describes.
                    **(
                        {"on_delete": c[3], "on_update": c[4]}
                        if c[0] == "FOREIGN KEY"
                        else {}
                    ),
                }
                for c in constraints
            ],
            "checks": [{"name": c[0], "clause": c[1]} for c in checks],
            "indexes": [
                {"name": i[0], "method": i[1], "def": i[2]} for i in indexes
            ],
        }

    return result


def canonical_json(structure: dict[str, Any]) -> str:
    return json.dumps(structure, sort_keys=True, separators=(",", ":"))


def compute_hash(connection: Connection, schema: str = "engine") -> tuple[str, dict[str, Any]]:
    structure = introspect_schema(connection, schema=schema)
    digest = hashlib.sha256(canonical_json(structure).encode("utf-8")).hexdigest()
    return digest, structure


def diff_structures(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    """Human-readable diff lines for a CI failure message."""
    diffs: list[str] = []
    expected_tables = set(expected.get("tables", {}))
    actual_tables = set(actual.get("tables", {}))
    for missing in sorted(expected_tables - actual_tables):
        diffs.append(f"missing table: {missing}")
    for extra in sorted(actual_tables - expected_tables):
        diffs.append(f"unexpected table: {extra}")
    for table in sorted(expected_tables & actual_tables):
        if expected["tables"][table] != actual["tables"][table]:
            diffs.append(f"table changed: {table}")
    return diffs
