"""F92 (PROGRESS.md) — vocabulary referential-integrity DETECTION.

`now_platform.engine.terms` is the shared vocabulary (407 terms as of this
writing). Several tables in a CITY database carry one of its `id` values
as a plain (unconstrained) uuid/text column, because Postgres cannot
declare an FK across databases (ARCHITECTURE.md §2). Nothing in the schema
stops a term being deleted from the platform vocabulary while a city still
references it by that now-dangling id.

This was harmless only by luck: E2.0c dropped `rawamangun` from the
vocabulary while every one of these city tables happened to be empty.
That is no longer true — a **real, pre-existing** orphan was found live in
`now_jakarta` while this module was being written: `engine.embeddings` has
a `entity_type='term'` row for id `58e339f8-2f72-422b-8ac1-af3c95ce16c1`
(written 2026-09-08 by E2.4's original backfill) that no longer matches
any row in `now_platform.engine.terms` — almost certainly the `rawamangun`
leftover, and undetected until now because `now_embeddings backfill`
deliberately disables pruning for `entity_type='term'`
(`prune_stale=not no_prune and entity_type != "term"`, `cli.py`). See this
package's verification report for the live count before/after and whether
it was removed (a data decision, never a silent side effect of running
this check).

## Enumerating every source, not trusting a single table

`entity_terms.term_id` is not the only place a city holds one of these
ids. Found by grepping every writer of a term-derived uuid, not assumed:

  - `engine.entity_terms.term_id` (uuid, every row) — E2.1's classifier
    and any future engine-worker upsert. LIVE: an orphan here is a
    currently-active (mis)tag on a real article/place.
  - `engine.embeddings.entity_id` (text, only WHERE entity_type='term')
    — E2.4's per-term embedding cache, keyed by the platform term's own
    id standing in as "the entity". LIVE: an orphan here is a stale
    vector for a term that no longer exists, wasting an HNSW slot and
    (if ever queried) returning a kNN neighbour that resolves to nothing.
  - `public.classification_reviews.term_id` (text, nullable) — Payload's
    review-queue snapshot of the *AI's original proposal* term id
    (E2.8/F86). Deliberately NOT treated as `live`: this collection is an
    explicit historical record ("a durable, human-reviewable SNAPSHOT",
    per `ClassificationReviews.ts`) — a term retired after a review was
    already decided is expected, not a corruption, and must not be
    reported with the same urgency as a live tag. Still surfaced (an
    operator triaging vocabulary changes should be able to see it), just
    flagged `live=False` so it never drives an exit code or a hard CI
    failure on its own.

A source table that does not exist in a given city database (e.g.
`now_test`, which has no Payload `public` schema at all — see this
package's README) is skipped for that database rather than erroring;
checked via `information_schema.tables` up front so a missing table never
leaves a connection's transaction aborted mid-sweep.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

DEFAULT_SAMPLE_SIZE = 5


@dataclass(frozen=True)
class TermRefSource:
    label: str
    schema: str
    table: str
    live: bool  # False = historical/snapshot reference, not a live tag (see module docstring)
    distinct_ids_sql: str
    sample_sql: str
    count_sql: str
    detail_entity_col: str  # what to print as "entity_type" in the report for this source


SOURCES: tuple[TermRefSource, ...] = (
    TermRefSource(
        label="engine.entity_terms.term_id",
        schema="engine",
        table="entity_terms",
        live=True,
        distinct_ids_sql="SELECT DISTINCT term_id::text FROM engine.entity_terms",
        sample_sql=(
            "SELECT entity_type, entity_id FROM engine.entity_terms "
            "WHERE term_id = CAST(:term_id AS uuid) ORDER BY entity_type, entity_id LIMIT :limit"
        ),
        count_sql="SELECT count(*) FROM engine.entity_terms WHERE term_id = CAST(:term_id AS uuid)",
        detail_entity_col="entity_type",
    ),
    TermRefSource(
        label="engine.embeddings.entity_id (entity_type='term')",
        schema="engine",
        table="embeddings",
        live=True,
        distinct_ids_sql="SELECT DISTINCT entity_id FROM engine.embeddings WHERE entity_type = 'term'",
        sample_sql=(
            "SELECT 'term', model FROM engine.embeddings "
            "WHERE entity_type = 'term' AND entity_id = :term_id ORDER BY model LIMIT :limit"
        ),
        count_sql="SELECT count(*) FROM engine.embeddings WHERE entity_type = 'term' AND entity_id = :term_id",
        detail_entity_col="term (model)",
    ),
    TermRefSource(
        label="public.classification_reviews.term_id",
        schema="public",
        table="classification_reviews",
        live=False,
        distinct_ids_sql="SELECT DISTINCT term_id FROM public.classification_reviews WHERE term_id IS NOT NULL",
        sample_sql=(
            "SELECT entity_type, id::text FROM public.classification_reviews "
            "WHERE term_id = :term_id ORDER BY id LIMIT :limit"
        ),
        count_sql="SELECT count(*) FROM public.classification_reviews WHERE term_id = :term_id",
        detail_entity_col="entity_type",
    ),
)


@dataclass(frozen=True)
class OrphanedTermRef:
    """One term id referenced from a city table with no matching row in
    `now_platform.engine.terms`."""

    term_id: str
    source: str  # e.g. "engine.entity_terms.term_id" — see TermRefSource.label
    live: bool
    entity_label: str  # what kind of thing referenced it (article/place/term/review id)
    row_count: int
    sample: list[str]


def _table_exists(conn: Connection, schema: str, table: str) -> bool:
    return bool(
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = :schema AND table_name = :table"
            ),
            {"schema": schema, "table": table},
        ).first()
    )


def find_orphaned_term_refs(
    city_conn: Connection,
    platform_conn: Connection,
    *,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
) -> list[OrphanedTermRef]:
    """Return every term id referenced from ANY known city source (see
    `SOURCES`) that has no matching row in `now_platform.engine.terms`.
    Empty list means clean. Read-only — never mutates either database.
    Sources whose table does not exist in this city database (e.g.
    `now_test` has no Payload `public` schema) are silently skipped.
    """
    platform_term_ids = {
        str(r) for r in platform_conn.execute(text("SELECT id FROM engine.terms")).scalars().all()
    }

    results: list[OrphanedTermRef] = []
    for source in SOURCES:
        if not _table_exists(city_conn, source.schema, source.table):
            continue

        referenced_ids = city_conn.execute(text(source.distinct_ids_sql)).scalars().all()
        if not referenced_ids:
            continue
        referenced_id_strs = {str(t) for t in referenced_ids}
        orphaned = sorted(referenced_id_strs - platform_term_ids)
        if not orphaned:
            continue

        for term_id in orphaned:
            sample_rows = city_conn.execute(
                text(source.sample_sql), {"term_id": term_id, "limit": sample_size}
            ).fetchall()
            row_count = city_conn.execute(
                text(source.count_sql), {"term_id": term_id}
            ).scalar_one()
            results.append(
                OrphanedTermRef(
                    term_id=term_id,
                    source=source.label,
                    live=source.live,
                    entity_label=str(sample_rows[0][0]) if sample_rows else "unknown",
                    row_count=row_count,
                    sample=[str(r[1]) for r in sample_rows],
                )
            )
    return results


def format_orphan_report(url: str, orphans: list[OrphanedTermRef]) -> list[str]:
    """Human-readable diagnostic lines, one per orphaned (source, term_id)
    pair — matches `now_db.schema_hash.diff_structures`'s "one line per
    finding" convention used by the `check` command."""
    if not orphans:
        return []
    live = [o for o in orphans if o.live]
    historical = [o for o in orphans if not o.live]
    lines = [
        f"{url}: {len(orphans)} orphaned term reference(s) — {len(live)} live, "
        f"{len(historical)} historical/snapshot-only (F92)"
    ]
    for o in orphans:
        tag = "LIVE" if o.live else "historical"
        sample = ", ".join(o.sample) if o.sample else "(none fetched)"
        lines.append(
            f"  - [{tag}] {o.source}: term_id={o.term_id} rows={o.row_count} "
            f"{o.entity_label}=[{sample}]"
        )
    return lines


def has_live_orphans(orphans: list[OrphanedTermRef]) -> bool:
    return any(o.live for o in orphans)
