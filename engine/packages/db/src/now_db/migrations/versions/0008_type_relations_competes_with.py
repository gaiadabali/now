r"""engine.type_relations: F&B as one competitive class (`competes_with`)

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-24

## The owner's rule, stated twice, narrower than the data it landed on

2026-09-11 and again 2026-09-24 (docs/EDITION-2-PLAN.md Sec.1): "On a hotel
story, never suggest a hotel -- suggest restaurants and other things. On a
restaurant story, suggest hotels and other things, never a restaurant, cafe
or F&B." The owner's words treat "restaurant/cafe/F&B" as ONE thing a diner
has already chosen. `engine.type_relations` (Sec.4's matrix) instead carries
`eat` and `drink` as two separate L1 types that list each other as
`complements` -- a co-recommendation whitelist. So a restaurant story could
recommend a bar and a bar story could recommend a restaurant, which is
exactly the "F&B" pairing the owner named as the one that must never happen.

`exclude_same` cannot express this: it is a single boolean per type ("does
this type exclude its own kind"), and eat/drink are not "their own kind" of
each other -- they are two rows that happen to compete. That needs a second,
explicit relation, not a repurposing of the first.

## `competes_with` -- a second, narrower exclusion axis

`complements` says "may co-recommend"; `competes_with` says "must not
co-recommend, even though it is a different L1 type". Both are per-row
text[] columns on the same table, so the policy stays entirely data (§4/
§8.A's own requirement -- "commercial policy, not a ranking preference") and
`now_filters.type_relations.excluded_types_for` gains exactly one union, not
a second code path (see that module, same ticket).

Only `eat`/`drink` get a non-empty `competes_with` today. Every other type
defaults to `'{}'::text[]` -- unaffected. This is additive and narrower than
the existing `exclude_same` axis: nothing that was excluded before stops
being excluded, and nothing outside eat/drink starts being excluded.

## Why a live-data UPDATE, not just the column

`engine.type_relations` is exactly the kind of table `seed_city()`
(`now_db.provisioning`) only ever back-fills (`ON CONFLICT (type) DO
NOTHING`) -- editable in place, per site, and the seed must never clobber an
existing row (see that function's own docstring). That is correct for a
brand-new type appearing after this ships, but it means the seed alone will
NOT fix the three real rows this migration cares about: `now_jakarta`,
`now_bali` and `now_test` all already carry `eat`/`drink` rows seeded before
this ticket, each still listing the other in `complements`. A schema-only
migration would add a column full of empty arrays and leave the live
competitor list wrong on every registered site until someone thought to
re-seed by hand.

So this migration does both, in the one place that runs against every
registered city by construction (`site:migrate --all` -- ARCHITECTURE.md
§2's migration discipline: "Zero manual DDL on a city database, ever," and
this is DML, not DDL, but the same "every city, no manual step" reasoning
applies): add the column, then an idempotent data step that
    - removes `drink` from `eat`'s `complements` and vice versa (the
      asymmetry-closing 2026-09-11 fix added this pairing; this ticket
      un-does exactly that one pairing, nothing else in either array), and
    - sets `competes_with = ARRAY['drink']` for `eat` and `ARRAY['eat']` for
      `drink`.
Re-running this migration (or a future `site:migrate --all` against an
already-migrated city) is a no-op: `array_remove` on an array that no longer
contains the target element returns the array unchanged, and setting
`competes_with` to the same literal array twice writes the same value.

Every other type's `complements`/`competes_with` is untouched -- this
migration touches exactly the two rows named above, by primary key, not a
blanket rewrite of the table.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE engine.type_relations "
        "ADD COLUMN IF NOT EXISTS competes_with text[] NOT NULL DEFAULT '{}'::text[]"
    )

    # Un-pair eat/drink from each other's co-recommendation whitelist --
    # idempotent: array_remove() on an element already absent is a no-op.
    op.execute("UPDATE engine.type_relations SET complements = array_remove(complements, 'drink') WHERE type = 'eat'")
    op.execute("UPDATE engine.type_relations SET complements = array_remove(complements, 'eat') WHERE type = 'drink'")

    # Record them as the one competitive class the owner actually asked for.
    # Plain assignment, not append-if-missing: the target value is a fixed
    # literal, so setting it twice converges rather than accumulating.
    op.execute("UPDATE engine.type_relations SET competes_with = ARRAY['drink']::text[] WHERE type = 'eat'")
    op.execute("UPDATE engine.type_relations SET competes_with = ARRAY['eat']::text[] WHERE type = 'drink'")


def downgrade() -> None:
    # Restores the migration-0001 baseline pairing this ticket removed
    # (eat <-> drink back in each other's `complements`) and empties
    # `competes_with` back to every row's schema default. Any OTHER
    # per-site edit made to these arrays after this migration ran is not
    # reconstructable from here -- same limitation 0001's own downgrade
    # documents for a dropped table, applied to a narrower, in-place edit.
    op.execute(
        "UPDATE engine.type_relations SET complements = array_append(complements, 'drink') "
        "WHERE type = 'eat' AND NOT ('drink' = ANY(complements))"
    )
    op.execute(
        "UPDATE engine.type_relations SET complements = array_append(complements, 'eat') "
        "WHERE type = 'drink' AND NOT ('eat' = ANY(complements))"
    )
    op.execute("ALTER TABLE engine.type_relations DROP COLUMN IF EXISTS competes_with")
