r"""widen `interactions.entity_id` / `impressions.entity_id` to `text` (F66)

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-09

Closes PROGRESS.md follow-up F66 -- the same class of bug as C4 (0003),
F33 (0005) and F44 (0006), for the two tables neither of those touched:

    column                  | before          | after
    -------------------------|-----------------|---------------
    interactions.entity_id   | uuid NULL       | text NULL
    impressions.entity_id    | uuid NOT NULL   | text NOT NULL

`public.articles.id` and `public.places.id` are Payload integer serials --
there is no uuid to store. Before this migration the beacon could record an
impression or interaction against a *synthetic* uuid entity (C4's
`stable_uuid`, deleted) but never against a real article or place, because
`interaction_entity_id`/the impressions insert path validated `entity_id` as
a uuid and rejected anything else with a 4xx. See the F66 completion report
(app/domain/events/normalize.py + service.py, this same task) for the
endpoint-side half of the fix -- this migration only changes column types.

F33's docstring (0005) explicitly rejected a derived-uuid hash for this
exact reason: hashing an integer PK to a uuid destroys the ability to join
back (`entity_id::int = articles.id`). Same reasoning applies here, so the
fix is the same shape: widen to `text`, store the native PK verbatim (e.g.
`"4821"`), no hash anywhere.

## Why `anon_id` / `session_id` / `user_id` are NOT touched

Confirmed, not assumed -- read `app/domain/events/service.py` and the live
schema before writing this migration. Unlike `entity_id`, these three
genuinely are uuids as of decision C4 (migration 0003) and F19 (the beacon
now emits `crypto.randomUUID()` for `anon_id`/`session_id`; `user_id`
references a real `identities` row when present). `entity_id` is the only
column C4/F33/F44 left inconsistent for these two tables. Widening the
other three would be an unrelated, unjustified type change to columns that
are already correct.

## Both tables are `PARTITION BY RANGE (ts)` (0001)

Verified live against `now_test` (PG 16.15) before writing this migration,
in a transaction rolled back afterwards: `ALTER TABLE engine.interactions
ALTER COLUMN entity_id TYPE text ...` issued against the partitioned
*parent* propagates the type change to every existing partition
automatically (`\d engine.interactions_p2026_09_09` showed `entity_id |
text` immediately after, indexes included, `NOT NULL` on
`impressions.entity_id` preserved) -- no per-partition DDL loop is needed,
matching 0002/0003's precedent for `ADD COLUMN`/`DROP NOT NULL` on these
same two tables. New partitions created after this migration by
`now_db.partitions.ensure_daily_partitions` (`CREATE TABLE ... PARTITION OF
...`) inherit the parent's *current* column definitions at creation time,
so every future partition is `text` for free -- `partitions.py` itself
needs no code change, since it never declares column types, only partition
bounds.

## Why this migration is safe to run as-is against a populated table

Same reasoning as 0005: `uuid -> text` is a lossless, information-preserving
widening for every existing row -- every valid uuid has an exact,
unambiguous text representation, and `USING <col>::text` cannot fail or
truncate. No populated-table guard is needed or added.

**Data-safety note, stated plainly:** row counts checked live in every
environment this migration will run against, before this migration was
written: `now_jakarta` 20 interactions / 5 impressions, `now_bali` 0 / 0,
`now_test` 3 / 0. `now_jakarta` carries real rows -- this migration must
not lose them. None of those rows are lost, truncated, or reinterpreted by
this migration: `uuid -> text` preserves every existing `entity_id` value
byte-for-byte as its canonical text form. Existing rows
whose `entity_id` was already NULL (interactions only -- every
`outbound`/`search_query` row since 0003) remain NULL. No row's
`entity_id` becomes a native-PK string as a side effect of this migration
-- that only happens for new writes once the endpoint fix (same task)
ships; this migration alone does not retroactively fix historical rows,
matching 0005's "widening the column type does not retroactively fix data
written under the old convention" note.

## Downgrade

`text -> uuid` is only lossless if every existing value happens to already
be valid uuid syntax. Immediately after `upgrade()` with no intervening
writes that is trivially true (verified live, see report). It stops being
true the moment the fixed endpoint writes a real integer-PK string (e.g.
`"4821"`) into either column -- the entire point of this migration.
Matching 0003/0005/0006's precedent exactly: `downgrade()` does not
fabricate a synthetic uuid to paper over that. It reissues the type change
(and, for `interactions.entity_id`, the nullability -- unchanged by this
migration, so nothing to restore there) and lets Postgres raise a clear
`22P02 invalid_text_representation` if the live data no longer supports it.
Downgrading after real integer-keyed impressions/interactions have landed
requires a deliberate data decision this migration will not make silently.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE engine.interactions ALTER COLUMN entity_id TYPE text USING entity_id::text")
    op.execute("ALTER TABLE engine.impressions ALTER COLUMN entity_id TYPE text USING entity_id::text")


def downgrade() -> None:
    # See "Downgrade" note above -- these raise 22P02 rather than silently
    # fabricating data if either column holds a non-uuid text value (e.g. a
    # native integer PK stored as text, which is exactly what F66 exists to
    # make happen).
    op.execute("ALTER TABLE engine.impressions ALTER COLUMN entity_id TYPE uuid USING entity_id::uuid")
    op.execute("ALTER TABLE engine.interactions ALTER COLUMN entity_id TYPE uuid USING entity_id::uuid")
