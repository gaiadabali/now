"""destinations, and the itinerary reshape for loose/planned mode

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-26

Phase 0 (P0.1), plan §3.1-§3.2. Lands after 0012 (offers) because
`destinations.offer_id` and `itinerary_stops.offer_id` both reference
`engine.offers(id)`.

## D1/D2/D3 in one sentence each (§3.1 has the full argument)

- **D1**: an itinerary can hold a Bali day and a Jakarta day, so no stop or
  destination can be a same-database foreign key to a city row — every
  reference here is the pair `(site_id, place_id)`, `place_id` typed `text`
  (never `uuid` — F69/`check_no_payload_uuid_refs.py`; Payload's real
  primary keys are plain `serial` integers).
- **D2**: `mode` (`loose`/`planned`) is a column, not a second collection —
  the unscheduled bucket of a planned trip and a reader's loose list are the
  same object at different points in its life.
- **D3**: `destinations` is its own table, many-to-many with itineraries via
  `itinerary_items` — a destination can sit in several itineraries, and
  `saved_items` (read-later) stays completely untouched by this migration.

## `itineraries.site_id` becomes nullable — the one relaxation, not a widening

Per §3.2's own framing: "the itinerary reshape is additive plus one
relaxation." `site_id` was `NOT NULL` because every itinerary used to
belong to exactly one site. A cross-city trip has no single home site until
the reader's days say otherwise, so this column becomes the *display* home
site (whichever the UI wants to default to, or NULL for "mixed") rather
than a hard ownership fact. This is a genuine narrowing of what the column
means, not a security relaxation — nothing that read `itineraries.site_id`
before this migration was relying on it for access control (P0.4's RLS
migration does not touch `itineraries` — see that migration's docstring for
which tables are in scope), so there is no policy to loosen here.

## `itinerary_items` — the loose list / unscheduled bucket

One row per `(itinerary, destination)`. `pinned` defaults `true`: a
destination added to an itinerary is assumed to be something the reader
wants placed when planning starts (§3.4 CANDIDATES/SOLVE — pinned
destinations are placed exactly once), and turning that off is a deliberate
"suggest me something, don't force this one" choice the UI exposes, not the
default.

## `itinerary_days`/`itinerary_stops` — the per-site segmentation §3.4 needs

The solver runs "one solve per site" (§3.4 SEGMENT) once an itinerary spans
cities, so a day and its stops need to know which site they belong to even
though the itinerary as a whole may not. `stay_site_id`/`stay_place_id` on
`itinerary_days` are the day's anchor hotel (§3.4 ANCHOR) — first/last-leg
travel origin, never a stop itself, which is why they are a bare pair
rather than a `destination_id` FK: an anchor is not necessarily something
the reader saved as a destination.

`itinerary_stops.destination_id` is nullable and `ON DELETE SET NULL`: a
stop the solver placed from the open catalogue (`source = 'solver'`, per
§3.2's note that `source` gains that vocabulary) was never a saved
destination, and a reader removing a destination from their account should
un-attribute a past plan's stop rather than delete history of where they
went — same reasoning 0008 gave for `itineraries.user_id` not cascading.

## Two limits are application checks, not database constraints

§3.2: 500 items per itinerary, 4,000-character notes. Deliberately not a
`CHECK` here — "a sentence, not a database error" is an explicit product
decision (the reader is told why they're capped, not shown a constraint
violation), and both numbers are things the product will tune. `note`
therefore stays plain `text` with no length constraint at the schema layer.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE engine.destinations (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            identity_id  uuid NOT NULL REFERENCES engine.identities(id) ON DELETE CASCADE,
            site_id      uuid NOT NULL REFERENCES engine.sites(id),
            kind         text NOT NULL CHECK (kind IN ('place', 'article', 'event', 'offer')),
            entity_id    text NOT NULL,
            place_id     text,
            offer_id     uuid REFERENCES engine.offers(id) ON DELETE SET NULL,
            area_term    text,
            note         text,
            created_at   timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_destinations_identity_entity UNIQUE (identity_id, site_id, kind, entity_id)
        )
        """
    )
    # The dashboard's *Destinations* panel: this reader's saves, grouped by
    # area (§3.3), newest first within a group.
    op.execute(
        """
        CREATE INDEX ix_destinations_identity_site
            ON engine.destinations (identity_id, site_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_destinations_place
            ON engine.destinations (site_id, place_id)
            WHERE place_id IS NOT NULL
        """
    )

    op.execute(
        """
        ALTER TABLE engine.itineraries
            ALTER COLUMN site_id DROP NOT NULL,
            ADD COLUMN mode           text NOT NULL DEFAULT 'loose'
                       CHECK (mode IN ('loose', 'planned')),
            ADD COLUMN kind           text NOT NULL DEFAULT 'reader'
                       CHECK (kind IN ('reader', 'curated')),
            ADD COLUMN labels         text[] NOT NULL DEFAULT '{}',
            ADD COLUMN visibility     text NOT NULL DEFAULT 'private'
                       CHECK (visibility IN ('private', 'link', 'public')),
            ADD COLUMN slug           text,
            ADD COLUMN end_date       date,
            ADD COLUMN forked_from_id uuid REFERENCES engine.itineraries(id) ON DELETE SET NULL,
            ADD COLUMN published_at   timestamptz,
            ADD COLUMN plan_status    text
                       CHECK (plan_status IS NULL OR plan_status IN ('solved', 'edited', 'stale', 'infeasible')),
            ADD COLUMN plan_report    jsonb
        """
    )
    # Curated itineraries (E5.6/E5.7, §11a.8) are indexable at `/itineraries/[slug]`
    # and slugs are only meaningful — and only need to be unique — within
    # `kind = 'curated'`; every reader itinerary leaves `slug` NULL.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_itineraries_curated_slug
            ON engine.itineraries (site_id, slug)
            WHERE kind = 'curated' AND slug IS NOT NULL
        """
    )
    # "Copy to my itineraries" / provenance display: which itineraries were
    # forked from a given original.
    op.execute(
        """
        CREATE INDEX ix_itineraries_forked_from
            ON engine.itineraries (forked_from_id)
            WHERE forked_from_id IS NOT NULL
        """
    )

    op.execute(
        """
        CREATE TABLE engine.itinerary_items (
            itinerary_id   uuid NOT NULL REFERENCES engine.itineraries(id) ON DELETE CASCADE,
            destination_id uuid NOT NULL REFERENCES engine.destinations(id) ON DELETE CASCADE,
            position       integer NOT NULL,
            pinned         boolean NOT NULL DEFAULT true,
            note           text,
            added_at       timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (itinerary_id, destination_id)
        )
        """
    )
    # The builder's ordered read: this itinerary's bucket, in position order.
    op.execute(
        """
        CREATE INDEX ix_itinerary_items_itinerary_position
            ON engine.itinerary_items (itinerary_id, position)
        """
    )
    # "Deleting a destination removes it from every itinerary" (P2.3's own
    # acceptance line) — the reverse-lookup the deletion path needs.
    op.execute("CREATE INDEX ix_itinerary_items_destination ON engine.itinerary_items (destination_id)")

    op.execute(
        """
        ALTER TABLE engine.itinerary_days
            ADD COLUMN site_id      uuid REFERENCES engine.sites(id),
            ADD COLUMN date         date,
            ADD COLUMN stay_site_id uuid REFERENCES engine.sites(id),
            ADD COLUMN stay_place_id text
        """
    )

    op.execute(
        """
        ALTER TABLE engine.itinerary_stops
            ADD COLUMN site_id                  uuid REFERENCES engine.sites(id),
            ADD COLUMN destination_id            uuid REFERENCES engine.destinations(id) ON DELETE SET NULL,
            ADD COLUMN offer_id                  uuid REFERENCES engine.offers(id) ON DELETE SET NULL,
            ADD COLUMN end_time                  time,
            ADD COLUMN travel_min_from_previous   integer
        """
    )
    op.execute(
        """
        CREATE INDEX ix_itinerary_stops_destination
            ON engine.itinerary_stops (destination_id)
            WHERE destination_id IS NOT NULL
        """
    )
    # `itinerary_stops.campaign_id` (0001) is left exactly as-is — §3.2's own
    # note: "a partner-placed stop still bills against a campaign when one
    # exists". Nothing in this migration touches that column.


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE engine.itinerary_stops
            DROP COLUMN IF EXISTS site_id,
            DROP COLUMN IF EXISTS destination_id,
            DROP COLUMN IF EXISTS offer_id,
            DROP COLUMN IF EXISTS end_time,
            DROP COLUMN IF EXISTS travel_min_from_previous
        """
    )
    op.execute(
        """
        ALTER TABLE engine.itinerary_days
            DROP COLUMN IF EXISTS site_id,
            DROP COLUMN IF EXISTS date,
            DROP COLUMN IF EXISTS stay_site_id,
            DROP COLUMN IF EXISTS stay_place_id
        """
    )
    op.execute("DROP TABLE IF EXISTS engine.itinerary_items")
    op.execute(
        """
        ALTER TABLE engine.itineraries
            DROP COLUMN IF EXISTS mode,
            DROP COLUMN IF EXISTS kind,
            DROP COLUMN IF EXISTS labels,
            DROP COLUMN IF EXISTS visibility,
            DROP COLUMN IF EXISTS slug,
            DROP COLUMN IF EXISTS end_date,
            DROP COLUMN IF EXISTS forked_from_id,
            DROP COLUMN IF EXISTS published_at,
            DROP COLUMN IF EXISTS plan_status,
            DROP COLUMN IF EXISTS plan_report
        """
    )
    # NOT reversed: `site_id` cannot be restored to NOT NULL blindly if any
    # mixed (`site_id IS NULL`) itinerary was created while this migration
    # was applied — that data loss decision belongs to whoever runs the
    # downgrade with real rows in front of them, not to this script.
    op.execute("DROP TABLE IF EXISTS engine.destinations")
