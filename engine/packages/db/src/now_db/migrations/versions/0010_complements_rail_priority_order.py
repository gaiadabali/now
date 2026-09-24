r"""Reorder engine.type_relations.complements to double as rail priority (Edition 2, WS1 second pass)

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-24

## What changed, and what didn't

Pure DATA, same membership as migration 0001/0008 left it -- no type gains
or loses a complement here. Only the ARRAY ORDER changes, for exactly the
5 venue types (`stay`/`eat`/`drink`/`wellness`/`shop`). `complements` has
had one job since §4: `now_rails.row1_complementary`'s `type = ANY
(complements)` whitelist, which is order-independent (`ANY` over an array
doesn't care about position). This migration gives the array a SECOND job
-- `apps/web/src/lib/recommendSql.ts`'s "plan around it" rail now reads
first-occurrence-by-SECTION order as ITS display priority (coordinator's
review: "put that priority order in data ... the complements order itself,
your call, documented") -- so the one existing array is reused rather
than a parallel ordering table being invented for a second axis of the
identical relationship.

## The priority each type's new order encodes

Sections come from `lib/payload.ts#TYPE_TO_SECTION`: eat/drink -> dining,
do/shop -> things-to-do, stay -> stay, wellness -> wellness, event ->
events. "Plan around it" takes the first 3 DISTINCT sections found by
walking `complements` in order, so what matters below is section order,
not exact type order within a section:

    stay      eat, drink, do, shop, wellness
              -> dining, things-to-do, wellness
              (coordinator's own example: "Hotel: eat & drink, things to
              do, unwind")
    eat       stay, do, shop, event, wellness
              -> stay, things-to-do, events
              (coordinator's own example: "Restaurant: stay, things to
              do, what's on" -- `wellness` drops out of the top 3, same
              as the example)
    drink     stay, do, shop, wellness
              -> stay, things-to-do, wellness
    wellness  eat, drink, stay, do, shop
              -> dining, stay, things-to-do
    shop      eat, drink, stay, do, wellness
              -> dining, stay, things-to-do

`do`/`event`/`editorial` are untouched: none of them build a "plan around
it" rail (that feature is scoped to venue-shaped, `exclude_same=true`
subjects -- `now_filters`'s own docs), so their `complements` order has no
second reader to serve.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None

# type -> new complements order (same SET as before this migration; only
# array position changes). Written as plain UPDATEs keyed by `type` (the
# primary key), each idempotent -- re-running this migration a second time
# sets the same array again, a no-op.
_NEW_ORDER: dict[str, list[str]] = {
    "stay": ["eat", "drink", "do", "shop", "wellness"],
    "eat": ["stay", "do", "shop", "event", "wellness"],
    "drink": ["stay", "do", "shop", "wellness"],
    "wellness": ["eat", "drink", "stay", "do", "shop"],
    "shop": ["eat", "drink", "stay", "do", "wellness"],
}


def upgrade() -> None:
    for type_slug, order in _NEW_ORDER.items():
        op.execute(
            "UPDATE engine.type_relations SET complements = ARRAY[" +
            ",".join(f"'{t}'" for t in order) +
            "]::text[] WHERE type = '" + type_slug + "'"
        )


def downgrade() -> None:
    # Restores the ARCHITECTURE.md §4 / migration-0008 order (same
    # membership, the order this migration found live). Any site-specific
    # reorder made after this migration ran is not reconstructable from
    # here -- same limitation every prior migration's downgrade in this
    # package documents for an in-place data edit.
    _PRE_MIGRATION_ORDER: dict[str, list[str]] = {
        "stay": ["eat", "drink", "wellness", "do", "shop"],
        "eat": ["stay", "wellness", "do", "shop", "event"],
        "drink": ["stay", "wellness", "do", "shop"],
        "wellness": ["eat", "stay", "drink", "do", "shop"],
        "shop": ["eat", "stay", "drink", "wellness", "do"],
    }
    for type_slug, order in _PRE_MIGRATION_ORDER.items():
        op.execute(
            "UPDATE engine.type_relations SET complements = ARRAY[" +
            ",".join(f"'{t}'" for t in order) +
            "]::text[] WHERE type = '" + type_slug + "'"
        )
