"""F132 -- `public.articles.primary_type`/`.format` <-> `engine.entity_terms`
consistency DETECTION.

The two stores are written by `now_classifier.db.write_results` in the
same transaction, per article, for the same classification decision (see
that module's F132 docstring for the root-cause history: before the
fix they used different re-run semantics -- `articles` was a "set once,
coalesce(NULL, ...)" write while `entity_terms` was overwritten/retracted
on every re-run -- so a re-classification run could move `entity_terms`
to a new value while `articles` silently kept the old one forever).

The write-path fix makes new drift far less likely, but it deliberately
still REFUSES to touch `articles` whenever it cannot prove the row is
still machine-owned (no provenance column exists on `public.articles` --
F131 -- so a genuine editor/CMS edit is indistinguishable from a drifted
row). That means drift can still appear, and now-db's own precedent
(`check-term-refs`, F92) is exactly the right shape for catching it: a
loud, non-fatal signal wired into `site:migrate`, plus a standalone
command that fails (exit 1) for CI.

This module mirrors `now_db.term_refs` deliberately -- same "one function
returns a list of findings, read-only, city table missing => skipped"
shape -- rather than inventing a new convention.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

DEFAULT_SAMPLE_SIZE = 5

# The two single-valued facets `public.articles` actually carries a column
# for. `subtype`/`location` have no articles-side counterpart (see
# `now_classifier.db.write_results`) so are out of scope for this check.
_ARTICLES_FACET_COLUMNS: tuple[tuple[str, str], ...] = (("type", "primary_type"), ("format", "format"))


@dataclass(frozen=True)
class FacetDriftGroup:
    """One (facet, kind) finding, aggregated -- not one row per article,
    since a real drift event (F132) affects thousands of rows and a
    CI/migrate-time report needs a summary, not a wall of ids."""

    facet: str  # "type" | "format"
    kind: str  # "disagree" | "missing_entity_terms_row"
    count: int
    sample_legacy_wp_ids: list[str]


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


def _term_slug_map(platform_conn: Connection, facet_key: str) -> dict[str, str]:
    """lowercased term uuid -> slug, for one facet (`type` or `format`)."""
    rows = platform_conn.execute(
        text(
            """
            SELECT t.id::text, t.slug
            FROM engine.terms t
            JOIN engine.facets f ON f.id = t.facet_id
            WHERE f.key = :facet_key
            """
        ),
        {"facet_key": facet_key},
    ).fetchall()
    return {str(r[0]).lower(): r[1] for r in rows}


def find_facet_drift(
    city_conn: Connection,
    platform_conn: Connection,
    *,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
) -> list[FacetDriftGroup]:
    """Return every (facet, kind) group where `public.articles` and
    `engine.entity_terms` disagree for this city. Empty list means clean.
    Read-only -- never mutates either database. Skips the check entirely
    if `public.articles` does not exist in this city db (e.g. `now_test`
    without the F132 test's scratch schema applied).

    Two kinds of finding, matching F132's own two shapes:
      - "disagree": `articles.<col>` is non-NULL and `entity_terms` holds
        a DIFFERENT value for that facet.
      - "missing_entity_terms_row": `articles.<col>` is non-NULL but
        `entity_terms` has NO row at all for that facet (the facet was
        downgraded to review by a later run and its old fact retracted,
        but `articles` was never told).
    """
    if not _table_exists(city_conn, "public", "articles"):
        return []

    groups: list[FacetDriftGroup] = []
    for facet_key, column in _ARTICLES_FACET_COLUMNS:
        slug_by_uuid = _term_slug_map(platform_conn, facet_key)
        term_ids = list(slug_by_uuid.keys())
        if not term_ids:
            continue

        rows = city_conn.execute(
            text(
                f"""
                SELECT a.legacy_wp_id::text, a.{column}::text, et.term_id::text
                FROM public.articles a
                LEFT JOIN engine.entity_terms et
                    ON et.entity_type = 'article' AND et.entity_id = a.id::text
                   AND et.term_id = ANY(CAST(:term_ids AS uuid[]))
                WHERE a.{column} IS NOT NULL
                """
            ),
            {"term_ids": term_ids},
        ).fetchall()

        disagree_wp: list[str] = []
        missing_wp: list[str] = []
        for legacy_wp_id, column_value, term_id in rows:
            if term_id is None:
                missing_wp.append(legacy_wp_id)
                continue
            if slug_by_uuid.get(term_id.lower()) != column_value:
                disagree_wp.append(legacy_wp_id)

        if disagree_wp:
            groups.append(FacetDriftGroup(facet_key, "disagree", len(disagree_wp), disagree_wp[:sample_size]))
        if missing_wp:
            groups.append(
                FacetDriftGroup(facet_key, "missing_entity_terms_row", len(missing_wp), missing_wp[:sample_size])
            )
    return groups


def format_facet_drift_report(url: str, groups: list[FacetDriftGroup]) -> list[str]:
    """Human-readable diagnostic lines, one per (facet, kind) group --
    matches `now_db.term_refs.format_orphan_report`'s convention."""
    if not groups:
        return []
    total = sum(g.count for g in groups)
    lines = [f"{url}: {total} articles.{{primary_type,format}} / entity_terms drift finding(s) (F132)"]
    for g in groups:
        sample = ", ".join(g.sample_legacy_wp_ids) if g.sample_legacy_wp_ids else "(none fetched)"
        lines.append(f"  - facet={g.facet} kind={g.kind} count={g.count} sample_legacy_wp_id=[{sample}]")
    return lines


def has_facet_drift(groups: list[FacetDriftGroup]) -> bool:
    """Unlike `term_refs`'s historical/live split, every finding here is
    LIVE (it's `public.articles`, not a snapshot table) -- any non-empty
    result should fail CI."""
    return bool(groups)
