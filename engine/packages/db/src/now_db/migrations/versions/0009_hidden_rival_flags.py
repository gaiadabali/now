r"""engine.hidden_rival_flags -- precomputed hidden-rival signal (Edition 2, WS1 second pass)

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-24

## Why a table, not a live regex join

`now_filters.hidden_rival`'s guard (migration-adjacent to 0008, same ticket)
computed its answer live, per request: for every Read Next/complement
candidate, `NOT EXISTS (... JOIN place_mentions/places ... WHERE name ~*
:pattern)`. `EXPLAIN (ANALYZE, BUFFERS)` against real `now_bali` data (a
`stay` subject, 2,874 eligible candidates) showed this -- and the
surrounding hard-filter predicates -- costing ~40-49ms of a query the
budget allows 150ms total for, across as many as five rail queries on one
page. The corpus is small (4,429 embeddings, ~6,000 places) -- the cost is
not data volume, it is doing the SAME regex scan over `places`/`articles`
freshly on every request for a signal that only changes when an article is
edited or a place is renamed.

**ARCHITECTURE.md principle 2**: "Humans write `public`, machines write
`engine`. The `engine` schema can be dropped and rebuilt from `public` at
any time." A hidden-rival flag is exactly this kind of derived fact --
computed FROM `public.articles`/`public.place_mentions`/`public.places`,
never authored directly. This table is the derived, precomputed home for
it, refreshed by `now_filters.hidden_rival_recompute` (offline, a full
recompute -- this table is small enough, low hundreds of rows per city,
that a full TRUNCATE + re-INSERT per run is simpler and no slower in
practice than an incremental diff, and it can never drift into a stale
partial state between runs).

## Shape

    article_id   text     -- entity_id convention (migration 0005's widening
                            precedent: Payload's integer PK, stored as its
                            canonical text form, never a derived hash)
    matched_type text     -- the L1 `type` this article's featured mention
                            or own title reads as (e.g. 'stay') -- what the
                            article being recommended is REALLY about,
                            independent of its own declared `primary_type`
    signal       text     -- 'featured_mention' | 'title' -- which of the
                            two detectors found it (see
                            `now_filters.hidden_rival` module docstring for
                            both; 'title' is scoped to `stay` only today,
                            per that module's measured precision)
    computed_at  timestamptz

Primary key is the full row `(article_id, matched_type, signal)`: the same
article can carry more than one matched_type (e.g. a hotel's restaurant
write-up could plausibly read as both `stay` and `eat`), and the two
signals are independent detectors whose provenance is worth keeping
separate rather than collapsed into one row.

Query shape this replaces (`now_filters.hard`'s hidden-rival predicate):
was a per-candidate `NOT EXISTS` regex join; becomes
`article_id NOT IN (SELECT article_id FROM engine.hidden_rival_flags
WHERE matched_type = ANY(:excluded_types))` -- an index-backed lookup
against a table sized in the hundreds of rows, not a live scan of
`places`/`articles`.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE engine.hidden_rival_flags (
            article_id   text NOT NULL,
            matched_type text NOT NULL,
            signal       text NOT NULL CHECK (signal IN ('featured_mention', 'title')),
            computed_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (article_id, matched_type, signal)
        )
        """
    )
    # The hot-path lookup is "which matched_types does THIS article carry"
    # (`article_id NOT IN (SELECT article_id FROM ... WHERE matched_type =
    # ANY(...))`) -- the primary key already leads with `article_id`, so a
    # second index on it would be redundant. No index on `matched_type`
    # alone: the whole table is a few hundred rows, and every real query
    # filters by `article_id` first regardless.


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS engine.hidden_rival_flags")
