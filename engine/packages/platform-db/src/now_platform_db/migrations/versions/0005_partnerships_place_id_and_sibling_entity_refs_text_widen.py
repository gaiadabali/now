r"""widen partnerships.place_id + sibling Payload-entity-ref columns to
`text` (F69)

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-09

Closes PROGRESS.md follow-up F69 -- the fourth appearance of the identical
bug class as C4 (0003, this package), F33 (now_db 0005) and F66 (now_db
0007), and the first to appear in schema written *after* the pattern was
already documented in three places. `engine.partnerships.place_id` is
`uuid`, but every city DB's `public.places.id` is a Payload `serial`
integer -- confirmed against the real Payload-generated DDL
(`engine/packages/cms/src/migrations/20260908_131927_initial_schema.ts`,
`CREATE TABLE "places" ("id" serial PRIMARY KEY NOT NULL, ...)`), not
assumed. `SELECT '42'::uuid` raises, so no real place could ever hold a
place-level partnership -- only org-level deals were reachable for real
places. Zero `partnerships` rows exist in production at the time of
writing, so this is a clean widening with nothing to backfill.

## Sibling audit (F69's brief: "check whether any sibling column has the
   same problem -- audit them, don't assume")

Audited every column in this package's baseline (0001) that is (a) typed
`uuid` and (b) not backed by a real in-database FK to `engine.sites` /
`engine.orgs` / `engine.campaigns` / `engine.terms` / `engine.identities`
-- i.e. every column documented as "city DB `x.id`, no FK (cross-database)"
in 0001's own docstring and this package's README. That is a short,
enumerable list; every member was checked against the real Payload table
it names and against a live count of rows:

    column                                | before | Payload PK it names      | rows today
    ---------------------------------------|--------|---------------------------|------------
    partnerships.place_id                  | uuid   | places.id (serial)       | 0 (F69, this migration)
    itinerary_stops.place_id               | uuid   | places.id (serial)       | 0 (found here, NOT
                                            |        |                           |  previously tracked)
    syndications.origin_article_id         | uuid   | articles.id (serial)     | 0 (found here, NOT
                                            |        |                           |  previously tracked)
    orgs.logo_media_id                     | uuid   | media.id (serial)        | 0 non-null of 1,562
                                            |        |                           |  rows (found here, NOT
                                            |        |                           |  previously tracked)

`placements`, `campaigns` and `ad_events` were audited too, per the brief,
and are clean:
  - `placements` (surface, slot, boost_factor, guaranteed_impressions,
    freq_cap, campaign_id) carries no column naming a Payload entity at
    all -- `campaign_id` is a real in-database FK to `engine.campaigns`.
  - `campaigns` (org_id, site_id, objective, budget, pacing, targeting
    jsonb, status) is the same -- `org_id`/`site_id` are real FKs.
    `targeting jsonb` may one day carry place/article ids as *values*
    inside the JSON, but that is not a typed column and out of a schema
    migration's reach; flagged for whoever designs `targeting`'s shape.
  - `ad_events` (campaign_id, placement_id, session_id) -- `session_id` is
    genuinely a uuid (the beacon's `crypto.randomUUID()`, same as
    `interactions`/`impressions.session_id` after F19/C4), not an entity
    reference; `campaign_id`/`placement_id` are real FKs.

`itinerary_days.area_term_id` (`uuid REFERENCES engine.terms (id)`) was
checked and is correct as-is: `engine.terms` is a *platform-local* table
with a real FK, not a cross-database reference, so it is not part of this
bug class at all.

**Three genuinely new instances were found and are fixed by this
migration alongside the one F69 named** -- `itinerary_stops.place_id`,
`syndications.origin_article_id`, `orgs.logo_media_id`. All three were
verified empty (`itinerary_stops`/`syndications`: 0 rows total;
`orgs.logo_media_id`: 0 non-NULL of 1,562 rows) via a live `SELECT count(*)`
against `now_platform` before this migration was written, so, like
`partnerships.place_id`, each is a clean widening with nothing to
backfill or risk losing. Leaving three more live instances of the
identical, just-diagnosed bug sitting in the same migration file F69 is
fixing would have undermined the whole point of this ticket -- see the
"enforceable, not merely documented" mandate in F69's brief -- so they are
fixed here rather than filed as a fifth/sixth/seventh follow-up to be
rediscovered later. `orgs.logo_media_id` carries an additional, separate
design question this migration does NOT attempt to resolve: an org can
span multiple cities (the `intercontinental` parent/child hierarchy from
0004's docstring), so "which city's `media` table does this id belong to"
is genuinely ambiguous in a way `partnerships.place_id`/`itinerary_stops.
place_id` (both already scoped to one `site_id` on the same row) are not.
Widening the *type* fixes the `'x'::uuid` crash either way; the ownership
question is a follow-up for whoever builds logo upload in the partner
console (E4.4) and is called out again in this migration's completion
report.

## Why `text`, not a Payload uuid

Same reasoning as C4/F33/F66 (do not re-litigate here): a derived
`uuid5(entity_type, id)` hash was explicitly rejected in F33's migration
because it destroys the ability to join back to the native PK. `text`
storing the native PK verbatim (`"42"`) keeps every future join a plain
`place_id::int = places.id` with no hash math anywhere.

## `place_id` still cannot be a real FK

Unchanged from 0001/0003: places live in each city's own database: DB
per city means Postgres cannot enforce a cross-database constraint.
Referential integrity for `place_id`/`origin_article_id`/`logo_media_id`
remains an application/worker responsibility, same as before this
migration -- only the column *type* changes here, never the FK story.

## E4.2's fail-closed defence keeps working, and stops being load-bearing

`now_link_resolver.resolver` casts the *column* to `::text` in every
comparison (`place_id::text = :place_id`) specifically so a non-uuid-shaped
`place_id` fails closed (no match -> free tier) instead of raising --
proven by `test_place_id_not_uuid_shaped_fails_closed_not_raises`. Casting
an already-`text` column with `::text` is a no-op, so that code path is
unaffected; verified live (see this migration's completion report) that a
real place-level partnership row with `place_id = '42'` now inserts and
resolves through `engine.partnerships_active`, which it could never do
before (`'42'::uuid` raised on `INSERT`, let alone `SELECT`). The defence
was written to survive exactly this migration and does.

## Why the view has to be dropped and recreated

`engine.partnerships_active` is `SELECT * FROM engine.partnerships ...`
(0003), so Postgres refuses `ALTER COLUMN place_id TYPE text` outright
with "cannot alter type of a column used by a view or rule" -- verified
live, not assumed. The `partnership_is_effective` function is untouched:
its parameters are `text`/`timestamptz` scalars, not `%TYPE`-bound to
`partnerships`, so it has no dependency on `place_id`'s type at all.

## Verified live before writing this migration

In a transaction rolled back afterwards, against the real `now_platform`
(PG 16, pgvector 0.8.6 + PostGIS 3.6.4): all four `ALTER COLUMN ... TYPE
text USING ...::text` statements succeed once the view is dropped first;
every index/constraint that depends on the widened columns (the
`ck_partnerships_org_xor_place` CHECK, `ix_partnerships_place_lookup`,
`ix_partnerships_place_active`, `uq_syndications_edge`) is automatically
rebuilt by Postgres against the new column type with no manual DROP/CREATE
needed; and a real place-level partnership (`place_id = '42'`, a genuine
integer-PK shape) inserts cleanly and appears in `engine.partnerships_active`.

## Downgrade

`text -> uuid` is only lossless if every existing value already happens to
be uuid-shaped -- trivially true immediately after `upgrade()` with no
intervening writes (today: zero rows across all four columns), and no
longer true the moment a real integer-PK string like `"42"` is written,
which is the entire point of this migration. Matching 0003/now_db 0005/
now_db 0007's precedent exactly: `downgrade()` does not fabricate a
synthetic uuid to paper over that. It drops and recreates the view (same
reason as upgrade), reissues the type change with `USING col::uuid`, and
lets Postgres raise `22P02 invalid_text_representation` if live data no
longer supports it. Downgrading after a real place-level partnership has
been sold requires a deliberate data decision this migration will not
make silently.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    # `partnerships_active` is `SELECT *` over `partnerships` (0003) so it
    # must be dropped before `place_id`'s type can change, and recreated
    # identically afterwards -- verified live, see module docstring.
    op.execute("DROP VIEW engine.partnerships_active")

    op.execute("ALTER TABLE engine.partnerships ALTER COLUMN place_id TYPE text USING place_id::text")
    op.execute("ALTER TABLE engine.itinerary_stops ALTER COLUMN place_id TYPE text USING place_id::text")
    op.execute(
        "ALTER TABLE engine.syndications ALTER COLUMN origin_article_id TYPE text "
        "USING origin_article_id::text"
    )
    op.execute("ALTER TABLE engine.orgs ALTER COLUMN logo_media_id TYPE text USING logo_media_id::text")

    op.execute(
        """
        CREATE VIEW engine.partnerships_active AS
        SELECT *
        FROM engine.partnerships p
        WHERE engine.partnership_is_effective(p.status, p.starts_at, p.ends_at)
        """
    )
    op.execute(
        "COMMENT ON VIEW engine.partnerships_active IS "
        "'Currently-effective partnerships, recomputed on every read via now() -- "
        "there is no refresh step and nothing here is ever stale by more than one query.'"
    )


def downgrade() -> None:
    # See "Downgrade" note above -- these raise 22P02 rather than silently
    # fabricating data if any of the four columns holds a non-uuid text
    # value (e.g. a native integer PK stored as text, which is exactly
    # what this migration exists to make happen).
    op.execute("DROP VIEW engine.partnerships_active")

    op.execute("ALTER TABLE engine.orgs ALTER COLUMN logo_media_id TYPE uuid USING logo_media_id::uuid")
    op.execute(
        "ALTER TABLE engine.syndications ALTER COLUMN origin_article_id TYPE uuid "
        "USING origin_article_id::uuid"
    )
    op.execute("ALTER TABLE engine.itinerary_stops ALTER COLUMN place_id TYPE uuid USING place_id::uuid")
    op.execute("ALTER TABLE engine.partnerships ALTER COLUMN place_id TYPE uuid USING place_id::uuid")

    op.execute(
        """
        CREATE VIEW engine.partnerships_active AS
        SELECT *
        FROM engine.partnerships p
        WHERE engine.partnership_is_effective(p.status, p.starts_at, p.ends_at)
        """
    )
    op.execute(
        "COMMENT ON VIEW engine.partnerships_active IS "
        "'Currently-effective partnerships, recomputed on every read via now() -- "
        "there is no refresh step and nothing here is ever stale by more than one query.'"
    )
