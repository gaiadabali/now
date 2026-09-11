#!/usr/bin/env python3
"""Fail if any live column looks like a reference to a Payload entity
(articles/places/events/media) but is typed `uuid`.

## Why this exists

This is the mechanical enforcement half of PROGRESS.md's F69 report. The
same defect shipped four times in this project before anyone caught it:

    C4   beacon identifiers hashed into uuid columns          -> fixed, now_db migration 0003
    F33  four now_db engine tables (quality_scores, entity_terms,
         covisitation, rail_cache)                             -> fixed, now_db migration 0005
    F66  now_db interactions + impressions                     -> fixed, now_db migration 0007
    F69  now_platform_db partnerships.place_id + 3 siblings     -> fixed, now_platform_db migration 0005

Every real Payload table (`public.articles`, `public.places`,
`public.events`, `public.media`, in every city database) has a plain
`serial` integer primary key -- Payload/Drizzle never generates a uuid PK
for these. There is no uuid to store. A column elsewhere named like
`<payload-entity>_id` (`place_id`, `origin_article_id`, `hero_media_id`,
`logo_media_id`, ...) but typed `uuid` can never hold a real row's id:
`SELECT '42'::uuid` raises `invalid_text_representation`. F69 was the
fourth time this was found by a human reading a diagnosis after the fact,
and the first time it happened in schema written *after* the first three
had already documented the rule in three different migration docstrings
and two package READMEs -- proof that a rule nobody encounters at the
point of writing does not stop the pattern from recurring, no matter how
many times it is written down. This script is the version of the rule
that runs whether or not the next author read any of those docstrings.

## Why this inspects the live schema, not migration source text

A tempting first design is `grep -R 'uuid' migrations/versions/*.py`. That
is wrong for this codebase: migration files are immutable history, and
every one of the four fixes above is a *later* migration correcting an
*earlier* one's `CREATE TABLE ... place_id uuid ...` -- that original line
is still sitting in 0001's source, forever, because rewriting a merged
migration is not how Alembic history works. A source-text grep would
therefore flag 0001 as a violation on every run, permanently, with no way
to distinguish "still broken" from "fixed three migrations later". The
only thing that actually matters is the shape of the schema a migration
*set* produces at HEAD -- so this script connects to a real,
fully-migrated database and reads `information_schema.columns`, the same
way `now_platform_db.schema_hash` and `now_db.schema_hash` already do for
the drift gate.

## Known, deliberate gaps (do not treat this as a complete guarantee)

- Only catches columns whose name ends in one of the four Payload entity
  stems + `_id` (see `_PATTERN`). PROGRESS.md's F44
  (`engine.travel_matrix.place_a` / `place_b`, in now_db) is the same bug
  under a naming convention this pattern does not match by design --
  `place_a`/`place_b` don't end in `_id`. Extending the pattern to catch
  that shape too was considered and rejected: `_a`/`_b` is specific to one
  table's own naming choice, not a second general convention, and a
  looser regex broad enough to catch it started matching legitimate
  platform-local columns in a spot check (`orgs.parent_org_id`-shaped
  names). Narrow-and-correct beats broad-and-noisy for a gate that has to
  stay trustworthy; F44 is tracked and fixed on its own schedule instead.
- Only catches `uuid`-typed columns. A future variant of this same bug
  (e.g. someone choosing `bigint` for a column that should be `text`
  because the native PK is sometimes prefixed, `"jkt-42"`) would not be
  caught by this script. It targets the specific, now four-times-repeated
  failure mode, not "any possible entity-reference type mistake".
- A polymorphic column (`entity_id`, used by now_db's `quality_scores` /
  `entity_terms` / `covisitation` / `rail_cache` / `embeddings`, disambiguated
  by a sibling `entity_type` column rather than by name) is not named after
  any single entity stem and so is invisible to this check by construction.
  Those five columns are independently already `text` (F33/C4) -- this is
  noted so nobody reads a clean run of this script as proof that pattern is
  covered too.

Usage:
    check_no_payload_uuid_refs.py <sqlalchemy-url> [<sqlalchemy-url> ...]

Exits 1 and prints every offending (schema, table, column) if any is
found; exits 0 (and prints a one-line OK) otherwise.
"""
from __future__ import annotations

import re
import sys

from sqlalchemy import create_engine, text

# Payload entity stems that can never legitimately back a uuid-typed
# column anywhere else in the schema, because the real table's PK is a
# plain serial integer (verified live against the shipped Payload DDL --
# see F69's report). Matched as the final "word" immediately before a
# trailing `_id`, so it catches `place_id`, `origin_article_id`,
# `hero_media_id`, `logo_media_id`, `event_id`, etc., but not columns that
# merely contain the substring elsewhere (e.g. a hypothetical
# `placement_id` or `mediation_id` -- neither exists today, and the
# word-boundary anchor is what keeps a coincidental substring match from
# ever becoming a false positive).
_ENTITY_STEMS = ("article", "place", "event", "media")
_PATTERN = re.compile(r"(?:^|_)(?:" + "|".join(_ENTITY_STEMS) + r")_id$", re.IGNORECASE)

_QUERY = text(
    """
    SELECT table_schema, table_name, column_name, data_type
    FROM information_schema.columns
    WHERE data_type = 'uuid'
      AND table_schema NOT IN ('pg_catalog', 'information_schema')
    ORDER BY table_schema, table_name, column_name
    """
)


def find_violations(url: str) -> list[tuple[str, str, str]]:
    engine = create_engine(url)
    violations: list[tuple[str, str, str]] = []
    with engine.connect() as conn:
        for schema, table, column, _dtype in conn.execute(_QUERY):
            if _PATTERN.search(column):
                violations.append((schema, table, column))
    return violations


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: check_no_payload_uuid_refs.py <db-url> [<db-url> ...]", file=sys.stderr)
        return 2

    all_violations: list[tuple[str, str, str, str]] = []
    for url in argv:
        for schema, table, column in find_violations(url):
            all_violations.append((url, schema, table, column))

    if not all_violations:
        print("[check-no-payload-uuid-refs] OK -- no uuid-typed Payload-entity-reference columns found")
        return 0

    print(
        "[check-no-payload-uuid-refs] VIOLATIONS -- these columns look like a reference to a "
        "Payload entity (articles/places/events/media) but are typed uuid. Payload's real "
        "primary keys are plain serial integers (SELECT '42'::uuid raises) -- widen to `text` "
        "and store the native PK verbatim, per PROGRESS.md C4 / F33 / F66 / F69.",
        file=sys.stderr,
    )
    for url, schema, table, column in all_violations:
        print(f"  - {schema}.{table}.{column}   (db: {url})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
