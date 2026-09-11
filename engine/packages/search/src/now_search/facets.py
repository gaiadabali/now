"""Facet counts, computed in one aggregate pass (ARCHITECTURE.md §9 /
task brief: "computed in one aggregate pass (the ecommerce rule: when
counting facet F, apply every filter except F)").

**Honesty note, stated plainly in the task brief and repeated here**:
`public.articles.primary_type` and `.format` are NULL for all 4,772 rows
(E2.1 classification hasn't run) and `engine.entity_terms` has 0 rows
(E2.2 facet extraction hasn't run). Every query below runs correctly
against real Postgres and returns real (if currently uninformative --
one bucket, NULL, count=N) results. **This mechanism is built and
correct, not exercised against real facet data** -- there is nothing to
show beyond "every article currently falls in the NULL bucket for both
column facets" until E2.1/E2.2 land. Do not read an empty/degenerate
facet_counts result as a bug in this module.

Design: for each facet F, count values of F over the candidate set with
every OTHER active filter applied (never F's own filter -- a facet's own
selected values would otherwise always show their own count as "100% of
the filtered set", which is useless for "what if I also selected X").
All facets are computed by ONE UNION ALL statement -- one round trip to
Postgres, which is what "one aggregate pass" means operationally here
(the alternative, N separate queries, is what this deliberately avoids).

Two facet kinds are supported:
  - "column" facets: values live directly on `public.articles`
    (currently: type -> primary_type, format -> format).
  - "term" facets: values are `engine.entity_terms.term_id` for a given
    facet key. Resolving a term_id to a human label/slug requires the
    *platform* DB (`now_platform.engine.terms` joined to
    `engine.facets`) -- a second database this package does not connect
    to by design (every other module here is `now_jakarta`/city-DB-only,
    matching the rest of this monorepo's per-package DB scoping). This
    module returns raw term_ids; resolving labels is the caller's job
    (the future API layer, which already talks to both databases for
    other reasons -- see README "Term facet label resolution").
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

COLUMN_FACETS: dict[str, str] = {
    "type": "primary_type",
    "format": "format",
}


@dataclass(frozen=True)
class ActiveFilter:
    """One reader-chosen facet filter already applied to the candidate
    set upstream (by E3.2's filter pipeline, once it exists -- E3.1 has
    no caller with real active filters yet, so this is exercised in
    tests with synthetic filters, not live traffic)."""

    facet: str  # a key in COLUMN_FACETS, or a term-facet key
    values: tuple[str, ...]


def compute_facet_counts(
    conn: Connection,
    *,
    candidate_ids: Sequence[int],
    active_filters: Sequence[ActiveFilter] = (),
    term_facet_term_ids: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, dict[str, int]]:
    """Returns {facet_name: {value: count}}. `value` is the column's
    text representation for column facets (including the literal string
    "null" when a row's column is NULL -- deliberately surfaced rather
    than silently dropped, since "unclassified" is real, visible
    information about the corpus right now), or a term_id (as text) for
    term facets.

    `candidate_ids` is normally the post-retrieval hit set (lexical ∪
    semantic, pre-fusion or post-fusion top-N -- caller's choice) so
    facet counts describe "if you also filtered by X, how many of
    *these* results would remain", not the whole corpus.
    """
    if not candidate_ids:
        return {name: {} for name in list(COLUMN_FACETS) + list(term_facet_term_ids or {})}

    active_by_facet: dict[str, tuple[str, ...]] = {f.facet: f.values for f in active_filters}
    term_facet_term_ids = term_facet_term_ids or {}

    branches: list[str] = []
    params: dict = {"candidate_ids": list(candidate_ids)}

    for facet_name, column in COLUMN_FACETS.items():
        where_parts = ["id = ANY(:candidate_ids)"]
        for other_facet, other_column in COLUMN_FACETS.items():
            if other_facet == facet_name:
                continue
            values = active_by_facet.get(other_facet)
            if values:
                key = f"colfilter_{other_facet}"
                where_parts.append(f"{other_column}::text = ANY(:{key})")
                params[key] = list(values)
        # Other-active TERM filters also constrain a column facet's counts
        # (a term filter narrows "these results" regardless of which kind
        # of facet is being counted).
        for other_term_facet, values in active_by_facet.items():
            if other_term_facet in COLUMN_FACETS or other_term_facet not in term_facet_term_ids:
                continue
            key = f"termfilter_{other_term_facet}_ids"
            where_parts.append(
                f"id IN (SELECT entity_id::int FROM engine.entity_terms "
                f"WHERE entity_type = 'article' AND term_id::text = ANY(:{key}))"
            )
            params[key] = list(values)
        where_sql = " AND ".join(where_parts)
        branches.append(
            f"SELECT '{facet_name}' AS facet, coalesce({column}::text, 'null') AS value, count(*) AS n "
            f"FROM public.articles WHERE {where_sql} GROUP BY {column}"
        )

    for facet_name, term_ids in term_facet_term_ids.items():
        if not term_ids:
            continue
        where_parts = [
            "et.entity_type = 'article'",
            "et.entity_id::int = ANY(:candidate_ids)",
            f"et.term_id::text = ANY(:termids_{facet_name})",
        ]
        # engine.entity_terms.term_id is uuid; compared as text so callers
        # can pass either uuid.UUID or plain str term ids uniformly.
        params[f"termids_{facet_name}"] = [str(t) for t in term_ids]
        for other_facet, other_column in COLUMN_FACETS.items():
            values = active_by_facet.get(other_facet)
            if values:
                key = f"colfilter_for_{facet_name}_{other_facet}"
                where_parts.append(
                    f"et.entity_id::int IN (SELECT id FROM public.articles WHERE {other_column}::text = ANY(:{key}))"
                )
                params[key] = list(values)
        for other_term_facet, values in active_by_facet.items():
            if other_term_facet == facet_name or other_term_facet in COLUMN_FACETS:
                continue
            if other_term_facet not in term_facet_term_ids:
                continue
            key = f"termfilter_for_{facet_name}_{other_term_facet}"
            where_parts.append(
                f"et.entity_id::int IN (SELECT entity_id::int FROM engine.entity_terms "
                f"WHERE entity_type = 'article' AND term_id::text = ANY(:{key}))"
            )
            params[key] = list(values)
        where_sql = " AND ".join(where_parts)
        branches.append(
            f"SELECT '{facet_name}' AS facet, et.term_id::text AS value, count(DISTINCT et.entity_id) AS n "
            f"FROM engine.entity_terms et WHERE {where_sql} GROUP BY et.term_id"
        )

    if not branches:
        return {}

    sql = text(" UNION ALL ".join(branches))
    rows = conn.execute(sql, params).fetchall()

    out: dict[str, dict[str, int]] = {name: {} for name in list(COLUMN_FACETS) + list(term_facet_term_ids)}
    for facet_name, value, n in rows:
        out.setdefault(facet_name, {})[value] = int(n)
    return out
