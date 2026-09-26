"""reading progress — Continue reading / Recently read

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-26

Phase 0 (P0.1), ITINERARY-AND-READER-PRODUCTS-PLAN.md §4.3. First migration
of the Phase 0 foundations set (0010-0017): destinations/itineraries/print/
offers/partner-identities/role-split/RLS follow in that order, chosen so
every FK this set adds resolves to a table that already exists by the time
it is created (offers before the itinerary reshape that references
`offer_id`, print/offers before the grants migration that revokes DELETE
on them, etc).

`reading_progress` has no dependency on anything added later in this set —
it only references `engine.identities` and `engine.sites`, both already
live — so it is safe to land first and independently.

## Why this is not derived from the beacon

§4.1 of the plan: the beacon measures the whole page, is consent/DNT-gated,
and its contract (ARCHITECTURE.md §7) is frozen. *Continue reading* has to
work for a reader who declined analytics consent (it is a product feature,
not measurement) and has to measure the article **body**, not the page. So
this is a first-party write from the article page itself, not a beacon
derivative — same relationship `saved_items` (0007) has to the beacon.

## Design choices worth stating

- **Composite primary key `(identity_id, site_id, article_id)`**, not a
  surrogate `id`. There is exactly one progress row per reader per article
  per masthead by definition (§4.2 "Order: most recently read first" reads
  one row per story) and the write path is `INSERT ... ON CONFLICT (identity_id,
  site_id, article_id) DO UPDATE` — a natural key is what makes that upsert
  possible without a round-trip to find an existing row first.
- **`article_id text`, no FK.** Same cross-database rule as `saved_items.entity_id`
  (0007) and every other pointer into a city DB: the article lives in
  `now_{city}.public.articles`, a different database, and Postgres cannot
  constrain across databases. `text`, not `uuid` — Payload's real primary
  keys are plain `serial` integers (see `scripts/check_no_payload_uuid_refs.py`
  and F69) — so this column deliberately does not trip that gate.
- **`dwell_ms` is cumulative**, matching the throttled-write design in
  §4.3: the client posts at body milestones (5/25/50/75/90/100%) plus on
  `pagehide`, and the handler upserts with `GREATEST(progress)` — that
  GREATEST is an application-level UPDATE clause, not a constraint, because
  a reader can legitimately re-open a finished article and its progress
  should not regress even though a fresh read starts the IntersectionObserver
  from block 0 again.
- **The partial index is the whole feature.** `ix_reading_progress_continue`
  serves exactly the dashboard's *Continue reading* query — unfinished,
  not dismissed, most-recent-first — and nothing else touches this table
  in a way that needs a second index yet. Kept partial (`WHERE finished_at
  IS NULL AND dismissed_at IS NULL`) rather than a plain composite index so
  it stays small as *Recently read* rows (finished, kept for 180 days per
  §4.2) accumulate outside it.
- **No FK-driven expiry.** §4.2's 60-day/180-day retention and the
  50-row-per-reader cap are described in the plan as "the oldest is
  evicted" / "deleted by a nightly job" — behaviour that depends on wall-clock
  time and eviction ordering, not a property the schema can express as a
  constraint. That job is P2.6's job, not this migration's.
- **`ON DELETE CASCADE` from `identities`**, matching 0008's reasoning for
  `user_profiles`: reading progress is derived from one person's behaviour
  on one masthead's content and has no meaning, and no export/delete
  obligation, once that person's account is gone. Unlike 0008's
  `itineraries` case, there is no shared-artifact reason to keep an orphaned
  row here — nobody else can see another reader's reading progress.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE engine.reading_progress (
            identity_id   uuid        NOT NULL
                          REFERENCES engine.identities(id) ON DELETE CASCADE,
            site_id       uuid        NOT NULL REFERENCES engine.sites(id),
            article_id    text        NOT NULL,
            progress_pct  smallint    NOT NULL CHECK (progress_pct BETWEEN 0 AND 100),
            block_index   integer,
            dwell_ms      integer     NOT NULL DEFAULT 0,
            started_at    timestamptz NOT NULL DEFAULT now(),
            last_read_at  timestamptz NOT NULL DEFAULT now(),
            finished_at   timestamptz,
            dismissed_at  timestamptz,
            seeded        boolean     NOT NULL DEFAULT false,
            PRIMARY KEY (identity_id, site_id, article_id)
        )
        """
    )
    # The *Continue reading* read, exactly: this reader, not finished, not
    # dismissed, most recent first. Partial so it stays small as finished
    # rows (kept for *Recently read* per §4.2) pile up outside it.
    op.execute(
        """
        CREATE INDEX ix_reading_progress_continue
            ON engine.reading_progress (identity_id, last_read_at DESC)
            WHERE finished_at IS NULL AND dismissed_at IS NULL
        """
    )
    # *Recently read* — finished stories, most recent first; same reader,
    # same site. Not partial: every finished row is read by this query.
    op.execute(
        """
        CREATE INDEX ix_reading_progress_recently_read
            ON engine.reading_progress (identity_id, site_id, last_read_at DESC)
            WHERE finished_at IS NOT NULL
        """
    )
    # The 60-day/180-day retention jobs (P2.6) scan by staleness across all
    # readers, not per-reader.
    op.execute(
        """
        CREATE INDEX ix_reading_progress_last_read_at
            ON engine.reading_progress (last_read_at)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS engine.reading_progress")
