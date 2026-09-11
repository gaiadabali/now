"""QA.5 F68 re-verification, part 2: real Postgres SQL-building path
(`hard.py::build_places_hard_filter_sql`), independent dataset from any
existing test file, subject_type=None, at BOTH a normal rung and the
`editorial_fallback` rung (the "every rung" claim covers this branch too).
Skips cleanly if now_jakarta is unreachable (matches package convention).
"""

from __future__ import annotations

import sys
from pathlib import Path

FILTERS_SRC = Path(__file__).resolve().parents[1] / "filters" / "src"
sys.path.insert(0, str(FILTERS_SRC))

from sqlalchemy import text  # noqa: E402

from now_db.settings import city_database_url  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from now_filters.hard import build_places_hard_filter_sql, fetch_places_hard_filtered  # noqa: E402
from now_filters.synthetic import SyntheticPlace, create_synthetic_places_table  # noqa: E402
from now_filters.type_relations import load_type_relations  # noqa: E402

QA5_TABLE = "now_filters_qa5_f68_places"

FAILURES: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {label}" + (f" -- {detail}" if detail else ""))
    if not cond:
        FAILURES.append(label)


try:
    eng = create_engine(city_database_url("now_jakarta"), future=True)
    conn = eng.connect()
    conn.execute(text("SELECT 1"))
except Exception as exc:  # noqa: BLE001
    print(f"UNTESTABLE (real-SQL part): now_jakarta unreachable: {exc}")
    sys.exit(2)

relations = load_type_relations(conn)

# Own dataset (not reused from test_hard_filters_competitor.py): a mix of
# every venue type + the two non-venue types, all 'active'.
rows = [
    SyntheticPlace(id=101, type="stay", status="active"),
    SyntheticPlace(id=102, type="eat", status="active"),
    SyntheticPlace(id=103, type="drink", status="active"),
    SyntheticPlace(id=104, type="wellness", status="active"),
    SyntheticPlace(id=105, type="shop", status="active"),
    SyntheticPlace(id=106, type="do", status="active"),
    SyntheticPlace(id=107, type="event", status="active"),
    SyntheticPlace(id=108, type="editorial", status="active"),
]
create_synthetic_places_table(conn, rows, table=QA5_TABLE)

print("=== subject_type=None, normal rung (editorial_fallback=False) ===")
q = build_places_hard_filter_sql(subject_type=None, relations=relations, places_table=QA5_TABLE, quality_floor=None)
survivors = {c.entity_id for c in fetch_places_hard_filtered(conn, q)}
survived_types = {r.id: r.type for r in rows if r.id in survivors}
print(f"SQL: {q.sql}")
print(f"params: {q.params}")
print(f"survivor ids: {sorted(survivors)} types: {survived_types}")
check("no venue-typed row survived (only do/event/editorial=106,107,108 allowed)", survivors <= {106, 107, 108}, f"survivors={survivors}")
check("all 6 venue-type ids (101-105 + none 'unknown' seeded) excluded", not (survivors & {101, 102, 103, 104, 105}), f"survivors={survivors}")

print()
print("=== subject_type=None, editorial_fallback rung (the terminal rung) ===")
q2 = build_places_hard_filter_sql(
    subject_type=None, relations=relations, places_table=QA5_TABLE, quality_floor=None, editorial_fallback=True
)
survivors2 = {c.entity_id for c in fetch_places_hard_filtered(conn, q2)}
print(f"SQL: {q2.sql}")
print(f"survivor ids: {sorted(survivors2)}")
check(
    "editorial_fallback rung ALSO excludes venue types for subject_type=None (competitor rule never relaxes, Sec.1 principle 6)",
    survivors2 <= {106, 107, 108},
    f"survivors2={survivors2}",
)

print()
print("=== control: subject_type='editorial' (known, non-venue) must NOT exclude anything ===")
q3 = build_places_hard_filter_sql(subject_type="editorial", relations=relations, places_table=QA5_TABLE, quality_floor=None)
survivors3 = {c.entity_id for c in fetch_places_hard_filtered(conn, q3)}
print(f"survivor ids: {sorted(survivors3)}")
check(
    "editorial subject excludes nothing (all 8 seeded active rows survive)",
    survivors3 == {r.id for r in rows},
    f"survivors3={survivors3}, expected={{r.id for r in rows}}",
)

conn.execute(text(f"DROP TABLE IF EXISTS {QA5_TABLE}"))
conn.close()

print()
print("=== SUMMARY ===")
if FAILURES:
    print(f"{len(FAILURES)} CHECK(S) FAILED:")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("ALL CHECKS PASSED")
