"""F132 -- one-time reconciliation of the ~1,795 disagreeing rows and 924+
missing-`entity_terms`-row rows found live in `now_jakarta`/`now_bali`
(see PROGRESS.md F132 and `now_classifier.db`'s F132 module docstring for
the root cause: `articles.primary_type`/`.format` was a "write once,
coalesce(NULL, ...)" column while `engine.entity_terms` was overwritten/
retracted on every re-run, so an early run's `articles` value survived
untouched while later runs kept moving `entity_terms` on).

This script does NOT re-run the classifier (that would churn all 9,201
rows and mask the bug rather than fix it -- explicitly out of scope per
the ticket). It only touches the specific rows verified live to be
inconsistent, and only the two `public.articles` columns
(`primary_type`, `format`) -- `engine.entity_terms` is never written here.

## Which store is authoritative, and why (a judgment call, stated not buried)

`engine.entity_terms` is treated as authoritative for every row this
script touches:

  - It is the LATEST decision `now_classifier` made for that article/facet
    (F125's re-run, 2026-09-11, itself the product of several
    since-fixed bugs: facet-scoped routing, the location-regression fix,
    the stale-retraction fix). `articles`'s disagreeing value is, by
    contrast, frozen at whatever an EARLIER run wrote (verified live:
    `articles.updated_at` for the sampled disagreements is 2026-09-08,
    `entity_terms.created_at` is 2026-09-11 -- two different runs of this
    same tool, not a CMS edit).
  - Zero of the disagreeing rows carry `entity_terms.source = 'editor'`
    (verified for both cities/both facets before writing this script) --
    so this reconciliation never overrides a human decision; F86's
    guarantee is untouched.
  - `public.articles` has no provenance column (F131/F132), so a genuine
    CMS edit is indistinguishable from this bug's own drift in general --
    but the SPECIFIC rows this script targets are exactly the ones where
    `articles.updated_at` predates `entity_terms`'s value and the value
    matches what a since-fixed, since-superseded classifier run would
    have produced. Reported to Hansel, not decided silently.

Two reconciliation shapes:

  1. **disagree** (articles non-NULL, entity_terms non-NULL, different):
     set `articles.<col>` to entity_terms's current value.
  2. **missing_entity_terms_row** (articles non-NULL, entity_terms has NO
     row for that facet -- the facet was downgraded to review and its old
     fact retracted): set `articles.<col>` to NULL. This is a judgment
     call worth surfacing on its own: it CHANGES what the article "is
     classified as" from a stale, no-longer-endorsed guess to explicitly
     unknown/pending-review, matching what `entity_terms` already asserts
     to every OTHER consumer. It is also the SAFE direction for
     `now_rails.subject`'s competitor-exclusion guarantee: F126 confirmed
     `excluded_types_for(None)` already excludes all 5 venue types (fully
     conservative), and NULL `primary_type` is a normal, common, already
     load-bearing state in this corpus (F50's synthetic-overlay mechanism
     exists precisely because most real articles have always been NULL
     here) -- so this is not a novel or risky state to introduce.

Only `type` and `format` are reconciled (the only two facets `public.
articles` has a column for -- `subtype`/`location` live only in
`entity_terms`/`classification_reviews`).

Usage:
    python scripts/reconcile_f132_articles_entity_terms.py            # dry-run, prints the plan
    python scripts/reconcile_f132_articles_entity_terms.py --execute  # applies it
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

from now_db.settings import city_database_url
from now_platform_db.settings import platform_database_url
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

CITY_DB = {"jakarta": "now_jakarta", "bali": "now_bali"}
FACET_COLUMNS = (("type", "primary_type"), ("format", "format"))
ENUM_CAST = {"primary_type": "enum_articles_primary_type", "format": "enum_articles_format"}


@dataclass
class CityFacetCounts:
    disagree: int = 0
    missing: int = 0
    editor_owned_skipped: int = 0  # should always be 0 -- see module docstring


def _term_slug_map(platform_engine: Engine, facet_key: str) -> dict[str, str]:
    with platform_engine.connect() as conn:
        rows = conn.execute(
            text(
                "select t.id::text, t.slug from engine.terms t "
                "join engine.facets f on f.id = t.facet_id where f.key = :facet_key"
            ),
            {"facet_key": facet_key},
        ).fetchall()
    return {str(r[0]).lower(): r[1] for r in rows}


def _plan_for_city_facet(city_engine: Engine, facet_key: str, column: str, slug_by_uuid: dict[str, str]):
    """Returns (disagree_rows, missing_rows) where each row is
    (article_id, legacy_wp_id, articles_value, entity_terms_slug_or_None,
    entity_terms_source_or_None)."""
    term_ids = list(slug_by_uuid.keys())
    with city_engine.connect() as conn:
        rows = conn.execute(
            text(
                f"""
                select a.id, a.legacy_wp_id::text, a.{column}::text, et.term_id::text, et.source
                from public.articles a
                left join engine.entity_terms et
                    on et.entity_type = 'article' and et.entity_id = a.id::text
                   and et.term_id = any(cast(:term_ids as uuid[]))
                where a.{column} is not null
                """
            ),
            {"term_ids": term_ids},
        ).fetchall()

    disagree, missing = [], []
    for article_id, wp_id, colval, term_id, source in rows:
        if term_id is None:
            missing.append((article_id, wp_id, colval, None, None))
            continue
        et_slug = slug_by_uuid.get(term_id.lower())
        if et_slug != colval:
            disagree.append((article_id, wp_id, colval, et_slug, source))
    return disagree, missing


def _current_counts(city_engine: Engine, facet_key: str, column: str, slug_by_uuid: dict[str, str]) -> CityFacetCounts:
    disagree, missing = _plan_for_city_facet(city_engine, facet_key, column, slug_by_uuid)
    editor_owned = sum(1 for *_r, source in disagree if source == "editor")
    return CityFacetCounts(disagree=len(disagree), missing=len(missing), editor_owned_skipped=editor_owned)


def reconcile(execute: bool) -> None:
    platform_engine = create_engine(platform_database_url())
    city_engines = {city: create_engine(city_database_url(db_ref)) for city, db_ref in CITY_DB.items()}

    print(f"=== F132 reconciliation ({'EXECUTE' if execute else 'DRY RUN'}) ===\n")

    for city, city_engine in city_engines.items():
        for facet_key, column in FACET_COLUMNS:
            slug_by_uuid = _term_slug_map(platform_engine, facet_key)
            before = _current_counts(city_engine, facet_key, column, slug_by_uuid)
            print(f"[{city}/{facet_key}] BEFORE: disagree={before.disagree} missing={before.missing} "
                  f"(editor-sourced disagreements, never touched: {before.editor_owned_skipped})")

            disagree, missing = _plan_for_city_facet(city_engine, facet_key, column, slug_by_uuid)

            to_set: list[tuple[int, str]] = []   # (article_id, new_value)
            to_null: list[int] = []               # article_id
            skipped_editor = 0
            for article_id, wp_id, colval, et_slug, source in disagree:
                if source == "editor":
                    skipped_editor += 1
                    continue
                to_set.append((article_id, et_slug))
            for article_id, wp_id, colval, _et_slug, _source in missing:
                to_null.append(article_id)

            print(f"[{city}/{facet_key}] PLAN: {len(to_set)} rows -> entity_terms's value, "
                  f"{len(to_null)} rows -> NULL, {skipped_editor} editor-sourced skipped")
            if to_set[:3]:
                print(f"    sample sets: {to_set[:3]}")
            if to_null[:3]:
                print(f"    sample nulls (article_id): {to_null[:3]}")

            if execute:
                enum_name = ENUM_CAST[column]
                with city_engine.begin() as conn:
                    for article_id, new_value in to_set:
                        conn.execute(
                            text(f"update public.articles set {column} = cast(:v as {enum_name}) where id = :id"),
                            {"v": new_value, "id": article_id},
                        )
                    for article_id in to_null:
                        conn.execute(
                            text(f"update public.articles set {column} = NULL where id = :id"),
                            {"id": article_id},
                        )

                after = _current_counts(city_engine, facet_key, column, slug_by_uuid)
                print(f"[{city}/{facet_key}] AFTER:  disagree={after.disagree} missing={after.missing}")
            print()

    for eng in city_engines.values():
        eng.dispose()
    platform_engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Apply the plan (default: dry run, print only).")
    args = parser.parse_args()
    reconcile(execute=args.execute)
