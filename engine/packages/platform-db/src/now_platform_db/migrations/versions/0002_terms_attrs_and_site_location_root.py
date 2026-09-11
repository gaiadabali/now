"""add `engine.terms.attrs` + `engine.sites.location_term_id` -- taxonomy
schema needs surfaced by E1.4's seed (PROGRESS.md WAVE 2/3, task E0.7)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-08

Context: E1.4 seeded 267 terms into `engine.facets`/`engine.terms` and hit
two schema gaps it was correctly forbidden from fixing itself (taxonomy
seeding is data-only; DDL is this package's job):

1. **No per-term attribute store.** `format` terms need a decay half-life
   (ARCHITECTURE.md §4 "Format -> decay half-life"), and there is nowhere
   on `engine.terms` to put it. E1.4 parked the whole format->decay policy
   object in `sites.ranking_weights['decay']` as a workaround (see
   `now_db.provisioning.seed_site_decay_defaults` / `format_decay.json`).
   That workaround still exists after this migration and is NOT touched
   here -- moving the decay policy from `sites.ranking_weights` onto
   `terms.attrs` (so it lives with the term it describes, once per format,
   rather than duplicated per-site) is a data migration, explicitly out of
   scope for this ticket: "Add the column; do NOT migrate the existing
   data -- leave that to a follow-up so this stays a pure schema change."

   `attrs jsonb NOT NULL DEFAULT '{}'` is intentionally schemaless -- the
   set of per-term attributes is expected to grow (decay policy today,
   possibly display icons/colors/synonyms later) and none of them are
   queried relationally today, so a jsonb bucket avoids a migration per new
   attribute. `NOT NULL DEFAULT '{}'` means every existing row (267 of
   them) gets `'{}'::jsonb` for free -- no backfill loop needed for a
   default value, and `attrs -> 'decay'` on any term reads NULL (absent)
   until a follow-up migration writes it, which is exactly the "pure
   schema change" this ticket asked for.

2. **No first-class default-location link for a site.** `sites.slug ==
   terms.slug` was being used as an implicit, unenforced convention to find
   a site's location root -- e.g. assuming the site `jakarta` corresponds to
   a `location` term with slug `jakarta`. That convention is fragile (a
   site slug is free text chosen by whoever runs `site:create`; a location
   term slug is part of the shared taxonomy tree and does not have to
   match, and today in fact does not -- the seeded `location` root terms
   are `indonesia`/`international`, not per-city slugs at all). A real FK
   makes the relationship explicit and enforced.

   `location_term_id uuid NULL REFERENCES engine.terms(id)` is nullable
   and unbackfilled on purpose -- no `location` term currently corresponds
   1:1 with `jakarta`/`bali`/`test` (see previous paragraph), so there is
   nothing correct to write here yet. Populating it is a follow-up once the
   location tree grows city-level nodes, or a per-site decision made by
   whoever owns `site:create`. No `ON DELETE` action is specified (default
   `NO ACTION`): a `terms` row that some site depends on as its location
   root must not vanish silently out from under it.

Both changes are purely additive -- no existing column is altered, no
constraint is tightened, no row is rewritten. `ADD COLUMN ... DEFAULT
'{}'` on `engine.terms` is a single fast metadata-level operation on
modern Postgres (>= 11) when the default is a non-volatile constant,
which `'{}'::jsonb` is -- no full-table rewrite despite the NOT NULL +
default combination. `sites` gets a nullable FK column, also
metadata-only. Safe to run against a database with live rows in both
tables (as this environment currently has: 267 terms, 3 sites).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE engine.terms ADD COLUMN attrs jsonb NOT NULL DEFAULT '{}'::jsonb")
    op.execute(
        "ALTER TABLE engine.sites ADD COLUMN location_term_id uuid NULL "
        "REFERENCES engine.terms (id)"
    )
    op.execute(
        "CREATE INDEX ix_sites_location_term ON engine.sites (location_term_id) "
        "WHERE location_term_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS engine.ix_sites_location_term")
    op.execute("ALTER TABLE engine.sites DROP COLUMN location_term_id")
    op.execute("ALTER TABLE engine.terms DROP COLUMN attrs")
