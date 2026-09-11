"""fix `engine.interactions` identifier typing + add `target_url` -- resolves
open contract decision C4 (PROGRESS.md)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-08

Context (PROGRESS.md "Open contract decisions", C4): 0001's `interactions`
contract typed `anon_id`, `session_id`, `user_id`, `entity_id` as `uuid NOT
NULL`. The beacon (E0.4) never emitted UUIDs for any of them -- `anon_id`/
`session_id` were 24-char base36 strings, `user_id` an arbitrary app string,
and `entity_id` carried a raw `href` for `outbound` events or free search
text for `search` events, neither of which is a UUID.

E0.5 shipped `stable_uuid` (`app/domain/events/normalize.py`) -- a
deterministic `uuid5` derivation -- as a stopgap so writes did not fail
outright. It works for joins (the same input always derives the same
output), but for `outbound`/`search` events it is lossy: hashing an href
into a UUID destroys the href. Partner click attribution and the `ad_events`
billing ledger (E4) need the actual URL, not a hash of it.

This migration, together with a beacon change (out of this task's ownership
-- see the E0.7 report) and the removal of `stable_uuid`, closes C4:

    column       | before          | after
    -------------|-----------------|----------------------------------
    anon_id      | uuid NOT NULL   | unchanged -- beacon now emits
    session_id   | uuid NOT NULL   | unchanged    crypto.randomUUID(),
                 |                 |              so these are already
                 |                 |              genuine random uuids
    user_id      | uuid NULL       | unchanged -- was already nullable
                 |                 |    in 0001 despite C4's summary
                 |                 |    table implying otherwise; the
                 |                 |    real gap was entity_id and the
                 |                 |    missing target_url column
    entity_id    | uuid NOT NULL   | uuid NULL -- set only for events that
                 |                 |    reference a real article/place/
                 |                 |    event row; NULL for `outbound`
                 |                 |    (see target_url) and `search`
                 |                 |    (see query, added in 0002)
    target_url   | (did not exist) | text NULL -- NEW. The actual outbound
                 |                 |    href for `kind='outbound'` events.

Nothing here changes `anon_id`/`session_id`/`user_id`'s type -- 0001 already
had them right (uuid, NOT NULL for the first two, nullable for the last).
The two real changes are additive/relaxing, not destructive:

  1. `ALTER COLUMN entity_id DROP NOT NULL` -- a constraint relaxation, not
     a type change. No existing value is touched or invalidated; instant,
     metadata-only.
  2. `ADD COLUMN target_url text NULL` -- brand new nullable column, no
     default, no backfill. Instant, metadata-only.

Both are safe to run against a city DB carrying live beacon traffic written
under the *old* contract: every existing row already satisfies `entity_id
NOT NULL` (trivially -- dropping a constraint can't violate it) and gets
`target_url = NULL` for free.

`interactions` is `PARTITION BY RANGE (ts)` (0001). Per Postgres 11+,
`ALTER TABLE ... ALTER COLUMN ... DROP NOT NULL` and `ALTER TABLE ... ADD
COLUMN` on a partitioned parent both recurse to every existing partition
automatically -- no per-partition DDL needed here, matching 0002's ADD
COLUMN precedent for this same table.

Reversibility note (downgrade): `ADD COLUMN target_url` reverses cleanly
(`DROP COLUMN`, unconditionally safe -- data loss is expected and is what
"downgrade" means). Restoring `entity_id`'s `NOT NULL` is only safe if
every row at downgrade time already has a non-NULL `entity_id` -- true
immediately after an upgrade with no new writes, but **not** guaranteed
once the application starts writing NULL `entity_id` for `outbound`/
`search` events under the new contract (which is the entire point of this
migration). `downgrade()` does not attempt to paper over that with a
synthetic backfill value (that would silently reintroduce the very data
loss C4 exists to fix) -- it reissues the constraint as-is and lets
Postgres raise a clear `23502 not_null_violation` if the data no longer
supports it. Downgrading after real `outbound`/`search` traffic has landed
requires a deliberate data decision (drop those rows, or backfill a
placeholder) that this migration will not make silently.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE engine.interactions ALTER COLUMN entity_id DROP NOT NULL")
    op.execute("ALTER TABLE engine.interactions ADD COLUMN target_url text NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE engine.interactions DROP COLUMN target_url")
    # See "Reversibility note" above -- this raises 23502 rather than
    # silently fabricating data if NULL entity_id rows exist.
    op.execute("ALTER TABLE engine.interactions ALTER COLUMN entity_id SET NOT NULL")
